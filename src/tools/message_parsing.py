import os
import email
from config import *
from email import message_from_string
from email import policy
from email.utils import make_msgid


def parse_message_to_dict(raw_str, attachments_dir, n_char=None):
    """
    Parse a raw RFC 822 message string into a dict with:
      * from, to, cc, date, subject, message_id, in_reply_to, references, body, attachments
    Truncate 'body' to n_char if desired. Assumes UTF-8 fallback for unknown charsets.
    Pull all attachments into a separate file and save their paths.
    """
    # Parse into an EmailMessage using the default policy (handles Unicode, MIME, etc.)
    email_message = email.message_from_string(raw_str, policy=policy.default)
    os.makedirs(attachments_dir, exist_ok=True)
    
    # ---HEADERS EXTRACTION--------------------------------------------------------------------
    result = {
        "from": email_message.get("From"),
        "to": email_message.get("To"),
        "cc": email_message.get("Cc"),
        "date": email_message.get("Date"),
        "subject": email_message.get("Subject"),
        "message_id": email_message.get("Message-ID"),
        "in_reply_to": email_message.get("In-Reply-To"),
        "references": email_message.get("References"),
        "attachments": [],
        "links": {}
    }

    # ---BODY EXTRACTION--------------------------------------------------------------------
    body = ""
    if email_message.is_multipart():
        for part in email_message.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition") or "")
            if ct == "text/plain" and "attachment" not in cd.lower():
                try:
                    payload_bytes = part.get_payload(decode=True)
                    charset = part.get_content_charset("utf-8")
                    body = payload_bytes.decode(charset, errors="replace")
                    break
                except Exception:
                    continue
        if not body:
            # Fallback: take first decodable payload
            for part in email_message.walk():
                try:
                    payload_bytes = part.get_payload(decode=True)
                    charset = part.get_content_charset("utf-8")
                    body = payload_bytes.decode(charset, errors="replace")
                    break
                except Exception:
                    continue
    else:
        try:
            payload_bytes = email_message.get_payload(decode=True)
            charset = email_message.get_content_charset("utf-8")
            body = payload_bytes.decode(charset, errors="replace")
        except Exception:
            body = ""

    if not n_char:
        result["body"] = body
    else:
        result["body"] = body[:n_char]

    # ---ATTACHMENTS EXTRACTION--------------------------------------------------------------------
    for part in email_message.walk():
        context_disp = part.get_content_disposition()          # returns "attachment", "inline", or None
        filename = part.get_filename()
        id_marker = "_id_"

        if context_disp != "attachment" and not filename:       # Only get "attachment" from CD
            continue

        if filename:
            filename = os.path.basename(filename)               # get the file extension
            root, ext = os.path.splitext(filename)
            ext = ext.lstrip(".").lower()

            
            if ext not in SUPPORTED_EXTENSIONS:                 # only accept SUPPORTED_EXTENSIONS. skipt the rest    
                continue

            # Optionally prefix to avoid name collisions,
            # but preserve original filename’s base
            msg_id = result["message_id"] or make_msgid(domain="example.com")           # inslude message id in the name of the attachment file
            clean_msg_id = msg_id.strip("<>").replace(":", "_")
            
            filename = f"{id_marker}{clean_msg_id}{id_marker}{filename}"

        else:
            mime_type = part.get_content_type()                                     # handling some extension edge-cases
            subtype = mime_type.split("/")[-1].lower()

            if subtype == "plain":
                ext = "txt"
            elif subtype == "msword":
                ext = "doc"
            elif subtype == "vnd.openxmlformats-officedocument.wordprocessingml.document":
                ext = "docx"
            elif subtype == "vnd.ms-excel":
                ext = "xls"
            elif subtype == "vnd.openxmlformats-officedocument.spreadsheetml.sheet":
                ext = "xlsx"
            else:
                ext = subtype  # e.g. "pdf", "xml", "csv", "rtf"

            if ext not in SUPPORTED_EXTENSIONS:
                continue

            msg_id = result["message_id"] or make_msgid(domain="example.com")               # Build a fallback filename since none was provided
            clean_msg_id = msg_id.strip("<>").replace(":", "_")
            filename = f"{id_marker}{clean_msg_id}{id_marker}.{ext}"

        save_path = os.path.join(attachments_dir, filename)

        try:                                                                                # saving attachment bytes to attachments folder specified
            payload_bytes = part.get_payload(decode=True)
            if payload_bytes is None:
                continue  # skip if decode returns None
            with open(save_path, "wb") as outf:
                outf.write(payload_bytes)
            result["attachments"].append(save_path)
        except Exception as e:
            print(f"Failed to save attachment {filename}: {e}")

    return result