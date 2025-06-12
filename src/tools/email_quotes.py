import re
import os
import json
from src.tools.safe_step import *
from config import *


# Only match exact capitalized “On Mon,” “On Tue,” … including the comma
WEEKDAY_HEADER = re.compile(r"On (Mon|Tue|Wed|Thu|Fri|Sat|Sun),")

# Match only capitalized meta-headers at the start of a block
META_HEADER   = re.compile(r"(?:From|Sent|To|Subject):")

@safe_step
def strip_quoted_text(email_dict):
    """
    Cuts off at the first occurrence of:
      • “On Mon,” / “On Tue,” / … / “On Sun,” (case-sensitive, comma required)
      • OR any “From:”, “Sent:”, “To:”, “Subject:” headers
    Keeps everything before that point and appends <END OF MESSAGE>.
    """
    body = email_dict["body"]
    idx = len(body)
    for pat in (WEEKDAY_HEADER, META_HEADER):
        m = pat.search(body)
        if m and m.start() < idx:
            idx = m.start()

    text = body[:idx].rstrip()
    email_dict["body"] = text + "\n<END OF MESSAGE>"

    return email_dict
