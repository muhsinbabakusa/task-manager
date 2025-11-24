from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks,File, UploadFile, Form
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
import schemas
import shutil
from fastapi.responses import HTMLResponse
import requests

load_dotenv()

# Security config
SECRET_KEY = os.getenv("SECRET_KEY", "change-this")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

#RESEND
RESEND_API_KEY= os.getenv("RESEND_API_KEY", "")
FROM_EMAIL=os.getenv("FROM_EMAIL", "") 

# Email (from .env)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")


PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://task-manager-8d1z.onrender.com")
FRONTEND_LOGIN_URL = os.getenv("FRONTEND_LOGIN_URL", "https://task-frontend-q4nk.onrender.com")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


# Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
# Initialize app
app = FastAPI()

app.mount("/static", StaticFiles(directory="static", html=True), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://task-frontend-q4nk.onrender.com",
    ],  # 👈 You can restrict this to ["http://127.0.0.1:5500"] later
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
from smtplib import SMTP_SSL
from email.mime.text import MIMEText


def send_verification_email(to_email: str, token: str):
    verification_link = f"{PUBLIC_BASE_URL}/verify-email?token={token}"
    subject = "🎉 Welcome to Tick App – Verify Your Email"

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f7f9fc; padding: 40px;">
        <div style="max-width: 600px; margin: auto; background: white; border-radius: 12px; 
                    box-shadow: 0 4px 8px rgba(0,0,0,0.05); padding: 30px; text-align: center;">
          <h2 style="color: #333;">Welcome to <span style="color:#4CAF50;">Tick</span></h2>
          <p style="font-size: 16px; color: #555;">
            Thank you for signing up, we’re excited to have you on board!
            <br><br>
            Please verify your email address by clicking the button below:
          </p>
          
          <a href="{verification_link}" 
             style="display:inline-block;margin-top:20px;padding:14px 28px;background-color:#4CAF50;
                    color:white;text-decoration:none;font-weight:bold;border-radius:6px;">
            Verify Email
          </a>
          
          <p style="margin-top: 30px; color:#777; font-size:14px;">
            If you didn’t create this account, you can safely ignore this email.
          </p>
          <hr style="margin: 30px 0; border: none; border-top: 1px solid #eee;">
          <p style="color:#aaa; font-size:12px;">
            &copy; 2025 Task Manager Inc. All rights reserved.
          </p>
        </div>
      </body>
    </html>
    """

    if not RESEND_API_KEY or not FROM_EMAIL:
        print("❌ RESEND_API_KEY or FROM_EMAIL is not set")
        return

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            },
            timeout=15,
        )
        print(" Resend verification status:", resp.status_code, resp.text)
    except Exception as e:
        print(" EMAIL SEND ERROR (verification):", repr(e))


def password_reset_email(to_email: str, token: str):
    reset_link = f"{PUBLIC_BASE_URL}/reset-password?token={token}"
    subject = "Reset your Tick App password"

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f7f9fc; padding: 40px;">
        <div style="max-width: 600px; margin: auto; background: white; border-radius: 12px; 
                    box-shadow: 0 4px 8px rgba(0,0,0,0.05); padding: 30px; text-align: center;">
          <h2 style="color: #333;">Password reset</h2>
          <p style="font-size: 16px; color: #555;">
            You requested to reset your Tick account password.
            <br><br>
            Click the button below to set a new password:
          </p>
          
          <a href="{reset_link}" 
             style="display:inline-block;margin-top:20px;padding:14px 28px;background-color:#4CAF50;
                    color:white;text-decoration:none;font-weight:bold;border-radius:6px;">
            Reset Password
          </a>
          
          <p style="margin-top: 30px; color:#777; font-size:14px;">
            If you didn’t request this, you can safely ignore this email.
          </p>
        </div>
      </body>
    </html>
    """

    if not RESEND_API_KEY or not FROM_EMAIL:
        print(" RESEND_API_KEY or FROM_EMAIL is not set")
        return

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            },
            timeout=15,
        )
        print("📧 Resend reset status:", resp.status_code, resp.text)
    except Exception as e:
        print("❌ EMAIL SEND ERROR (reset):", repr(e))


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

