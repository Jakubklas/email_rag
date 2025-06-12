import re
from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime, getaddresses
from dateutil import parser
import datetime
from src.tools.safe_step import *
from config import *


class EmailCleaner:
    def __init__(self, email_json):
        self.email_json = email_json
        self.raw_body = email_json.get("body", "")
        self.subject = email_json.get("subject", "")
        self.date = email_json.get("date", "")
        self.from_line = email_json.get("from", "")
        self.to_line = email_json.get("to") or ""
        self.participants = []
        self.links = {}
    
    @safe_step
    def clean_html(self):
        if isinstance(self.email_json.get("body"), dict) and "html" in self.email_json["body"]:
            self.raw_body = self.email_json["body"]["html"]
        elif isinstance(self.email_json.get("body"), str):
            self.raw_body = self.email_json["body"]
        else:
            self.raw_body = ""
        
        self.raw_body = BeautifulSoup(self.raw_body, "html.parser").get_text(separator=" ")

    @safe_step
    def normalize_characters(self):
        for char, replacement in CHARACTER_REPLACEMENTS.items():
            self.raw_body = self.raw_body.replace(char, replacement)

    @safe_step
    def normalize_subject(self):
        raw_subj = self.subject or ""
        # remove non-breaking spaces
        subj = raw_subj.replace("\xa0", " ")
        # strip any leading RE:, FW:, FWD:, including repeated prefixes
        pattern = r"^\s*(?:(?:re|fw|fwd)\s*:?\s*)+"
        subj = re.sub(pattern, "", subj, flags=re.IGNORECASE)
        # collapse multiple spaces and trim
        subj = re.sub(r"\s+", " ", subj).strip().lower()
        # update and return
        self.subject = subj

    @safe_step
    def isolate_urls(self):
        urls = re.findall(r"https?://\S+|\\:https?://\S+", self.raw_body)
        self.links = {}
        for idx, url in enumerate(urls):
            placeholder = f"URL_LINK_{idx}"
            self.raw_body = re.sub(re.escape(url), placeholder, self.raw_body)
            self.links[placeholder] = (url)

    @safe_step
    def strip_boilerplate(self):
        for keyword in BOILERPLATE:
            idx = self.raw_body.lower().find(keyword)
            if idx != -1:
                self.raw_body = self.raw_body[:idx]
                break

    @safe_step
    def remove_signature(self):
        lower_body = self.raw_body.lower()
        cutoff = len(self.raw_body)
        for marker in SIGNATURE_MARKERS:
            pos = lower_body.find("\n" + marker)
            if pos == -1:
                pos = lower_body.find("\n" + marker.title())
            if pos != -1 and pos < cutoff:
                cutoff = pos
        self.raw_body = self.raw_body[:cutoff].strip()

    @safe_step
    def date_to_iso(self):
        """Convert the email's date header into an ISO-8601 formatted string."""
        try:
            dt = parsedate_to_datetime(self.date)
        except Exception:
            dt = parser.parse(self.date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=datetime.timezone.utc)
        iso_date = dt.astimezone(datetime.timezone.utc).isoformat()
        self.date = iso_date

    @safe_step
    def prcocess_participants(self):
        """Normalize and collect all email participants (sender, to, cc) into the participants field."""
        addr_lines = [self.from_line]
        if isinstance(self.to_line, (list, tuple)):
            addr_lines.extend(self.to_line)
        else:
            addr_lines.append(self.to_line)
        cc_line = self.email_json.get("cc")
        if cc_line:
            if isinstance(cc_line, (list, tuple)):
                addr_lines.extend(cc_line)
            else:
                addr_lines.append(cc_line)
        parsed = getaddresses(addr_lines)
        unique = []
        for name, email_addr in parsed:
            entry = f"{name} <{email_addr}>" if name else email_addr
            if entry not in unique:
                unique.append(entry)
        self.participants = unique

    @safe_step
    def commit_changes(self):
        """Write back all cleaned and extracted fields into the email_json."""
        self.email_json["body"] = self.raw_body
        self.email_json["date"] = self.date
        self.email_json["participants"] = self.participants
        self.email_json["links"] = self.links


    def process(self):
        ( self.clean_html()
        , self.normalize_characters()
        , self.normalize_subject()
        , self.isolate_urls()
        #, self.strip_boilerplate()          # This becomes an issue when the "body" contains multiple messages (=multiple boilerplate strings)
        #, self.remove_signature()           # This becomes an issue when the "body" contains multiple messages (=multiple signatures) 
        , self.date_to_iso()
        , self.prcocess_participants()
        , self.commit_changes()
        )
        return self.email_json
