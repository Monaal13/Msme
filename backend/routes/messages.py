from datetime import datetime
from flask import Blueprint, jsonify, request
from services.db import execute, fetch_all, fetch_one, db_cursor, normalize_query
from services.notifications import (
    get_or_create_settings,
    get_or_create_templates,
    NotificationService,
    process_due_scheduled_messages
)
from .common import DatabaseError, current_business_id, handle_db_error, login_required

messages_bp = Blueprint("messages", __name__)

@messages_bp.get("")
@login_required
def list_messages():
    biz_id = current_business_id()
    status_filter = request.args.get("status", "all").strip().lower()
    search = f"%{request.args.get('search', '').strip()}%"
    
    try:
        query = """
            SELECT m.*, c.name AS customer_name, c.phone AS customer_phone, s.invoice_number
            FROM messages m
            JOIN customers c ON c.id = m.customer_id
            LEFT JOIN sales s ON s.id = m.sale_id
            WHERE m.business_id = %s
              AND (c.name LIKE %s OR c.phone LIKE %s OR m.message_text LIKE %s)
        """
        params = [biz_id, search, search, search]
        
        if status_filter in ("sent", "scheduled", "failed", "pending", "cancelled"):
            query += " AND m.status = %s"
            params.append(status_filter)
            
        query += " ORDER BY m.created_at DESC, m.id DESC"
        
        messages = fetch_all(query, tuple(params))
        
        # Calculate summary metrics for the business
        summary = {
            "total": fetch_one("SELECT COUNT(*) AS value FROM messages WHERE business_id = %s", (biz_id,))["value"],
            "sent": fetch_one("SELECT COUNT(*) AS value FROM messages WHERE business_id = %s AND status = 'sent'", (biz_id,))["value"],
            "scheduled": fetch_one("SELECT COUNT(*) AS value FROM messages WHERE business_id = %s AND status = 'scheduled'", (biz_id,))["value"],
            "failed": fetch_one("SELECT COUNT(*) AS value FROM messages WHERE business_id = %s AND status = 'failed'", (biz_id,))["value"]
        }
        
        return jsonify({
            "messages": messages,
            "summary": summary
        })
    except DatabaseError as exc:
        return handle_db_error(exc)

@messages_bp.get("/settings")
@login_required
def get_settings():
    biz_id = current_business_id()
    try:
        settings = get_or_create_settings(biz_id)
        return jsonify(settings)
    except DatabaseError as exc:
        return handle_db_error(exc)

@messages_bp.put("/settings")
@login_required
def update_settings():
    biz_id = current_business_id()
    data = request.get_json() or {}
    
    purchase_conf = 1 if data.get("purchase_confirmation") in (True, 1, '1') else 0
    followup = 1 if data.get("post_purchase_followup") in (True, 1, '1') else 0
    
    try:
        days = int(data.get("followup_days", 3))
        if days < 0:
            return jsonify({"error": "Follow-up days cannot be negative"}), 400
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid follow-up days"}), 400
        
    channel = data.get("preferred_channel", "WhatsApp").strip()
    if channel not in ("WhatsApp", "SMS", "Email"):
        channel = "WhatsApp"
        
    try:
        execute(
            """
            UPDATE notification_settings
            SET purchase_confirmation = %s, post_purchase_followup = %s, followup_days = %s, preferred_channel = %s
            WHERE business_id = %s
            """,
            (purchase_conf, followup, days, channel, biz_id)
        )
        return jsonify({
            "message": "Notification settings updated successfully",
            "settings": {
                "business_id": biz_id,
                "purchase_confirmation": purchase_conf,
                "post_purchase_followup": followup,
                "followup_days": days,
                "preferred_channel": channel
            }
        })
    except DatabaseError as exc:
        return handle_db_error(exc)

@messages_bp.get("/templates")
@login_required
def get_templates():
    biz_id = current_business_id()
    try:
        templates = get_or_create_templates(biz_id)
        return jsonify(templates)
    except DatabaseError as exc:
        return handle_db_error(exc)

@messages_bp.put("/templates")
@login_required
def update_templates():
    biz_id = current_business_id()
    data = request.get_json() or {}
    
    try:
        with db_cursor(commit=True) as cursor:
            for t_type, t_text in data.items():
                if t_type not in ("purchase", "follow_up", "payment_reminder"):
                    continue
                cursor.execute(
                    normalize_query("""
                    INSERT INTO message_templates (business_id, type, template_text)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(business_id, type) DO UPDATE SET template_text = excluded.template_text
                    """),
                    (biz_id, t_type, t_text.strip())
                )
        return jsonify({"message": "Templates updated successfully"})
    except DatabaseError as exc:
        return handle_db_error(exc)

