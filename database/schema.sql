PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS businesses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    industry TEXT,
    phone TEXT,
    email TEXT,
    address TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'staff',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_users_business ON users(business_id);

CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    address TEXT,
    company_name TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_customers_business ON customers(business_id);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    sku TEXT NOT NULL,
    category TEXT,
    selling_price REAL DEFAULT 0,
    cost_price REAL DEFAULT 0,
    description TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    UNIQUE (business_id, sku)
);

CREATE INDEX IF NOT EXISTS idx_products_business ON products(business_id);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);

CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL UNIQUE,
    quantity INTEGER DEFAULT 0,
    minimum_stock_level INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_inventory_business ON inventory(business_id);

CREATE TABLE IF NOT EXISTS departments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_departments_business ON departments(business_id);

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    department_id INTEGER,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    designation TEXT,
    salary REAL DEFAULT 0,
    joining_date TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_employees_business ON employees(business_id);
CREATE INDEX IF NOT EXISTS idx_employees_name ON employees(name);

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    customer_id INTEGER,
    invoice_number TEXT UNIQUE,
    subtotal REAL DEFAULT 0,
    total_amount REAL DEFAULT 0,
    payment_status TEXT DEFAULT 'unpaid',
    payment_date TEXT,
    due_date TEXT,
    sale_date TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_sales_business_date ON sales(business_id, sale_date);

CREATE TABLE IF NOT EXISTS payment_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_payment_history_sale ON payment_history(sale_id);

CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    subtotal REAL NOT NULL,
    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    category TEXT,
    amount REAL NOT NULL,
    expense_date TEXT,
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_expenses_business_date ON expenses(business_id, expense_date);

CREATE TABLE IF NOT EXISTS notification_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL UNIQUE,
    purchase_confirmation INTEGER DEFAULT 1,
    post_purchase_followup INTEGER DEFAULT 1,
    followup_days INTEGER DEFAULT 3,
    preferred_channel TEXT DEFAULT 'WhatsApp',
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS message_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    template_text TEXT NOT NULL,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    UNIQUE (business_id, type)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    sale_id INTEGER,
    type TEXT NOT NULL,
    message_text TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    scheduled_at TEXT,
    sent_at TEXT,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_business ON messages(business_id);
CREATE INDEX IF NOT EXISTS idx_messages_customer ON messages(customer_id);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);

-- Multi-tenant Customer Account Linkage
CREATE TABLE IF NOT EXISTS customer_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    business_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    UNIQUE (user_id, business_id)
);

CREATE INDEX IF NOT EXISTS idx_customer_users_user ON customer_users(user_id);
CREATE INDEX IF NOT EXISTS idx_customer_users_biz_cust ON customer_users(business_id, customer_id);

-- Suppliers
CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    address TEXT,
    material_types TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_suppliers_business ON suppliers(business_id);

-- Raw Material Inventory
CREATE TABLE IF NOT EXISTS raw_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    category TEXT, -- Fabric, Thread, Buttons, Zippers, Labels, Packaging Material
    unit TEXT DEFAULT 'meters', -- meters, rolls, pieces, boxes, kg
    current_stock REAL DEFAULT 0,
    minimum_stock REAL DEFAULT 0,
    supplier_id INTEGER,
    purchase_price REAL DEFAULT 0,
    last_purchase_date TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_raw_materials_business ON raw_materials(business_id);

-- Raw Material Procurement / Purchases
CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    supplier_id INTEGER,
    raw_material_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    unit_price REAL NOT NULL,
    total_amount REAL NOT NULL,
    purchase_date TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'Received', -- Received, Pending
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL,
    FOREIGN KEY (raw_material_id) REFERENCES raw_materials(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_purchases_business ON purchases(business_id);

-- Production Orders (Knitwear / Garments Manufacturing)
CREATE TABLE IF NOT EXISTS production_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    sale_id INTEGER,
    order_number TEXT NOT NULL,
    product_id INTEGER,
    garment_name TEXT NOT NULL,
    design TEXT,
    size TEXT,
    color TEXT,
    quantity INTEGER NOT NULL DEFAULT 1,
    price REAL DEFAULT 0,
    current_stage TEXT DEFAULT 'New', -- New, Cutting, Stitching, Finishing, Quality Check, Packing, Ready for Dispatch, Completed
    assigned_employee_id INTEGER,
    start_date TEXT,
    expected_completion TEXT,
    actual_completion TEXT,
    special_requirements TEXT,
    notes TEXT,
    status TEXT DEFAULT 'New', -- New, Confirmed, Material Pending, Material Ready, In Production, Quality Check, Packed, Ready for Dispatch, Dispatched, Completed, Cancelled
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE,
    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE SET NULL,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
    FOREIGN KEY (assigned_employee_id) REFERENCES employees(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_production_orders_business ON production_orders(business_id);
CREATE INDEX IF NOT EXISTS idx_production_orders_customer ON production_orders(customer_id);

-- Order Material Requirements (BOM Check)
CREATE TABLE IF NOT EXISTS order_material_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    production_order_id INTEGER NOT NULL,
    raw_material_id INTEGER NOT NULL,
    required_quantity REAL NOT NULL,
    allocated_quantity REAL DEFAULT 0,
    status TEXT DEFAULT 'Shortage', -- Available, Shortage
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (production_order_id) REFERENCES production_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (raw_material_id) REFERENCES raw_materials(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_order_req_order ON order_material_requirements(production_order_id);

-- Quality Control
CREATE TABLE IF NOT EXISTS quality_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    production_order_id INTEGER NOT NULL,
    checked_quantity INTEGER NOT NULL,
    passed_quantity INTEGER NOT NULL,
    failed_quantity INTEGER DEFAULT 0,
    defective_quantity INTEGER DEFAULT 0,
    remarks TEXT,
    checked_by_employee_id INTEGER,
    check_date TEXT DEFAULT CURRENT_TIMESTAMP,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (production_order_id) REFERENCES production_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (checked_by_employee_id) REFERENCES employees(id) ON DELETE SET NULL
);

-- Packing Records
CREATE TABLE IF NOT EXISTS packing_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    production_order_id INTEGER NOT NULL,
    packed_quantity INTEGER NOT NULL,
    packaging_material_used TEXT,
    packed_by_employee_id INTEGER,
    pack_date TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'Packed',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (production_order_id) REFERENCES production_orders(id) ON DELETE CASCADE,
    FOREIGN KEY (packed_by_employee_id) REFERENCES employees(id) ON DELETE SET NULL
);

-- Dispatch Management
CREATE TABLE IF NOT EXISTS dispatches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    production_order_id INTEGER,
    sale_id INTEGER,
    customer_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    dispatch_date TEXT DEFAULT CURRENT_TIMESTAMP,
    courier_transport_details TEXT,
    tracking_number TEXT,
    status TEXT DEFAULT 'Dispatched', -- Pending, Ready, Dispatched, Delivered
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (production_order_id) REFERENCES production_orders(id) ON DELETE SET NULL,
    FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE SET NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dispatches_business ON dispatches(business_id);

-- Employee Attendance
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    business_id INTEGER NOT NULL,
    employee_id INTEGER NOT NULL,
    date TEXT NOT NULL, -- YYYY-MM-DD
    status TEXT DEFAULT 'Present', -- Present, Absent, Leave
    notes TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    UNIQUE (business_id, employee_id, date)
);

CREATE INDEX IF NOT EXISTS idx_attendance_biz_date ON attendance(business_id, date);


