import os
import secrets
import base64
import cv2
import numpy as np
import face_recognition
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import smtplib
from email.mime.text import MIMEText
import random
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///smartupi.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
db = SQLAlchemy(app)

# --- Database Models ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    bank_card_last4 = db.Column(db.String(4), nullable=False)
    pin_hash = db.Column(db.String(128), nullable=False)
    face_encoding = db.Column(db.PickleType, nullable=True) # Binary storage of 128-d vector
    balance = db.Column(db.Float, default=0.0)
    is_activated = db.Column(db.Boolean, default=False)
    upi_id = db.Column(db.String(50), unique=True, nullable=False)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_upi = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='SUCCESS')

class OTPRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), nullable=False)
    otp = db.Column(db.String(6), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, default=0)

# --- Helper Functions ---

def get_face_encoding(image_data):
    """Processes base64 image data and returns face encoding."""
    try:
        header, encoded = image_data.split(",", 1)
        data = base64.b64decode(encoded)
        nparr = np.frombuffer(data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        encodings = face_recognition.face_encodings(rgb_img)
        if len(encodings) == 0:
            return None, "No face detected"
        if len(encodings) > 1:
            return None, "Multiple faces detected"
        
        return encodings[0], None
    except Exception as e:
        return None, str(e)

def send_otp_email(to_email, otp):
    # Dummy implementation for SMTP - replaces with actual credentials via env
    # For demo, prints to console and simulates sending
    sender_email = os.environ.get('SMTP_EMAIL', 'no-reply@smartupi.com')
    sender_pw = os.environ.get('SMTP_PASSWORD', '')
    
    msg = MIMEText(f"Your SmartUPI password reset OTP is: {otp}\n\nIt expires in 5 minutes.")
    msg['Subject'] = 'SmartUPI Password Reset OTP'
    msg['From'] = sender_email
    msg['To'] = to_email

    print(f"[MAIL_SERVER_SIMULATION] Sending to {to_email}: OTP is {otp}")
    
    if sender_pw:
        try:
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
                server.login(sender_email, sender_pw)
                server.send_message(msg)
            return True, "Email sent successfully"
        except Exception as e:
            return False, f"Failed to send email: {e}"
    return True, "Email sent (simulated)"

# --- Routes ---

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.form
        face_img = data.get('face_image')
        pin = data.get('pin')
        
        if not face_img:
            return jsonify({"status": "error", "message": "No face image provided"})
        if not pin:
            return jsonify({"status": "error", "message": "No PIN provided"})
        
        # Check if user already exists
        if User.query.filter_by(mobile=data['mobile']).first():
            return jsonify({"status": "error", "message": "Mobile already registered"})
        if User.query.filter_by(email=data['email']).first():
            return jsonify({"status": "error", "message": "Email already registered"})
        
        encoding, error = get_face_encoding(face_img)
        if error:
            return jsonify({"status": "error", "message": error})

        # Prevent duplicate face registration
        all_users = User.query.filter(User.face_encoding.isnot(None)).all()
        for existing_user in all_users:
            matches = face_recognition.compare_faces([existing_user.face_encoding], encoding, tolerance=0.5)
            if matches[0]:
                return jsonify({"status": "error", "message": "This face is already registered with another account."})

        # Generate PIN hash
        hashed_pin = generate_password_hash(data['pin'])
        
        new_user = User(
            full_name=data['full_name'],
            mobile=data['mobile'],
            email=data['email'],
            bank_card_last4=data['card_last4'],
            pin_hash=hashed_pin,
            face_encoding=encoding,
            upi_id=f"{data['mobile']}@smartupi",
            balance=50000.0,
            is_activated=True
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        session['user_id'] = new_user.id
        return jsonify({"status": "success", "message": "Registration successful! Redirecting to dashboard..."})
    
    return render_template('register.html')



@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    transactions = Transaction.query.filter(
        (Transaction.sender_id == user.id) | (Transaction.recipient_upi == user.upi_id)
    ).order_by(Transaction.timestamp.desc()).all()
    return render_template('dashboard.html', user=user, transactions=transactions)

@app.route('/transfer', methods=['POST'])
def transfer():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Not logged in"})
    
    data = request.form
    user = User.query.get(session['user_id'])
    amount = float(data['amount'])
    recipient_upi = data['recipient_upi']
    face_img = data.get('face_image')
    pin = data.get('pin')
    
    if user.upi_id == recipient_upi:
        return jsonify({"status": "error", "message": "Cannot send money to yourself"})

    if amount <= 0:
        return jsonify({"status": "error", "message": "Amount must be greater than zero"})

    if user.balance < amount:
        return jsonify({"status": "error", "message": "Insufficient balance"})
        
    recipient_user = User.query.filter_by(upi_id=recipient_upi).first()
    
    # We allow external simulated transfers (recipient not in DB). We just won't update their balance locally.
    
    # Facial Verification
    if not face_img:
        return jsonify({"status": "error", "message": "No face image provided"})
        
    current_encoding, error = get_face_encoding(face_img)
    if error:
        return jsonify({"status": "error", "message": error})
    
    matches = face_recognition.compare_faces([user.face_encoding], current_encoding, tolerance=0.5)
    
    if not matches[0]:
        return jsonify({"status": "error", "message": "Face Not Matched"})
    
    # PIN Verification after face match
    if not pin or not check_password_hash(user.pin_hash, pin):
        return jsonify({"status": "error", "message": "Invalid Transaction PIN"})
    
    # Process Transaction
    user.balance -= amount
    if recipient_user:
        recipient_user.balance += amount
    
    new_tx = Transaction(sender_id=user.id, recipient_upi=recipient_upi, amount=amount)
    db.session.add(new_tx)
    db.session.commit()
    
    return jsonify({"status": "success", "message": "Transaction Successful!"})


@app.route('/verify_face_only', methods=['POST'])
def verify_face_only():
    if 'user_id' not in session:
        return jsonify({"status": "error", "message": "Not logged in"})
    
    face_img = request.form.get('face_image')
    if not face_img:
        return jsonify({"status": "error", "message": "No face image provided"})
        
    user = User.query.get(session['user_id'])
    current_encoding, error = get_face_encoding(face_img)
    
    if error:
        return jsonify({"status": "error", "message": error})
    
    matches = face_recognition.compare_faces([user.face_encoding], current_encoding, tolerance=0.5)
    
    if matches[0]:
        return jsonify({"status": "success", "message": "Face Verified Successfully"})
    else:
        return jsonify({"status": "error", "message": "Face Not Matched"})


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        mobile = request.form.get('mobile')
        pin = request.form.get('pin')
        user = User.query.filter_by(mobile=mobile).first()
        if user and check_password_hash(user.pin_hash, pin):
            if not user.is_activated:
                user.is_activated = True
                user.balance = 50000.0
                db.session.commit()
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

@app.route('/api/admin/reset_db', methods=['POST'])
def api_admin_reset_db():
    pw = request.form.get('password')
    confirm = request.form.get('confirm')
    
    admin_secret = os.environ.get('ADMIN_PASSWORD', 'admin123')
    
    if pw != admin_secret:
        return jsonify({"status": "error", "message": "Unauthorized: Invalid core admin credentials"})
        
    if confirm != "DELETE":
        return jsonify({"status": "error", "message": "Missing exactly typed confirmation word: DELETE"})
        
    try:
        # Correctly ordered cascading deletion (child tables -> parent tables)
        db.session.query(Transaction).delete()
        db.session.query(OTPRequest).delete()
        db.session.query(User).delete()
        db.session.commit()
        return jsonify({"status": "success", "message": "All data cleared successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": f"Server DB Clear Failed: {str(e)}"})

@app.route('/forgot_password')
def forgot_password():
    return render_template('forgot_password.html')

@app.route('/api/send_otp', methods=['POST'])
def api_send_otp():
    email = request.form.get('email')
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return jsonify({"status": "error", "message": "Email not registered"})
        
    otp = f"{random.randint(100000, 999999)}"
    expires_at = datetime.utcnow() + timedelta(minutes=5)
    
    # Store OTP request
    otp_req = OTPRequest.query.filter_by(email=email).first()
    if otp_req:
        otp_req.otp = otp
        otp_req.expires_at = expires_at
        otp_req.attempts = 0
    else:
        otp_req = OTPRequest(email=email, otp=otp, expires_at=expires_at)
        db.session.add(otp_req)
        
    db.session.commit()
    
    success, msg = send_otp_email(email, otp)
    if not success:
        return jsonify({"status": "error", "message": msg})
        
    return jsonify({"status": "success", "message": "OTP sent to your email"})

@app.route('/api/verify_otp', methods=['POST'])
def api_verify_otp():
    email = request.form.get('email')
    entered_otp = request.form.get('otp')
    
    otp_req = OTPRequest.query.filter_by(email=email).first()
    if not otp_req:
        return jsonify({"status": "error", "message": "No OTP request found for this email"})
        
    if datetime.utcnow() > otp_req.expires_at:
        return jsonify({"status": "error", "message": "OTP expired, resend again"})
        
    if otp_req.attempts >= 3:
        return jsonify({"status": "error", "message": "Max matching attempts reached. Please request a new OTP."})
        
    if otp_req.otp != entered_otp:
        otp_req.attempts += 1
        db.session.commit()
        return jsonify({"status": "error", "message": "Invalid OTP"})
        
    return jsonify({"status": "success", "message": "OTP verified successfully"})

@app.route('/api/reset_pin', methods=['POST'])
def api_reset_pin():
    email = request.form.get('email')
    entered_otp = request.form.get('otp')
    new_pin = request.form.get('pin')
    
    if not new_pin or len(new_pin) != 6 or not new_pin.isdigit():
        return jsonify({"status": "error", "message": "PIN must be exactly 6 digits"})
        
    otp_req = OTPRequest.query.filter_by(email=email).first()
    if not otp_req or otp_req.otp != entered_otp or datetime.utcnow() > otp_req.expires_at:
        return jsonify({"status": "error", "message": "Verification session invalid or expired"})
        
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"status": "error", "message": "User not found"})
        
    user.pin_hash = generate_password_hash(new_pin)
    db.session.delete(otp_req)
    db.session.commit()
    
    return jsonify({"status": "success", "message": "PIN updated successfully"})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
