from datetime import datetime, timedelta
import logging
from werkzeug.security import generate_password_hash

from services.db import db_cursor, fetch_one, normalize_query

logger = logging.getLogger(__name__)


def seed_demo_data(app=None):
    """Cleanly seed fictional demo business, accounts, and manufacturing data."""
    try:
        with db_cursor(commit=True) as cursor:
            # 1. Clean existing records for fresh demo presentation
            cursor.execute("DELETE FROM attendance")
            cursor.execute("DELETE FROM dispatches")
            cursor.execute("DELETE FROM packing_records")
            cursor.execute("DELETE FROM quality_checks")
            cursor.execute("DELETE FROM order_material_requirements")
            cursor.execute("DELETE FROM production_orders")
            cursor.execute("DELETE FROM purchases")
            cursor.execute("DELETE FROM raw_materials")
            cursor.execute("DELETE FROM suppliers")
            cursor.execute("DELETE FROM sale_items")
            cursor.execute("DELETE FROM payment_history")
            cursor.execute("DELETE FROM sales")
            cursor.execute("DELETE FROM inventory")
            cursor.execute("DELETE FROM products")
            cursor.execute("DELETE FROM expenses")
            cursor.execute("DELETE FROM employees")
            cursor.execute("DELETE FROM departments")
            cursor.execute("DELETE FROM messages")
            cursor.execute("DELETE FROM message_templates")
            cursor.execute("DELETE FROM notification_settings")
            cursor.execute("DELETE FROM customer_users")
            cursor.execute("DELETE FROM customers")
            cursor.execute("DELETE FROM users")
            cursor.execute("DELETE FROM businesses")

            # 2. Seed Business
            cursor.execute(
                normalize_query("""
                INSERT INTO businesses (id, name, industry, business_type, phone, email, address)
                VALUES (1, 'Aura Garment Industry', 'Garment Manufacturing', 'Knitwear / Garment Manufacturing', '+91 98765 00000', 'admin@auragarments.example', 'Plot 42, Textile Park, Industrial Area, Sector 5, New Delhi')
                """)
            )
            biz_id = 1

            # 3. Seed Demo User Accounts
            admin_pass = generate_password_hash("Demo@12345")
            cursor.execute(
                normalize_query("""
                INSERT INTO users (id, business_id, name, email, phone, password_hash, role)
                VALUES (1, 1, 'Demo Store Owner', 'admin@demo.local', '+91 98765 00000', %s, 'admin')
                """),
                (admin_pass,),
            )

            customer_pass = generate_password_hash("Customer@12345")
            cursor.execute(
                normalize_query("""
                INSERT INTO users (id, business_id, name, email, phone, password_hash, role)
                VALUES (2, 1, 'Demo Customer', 'customer@demo.local', '+91 98765 11111', %s, 'customer')
                """),
                (customer_pass,),
            )

            # 4. Seed Fictional Customers (10 Fictional Customers)
            customers = [
                ("Demo Customer", "+91 98765 11111", "customer@demo.local", "Demo Store Buyer", "Sector 62, Noida, Uttar Pradesh"),
                ("Aarav Garment Traders", "+91 98100 11223", "sales@aaravtraders.example", "Aarav Garment Traders", "Shop 14, Textile Market, Chandni Chowk, New Delhi"),
                ("Mehta Cloth Store", "+91 98200 22334", "mehta.retail@example.com", "Mehta Cloth Store", "45 Commercial Street, Jaipur, Rajasthan"),
                ("Urban Threads Apparel", "+91 98300 33445", "contact@urbanthreads.example", "Urban Threads Apparel", "Plot 8, Fashion Hub, Sector 18, Noida, Uttar Pradesh"),
                ("Nova Fashion Studio", "+91 98400 44556", "orders@novafashion.example", "Nova Fashion Studio", "102 Linking Road, Bandra West, Mumbai, Maharashtra"),
                ("StyleHub Wholesale", "+91 98500 55667", "info@stylehub.example", "StyleHub Wholesale", "78 Wholesale Complex, Ring Road, Surat, Gujarat"),
                ("Prime Garments Store", "+91 98600 66778", "prime.store@example.com", "Prime Garments Store", "22 Mall Road, Ludhiana, Punjab"),
                ("Trendline Retailers", "+91 98700 77889", "trendline@example.org", "Trendline Retailers", "55 MG Road, Bengaluru, Karnataka"),
                ("Fashion Point Emporium", "+91 98800 88990", "fpoint@example.local", "Fashion Point Emporium", "34 Main Market, Kanpur, Uttar Pradesh"),
                ("Velvet Vogue Outfits", "+91 98900 99001", "ritu@velvetvogue.example", "Velvet Vogue Outfits", "19 Heritage Arcade, C.G. Road, Ahmedabad, Gujarat"),
            ]

            cust_ids = {}
            for name, phone, email, company, addr in customers:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO customers (business_id, name, phone, email, address, company_name, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'active')
                    """),
                    (biz_id, name, phone, email, addr, company),
                )
                c_id = cursor.lastrowid
                cust_ids[name] = c_id

            # Link Demo Customer user account to business customer profile
            cursor.execute(
                normalize_query("""
                INSERT INTO customer_users (user_id, business_id, customer_id)
                VALUES (2, 1, %s)
                """),
                (cust_ids["Demo Customer"],),
            )

            # 5. Seed Garment Products & Inventory (10 Products)
            products = [
                ("Classic Cotton T-Shirt", "GAR-TS-101", "T-Shirts", 299.00, 140.00, 450, 50, "100% bio-washed combed cotton round neck t-shirt"),
                ("Polo T-Shirt", "GAR-PL-102", "Polo Shirts", 499.00, 230.00, 320, 40, "Premium cotton polo shirt with ribbed collar and placket"),
                ("Full Sleeve T-Shirt", "GAR-FS-103", "T-Shirts", 399.00, 190.00, 180, 35, "Ribbed cuff full sleeve combed cotton t-shirt"),
                ("Cotton Sweatshirt", "GAR-SW-104", "Sweatshirts", 699.00, 340.00, 110, 25, "Crewneck heavy fleece cotton blend sweatshirt"),
                ("Basic Hoodie", "GAR-HD-105", "Hoodies", 899.00, 450.00, 85, 20, "Fleece-lined winter hoodie with adjustable drawstring and kangaroo pocket"),
                ("Track Pant", "GAR-TP-106", "Bottomwear", 599.00, 280.00, 140, 30, "Poly-cotton breathable athletic track pants with zippered pockets"),
                ("Jogger", "GAR-JG-107", "Bottomwear", 649.00, 310.00, 12, 25, "Slim-fit cotton fleece jogger pants with elastic cuff"), # Low stock
                ("Casual Shorts", "GAR-SH-108", "Bottomwear", 349.00, 160.00, 220, 40, "Lightweight summer cotton casual shorts with side pockets"),
                ("Fleece Jacket", "GAR-JK-109", "Outerwear", 1199.00, 600.00, 8, 15, "Full-zip insulated fleece winter jacket"), # Low stock
                ("Sports T-Shirt", "GAR-SP-110", "Activewear", 379.00, 180.00, 260, 50, "Dri-fit breathable athletic performance t-shirt"),
            ]

            prod_ids = {}
            for name, sku, category, sell, cost, qty, min_lvl, desc in products:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO products (business_id, name, sku, category, selling_price, cost_price, description, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'active')
                    """),
                    (biz_id, name, sku, category, sell, cost, desc),
                )
                p_id = cursor.lastrowid
                prod_ids[name] = p_id

                cursor.execute(
                    normalize_query("""
                    INSERT INTO inventory (business_id, product_id, quantity, minimum_stock_level, status)
                    VALUES (%s, %s, %s, %s, 'active')
                    """),
                    (biz_id, p_id, qty, min_lvl),
                )

            # 6. Seed Suppliers (5 Suppliers)
            suppliers = [
                ("Vardhman Yarns & Mills", "+91 98111 22331", "supplier1@varnmills.example", "Ludhiana Industrial Area, Punjab", "Cotton Fabric, Polyester Fabric, Thread"),
                ("Zenith Fasteners Co", "+91 98111 22332", "orders@zenithfasteners.example", "Sector 34, Manesar, Haryana", "Buttons, Zippers"),
                ("Heritage Labels & Trims", "+91 98111 22333", "sales@heritagetrims.example", "Okhla Industrial Estate Phase III, New Delhi", "Woven Labels, Hang Tags"),
                ("PackWell Box & Packaging", "+91 98111 22334", "contact@packwell.example", "Site IV Industrial Area, Sahibabad, Uttar Pradesh", "Poly Bags, Cartons, Packaging Tape"),
                ("Apex Textile Processors", "+91 98111 22335", "apex@textiles.example", "Tirupur Knitwear Cluster, Tamil Nadu", "Dyed Fabrics, Knitted Fabrics"),
            ]

            sup_ids = {}
            for sname, sphone, semail, saddr, stypes in suppliers:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO suppliers (business_id, name, phone, email, address, material_types, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'active')
                    """),
                    (biz_id, sname, sphone, semail, saddr, stypes),
                )
                sup_ids[sname] = cursor.lastrowid

            # 7. Seed Raw Materials (Mix of Healthy, Low Stock, and Out of Stock)
            raw_mats = [
                ("Cotton Fabric", "Fabric", "meters", 1400.0, 400.0, sup_ids["Vardhman Yarns & Mills"], 175.00),
                ("Polyester Fabric", "Fabric", "meters", 650.0, 250.0, sup_ids["Vardhman Yarns & Mills"], 135.00),
                ("Polyester/Cotton Thread", "Thread", "spools", 120.0, 30.0, sup_ids["Vardhman Yarns & Mills"], 42.00),
                ("Buttons", "Fasteners", "pieces", 180.0, 500.0, sup_ids["Zenith Fasteners Co"], 2.20), # Low stock
                ("Zippers", "Fasteners", "pieces", 60.0, 200.0, sup_ids["Zenith Fasteners Co"], 11.50), # Low stock
                ("Woven Labels", "Trims", "pieces", 3200.0, 600.0, sup_ids["Heritage Labels & Trims"], 1.40),
                ("Poly Bags", "Packaging Material", "pieces", 2400.0, 500.0, sup_ids["PackWell Box & Packaging"], 2.80),
                ("Cartons", "Packaging Material", "boxes", 15.0, 80.0, sup_ids["PackWell Box & Packaging"], 34.00), # Low stock
                ("Packaging Tape", "Packaging Material", "rolls", 0.0, 20.0, sup_ids["PackWell Box & Packaging"], 25.00), # Out of stock
            ]

            mat_ids = {}
            for mname, cat, unit, cur_st, min_st, sup_id, price in raw_mats:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO raw_materials (business_id, name, category, unit, current_stock, minimum_stock, supplier_id, purchase_price, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
                    """),
                    (biz_id, mname, cat, unit, cur_st, min_st, sup_id, price),
                )
                mat_ids[mname] = cursor.lastrowid

            # Seed Raw Material Procurement / Purchase Records
            purchases = [
                (sup_ids["Vardhman Yarns & Mills"], mat_ids["Cotton Fabric"], 1000.0, 175.00, 175000.00, "2026-08-01", "Received", "Bulk cotton fabric order for Q3 production"),
                (sup_ids["Vardhman Yarns & Mills"], mat_ids["Polyester Fabric"], 500.0, 135.00, 67500.00, "2026-08-05", "Received", "Polyester fabric shipment received"),
                (sup_ids["Vardhman Yarns & Mills"], mat_ids["Polyester/Cotton Thread"], 100.0, 42.00, 4200.00, "2026-08-10", "Received", "High tenacity sewing thread spools"),
                (sup_ids["Heritage Labels & Trims"], mat_ids["Woven Labels"], 3000.0, 1.40, 4200.00, "2026-08-12", "Received", "Custom brand woven neck labels"),
                (sup_ids["PackWell Box & Packaging"], mat_ids["Poly Bags"], 2000.0, 2.80, 5600.00, "2026-08-15", "Received", "Transparent polybags for garment packaging"),
                (sup_ids["Zenith Fasteners Co"], mat_ids["Buttons"], 500.0, 2.20, 1100.00, "2026-09-02", "Pending", "Order placed for polo shirt buttons"),
            ]

            for s_id, rm_id, qty, u_pr, tot_amt, p_dt, p_st, p_notes in purchases:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO purchases (business_id, supplier_id, raw_material_id, quantity, unit_price, total_amount, purchase_date, status, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """),
                    (biz_id, s_id, rm_id, qty, u_pr, tot_amt, p_dt, p_st, p_notes),
                )

            # 8. Seed Departments & Employees (12 Employees)
            depts = ["Cutting", "Stitching", "Finishing", "Quality", "Packing", "Store & Management"]
            dept_ids = {}
            for dname in depts:
                cursor.execute(
                    normalize_query("INSERT INTO departments (business_id, name, status) VALUES (%s, %s, 'active')"),
                    (biz_id, dname),
                )
                dept_ids[dname] = cursor.lastrowid

            employees = [
                ("Rajesh Kumar", dept_ids["Cutting"], "Master Cutter", "+91 98700 10001", "rajesh.kumar@example.local", 24000.0, "2024-03-10"),
                ("Suresh Patel", dept_ids["Cutting"], "Fabric Spreader", "+91 98700 10002", "suresh.patel@example.local", 18000.0, "2024-06-15"),
                ("Anita Verma", dept_ids["Stitching"], "Senior Tailor", "+91 98700 10003", "anita.verma@example.local", 22000.0, "2024-01-20"),
                ("Deepak Singh", dept_ids["Stitching"], "Machine Operator", "+91 98700 10004", "deepak.singh@example.local", 19000.0, "2024-04-12"),
                ("Manoj Yadav", dept_ids["Stitching"], "Overlock Operator", "+91 98700 10005", "manoj.yadav@example.local", 18500.0, "2024-05-01"),
                ("Vikram Malhotra", dept_ids["Finishing"], "Ironing Specialist", "+91 98700 10006", "vikram.m@example.local", 17000.0, "2024-07-10"),
                ("Sunita Sharma", dept_ids["Finishing"], "Thread Trimmer", "+91 98700 10007", "sunita.s@example.local", 15500.0, "2024-08-01"),
                ("Kavita Gupta", dept_ids["Quality"], "QA Lead", "+91 98700 10008", "kavita.gupta@example.local", 25000.0, "2023-11-15"),
                ("Ravi Shankar", dept_ids["Quality"], "Quality Inspector", "+91 98700 10009", "ravi.shankar@example.local", 19500.0, "2024-02-18"),
                ("Amit Joshi", dept_ids["Packing"], "Packing Lead", "+91 98700 10010", "amit.joshi@example.local", 16500.0, "2024-05-20"),
                ("Sanjay Gupta", dept_ids["Packing"], "Box Sealer", "+91 98700 10011", "sanjay.gupta@example.local", 16000.0, "2024-09-01"),
                ("Rekha Devi", dept_ids["Store & Management"], "Production Supervisor", "+91 98700 10012", "rekha.devi@example.local", 28000.0, "2023-08-01"),
            ]

            emp_ids = {}
            for ename, d_id, desig, ephone, eemail, sal, jdate in employees:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO employees (business_id, department_id, name, phone, email, designation, salary, joining_date, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
                    """),
                    (biz_id, d_id, ename, ephone, eemail, desig, sal, jdate),
                )
                emp_ids[ename] = cursor.lastrowid

            # Seed Employee Attendance Records over recent days
            dates_to_seed = [
                (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d"),
                (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
                (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
                datetime.now().strftime("%Y-%m-%d"),
            ]

            for d_idx, dt_str in enumerate(dates_to_seed):
                for idx, (e_name, e_id) in enumerate(emp_ids.items()):
                    if (idx + d_idx) % 7 == 0:
                        att_st = "Absent"
                        notes = "Personal leave requested"
                    elif (idx + d_idx) % 11 == 0:
                        att_st = "Half Day"
                        notes = "First half present"
                    elif (idx + d_idx) % 13 == 0:
                        att_st = "Leave"
                        notes = "Medical leave"
                    else:
                        att_st = "Present"
                        notes = "On time"

                    cursor.execute(
                        normalize_query("""
                        INSERT INTO attendance (business_id, employee_id, date, status, notes)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT(business_id, employee_id, date) DO UPDATE SET status=excluded.status, notes=excluded.notes
                        """),
                        (biz_id, e_id, dt_str, att_st, notes),
                    )

            # 9. Seed Manufacturing Expenses
            expenses = [
                ("Raw Material Freight & Logistics", "Freight", 14500.00, "2026-08-15", "Transport charges for fabric delivery from Ludhiana"),
                ("Factory Electricity & Power Bill", "Utilities", 32000.00, "2026-08-20", "Monthly power consumption bill for factory machines"),
                ("Cutting & Sewing Machine Maintenance", "Maintenance", 8800.00, "2026-08-22", "Servicing of motor and needles calibration"),
                ("Worker Refreshment & Pantry Expenses", "Operational", 4200.00, "2026-08-25", "Tea and refreshments for shop floor workers"),
                ("Industrial Factory Rent - August 2026", "Rent", 65000.00, "2026-09-01", "Monthly rental payment for factory premises"),
                ("Needles & Trims Consumables", "Supplies", 5600.00, "2026-09-02", "Spare sewing needles and oil lubrication"),
            ]

            for title, cat, amt, exp_dt, notes in expenses:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO expenses (business_id, title, category, amount, expense_date, notes)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """),
                    (biz_id, title, cat, amt, exp_dt, notes),
                )

            # 10. Seed Connected Orders & Production Workflow (12 Customer Orders)
            today_date = datetime.now()
            orders_config = [
                ("ORD-1001", cust_ids["Aarav Garment Traders"], prod_ids["Classic Cotton T-Shirt"], "Classic Cotton T-Shirt", "PL-101", "L", "Navy Blue", 500, 299.00, "Stitching", "In Production", emp_ids["Anita Verma"], (today_date - timedelta(days=15)).strftime("%Y-%m-%d"), (today_date + timedelta(days=6)).strftime("%Y-%m-%d"), None),
                ("ORD-1002", cust_ids["Mehta Cloth Store"], prod_ids["Polo T-Shirt"], "Polo T-Shirt", "PL-102", "M", "White", 300, 499.00, "Quality Check", "Quality Check", emp_ids["Kavita Gupta"], (today_date - timedelta(days=13)).strftime("%Y-%m-%d"), (today_date + timedelta(days=1)).strftime("%Y-%m-%d"), None),
                ("ORD-1003", cust_ids["Urban Threads Apparel"], prod_ids["Basic Hoodie"], "Basic Hoodie", "HD-105", "XL", "Black", 200, 899.00, "Completed", "Completed", emp_ids["Amit Joshi"], (today_date - timedelta(days=20)).strftime("%Y-%m-%d"), (today_date - timedelta(days=5)).strftime("%Y-%m-%d"), (today_date - timedelta(days=7)).strftime("%Y-%m-%d")),
                ("ORD-1004", cust_ids["Nova Fashion Studio"], prod_ids["Cotton Sweatshirt"], "Cotton Sweatshirt", "SW-104", "L", "Heather Grey", 150, 699.00, "Ready for Dispatch", "Packed", emp_ids["Amit Joshi"], (today_date - timedelta(days=17)).strftime("%Y-%m-%d"), (today_date - timedelta(days=7)).strftime("%Y-%m-%d"), None),
                ("ORD-1005", cust_ids["StyleHub Wholesale"], prod_ids["Full Sleeve T-Shirt"], "Full Sleeve T-Shirt", "FS-103", "M", "Olive Green", 400, 399.00, "Cutting", "In Production", emp_ids["Rajesh Kumar"], (today_date - timedelta(days=10)).strftime("%Y-%m-%d"), (today_date + timedelta(days=8)).strftime("%Y-%m-%d"), None),
                ("ORD-1006", cust_ids["Prime Garments Store"], prod_ids["Track Pant"], "Track Pant", "TP-106", "L", "Charcoal", 250, 599.00, "Finishing", "In Production", emp_ids["Vikram Malhotra"], (today_date - timedelta(days=7)).strftime("%Y-%m-%d"), (today_date + timedelta(days=11)).strftime("%Y-%m-%d"), None),
                ("ORD-1007", cust_ids["Trendline Retailers"], prod_ids["Sports T-Shirt"], "Sports T-Shirt", "SP-110", "L", "Royal Blue", 600, 379.00, "Completed", "Completed", emp_ids["Vikram Malhotra"], (today_date - timedelta(days=25)).strftime("%Y-%m-%d"), (today_date - timedelta(days=10)).strftime("%Y-%m-%d"), (today_date - timedelta(days=11)).strftime("%Y-%m-%d")),
                ("ORD-1008", cust_ids["Fashion Point Emporium"], prod_ids["Jogger"], "Jogger", "JG-107", "M", "Beige", 100, 649.00, "New", "Material Pending", None, (today_date - timedelta(days=3)).strftime("%Y-%m-%d"), (today_date + timedelta(days=14)).strftime("%Y-%m-%d"), None),
                ("ORD-1009", cust_ids["Velvet Vogue Outfits"], prod_ids["Casual Shorts"], "Casual Shorts", "SH-108", "S", "Khaki", 350, 349.00, "Packing", "Quality Check", emp_ids["Amit Joshi"], (today_date - timedelta(days=6)).strftime("%Y-%m-%d"), (today_date + timedelta(days=10)).strftime("%Y-%m-%d"), None),
                ("ORD-1010", cust_ids["Demo Customer"], prod_ids["Classic Cotton T-Shirt"], "Classic Cotton T-Shirt", "TS-101", "L", "Black", 100, 299.00, "Order Received", "Material Ready", None, today_date.strftime("%Y-%m-%d"), (today_date + timedelta(days=16)).strftime("%Y-%m-%d"), None),
                ("ORD-1011", cust_ids["Demo Customer"], prod_ids["Basic Hoodie"], "Basic Hoodie", "HD-105", "M", "Maroon", 50, 899.00, "Ready for Dispatch", "Packed", emp_ids["Amit Joshi"], today_date.strftime("%Y-%m-%d"), (today_date + timedelta(days=16)).strftime("%Y-%m-%d"), None),
                ("ORD-1012", cust_ids["Aarav Garment Traders"], prod_ids["Fleece Jacket"], "Fleece Jacket", "JK-109", "XL", "Navy Blue", 80, 1199.00, "Completed", "Completed", emp_ids["Rekha Devi"], (today_date - timedelta(days=23)).strftime("%Y-%m-%d"), (today_date - timedelta(days=9)).strftime("%Y-%m-%d"), (today_date - timedelta(days=10)).strftime("%Y-%m-%d")),
            ]

            order_ids = {}
            for onum, c_id, p_id, gname, des, sz, col, qty, pr, stage, st, emp_assign, s_dt, e_dt, a_comp in orders_config:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO production_orders (
                        business_id, customer_id, product_id, order_number, garment_name, design, size, color,
                        quantity, price, current_stage, assigned_employee_id, start_date, expected_completion, actual_completion, status, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """),
                    (
                        biz_id, c_id, p_id, onum, gname, des, sz, col, qty, pr, stage, emp_assign,
                        s_dt, e_dt, a_comp, st, s_dt + " 10:00:00"
                    ),
                )
                o_id = cursor.lastrowid
                order_ids[onum] = o_id

                # Attach Raw Material BOM Requirements
                req_status = "Shortage" if onum == "ORD-1008" else "Available"
                cursor.execute(
                    normalize_query("""
                    INSERT INTO order_material_requirements (production_order_id, raw_material_id, required_quantity, allocated_quantity, status)
                    VALUES (%s, %s, %s, %s, %s)
                    """),
                    (o_id, mat_ids["Cotton Fabric"], qty * 1.4, qty * (1.4 if req_status == "Available" else 0.4), req_status),
                )

            # 11. Seed Quality Audit Records
            q_checks_data = [
                (order_ids["ORD-1002"], 300, 292, 8, 8, "8 pcs minor stitching flaws flagged for reworking", emp_ids["Kavita Gupta"]),
                (order_ids["ORD-1003"], 200, 198, 2, 2, "2 pcs fabric shade variance rejected", emp_ids["Kavita Gupta"]),
                (order_ids["ORD-1007"], 600, 595, 5, 5, "5 pcs neck rib alignment issue", emp_ids["Ravi Shankar"]),
                (order_ids["ORD-1009"], 350, 348, 2, 2, "2 pcs loose button attachment fixed", emp_ids["Ravi Shankar"]),
            ]

            for o_id, chk_q, pass_q, fail_q, def_q, rmks, emp_chk in q_checks_data:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO quality_checks (production_order_id, checked_quantity, passed_quantity, failed_quantity, defective_quantity, remarks, checked_by_employee_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """),
                    (o_id, chk_q, pass_q, fail_q, def_q, rmks, emp_chk),
                )

            # 12. Seed Packing Records
            packing_data = [
                (order_ids["ORD-1003"], 198, "Polybag + 4 Master Cartons", emp_ids["Amit Joshi"]),
                (order_ids["ORD-1004"], 150, "Polybag + 3 Master Cartons", emp_ids["Amit Joshi"]),
                (order_ids["ORD-1007"], 595, "Polybag + 12 Master Cartons", emp_ids["Sanjay Gupta"]),
                (order_ids["ORD-1009"], 348, "Polybag + 7 Master Cartons", emp_ids["Sanjay Gupta"]),
                (order_ids["ORD-1011"], 50, "Polybag + 1 Master Carton", emp_ids["Amit Joshi"]),
            ]

            for o_id, pack_q, mat_u, emp_pk in packing_data:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO packing_records (production_order_id, packed_quantity, packaging_material_used, packed_by_employee_id)
                    VALUES (%s, %s, %s, %s)
                    """),
                    (o_id, pack_q, mat_u, emp_pk),
                )

            # 13. Seed Sales Invoices & Line Items (Interconnected with Orders & Customers)
            invoices_config = [
                ("INV-1001", cust_ids["Aarav Garment Traders"], order_ids["ORD-1001"], prod_ids["Classic Cotton T-Shirt"], 500, 299.00, 149500.00, "paid", (today_date - timedelta(days=13)).strftime("%Y-%m-%d"), (today_date + timedelta(days=6)).strftime("%Y-%m-%d"), (today_date - timedelta(days=15)).strftime("%Y-%m-%d")),
                ("INV-1002", cust_ids["Mehta Cloth Store"], order_ids["ORD-1002"], prod_ids["Polo T-Shirt"], 300, 499.00, 149700.00, "paid", (today_date - timedelta(days=10)).strftime("%Y-%m-%d"), (today_date + timedelta(days=1)).strftime("%Y-%m-%d"), (today_date - timedelta(days=13)).strftime("%Y-%m-%d")),
                ("INV-1003", cust_ids["Urban Threads Apparel"], order_ids["ORD-1003"], prod_ids["Basic Hoodie"], 200, 899.00, 179800.00, "paid", (today_date - timedelta(days=7)).strftime("%Y-%m-%d"), (today_date - timedelta(days=5)).strftime("%Y-%m-%d"), (today_date - timedelta(days=20)).strftime("%Y-%m-%d")),
                ("INV-1004", cust_ids["Nova Fashion Studio"], order_ids["ORD-1004"], prod_ids["Cotton Sweatshirt"], 150, 699.00, 104850.00, "unpaid", None, (today_date - timedelta(days=7)).strftime("%Y-%m-%d"), (today_date - timedelta(days=17)).strftime("%Y-%m-%d")), # OVERDUE!
                ("INV-1005", cust_ids["StyleHub Wholesale"], order_ids["ORD-1005"], prod_ids["Full Sleeve T-Shirt"], 400, 399.00, 159600.00, "unpaid", None, (today_date + timedelta(days=8)).strftime("%Y-%m-%d"), (today_date - timedelta(days=10)).strftime("%Y-%m-%d")),
                ("INV-1006", cust_ids["Prime Garments Store"], order_ids["ORD-1006"], prod_ids["Track Pant"], 250, 599.00, 149750.00, "partially_paid", (today_date - timedelta(days=3)).strftime("%Y-%m-%d"), (today_date + timedelta(days=11)).strftime("%Y-%m-%d"), (today_date - timedelta(days=7)).strftime("%Y-%m-%d")),
                ("INV-1007", cust_ids["Trendline Retailers"], order_ids["ORD-1007"], prod_ids["Sports T-Shirt"], 600, 379.00, 227400.00, "paid", (today_date - timedelta(days=11)).strftime("%Y-%m-%d"), (today_date - timedelta(days=10)).strftime("%Y-%m-%d"), (today_date - timedelta(days=25)).strftime("%Y-%m-%d")),
                ("INV-1008", cust_ids["Fashion Point Emporium"], order_ids["ORD-1008"], prod_ids["Jogger"], 100, 649.00, 64900.00, "unpaid", None, (today_date + timedelta(days=14)).strftime("%Y-%m-%d"), (today_date - timedelta(days=3)).strftime("%Y-%m-%d")),
                ("INV-1009", cust_ids["Velvet Vogue Outfits"], order_ids["ORD-1009"], prod_ids["Casual Shorts"], 350, 349.00, 122150.00, "paid", (today_date - timedelta(days=2)).strftime("%Y-%m-%d"), (today_date + timedelta(days=10)).strftime("%Y-%m-%d"), (today_date - timedelta(days=6)).strftime("%Y-%m-%d")),
                ("INV-1010", cust_ids["Demo Customer"], order_ids["ORD-1010"], prod_ids["Classic Cotton T-Shirt"], 100, 299.00, 29900.00, "paid", today_date.strftime("%Y-%m-%d"), (today_date + timedelta(days=16)).strftime("%Y-%m-%d"), today_date.strftime("%Y-%m-%d")), # Paid Today
                ("INV-1011", cust_ids["Demo Customer"], order_ids["ORD-1011"], prod_ids["Basic Hoodie"], 50, 899.00, 44950.00, "unpaid", None, (today_date + timedelta(days=16)).strftime("%Y-%m-%d"), today_date.strftime("%Y-%m-%d")), # Order Today
                ("INV-1012", cust_ids["Aarav Garment Traders"], order_ids["ORD-1012"], prod_ids["Fleece Jacket"], 80, 1199.00, 95920.00, "unpaid", None, (today_date - timedelta(days=9)).strftime("%Y-%m-%d"), (today_date - timedelta(days=23)).strftime("%Y-%m-%d")), # OVERDUE!
            ]

            sale_ids = {}
            for inv_num, c_id, o_id, p_id, qty, u_pr, total, pay_st, pay_dt, due_dt, sale_dt in invoices_config:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO sales (business_id, customer_id, invoice_number, subtotal, total_amount, payment_status, payment_date, due_date, sale_date, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """),
                    (biz_id, c_id, inv_num, total, total, pay_st, pay_dt, due_dt, sale_dt, sale_dt + " 11:30:00"),
                )
                s_id = cursor.lastrowid
                sale_ids[inv_num] = s_id

                # Link sale_id to production_order
                cursor.execute(
                    normalize_query("UPDATE production_orders SET sale_id = %s WHERE id = %s"),
                    (s_id, o_id),
                )

                # Insert line item
                cursor.execute(
                    normalize_query("""
                    INSERT INTO sale_items (sale_id, product_id, quantity, unit_price, subtotal)
                    VALUES (%s, %s, %s, %s, %s)
                    """),
                    (s_id, p_id, qty, u_pr, total),
                )

                # Payment history
                if pay_st == "paid":
                    cursor.execute(
                        normalize_query("INSERT INTO payment_history (sale_id, action, created_at) VALUES (%s, %s, %s)"),
                        (s_id, "Invoice Issued & Paid in Full", pay_dt + " 14:00:00" if pay_dt else sale_dt + " 14:00:00"),
                    )
                elif pay_st == "partially_paid":
                    cursor.execute(
                        normalize_query("INSERT INTO payment_history (sale_id, action, created_at) VALUES (%s, %s, %s)"),
                        (s_id, "Invoice Issued", sale_dt + " 11:30:00"),
                    )
                    cursor.execute(
                        normalize_query("INSERT INTO payment_history (sale_id, action, created_at) VALUES (%s, %s, %s)"),
                        (s_id, "Partial Payment Received (₹75,000 via NEFT)", pay_dt + " 15:30:00" if pay_dt else sale_dt + " 15:30:00"),
                    )
                else:
                    cursor.execute(
                        normalize_query("INSERT INTO payment_history (sale_id, action, created_at) VALUES (%s, %s, %s)"),
                        (s_id, "Invoice Issued", sale_dt + " 11:30:00"),
                    )

            # 14. Seed Dispatch Records (Connected to Completed / Ready Orders)
            dispatches_data = [
                (order_ids["ORD-1003"], sale_ids["INV-1003"], cust_ids["Urban Threads Apparel"], 198, (today_date - timedelta(days=6)).strftime("%Y-%m-%d"), "SafeExpress Logistics", "SE-991042", "Delivered", "Delivered to buyer warehouse"),
                (order_ids["ORD-1007"], sale_ids["INV-1007"], cust_ids["Trendline Retailers"], 595, (today_date - timedelta(days=9)).strftime("%Y-%m-%d"), "BlueDart Express", "BD-883019", "Delivered", "Acknowledged by store manager"),
                (order_ids["ORD-1011"], sale_ids["INV-1011"], cust_ids["Demo Customer"], 50, today_date.strftime("%Y-%m-%d"), "Delhivery Surface", "DL-109283", "Dispatched", "In transit to delivery address"),
            ]

            for o_id, s_id, c_id, qty, d_dt, cour, trk, d_st, notes in dispatches_data:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO dispatches (business_id, production_order_id, sale_id, customer_id, quantity, dispatch_date, courier_transport_details, tracking_number, status, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """),
                    (biz_id, o_id, s_id, c_id, qty, d_dt, cour, trk, d_st, notes),
                )

            # 15. Seed Notification Settings, Templates & Logged Messages
            cursor.execute(
                normalize_query("""
                INSERT INTO notification_settings (business_id, purchase_confirmation, post_purchase_followup, followup_days, preferred_channel)
                VALUES (%s, 1, 1, 3, 'WhatsApp')
                ON CONFLICT(business_id) DO UPDATE SET preferred_channel = 'WhatsApp'
                """),
                (biz_id,),
            )

            templates = [
                ("purchase", "Dear {{customer_name}}, thank you for your order! Your invoice #{{invoice_number}} for ₹{{amount}} has been recorded."),
                ("follow_up", "Hi {{customer_name}}, hope you are satisfied with your recent garment shipment! Let us know if you need anything."),
                ("payment_reminder", "Dear {{customer_name}}, friendly reminder that invoice #{{invoice_number}} is due for payment. Thank you!"),
            ]

            for t_type, t_txt in templates:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO message_templates (business_id, type, template_text)
                    VALUES (%s, %s, %s)
                    ON CONFLICT(business_id, type) DO UPDATE SET template_text = excluded.template_text
                    """),
                    (biz_id, t_type, t_txt),
                )

            notifications = [
                (cust_ids["Demo Customer"], sale_ids["INV-1010"], "purchase", "Dear Demo Customer, thank you for your order! Your invoice #INV-1010 for ₹29,900 has been recorded.", "WhatsApp", "sent", today_date.strftime("%Y-%m-%d %H:%M:%S")),
                (cust_ids["Aarav Garment Traders"], sale_ids["INV-1001"], "purchase", "Dear Aarav Garment Traders, thank you for your order! Your invoice #INV-1001 for ₹149,500 has been recorded.", "WhatsApp", "sent", (today_date - timedelta(days=15)).strftime("%Y-%m-%d %H:%M:%S")),
                (cust_ids["Nova Fashion Studio"], sale_ids["INV-1004"], "payment_reminder", "Dear Nova Fashion Studio, friendly reminder that invoice #INV-1004 is due for payment. Thank you!", "WhatsApp", "scheduled", None),
            ]

            for c_id, s_id, m_type, txt, ch, st, s_at in notifications:
                cursor.execute(
                    normalize_query("""
                    INSERT INTO messages (business_id, customer_id, sale_id, type, message_text, channel, status, sent_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """),
                    (biz_id, c_id, s_id, m_type, txt, ch, st, s_at),
                )

            logger.info("Demo database seeded successfully!")
            print("Demo business, accounts, and manufacturing data seeded cleanly! SUCCESS")

    except Exception as e:
        logger.error(f"Error seeding demo database: {e}", exc_info=True)
        raise e

