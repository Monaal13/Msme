from datetime import datetime, timedelta
import logging
from services.db import execute, fetch_all, fetch_one, db_cursor, normalize_query

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES = {
    "purchase": "Hi {{customer_name}} 👋\n\nThank you for shopping with {{shop_name}}!\n\nYour purchase of {{amount}} has been successfully completed.\n\nInvoice: {{invoice_number}}\n\nThank you for choosing us! ❤️",
    "follow_up": "Hi {{customer_name}} 👋\n\nWe hope you liked your recent purchase from {{shop_name}}.\n\nWe would love to know about your experience.\n\nPlease share your feedback with us. ⭐\n\nThank you for shopping with us!",
    "payment_reminder": "Hi {{customer_name}},\n\nThis is a friendly reminder regarding your pending payment of {{amount}}.\n\nPlease contact {{shop_name}} if you need any assistance."
}

def get_or_create_settings(business_id):
    """Fetch settings, seeding defaults if missing."""
    settings = fetch_one("SELECT * FROM notification_settings WHERE business_id = %s", (business_id,))
    if not settings:
        try:
            execute(
                """
                INSERT INTO notification_settings (business_id, purchase_confirmation, post_purchase_followup, followup_days, preferred_channel)
                VALUES (%s, 1, 1, 3, 'WhatsApp')
                """,
                (business_id,)
            )
            settings = fetch_one("SELECT * FROM notification_settings WHERE business_id = %s", (business_id,))
        except Exception as e:
            logger.error(f"Error seeding notification settings: {e}")
            return {
                "business_id": business_id,
                "purchase_confirmation": 1,
                "post_purchase_followup": 1,
                "followup_days": 3,
                "preferred_channel": "WhatsApp"
            }
    return dict(settings)

def get_or_create_templates(business_id):
    """Fetch message templates, seeding defaults if missing."""
    rows = fetch_all("SELECT * FROM message_templates WHERE business_id = %s", (business_id,))
    templates = {row["type"]: row["template_text"] for row in rows}
    
    missing = [t_type for t_type in DEFAULT_TEMPLATES if t_type not in templates]
    if missing:
        for t_type in missing:
            try:
                execute(
                    """
                    INSERT INTO message_templates (business_id, type, template_text)
                    VALUES (%s, %s, %s)
                    """,
                    (business_id, t_type, DEFAULT_TEMPLATES[t_type])
                )
                templates[t_type] = DEFAULT_TEMPLATES[t_type]
            except Exception as e:
                logger.error(f"Error seeding default template {t_type}: {e}")
                templates[t_type] = DEFAULT_TEMPLATES[t_type]
    return templates

def render_template(template_text, variables):
    """Replace {{variable_name}} with actual values."""
    rendered = template_text
    for key, val in variables.items():
        placeholder = f"{{{{{key}}}}}"
        rendered = rendered.replace(placeholder, str(val if val is not None else ""))
    return rendered

class NotificationService:
    def send_message(self, message_id):
        """Simulates sending a message using the Mock Provider logic."""
        message = fetch_one(
            """
            SELECT m.*, c.phone, c.name AS customer_name
            FROM messages m
            JOIN customers c ON c.id = m.customer_id
            WHERE m.id = %s
            """,
            (message_id,)
        )
        if not message:
            logger.error(f"Message ID {message_id} not found for sending.")
            return False

        phone = (message["phone"] or "").strip()
        
        # Test failure condition: phone starts with 999 or starts with +91 999
        is_failure_test = (
            phone.startswith("999") or 
            phone.startswith("+91 999") or 
            phone.startswith("+91999")
        )

        sent_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if is_failure_test:
            execute(
                """
                UPDATE messages 
                SET status = 'failed', error_message = 'Mock provider: Network unreachable / API quota exceeded', updated_at = %s 
                WHERE id = %s
                """,
                (sent_time, message_id)
            )
            logger.warning(f"Simulated message delivery failure for message ID {message_id} (phone: {phone})")
            return False
        else:
            execute(
                """
                UPDATE messages 
                SET status = 'sent', sent_at = %s, error_message = NULL, updated_at = %s 
                WHERE id = %s
                """,
                (sent_time, sent_time, message_id)
            )
            logger.info(f"Simulated message delivery success for message ID {message_id} (phone: {phone})")
            return True

