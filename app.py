import base64
import hashlib
import hmac
import json
import os
import smtplib
import urllib.request
from email.message import EmailMessage
from flask import Flask, jsonify, request, send_file

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_APP_PASS = os.getenv("SMTP_APP_PASS", "")
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "")

@app.get("/")
def home():
    for candidate in (
        os.path.join(BASE_DIR, "index.html"),
        os.path.join(BASE_DIR, "templates", "index.html"),
    ):
        if os.path.exists(candidate):
            return send_file(candidate, mimetype="text/html")
    return "index.html not found in deployment folder", 404


@app.get("/health")
def health():
    return jsonify({"status": "ok", "app": "BM FUTUROMIND AI Academy"})


@app.post("/api/send-otp")
def send_otp():
    data = request.get_json(silent=True) or {}
    to_email = str(data.get("email", "")).strip()
    otp = str(data.get("otp", "")).strip()
    if not to_email or not otp:
        return jsonify({"sent": False, "error": "Email and OTP required"}), 400
    if not SMTP_USER or not SMTP_APP_PASS:
        return jsonify({"sent": False, "error": "Set SMTP_USER and SMTP_APP_PASS"}), 200
    try:
        msg = EmailMessage()
        msg["Subject"] = "BM FUTUROMIND AI — Your Verification OTP"
        msg["From"] = SMTP_USER
        msg["To"] = to_email
        msg.set_content(
            f"Hello,\n\nYour 6-digit verification OTP for BM FUTUROMIND AI Academy is: {otp}\n\n"
            f"Regards,\nBM FUTUROMIND AI (9150851916)"
        )
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.login(SMTP_USER, SMTP_APP_PASS)
            server.send_message(msg)
        return jsonify({"sent": True})
    except Exception as exc:
        return jsonify({"sent": False, "error": str(exc)}), 200


@app.post("/api/razorpay/create-order")
def create_razorpay_order():
    if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
        return jsonify({"error": "Razorpay keys not configured"}), 200
    try:
        data = request.get_json(silent=True) or {}
        payload = json.dumps({
            "amount": 100000,
            "currency": "INR",
            "receipt": f"bm_{str(data.get('email', 'student'))[:24]}",
        }).encode("utf-8")
        auth = base64.b64encode(f"{RAZORPAY_KEY_ID}:{RAZORPAY_KEY_SECRET}".encode("utf-8")).decode("utf-8")
        req = urllib.request.Request(
            "https://api.razorpay.com/v1/orders",
            data=payload,
            headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            order = json.loads(resp.read().decode("utf-8"))
        return jsonify({"order_id": order.get("id"), "amount": 100000, "key_id": RAZORPAY_KEY_ID})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 200


@app.post("/api/razorpay/verify")
def verify_razorpay_payment():
    if not RAZORPAY_KEY_SECRET:
        return jsonify({"verified": False, "error": "Razorpay secret not set"}), 200
    try:
        data = request.get_json(silent=True) or {}
        order_id = str(data.get("razorpay_order_id", ""))
        payment_id = str(data.get("razorpay_payment_id", ""))
        signature = str(data.get("razorpay_signature", ""))
        expected = hmac.new(
            RAZORPAY_KEY_SECRET.encode("utf-8"),
            f"{order_id}|{payment_id}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return jsonify({"verified": hmac.compare_digest(expected, signature)})
    except Exception as exc:
        return jsonify({"verified": False, "error": str(exc)}), 200


def send_email(to_email, subject, body):
    if not SMTP_USER or not SMTP_APP_PASS:
        return False
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg.set_content(body)
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as server:
        server.login(SMTP_USER, SMTP_APP_PASS)
        server.send_message(msg)
    return True


@app.post("/api/register-notification")
def register_notification():
    data = request.get_json(silent=True) or {}
    student_email = str(data.get("email", "")).strip()
    name = str(data.get("name", "Student")).strip()
    mobile = str(data.get("mobile", "")).strip()
    course = str(data.get("course", "")).strip()
    registered_at = str(data.get("registeredAt", "")).strip()

    if not student_email:
        return jsonify({"sent": False, "error": "Student email required"}), 400

    try:
        student_sent = send_email(
            student_email,
            "Welcome to BM FUTUROMIND AI Academy",
            f"Hello {name},\n\nWelcome to BM FUTUROMIND AI Academy!\n\n"
            f"Your registration details:\nName: {name}\nEmail: {student_email}\n"
            f"Mobile: {mobile}\nSelected Course: {course}\nRegistered At: {registered_at}\n\n"
            "Regards,\nBM FUTUROMIND AI (9150851916)",
        )
        admin_sent = send_email(
            "info@bmfuturomindai.com",
            "New Student Registration - BM FUTUROMIND AI",
            f"New student registered:\n\nName: {name}\nEmail: {student_email}\n"
            f"Mobile: {mobile}\nSelected Course: {course}\nRegistered At: {registered_at}",
        )
        return jsonify({"sent": student_sent and admin_sent, "studentSent": student_sent, "adminSent": admin_sent})
    except Exception as exc:
        return jsonify({"sent": False, "error": str(exc)}), 200


@app.post("/api/payment-notification")
def payment_notification():
    data = request.get_json(silent=True) or {}
    student_email = str(data.get("email", "")).strip()
    name = str(data.get("name", "Student")).strip()
    mobile = str(data.get("mobile", "")).strip()
    course = str(data.get("course", "")).strip()
    amount = str(data.get("amount", "₹1,000 INR (Lifetime)")).strip()
    payment_id = str(data.get("paymentId", "")).strip()
    date = str(data.get("date", "")).strip()

    if not student_email:
        return jsonify({"sent": False, "error": "Student email required"}), 400

    try:
        student_sent = send_email(
            student_email,
            "Payment Received - BM FUTUROMIND AI Academy",
            f"Hello {name},\n\nYour payment has been received.\n\n"
            f"Amount: {amount}\nCourse: {course}\nPayment ID: {payment_id}\nDate: {date}\n\n"
            "Welcome to your lifetime course access!\n\nRegards,\nBM FUTUROMIND AI (9150851916)",
        )
        admin_sent = send_email(
            "info@bmfuturomindai.com",
            "Payment Received - Student Payment Details",
            f"Payment details:\n\nName: {name}\nEmail: {student_email}\nMobile: {mobile}\n"
            f"Course: {course}\nAmount: {amount}\nPayment ID: {payment_id}\nDate: {date}",
        )
        return jsonify({"sent": student_sent and admin_sent, "studentSent": student_sent, "adminSent": admin_sent})
    except Exception as exc:
        return jsonify({"sent": False, "error": str(exc)}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)
