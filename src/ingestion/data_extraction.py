import os

from config.config import *
from src.utils.mbox_streaming import fast_stream_first_n
from src.utils.message_to_json import write_json_per_msg
from src.utils.email_parser import EmailParser
from src.utils.email_quotes import strip_quoted_text
from src.utils.email_cleaner import EmailCleaner


def main():
    """
    Extracts email text (as JSON) and raw attachment data from MBOX files.
    Flow: Parse → Clean → Strip quotes → Save as JSON
    """
    # Ensure output directories
    os.makedirs(attachments_dir, exist_ok=True)
    os.makedirs(emails_dir, exist_ok=True)
    
    # Process each email from the MBOX file
    for idx, raw_email in enumerate(fast_stream_first_n(mbox_path, num_emails)):
        try:
            # Parse email to dictionary format
            parsed = EmailParser(raw_email, attachments_dir).parse()
            
            # Clean text & turn into a structured dict
            cleaned = EmailCleaner(parsed).process()
            
            # Remove quoted past messages
            stripped = strip_quoted_text(cleaned)
            
            # Save email dict as JSON
            write_json_per_msg(stripped, idx, emails_dir)
            
            # Log progress
            if idx % VERBOSITY == 0:
                print(f"  → Processed {idx+1}/{num_emails} emails", flush=True)
                
        except Exception as e:
            print(f"[ERROR] Failed to process email {idx+1}: {e}")

    print("Extraction complete!")


if __name__ == "__main__":
    main()
