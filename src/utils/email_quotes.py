from src.utils.safe_step import *
from config.config import *


@safe_step
def strip_quoted_text(email_dict):
    """
    Removes email quotes to only get single messages - not the whole thread.
    Breaks on: 'On Mon,'/'On Tue,' or 'From:'/'Sent:'/'To:'/'Subject:' headers.
    Keeps everything before break appends '<END OF MESSAGE>'.
    """
    body = email_dict["body"]
    idx = len(body)
    for splitter in (WEEKDAY_SPLITTER, HEADER_SPLITTER):
        match = splitter.search(body)
        if match and match.start() < idx:
            idx = match.start()

    text = body[:idx].rstrip()
    email_dict["body"] = text + "\n<END OF MESSAGE>"

    return email_dict
