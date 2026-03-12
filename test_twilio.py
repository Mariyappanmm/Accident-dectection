import os
import sys

# Windows Path Limit Workaround: load local vendor folder first
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'vendor')))

from twilio.rest import Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
twilio_from = os.environ.get('TWILIO_FROM_NUMBER')
target_number = '+917812853956'  # Assuming India (+91) based on the structure, adjust if needed!

print(f"Attempting to send a test SMS to {target_number}...")

try:
    client = Client(account_sid, auth_token)
    message = client.messages.create(
        body="Hello! This is a test message from your Smart Helmet Accident Detection backend.",
        from_=twilio_from,
        to=target_number
    )
    print(f"\nSUCCESS! SMS sent successfully.\nMessage SID: {message.sid}")
except Exception as e:
    print(f"\nFAILED to send SMS.\nError details: {e}")
