import json
import os
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from config import *

def build_thread_map(emails_dir):
    """
    Scans a directory of email JSON files and builds a mapping
    { message_id: thread_id } where thread_id is the ID of the
    top‐level message in that conversation.
    """
    # 1) Load and parse each JSON, capturing its datetime
    messages = []
    for filename in os.listdir(emails_dir):
        full_path = os.path.join(emails_dir, filename)
        with open(full_path, "r", encoding="utf-8") as f:
            content = json.load(f)

        raw_date = content.get("date")
        try:
            dt = parsedate_to_datetime(raw_date)
        except Exception:
            dt = datetime.min.replace(tzinfo=None)

        messages.append((content, dt))

    # 2) Sort all messages by date ascending
    messages.sort(key=lambda item: item[1])

    # 3) Build the thread map
    thread_map = {}
    for content, _ in messages:
        child_id  = content["message_id"].strip("<>")
        parent_id = (content.get("in_reply_to") or "").strip("<>")
        if parent_id and parent_id in thread_map:
            # inherit the thread_id of the parent
            thread_id = thread_map[parent_id]
        else:
            # no known parent → start a new thread
            thread_id = child_id
        thread_map[child_id] = thread_id

    return thread_map   

# python -m src.tools.thread_map