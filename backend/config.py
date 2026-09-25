import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

VENV_SITE_PACKAGES = os.path.join(PROJECT_DIR, ".venv", "Lib", "site-packages")
if os.path.exists(VENV_SITE_PACKAGES) and VENV_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, VENV_SITE_PACKAGES)

from dotenv import load_dotenv

# Load project-root .env even when Flask is started from the backend folder.
load_dotenv(os.path.join(PROJECT_DIR, ".env"))
load_dotenv()


def project_path(path):
    if os.path.isabs(path):
        return path
    return os.path.join(PROJECT_DIR, path)


def get_database_path():
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        tmp_db = "/tmp/msme_digital_platform.db"
        seed_db = project_path(os.path.join("database", "msme_digital_platform.db"))
        if not os.path.exists(tmp_db) and os.path.exists(seed_db):
            try:
                import shutil
                shutil.copyfile(seed_db, tmp_db)
            except Exception:
                pass
        return tmp_db
    return project_path(os.getenv("DATABASE_PATH", os.path.join("database", "msme_digital_platform.db")))


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-development-secret")
    DATABASE_PATH = get_database_path()
    SCHEMA_PATH = os.path.join(PROJECT_DIR, "database", "schema.sql")
    JSON_SORT_KEYS = False