@messages_bp.post("/<int:msg_id>/retry")
@login_required
def retry_message(msg_id):
    biz_id = current_business_id()
    try:
        msg = fetch_one("SELECT * FROM messages WHERE id = %s AND business_id = %s", (msg_id, biz_id))
        if not msg:
            return jsonify({"error": "Message not found or does not belong to your business"}), 404
            
        if msg["status"] not in ("failed", "pending"):
            return jsonify({"error": f"Cannot retry a message with status '{msg['status']}'"}), 400
            
        success = NotificationService().send_message(msg_id)
        updated = fetch_one("SELECT * FROM messages WHERE id = %s", (msg_id,))
        
        return jsonify({
            "success": success,
            "message": "Message resent successfully" if success else "Failed to send message (Simulated)",
            "status": updated["status"],
            "error_message": updated["error_message"]
        })
    except DatabaseError as exc:
        return handle_db_error(exc)

@messages_bp.post("/send-custom")
@login_required
def send_custom_message():
    biz_id = current_business_id()
    data = request.get_json() or {}
    
    cust_id = data.get("customer_id")
    msg_text = (data.get("message_text") or "").strip()
    
    if not cust_id:
        return jsonify({"error": "Customer ID is required"}), 400
    if not msg_text:
        return jsonify({"error": "Message text cannot be empty"}), 400
        
    try:
        customer = fetch_one("SELECT id, phone FROM customers WHERE id = %s AND business_id = %s", (cust_id, biz_id))
        if not customer:
            return jsonify({"error": "Customer not found"}), 404
            
        settings = get_or_create_settings(biz_id)
        channel = settings.get("preferred_channel", "WhatsApp")
        
        msg_id = execute(
            """
            INSERT INTO messages (business_id, customer_id, type, message_text, channel, status, scheduled_at)
            VALUES (%s, %s, 'custom', %s, %s, 'pending', %s)
            """,
            (biz_id, cust_id, msg_text, channel, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        
        success = NotificationService().send_message(msg_id)
        updated = fetch_one("SELECT * FROM messages WHERE id = %s", (msg_id,))
        
        return jsonify({
            "id": msg_id,
            "success": success,
            "status": updated["status"],
            "error_message": updated["error_message"],
            "message": "Custom message sent successfully" if success else "Custom message failed to send (Simulated)"
        }), 201
    except DatabaseError as exc:
        return handle_db_error(exc)

@messages_bp.post("/process-scheduled")
@login_required
def trigger_process_scheduled():
    try:
        count = process_due_scheduled_messages()
        return jsonify({"message": f"Processed {count} due scheduled messages.", "count": count})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@messages_bp.post("/send-campaign")
@login_required
def send_campaign():
    biz_id = current_business_id()
    data = request.get_json() or {}
    msg_text = (data.get("message_text") or "").strip()
    
    if not msg_text:
        return jsonify({"error": "Message text cannot be empty"}), 400
        
    try:
        # Fetch inactive customers (max sale_date < 30 days ago or never purchased and created < 30 days ago)
        inactive_customers = fetch_all(
            """
            SELECT c.id, c.name, c.phone
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id AND s.business_id = c.business_id
            WHERE c.business_id = %s
            GROUP BY c.id
            HAVING COALESCE(MAX(s.sale_date), c.created_at) < DATE('now', '-30 days')
            """,
            (biz_id,),
        )
        
        if not inactive_customers:
            return jsonify({"message": "No inactive customers found to target.", "sent_count": 0})
            
        settings = get_or_create_settings(biz_id)
        channel = settings.get("preferred_channel", "WhatsApp")
        
        sent_count = 0
        service = NotificationService()
        
        for cust in inactive_customers:
            custom_msg = msg_text.replace("{{customer_name}}", cust["name"])
            
            msg_id = execute(
                """
                INSERT INTO messages (business_id, customer_id, type, message_text, channel, status, scheduled_at)
                VALUES (%s, %s, 'campaign', %s, %s, 'pending', %s)
                """,
                (biz_id, cust["id"], custom_msg, channel, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            )
            service.send_message(msg_id)
            sent_count += 1
            
        return jsonify({"message": f"Successfully sent offer messages to {sent_count} inactive customers.", "sent_count": sent_count})
    except DatabaseError as exc:
        return handle_db_error(exc)
