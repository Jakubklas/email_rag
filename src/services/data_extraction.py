from config import *
import os
from src.tools.mbox_streaming import fast_stream_first_n
from src.tools.message_to_json import write_json_per_msg
from src.tools.message_parsing import parse_message_to_dict
from src.tools.email_quotes import strip_quoted_text
from src.tools.email_cleaner import EmailCleaner

def main():
    os.makedirs(attachments_dir, exist_ok=True)
    os.makedirs(emails_dir, exist_ok=True)
    
    for idx, raw in enumerate(fast_stream_first_n(mbox_path, num_emails)):      # itereates though the streaming generator
        parsed = parse_message_to_dict(raw, attachments_dir)                    # convertrs each email to a dictionary
        cleaned = EmailCleaner(parsed).process()                                # Cleans and pre-process the dictionary
        stripped = strip_quoted_text(cleaned)                                   # Strips email quotes from email's body, so that only one message per JSON remains
        out_file = write_json_per_msg(stripped, idx, emails_dir)                # saves each dictionary as JSON
        if idx % verbosity == 0:
            print(f"Wrote {idx+1}/{num_emails} emails.", flush=True)

    print("Done!")



if __name__ == "__main__":
    main()



# python -m src.services.data_extraction