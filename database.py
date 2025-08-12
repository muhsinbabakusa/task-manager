# database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine.url import make_url
from dotenv import load_dotenv

load_dotenv()

# Use SQLite by default so the app boots if no env var is set
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data.db")

# Log (no password) so we can SEE what URL is used on Render
try:
    url = make_url(DATABASE_URL)
    print(f"[DB] Using driver={url.get_backend_name()} host={url.host} port={url.port} db={url.database}")
except Exception as e:
    print(f"[DB] Could not parse DATABASE_URL: {e}")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=280)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()