def create_purchase_notifications(business_id, sale_id):
    """Generates confirmation and follow-up messages on sale completion."""
    try:
        # Load sale details
        sale = fetch_one(
            """
            SELECT s.*, c.name AS customer_name, c.phone AS customer_phone, b.name AS business_name
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            LEFT JOIN businesses b ON b.id = s.business_id
            WHERE s.id = %s AND s.business_id = %s
            """,
            (sale_id, business_id)
        )
        if not sale or not sale["customer_id"]:
            return

        # Fetch product names
        items = fetch_all(
            """
            SELECT p.name 
            FROM sale_items si
            JOIN products p ON p.id = si.product_id
            WHERE si.sale_id = %s
            """,
            (sale_id,)
        )
        product_names = ", ".join([item["name"] for item in items]) if items else "Products"

        # Load settings and templates
        settings = get_or_create_settings(business_id)
        templates = get_or_create_templates(business_id)

        variables = {
            "customer_name": sale["customer_name"],
            "shop_name": sale["business_name"] or "ABC Store",
            "amount": f"₹{sale['total_amount']:,.0f}",
            "invoice_number": sale["invoice_number"],
            "purchase_date": sale["sale_date"][:10] if sale["sale_date"] else datetime.now().strftime("%Y-%m-%d"),
            "product_name": product_names
        }

        # 1. Immediate Purchase Confirmation Notification
        if settings.get("purchase_confirmation") == 1:
            raw_text = templates.get("purchase", DEFAULT_TEMPLATES["purchase"])
            message_text = render_template(raw_text, variables)
            channel = settings.get("preferred_channel", "WhatsApp")
            
            msg_id = execute(
                """
                INSERT INTO messages (business_id, customer_id, sale_id, type, message_text, channel, status, scheduled_at)
                VALUES (%s, %s, %s, 'purchase', %s, %s, 'pending', %s)
                """,
                (
                    business_id,
                    sale["customer_id"],
                    sale_id,
                    message_text,
                    channel,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )
            # Send immediately
            NotificationService().send_message(msg_id)

        # 2. Post-Purchase Follow-up Notification
        if settings.get("post_purchase_followup") == 1:
            raw_text = templates.get("follow_up", DEFAULT_TEMPLATES["follow_up"])
            message_text = render_template(raw_text, variables)
            channel = settings.get("preferred_channel", "WhatsApp")
            
            days_delay = int(settings.get("followup_days", 3))
            scheduled_date = datetime.now() + timedelta(days=days_delay)
            scheduled_str = scheduled_date.strftime("%Y-%m-%d %H:%M:%S")

            execute(
                """
                INSERT INTO messages (business_id, customer_id, sale_id, type, message_text, channel, status, scheduled_at)
                VALUES (%s, %s, %s, 'follow_up', %s, %s, 'scheduled', %s)
                """,
                (
                    business_id,
                    sale["customer_id"],
                    sale_id,
                    message_text,
                    channel,
                    scheduled_str
                )
            )
    except Exception as e:
        logger.error(f"Error creating purchase notifications for sale_id {sale_id}: {e}", exc_info=True)

def process_due_scheduled_messages():
    """Scans for and delivers scheduled messages that have become due."""
    try:
        # We query using local time comparison
        due_messages = fetch_all(
            """
            SELECT id FROM messages 
            WHERE status = 'scheduled' 
              AND datetime(scheduled_at) <= datetime('now', 'localtime')
            """
        )
        if not due_messages:
            return 0
        
        service = NotificationService()
        processed_count = 0
        for msg in due_messages:
            try:
                service.send_message(msg["id"])
                processed_count += 1
            except Exception as e:
                logger.error(f"Error processing due message ID {msg['id']}: {e}")
        return processed_count
    except Exception as e:
        logger.error(f"Error in batch processing due scheduled messages: {e}", exc_info=True)
        return 0
