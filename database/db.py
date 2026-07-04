
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

from database.models import Base

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# --- Swap this line for MS SQL Server later, e.g.: ---
# DATABASE_URL = "mssql+pyodbc://user:pass@server/db?driver=ODBC+Driver+17+for+SQL+Server"
DATABASE_URL = os.environ.get(
    "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'pakwheels.db')}"
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, echo=False)
SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))


def init_db():
    """Create all tables if they don't already exist. Safe to call every run."""
    Base.metadata.create_all(bind=engine)


def get_session():
    """Return a new scoped session. Caller is responsible for closing it."""
    return SessionLocal()
