import re
import os
import json
from config import *


# Only match exact capitalized “On Mon,” “On Tue,” … including the comma
WEEKDAY_HEADER = re.compile(r"On (Mon|Tue|Wed|Thu|Fri|Sat|Sun),")

# Match only capitalized meta-headers at the start of a block
META_HEADER   = re.compile(r"(?:From|Sent|To|Subject):")

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


# def strip_and_save(emails_dict, stripped_dict):
#     """
#     For each JSON in input_dir, strip quoted text from its 'body' field
#     and write the result into output_dir (same filename).
#     """

#     for idx, filename in enumerate(files):
#         in_path  = os.path.join(emails_dir, filename)
#         out_path = os.path.join(stripped_emails_dir, "stripped_"+filename)

#         # load
#         with open(in_path, "r", encoding="utf-8") as f:
#             data = json.load(f)

#         # strip
#         raw = data.get("body", "")
#         data["body"] = strip_quoted_text(raw)

#         # save
#         with open(out_path, "w", encoding="utf-8") as f:
#             json.dump(data, f, ensure_ascii=False, indent=2)

#         if idx % verbosity == 0:
#             print(f"Stripped quotes from {idx}/{len(files)}")