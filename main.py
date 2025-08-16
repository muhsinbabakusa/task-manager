from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User, Task
from typing import Optional
from pydantic import BaseModel
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt, JWTError
from fastapi.security import OAuth2PasswordBearer
from fastapi.security import OAuth2PasswordRequestForm
from database import Base, engine
from smtplib import SMTP_SSL
from email.mime.text import MIMEText
import random
import uuid
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()

# Security config
SECRET_KEY = os.getenv("SECRET_KEY", "change-this")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# Email (from .env)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = SMTP_USER

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
# Initialize app
app = FastAPI()

app.mount("/static", StaticFiles(directory="static", html=True), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 👈 You can restrict this to ["http://127.0.0.1:5500"] later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def send_verification_email(to_email: str, token: str):
    verification_link = f"http://localhost:8000/verify-email?token={token}"
    subject = "Welcome new user, Verify Your Email"
    body = f"Click this link to verify your email:\n\n{verification_link}\n\nIf you didn’t register, ignore this email."

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email

    with SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.sendmail(FROM_EMAIL, [to_email], msg.as_string())

def password_reset_email(to_email: str, token: str):
    reset_link = f"http://localhost:8000/verify-email?token={token}"
    subject = "Password reset"
    body = f"Click this link to reset your email:\n\n{reset_link}"

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email

    with SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USER, SMTP_PASS)
        smtp.sendmail(FROM_EMAIL, [to_email], msg.as_string())

# Token creation
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# Get current user
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == username).first()
    if user is None:
        raise credentials_exception
    return user

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

# Schemas
class UserCreate(BaseModel):
    full_name: str
    email: str
    password: str

class TaskCreate(BaseModel):
    title: str
    description: str
    priority: Optional[str] = "medium"
    status: Optional[str] = "pending"  # ✅ New
    deadline: Optional[datetime] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None  # ✅ New
    deadline: Optional[datetime] = None

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

@app.get("/_debug/db")
def debug_db(db: Session = Depends(get_db)):
    from database import engine
    url = str(engine.url)
    with engine.connect() as conn:
        row = conn.execute(text("SELECT DATABASE()")).scalar()
    return {"url": url, "database": row}
# Register
@app.post("/register")
def register(user: UserCreate, background_tasks:BackgroundTasks, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    token = str(uuid.uuid4())
    hashed_password = get_password_hash(user.password)

    new_user = User(
        full_name=user.full_name,
        email=user.email,
        password=hashed_password,
        reset_token=token
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    background_tasks.add_task(send_verification_email, user.email, token)

    return {"message": "User created successfully"}

# Login
@app.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(data={"sub": user.email})

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }
# Create task
@app.post("/create_task")
def create_task(task: TaskCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    new_task = Task(
        title=task.title,
        description=task.description,
        priority=task.priority,
        deadline=task.deadline,
        user_id=user.id
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    
    
    return {"message": "Task created", "task": {
        "id": new_task.id,
        "title": new_task.title
    }}

# Get tasks
@app.get("/get_task")
def get_task(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tasks = db.query(Task).filter(Task.user_id == user.id).all()
    return {"tasks": tasks}

# Update task
@app.put("/update_task/{task_id}")
def update_task(
    task_id: int,
    task: TaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    existing_task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()

    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found or unauthorized")

    existing_task.title = task.title
    existing_task.description = task.description
    existing_task.priority = task.priority
    existing_task.deadline = task.deadline

    db.commit()
    db.refresh(existing_task)

    return {"message": "Task updated", "task": {
        "id": existing_task.id,
        "title": existing_task.title
    }}


@app.delete("/delete_task")
def delete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or not authorized")

    db.delete(task)  # Now this is a proper instance
    db.commit()

    return {"message": "Task deleted successfully"}

@app.patch("/mark_done")
def mark_task_done(task_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.status = "Done"
    task.completed = 1
    db.commit()
    return {"message": "Task marked as completed"}

@app.post("/forget-password")
def forget_password(request: ForgotPasswordRequest,background_tasks:BackgroundTasks, db: Session =  Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()

    if not user:
        raise HTTPException(status_code=401, detail="user not found")
    
       
    token = str(uuid.uuid4())
    user.reset_token = token
    db.commit()

    background_tasks.add_task(password_reset_email, user.email, token)

    return{
        "msg":"Password reset link sent, otp",
        "otp": user.reset_token
    } 
    
@app.post("/rest_password")
def reset_password(reset: ResetPasswordRequest,db:Session  = Depends(get_db)):
    return