# Wannan ze kira task dina
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
    
@app.post("/reset_password")
def reset_password(reset: ResetPasswordRequest,db:Session  = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == reset.token)
    return

@app.get("/profile")
def get_profile(db:Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return current_user

@app.put("/profile/update")
async def update_profile(
    full_name: str = Form(...),
    bio: str = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # Update fields
    user.full_name = full_name or user.full_name
    user.bio = bio or user.bio

    # Handle file upload if provided
    if file:
        # Ensure static dir exists
        os.makedirs("static/profiles", exist_ok=True)

        file_path = f"static/profiles/{user.id}_{file.filename}"
        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Save relative path in DB
        user.profile_picture = "/" + file_path  

    # Save changes
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "bio": user.bio,
        "profile_picture": user.profile_picture
    }
@app.post("/profile/profile_pic")
def profile_pic(file: UploadFile = File(...),db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    upload_dir = "static/profile_pics"
    os.makedirs(upload_dir, exist_ok=True) 

    # Create a unique filename
    file_ext = file.filename.split(".")[-1]
    filename = f"user_{current_user.id}.{file_ext}"
    file_path = os.path.join(upload_dir, filename)

    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

 # Update DB with relative path
    current_user.profile_picture = f"/static/profile_pics/{filename}"
    db.commit()
    db.refresh(current_user)

    return current_user


# def upload_profile_picture(
#     file: UploadFile = File(...),
#     db: Session = Depends(get_db),
#     current_user: User = Depends(get_current_user)
# ):
#     upload_dir = "static/profile_pics"
#     os.makedirs(upload_dir, exist_ok=True)

#     # create unique filename (overwrite old if same user)
#     file_ext = file.filename.split(".")[-1]
#     filename = f"user_{current_user.id}.{file_ext}"
#     file_path = os.path.join(upload_dir, filename)

#     # save file
#     with open(file_path, "wb") as buffer:
#         shutil.copyfileobj(file.file, buffer)

#     # update DB with path
#     current_user.profile_picture = f"/static/profile_pics/{filename}"
#     db.commit()
#     db.refresh(current_user)

#     return current_user

@app.put("/profile/change_password")
def change_password(
    old_pwd: str = Form(...),
    new_pwd: str = Form(...),
    db: Session = Depends(get_db),
    user: User= Depends(get_current_user)
):
    if not verify_password(old_pwd, user.password):
        raise HTTPException(status_code=400, detail= "Old password is not correct")

    user.password = get_password_hash(new_pwd)
    db.commit()
    db.refresh(user)    

    return {"message": "Password has successfully been changed"}

@app.get("/verify-email", response_class=HTMLResponse)
def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.reset_token == token).first()
    if not user:
        return HTMLResponse("""
            <h2 style="font-family:Arial">Invalid or expired link</h2>
            <p>The verification link is invalid or has already been used.</p>
        """, status_code=400)

    # OPTIONAL: requires you to add is_verified column in models.py
    # If you haven’t added it yet, skip this line and just clear the token.
    if hasattr(user, "is_verified"):
        user.is_verified = True

    user.reset_token = None  # consume the token so it can’t be reused
    db.commit()

    return HTMLResponse(f"""
    <div style="font-family:Arial;max-width:600px;margin:40px auto;padding:24px;border:1px solid #eee;border-radius:10px;">
      <h2>✅ Email Verified</h2>
      <p>{user.email} has been verified successfully.</p>
      <a href="{FRONTEND_LOGIN_URL}" 
         style="display:inline-block;margin-top:14px;padding:10px 16px;background:#4CAF50;color:#fff;text-decoration:none;border-radius:6px;">
         Go to Login
      </a>
    </div>
""")