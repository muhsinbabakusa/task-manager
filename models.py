from sqlalchemy import Column, Integer, String,DateTime, ForeignKey, Enum, Boolean
from database import Base
import enum



class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key= True, index=True)
    full_name = Column(String(100))
    email = Column(String(100), unique = True, index = True)
    password = Column(String(100))
    reset_token = Column(String(100), nullable=True)

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255))
    description = Column(String(255))
    status = Column(String(20), default="pending")  # 👈 replaces completed
    priority = Column(String(20), default="medium")
    deadline = Column(DateTime, nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"))
