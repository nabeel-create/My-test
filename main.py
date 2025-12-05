# ===========================================================
# 📧 AI Gmail Sender – FastAPI Backend
# Converted from Streamlit (NO logic changed)
# ===========================================================

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import smtplib, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from openai import OpenAI
import tempfile
import shutil

app = FastAPI()

# ---------------- CORS (Allow frontend to call API) ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- Login Model ----------------
class LoginRequest(BaseModel):
    email: str
    app_password: str

# ---------------- AI Generate Request ----------------
class AIRquest(BaseModel):
    description: str

# ---------------- Email Sending Model ----------------
class EmailSendRequest(BaseModel):
    sender_email: str
    sender_password: str
    subject: str
    body: str
    contacts: list  # list of dicts: [{"name": "...", "email": "..."}]
    attachments: list  # uploaded filenames

# -------------------------------------------------------
# LOGIN CHECK ENDPOINT
# -------------------------------------------------------
@app.post("/login")
def login(data: LoginRequest):
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(data.email, data.app_password)
        server.quit()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# -------------------------------------------------------
# AI GENERATION ENDPOINT
# -------------------------------------------------------
@app.post("/generate")
def generate_email(data: AIRquest):
    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY")
        )
        completion = client.chat.completions.create(
            model="meta-llama/llama-3.3-70b-instruct:free",
            messages=[
                {"role": "system", "content": "You are a professional email writer."},
                {"role": "user", "content": data.description}
            ],
            temperature=0.7,
            max_tokens=400
        )
        return {"result": completion.choices[0].message.content}

    except Exception as e:
        return {"error": str(e)}

# -------------------------------------------------------
# CSV UPLOAD ENDPOINT
# -------------------------------------------------------
@app.post("/upload_csv")
def upload_csv(file: UploadFile = File(...)):
    df = pd.read_csv(file.file)
    contacts = df.to_dict(orient="records")
    return {"contacts": contacts}

# -------------------------------------------------------
# UPLOAD ATTACHMENT ENDPOINT
# -------------------------------------------------------
@app.post("/upload_attachment")
def upload_attachment(file: UploadFile = File(...)):
    save_path = os.path.join("attachments", file.filename)
    os.makedirs("attachments", exist_ok=True)
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"filename": file.filename}

# -------------------------------------------------------
# SEND EMAILS ENDPOINT
# -------------------------------------------------------
@app.post("/send")
def send_email(data: EmailSendRequest):

    def create_message(sender, to, subject, text, attachments):
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(text, "plain"))

        for filename in attachments:
            filepath = os.path.join("attachments", filename)
            part = MIMEBase("application", "octet-stream")
            with open(filepath, "rb") as f:
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={filename}")
            msg.attach(part)

        return msg

    def send(to, msg):
        try:
            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(data.sender_email, data.sender_password)
            server.send_message(msg)
            server.quit()
            return "Sent"
        except Exception as e:
            return str(e)

    logs = []
    for contact in data.contacts:
        name = contact.get("name", "")
        email = contact["email"]
        personalized = data.body.replace("{{name}}", name)

        msg = create_message(
            data.sender_email,
            email,
            data.subject,
            personalized,
            data.attachments
        )

        result = send(email, msg)
        logs.append({"email": email, "status": result})

    return {"result": logs}
