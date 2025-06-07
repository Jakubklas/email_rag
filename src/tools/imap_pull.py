import imaplib
import email
from config import *
from services.local_save import *
from email_cleaner import EmailCleaner

def pull_emails(n_char=99999):
    all_mail = []

    # Connect to the IMAP server over SSL
    mail = imaplib.IMAP4_SSL(imap_server, imap_port)
    mail.login(username, password)

    # Select the "inbox" folder
    status, _ = mail.select('inbox')
    if status != "OK":
        print("Failed to select the inbox folder.")
        return all_mail

    try:
        # Search for all emails in the "Primary" inbox
        status, message_numbers = mail.search(None, "ALL")
        if status != "OK" or not message_numbers[0]:
            print("No messages found!")
        else:
            # Iterate through each email id
            idx = 0
            for email_id in list(reversed(message_numbers[0].split()))[:num_mails]:
                idx +=1
                email_json = {}
                status, data = mail.fetch(email_id, "(RFC822)")
                if status == "OK":
                    email_message = email.message_from_bytes(data[0][1])

                    email_json = {
                        "from": email_message.get("From"),
                        "to": email_message.get("To"),
                        "date": email_message.get("Date"),
                        "subject": email_message.get("Subject"),
                        "message_id": email_message.get("Message-ID"),
                    }

                    if email_message.is_multipart():
                        body = None
                        for part in email_message.walk():
                            content_type = part.get_content_type()
                            content_disposition = str(part.get("Content-Disposition") or "")

                            if content_type == "text/plain" and "attachment" not in content_disposition.lower():
                                try:
                                    body = part.get_payload(decode=True).decode(errors="replace")
                                    break  # only break if a valid plain text body is found
                                except Exception:
                                    continue

                        if body is None:
                            # Fallback: try to extract text from any part
                            for part in email_message.walk():
                                try:
                                    body = part.get_payload(decode=True).decode(errors="replace")
                                    break
                                except Exception:
                                    continue

                        if body is None:
                            body = ""  # guarantee it's always assigned
                    else:
                        body = email_message.get_payload(decode=True).decode(errors="replace")

                    cleaner = EmailCleaner(body)
                    body = cleaner.process()            

                    email_json["body"] = body[:n_char]
                    all_mail.append(email_json)
                    
                else:
                    print("Failed to fetch email with id:", email_id)
                
                if idx % 10 == 0:
                    print(f"Pulled emails: {idx}")

        return all_mail

    except Exception as e:
        print("An error occurred:", e)
    finally:
        mail.logout()
