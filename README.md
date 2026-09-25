# MSME Digital Transformation Platform

An integrated web-based platform foundation for MSMEs to digitize CRM, inventory, billing, HR, analytics, and reporting workflows.

This version uses SQLite for local development. It does not require MySQL, XAMPP, or MySQL Workbench.

## Technology Stack

- Frontend: HTML5, CSS3, JavaScript
- Backend: Python Flask
- Database: SQLite
- Charts: Chart.js
- Development: VS Code

## Folder Structure

```text
MSME-Digital-Transformation/
├── frontend/
│   ├── css/
│   ├── js/
│   ├── pages/
│   └── assets/
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── routes/
│   ├── models/
│   └── services/
├── database/
│   ├── schema.sql
│   └── msme_digital_platform.db
├── requirements.txt
├── README.md
└── .gitignore
```

## Database Setup

No manual database server setup is required.

When the Flask app starts, it initializes:

```text
database/msme_digital_platform.db
```

The schema in `database/schema.sql` is executed with `CREATE TABLE IF NOT EXISTS`, so existing data is preserved across restarts.

## Environment Configuration

`.env` is optional for development. Copy `.env.example` only if you want to override defaults.

```bash
SECRET_KEY=replace-with-a-long-random-development-secret
DATABASE_PATH=database/msme_digital_platform.db
```

Do not commit `.env` or local database files.

## Python Virtual Environment

```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Run the Application

From the project root:

```bash
python backend/app.py
```

Open:

```text
http://127.0.0.1:5000
```

## Implemented Modules

- Session-based registration, login, logout, and password hashing
- SQLite database initialization with foreign-key enforcement
- Modular Flask route files
- CRM customer CRUD foundation
- Product and inventory CRUD foundation with low-stock indicator
- Billing foundation with invoice creation and sale items
- Invoice listing
- Employee CRUD foundation
- Department creation and listing
- Analytics summary and chart data endpoints
- Business reports placeholder page
- Responsive ERP-style layout with sidebar and top navigation
- 404 and 500 pages

## API Endpoints

- `/api/auth`
- `/api/customers`
- `/api/products`
- `/api/inventory`
- `/api/sales`
- `/api/expenses`
- `/api/employees`
- `/api/departments`
- `/api/analytics`
- `/api/reports`

## Demo Data

Dashboard cards and charts show clearly labelled Demo Data when the database has no real business records yet.

## Future Development Phase

- Add editable forms for existing records
- Improve invoice UI to support multiple product rows
- Add configurable custom fields after business requirements arrive
- Add role-based permissions
- Add PDF/Excel report exports
- Add taxation/GST only after exact business rules are provided
- Add AI/ML analytics when genuine MSME use cases are identified
