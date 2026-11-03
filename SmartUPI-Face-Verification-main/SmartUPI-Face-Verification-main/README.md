# SmartUPI: UPI Verification Using Face Recognition

SmartUPI is a Flask-based demonstration application for UPI-style payments protected by face verification and a transaction PIN. It uses SQLite for local storage and captures a face image from the browser during registration and payment verification.

> This project is for learning and demonstration. It is not a production banking or payment system.

## Features

- User registration with mobile number, email, card last four digits, PIN, and face capture.
- Face encoding and duplicate-face detection using `face_recognition`.
- Login with mobile number and hashed PIN.
- Dashboard with balance and transaction history.
- Transfers protected by both face verification and transaction PIN.
- Local recipient balance updates and simulated external UPI transfers.
- Password/PIN recovery using a time-limited OTP.
- Optional SMTP email delivery for OTPs, with console simulation when SMTP is not configured.
- Admin page and database reset endpoint for local demonstration.
- SQLite data export to CSV using `export_db_csv.py`.

## Problems Solved

### 1. Extra identity verification for payments
A PIN alone can be stolen or shared. The transfer flow checks the logged-in user's face before accepting the transaction.

### 2. Duplicate face registration
During registration, the submitted face encoding is compared with existing users so the same face cannot be registered for multiple accounts.

### 3. Unauthorized transfers
A transfer requires an authenticated session, a matching face, and the correct PIN. The app also checks for invalid amounts, insufficient balance, and self-transfers.

### 4. Forgotten PIN recovery
Users can request a six-digit OTP, receive a five-minute verification window, and set a new six-digit PIN.

### 5. Local transaction tracking
Successful transfers update balances and are stored in SQLite with recipient, amount, timestamp, and status information.

### 6. Data inspection for demonstrations
The export script converts users and transactions from SQLite into CSV files for review or reporting.

## Technology Stack

- Python 3.10+ recommended
- Flask
- Flask-SQLAlchemy
- SQLite
- OpenCV
- face_recognition and dlib
- NumPy
- HTML, CSS, and browser camera APIs

## Project Structure

```text
.
|-- app.py                  # Flask application and routes
|-- export_db_csv.py        # Export SQLite tables to CSV
|-- requirements.txt        # Python dependencies
|-- test.py                 # Basic face_recognition import check
|-- instance/               # Local SQLite database (ignored by Git)
|-- templates/              # Flask HTML templates
|-- .env                    # Local secrets (ignored by Git)
`-- README.md
```

## Setup on Windows

Use a virtual environment from the project directory:

```cmd
cd /d "D:\uip app face recognition\UPI-verification-using-face-recognition"
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If the `face_recognition` or `dlib` installation fails on Windows, use a supported Python version and install the package in a compatible environment. Python 3.10 or 3.11 is commonly easier for this dependency than the newest Python releases.

## Configuration

Create a local `.env` file. Never commit it:

```env
ADMIN_PASSWORD=change-this-for-local-use
SMTP_EMAIL=your-email@example.com
SMTP_PASSWORD=your-smtp-app-password
```

SMTP variables are optional. Without `SMTP_PASSWORD`, the application prints the OTP to the terminal instead of sending a real email.

## Run the Application

```cmd
venv\Scripts\activate
python app.py
```

Open <http://127.0.0.1:5000> in a browser. Allow camera access when registering or verifying a face.

## Export Data

With `instance\smartupi.db` present, run:

```cmd
venv\Scripts\python.exe export_db_csv.py
```

This creates `registered_users.csv` and `transactions.csv`. These files are ignored by Git because they may contain personal or financial data.

## Basic Check

```cmd
venv\Scripts\python.exe test.py
```

## Important Limitations

- This is a local simulation, not a connection to a real UPI or bank network.
- The default Flask debug server must not be used for production.
- The current admin reset route needs stronger authentication and authorization before deployment.
- Face verification needs liveness detection, secure camera handling, and protection against spoofing.
- OTPs should be stored hashed, invalidated after successful verification, and rate limited.
- CSRF protection, secure cookie settings, input validation, audit logging, and HTTPS should be added for production.
- Financial amounts should use integer minor units or `Decimal`, not floating-point values.
- Existing local database files may contain biometric and account data; keep them private.

## GitHub Push

The repository is already configured with an `origin` remote. Before pushing, review the files that will be committed:

```cmd
git status
git diff -- app.py templates requirements.txt README.md .gitignore
```

Then commit and push:

```cmd
git add README.md .gitignore app.py templates requirements.txt export_db_csv.py test.py
git status
git commit -m "Document SmartUPI face verification application"
git push origin main
```

If GitHub asks for authentication, use GitHub Desktop, a configured SSH remote, or a GitHub personal access token instead of a password.

## Security Reminder

Before publishing, confirm that `.env`, `instance/smartupi.db`, `venv`, `__pycache__`, uploaded images, and exported CSV files are not tracked. If a secret was ever committed, rotate it immediately and remove it from Git history; adding it to `.gitignore` does not erase an old commit.
