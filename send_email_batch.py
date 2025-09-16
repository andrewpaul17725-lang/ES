import smtplib
import os
import sys
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re # Email validation ke liye

# --- Configuration ---
# Ab hum HTML body file istemal karenge
SUBJECTS_FILE = 'subjects.txt'
BODY_FILE = 'email_body.html' # <-- File ka naam update kar diya gaya hai
RECIPIENTS_FILE = 'recipients.txt'
STATE_FILE = 'state.txt'
FAILED_EMAILS_FILE = 'failed_emails.txt'
BATCH_SIZE = 5

# Email format ko check karne ke liye function
def is_valid_email(email):
    """Email ke format ko validate karta hai."""
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email) is not None

def send_email_batch():
    # --- Step 1: GitHub Secrets se credentials hasil karna ---
    smtp_server = "mail.inbox.lv"
    smtp_port = 587
    sender_email = os.getenv('SMTP_USERNAME')
    password = os.getenv('SMTP_PASSWORD')

    if not sender_email or not password:
        print("::error::SMTP credentials not found in GitHub Secrets.")
        sys.exit(1)

    # --- Step 2: Zaroori files parhna ---
    try:
        with open(BODY_FILE, 'r', encoding='utf-8') as f:
            body = f.read()
        with open(SUBJECTS_FILE, 'r', encoding='utf-8') as f:
            subjects = [line.strip() for line in f.readlines() if line.strip()]
        with open(RECIPIENTS_FILE, 'r', encoding='utf-8') as f:
            all_recipients = [line.strip() for line in f.readlines() if line.strip()]
        with open(STATE_FILE, 'r') as f:
            last_index = int(f.read().strip())
    except FileNotFoundError as e:
        # Agar state file nahi milti to 0 se shuru karna
        if e.filename == STATE_FILE:
            print(f"::warning::State file not found. Starting from 0.")
            last_index = 0
        else:
            print(f"::error::Required file not found: {e.filename}")
            sys.exit(1)
    except (ValueError, IndexError):
        print("::warning::State file is corrupt or empty. Resetting to 0.")
        last_index = 0

    # --- Step 3: Agle batch ke liye recipients select karna ---
    if not all_recipients:
        print("::warning::Recipients file is empty. No emails to send.")
        sys.exit(0)
        
    recipients_to_send = []
    for i in range(BATCH_SIZE):
        if not all_recipients: break
        recipient_index = (last_index + i) % len(all_recipients)
        recipients_to_send.append(all_recipients[recipient_index])

    print(f"This run will attempt to send emails to {len(recipients_to_send)} recipients.")

    # --- Step 4: SMTP server se connect karna ---
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, password)
        print("Successfully connected to SMTP server.")
    except Exception as e:
        print(f"::error::Failed to connect to SMTP server: {e}")
        sys.exit(1)

    # --- Step 5: Batch mein emails bhejna aur failed emails ko track karna ---
    emails_sent_count = 0
    failed_recipients = []

    for i, recipient_email in enumerate(recipients_to_send):
        if not is_valid_email(recipient_email):
            print(f"::warning::Invalid email format for '{recipient_email}'. Skipping.")
            failed_recipients.append(recipient_email)
            continue

        # Har email ke liye naya subject select karna
        subject_index = (last_index + i) % len(subjects) if subjects else 0
        subject = subjects[subject_index] if subjects else "A message for you"

        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = recipient_email
        message["Subject"] = subject
        
        # Email body ko "html" ke tor par attach karna
        message.attach(MIMEText(body, "html", "utf-8")) # <-- Yahan "html" set hai

        try:
            print(f"Sending email {i+1}/{len(recipients_to_send)} to {recipient_email}...")
            server.sendmail(sender_email, recipient_email, message.as_string())
            emails_sent_count += 1
            time.sleep(2)
        except Exception as e:
            print(f"::warning::Failed to send email to {recipient_email}: {e}")
            failed_recipients.append(recipient_email)
    
    server.quit()
    print(f"Finished sending batch. Total emails sent successfully: {emails_sent_count}/{len(recipients_to_send)}")

    # --- Step 6: Failed emails ko file mein likhna ---
    if failed_recipients:
        with open(FAILED_EMAILS_FILE, 'a', encoding='utf-8') as f:
            for email in failed_recipients:
                f.write(email + '\n')
        print(f"Saved {len(failed_recipients)} failed or invalid recipients to {FAILED_EMAILS_FILE}.")

    # --- Step 7: State file ko update karna ---
    next_index = last_index + BATCH_SIZE
    with open(STATE_FILE, 'w') as f:
        f.write(str(next_index))
    print(f"State file updated to index {next_index}.")

if __name__ == "__main__":
    send_email_batch()
