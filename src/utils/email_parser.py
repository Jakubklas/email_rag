import os
import email
from src.utils.safe_step import *
from config.config import *


class EmailParser:
    def __init__(self, raw_str, attachments_dir, n_char=None):
        self.raw_str = raw_str
        self.attachments_dir = attachments_dir
        self.n_char = n_char
        self.email_message = None
        self.clean_msg_id = ""
        self.result = {
            "type": "email",
            "attachments": [],
            "links": {}
        }

    @safe_step
    def parse_headers(self):
        self.email_message = email.message_from_string(self.raw_str, policy=email.policy.default)
        
        labels = self.email_message.get("X-GM-LABELS", "").lower()
        for label in ["spam", "category promotions", "promotions"]:
            if label in labels:  
                return None

        raw_msg_id = self.email_message.get("Message-ID", "") or ""
        self.clean_msg_id = raw_msg_id.strip().strip("<>").lower()
        raw_in_reply = self.email_message.get("In-Reply-To", "") or ""
        clean_in_reply = raw_in_reply.strip().strip("<>").lower()
        raw_refs = self.email_message.get("References", "") or ""
        clean_references = [ref.strip().strip("<>").lower() for ref in raw_refs.split() if ref.strip()]

        self.result.update({
            "from": self.email_message.get("From"),
            "to": self.email_message.get("To"),
            "cc": self.email_message.get("Cc"),
            "date": self.email_message.get("Date"),
            "subject": self.email_message.get("Subject"),
            "message_id": self.clean_msg_id,
            "in_reply_to": clean_in_reply,
            "references": clean_references
        })

    @safe_step
    def parse_body(self):
        body = ""
        if self.email_message.is_multipart():
            for part in self.email_message.walk():
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
                for part in self.email_message.walk():
                    try:
                        payload_bytes = part.get_payload(decode=True)
                        charset = part.get_content_charset("utf-8")
                        body = payload_bytes.decode(charset, errors="replace")
                        break
                    except Exception:
                        continue
        else:
            try:
                payload_bytes = self.email_message.get_payload(decode=True)
                charset = self.email_message.get_content_charset("utf-8")
                body = payload_bytes.decode(charset, errors="replace")
            except Exception:
                body = ""

        self.result["body"] = body[:self.n_char] if self.n_char else body

    @safe_step
    def parse_attachments(self):
        for part in self.email_message.walk():
            disp = part.get_content_disposition()
            filename = part.get_filename()

            if disp != "attachment" and not filename:
                continue
                
            if filename:
                filename = os.path.basename(filename)
                _, ext = os.path.splitext(filename)
                ext = ext.lstrip(".").lower()
                if ext in SUPPORTED_EXTENSIONS:  
                    filename = f"{id_marker}{self.clean_msg_id}{id_marker}{filename}"
                else:
                    continue
            else:
                mime_type = part.get_content_type()
                subtype = mime_type.split("/")[-1].lower()
                ext = EDGE_CASE_EXTENSIONS.get(subtype, subtype)
                if ext not in SUPPORTED_EXTENSIONS:
                    continue
                filename = f"{id_marker}{self.clean_msg_id}{id_marker}.{ext}"
            
            save_path = os.path.join(self.attachments_dir, filename)
            try:                                                                                
                payload_bytes = part.get_payload(decode=True)
                if payload_bytes is None:
                    continue
                with open(save_path, "wb") as outf:
                    outf.write(payload_bytes)
                self.result["attachments"].append(save_path)
            except Exception as e:
                print(f"Failed to save attachment {filename}: {e}")

    def parse(self):
        os.makedirs(self.attachments_dir, exist_ok=True)
        (self.parse_headers(),
         self.parse_body(),
         self.parse_attachments())
        return self.result
