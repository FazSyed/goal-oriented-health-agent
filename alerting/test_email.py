import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SENDER = os.getenv("ALERT_EMAIL_SENDER")
PASSWORD = os.getenv("ALERT_EMAIL_PASSWORD")
RECEIVER = os.getenv("ALERT_EMAIL_RECEIVER")


def validate_config():
    """Check that required environment variables exist."""
    print("Checking .env configuration...")

    if not SENDER:
        print("❌ ALERT_EMAIL_SENDER not found.")
        return False

    if not PASSWORD:
        print("❌ ALERT_EMAIL_PASSWORD not found.")
        return False

    if not RECEIVER:
        print("❌ ALERT_EMAIL_RECEIVER not found.")
        return False

    print("✅ .env loaded successfully")
    print(f"Sender   : {SENDER}")
    print(f"Receiver : {RECEIVER}")
    return True


def send_test_email():
    """Send a simple test email."""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    subject = "MAS Email Test"

    body = f"""
This is a test email from your Multi-Agent System.

Timestamp:
{timestamp}

If you received this email, then:

✓ .env was loaded successfully
✓ Gmail SMTP connection succeeded
✓ Login credentials are correct
✓ Email sending works

You can now safely integrate the alert_mailer.py module into your MAS.

Regards,
MAS Email Test Script
"""

    try:
        print("\nConnecting to Gmail SMTP server...")

        msg = MIMEMultipart()
        msg["From"] = SENDER
        msg["To"] = RECEIVER
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            print("Logging in...")
            server.login(SENDER, PASSWORD)

            print("Sending email...")
            server.sendmail(
                SENDER,
                RECEIVER,
                msg.as_string()
            )

        print("\n🎉 SUCCESS!")
        print("Test email sent successfully.")
        print(f"Check the inbox of: {RECEIVER}")

    except Exception as e:
        print("\n❌ EMAIL FAILED")
        print(type(e).__name__)
        print(e)


if __name__ == "__main__":

    print("=" * 50)
    print("MAS EMAIL TEST")
    print("=" * 50)

    if validate_config():
        send_test_email()