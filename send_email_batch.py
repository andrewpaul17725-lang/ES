import smtplib
import os
import sys
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re

# --- Configuration ---
SUBJECTS_FILE = 'subjects.txt'
BODY_FILE = 'email_body.html'
RECIPIENTS_FILE = 'recipients.txt'
STATE_FILE = 'state.txt'
FAILED_EMAILS_FILE = 'failed_emails.txt'
EMAILS_PER_RUN = 11  # 1 'To' + 10 'BCC'

def is_valid_email(email):
    """Email ke format ko validate karta hai."""
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email) is not None

def send_email_batch():
    # --- Step 1: Credentials hasil karna ---
    smtp_server = "mail.inbox.lv"
    smtp_port = 587
    sender_email = os.getenv('SMTP_USERNAME')
    password = os.getenv('SMTP_PASSWORD')

    if not sender_email or not password:
        print("::error::SMTP credentials not found.")
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
        if e.filename == STATE_FILE:
            print("::warning::State file not found. Starting from 0.")
            last_index = 0
        else:
            print(f"::error::Required file not found: {e.filename}")
            sys.exit(1)
    except (ValueError, IndexError):
        print("::warning::State file is corrupt or empty. Resetting to 0.")
        last_index = 0

    if not all_recipients:
        print("::warning::Recipients file is empty. No emails to send.")
        sys.exit(0)

    # --- NAYA LOGIC: 'To' aur 'BCC' recipients ko select karna ---
    total_recipients = len(all_recipients)
    
    if last_index >= total_recipients:
        print("::info::All recipients have been processed. Resetting to start from the beginning.")
        last_index = 0

    to_recipient_index = last_index % total_recipients
    to_recipient = all_recipients[to_recipient_index]
    
    bcc_recipients = []
    for i in range(1, EMAILS_PER_RUN):
        bcc_index = (last_index + i)
        if bcc_index < total_recipients:
            bcc_recipients.append(all_recipients[bcc_index])

    print(f"Preparing to send email TO: {to_recipient}")
    print(f"Adding {len(bcc_recipients)} recipients in BCC.")

    # --- Step 3: SMTP server se connect karna ---
    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        # --- DEBUGGING LINE ---
        # Yeh server se hone wali tamam बातचीत ko logs mein print karega
        server.set_debuglevel(1)
        # --------------------
        server.starttls()
        server.login(sender_email, password)
        print("Successfully connected to SMTP server.")
    except Exception as e:
        print(f"::error::Failed to connect to SMTP server: {e}")
        sys.exit(1)

    # --- Step 4: Email bhejna ---
    failed_recipients = []
    
    valid_targets = []
    if is_valid_email(to_recipient):
        valid_targets.append(to_recipient)
    else:
        failed_recipients.append(to_recipient)
        print(f"::warning::Invalid 'To' email format: {to_recipient}")

    for email in bcc_recipients:
        if is_valid_email(email):
            valid_targets.append(email)
        else:
            failed_recipients.append(email)
            print(f"::warning::Invalid 'BCC' email format: {email}")

    if valid_targets:
        subject_index = last_index % len(subjects) if subjects else 0
        subject = subjects[subject_index] if subjects else "A message for you"

        message = MIMEMultipart()
        message["From"] = sender_email
        message["To"] = to_recipient
        message["Bcc"] = ", ".join(bcc_recipients)
        message["Subject"] = subject
        message.attach(MIMEText(body, "html", "utf-8"))

        try:
            print("Sending the email...")
            server.sendmail(sender_email, valid_targets, message.as_string())
            print("Email sent successfully to 1 'To' and", len(bcc_recipients), "'BCC' recipients.")
        except Exception as e:
            print(f"::error::Failed to send email batch: {e}")
            failed_recipients.extend(valid_targets)
    
    server.quit()

    # --- Step 5: Failed emails ko save karna ---
    if failed_recipients:
        with open(FAILED_EMAILS_FILE, 'a', encoding='utf-8') as f:
            for email in failed_recipients:
                f.write(email + '\n')
        print(f"Saved {len(failed_recipients)} failed or invalid recipients.")

    # --- Step 6: State file ko update karna ---
    next_index = last_index + EMAILS_PER_RUN
    with open(STATE_FILE, 'w') as f:
        f.write(str(next_index))
    print(f"State file updated. Next run will start from index {next_index}.")

if __name__ == "__main__":
    send_email_batch()
