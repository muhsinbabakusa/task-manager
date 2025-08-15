# database.py
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()  # read .env locally; on Render/Railway their env panel provides vars

DATABASE_URL = "mysql+mysqlconnector://root:uUDXddXFMxVVEAhZWZQlnWdkbFHMPyat@switchyard.proxy.rlwy.net:27561/railway"
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=280,   # helps with idle connection timeouts
    pool_size=5,
    max_overflow=10,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()

