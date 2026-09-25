from .analytics import analytics_bp
from .attendance import attendance_bp
from .auth import auth_bp
from .customer_portal import customer_portal_bp
from .customers import customers_bp
from .departments import departments_bp
from .dispatches import dispatches_bp
from .employees import employees_bp
from .expenses import expenses_bp
from .messages import messages_bp
from .orders import orders_bp
from .products import products_bp
from .purchases import purchases_bp
from .raw_materials import raw_materials_bp
from .reports import reports_bp
from .sales import sales_bp


def register_blueprints(app):
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(customers_bp, url_prefix="/api/customers")
    app.register_blueprint(products_bp, url_prefix="/api/products")
    app.register_blueprint(products_bp, url_prefix="/api/inventory", name="inventory")
    app.register_blueprint(raw_materials_bp, url_prefix="/api/raw-materials")
    app.register_blueprint(purchases_bp, url_prefix="/api/purchases")
    app.register_blueprint(orders_bp, url_prefix="/api/orders")
    app.register_blueprint(dispatches_bp, url_prefix="/api/dispatches")
    app.register_blueprint(attendance_bp, url_prefix="/api/attendance")
    app.register_blueprint(customer_portal_bp, url_prefix="/api/customer-portal")
    app.register_blueprint(sales_bp, url_prefix="/api/sales")
    app.register_blueprint(expenses_bp, url_prefix="/api/expenses")
    app.register_blueprint(employees_bp, url_prefix="/api/employees")
    app.register_blueprint(departments_bp, url_prefix="/api/departments")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(reports_bp, url_prefix="/api/reports")
    app.register_blueprint(messages_bp, url_prefix="/api/messages")
