import os
import sqlite3
from contextlib import contextmanager

from flask import current_app


def get_connection():
    connection = sqlite3.connect(current_app.config["DATABASE_PATH"])
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def normalize_query(query):
    return query.replace("%s", "?")


class DatabaseCursor:
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        return self.cursor.execute(normalize_query(query), params or ())

    def fetchall(self):
        return self.cursor.fetchall()

    def fetchone(self):
        return self.cursor.fetchone()

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    def close(self):
        self.cursor.close()


@contextmanager
def db_cursor(commit=False):
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = DatabaseCursor(connection.cursor())
        yield cursor
        if commit:
            connection.commit()
    except sqlite3.Error:
        if connection:
            connection.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def run_migrations(connection):
    cursor = connection.cursor()
    columns_sales = [row[1] for row in cursor.execute("PRAGMA table_info(sales)").fetchall()]
    if "payment_date" not in columns_sales:
        cursor.execute("ALTER TABLE sales ADD COLUMN payment_date TEXT")
    if "due_date" not in columns_sales:
        cursor.execute("ALTER TABLE sales ADD COLUMN due_date TEXT")

    cols_biz = [row[1] for row in cursor.execute("PRAGMA table_info(businesses)").fetchall()]
    if "business_type" not in cols_biz:
        cursor.execute("ALTER TABLE businesses ADD COLUMN business_type TEXT DEFAULT 'Knitwear / Garment Manufacturing'")

    cols_users = [row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()]
    if "phone" not in cols_users:
        cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")

    for table in ["customers", "products", "inventory", "departments"]:
        cols = [row[1] for row in cursor.execute(f"PRAGMA table_info({table})").fetchall()]
        if "status" not in cols:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN status TEXT DEFAULT 'active'")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payment_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notification_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL UNIQUE,
        purchase_confirmation INTEGER DEFAULT 1,
        post_purchase_followup INTEGER DEFAULT 1,
        followup_days INTEGER DEFAULT 3,
        preferred_channel TEXT DEFAULT 'WhatsApp',
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS message_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        template_text TEXT NOT NULL,
        FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE,
        UNIQUE (business_id, type)
    )
    """)
    
    cursor.execute("""
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
    )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_business ON messages(business_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_customer ON messages(customer_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status)")
    
    connection.commit()


def initialize_database(app):
    database_path = app.config["DATABASE_PATH"]
    os.makedirs(os.path.dirname(database_path), exist_ok=True)

    with app.app_context():
        with get_connection() as connection:
            schema_path = app.config["SCHEMA_PATH"]
            with open(schema_path, "r", encoding="utf-8") as schema_file:
                connection.executescript(schema_file.read())
            run_migrations(connection)

        # Check if demo admin account exists; if missing, seed demo data automatically
        admin = fetch_one("SELECT id FROM users WHERE email = %s", ("admin@demo.local",))
        if not admin:
            from services.seed_demo import seed_demo_data
            seed_demo_data(app)


def rows_to_dicts(rows):
    return [dict(row) for row in rows]


def fetch_all(query, params=None):
    with db_cursor() as cursor:
        cursor.execute(normalize_query(query), params or ())
        return rows_to_dicts(cursor.fetchall())


def fetch_one(query, params=None):
    with db_cursor() as cursor:
        cursor.execute(normalize_query(query), params or ())
        row = cursor.fetchone()
        return dict(row) if row else None


def execute(query, params=None):
    with db_cursor(commit=True) as cursor:
        cursor.execute(normalize_query(query), params or ())
        return cursor.lastrowid
