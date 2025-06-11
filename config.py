import os

#-- PERSONAL -------------------------------------------------------------------------------------------

username = "jakub.klas@gmail.com"
password = "rkgq zrzg iuwk zodf"
imap_server = "imap.gmail.com"
imap_port = 993


#-- IMAP CONFIG -----------------------------------------------------------------------------------------

num_mails = 200
all_mail = []
output_file = os.path.join(os.getcwd(), "emails")
# email_dir = r"C:\Users\jklas\email_processor\emails"

#-- DATA EXTRACTION & PROCESSING --------------------------------------------------------------------------

mbox_path= r"\\ant\dept-eu\Amazon-Flex-Europe\Users\jklas\all_mail\Takeout\Mail\all_mail.mbox"
data_dir= r"C:\Users\jklas\email_processor\email_rag\data"
emails_dir= r"C:\Users\jklas\email_processor\email_rag\data\emails"
attachments_dir = r"C:\Users\jklas\email_processor\email_rag\data\attachments"
relevant_images_dir = r"C:\Users\jklas\email_processor\email_rag\data\attachments\relevant_images"
parsed_attachments_dir = r"C:\Users\jklas\email_processor\email_rag\data\parsed_attachments"
email_chunks_dir = r"C:\Users\jklas\email_processor\email_rag\data\chunked_emails"
attachment_chunks_dir = r"C:\Users\jklas\email_processor\email_rag\data\chunked_attachments"
thread_documents_dir = r"C:\Users\jklas\email_processor\email_rag\data\thread_documents"
stripped_emails_dir = r"C:\Users\jklas\email_processor\email_rag\data\stripped_emails"



poppler_path = r"C:\Users\jklas\Downloads\Release-24.08.0-0\poppler-24.08.0\Library\bin"
tesseract_path = r"C:\Users\jklas\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

num_emails= 100
n_char=None
verbosity = 20

#-- AWS CONFIG ------------------------------------------------------------------------------------------

AWS_REGION = "us-east-1"
AWS_PUBLIC_KEY = None
AWS_SECRET_KEY = None

#-- S3 CONFIG -------------------------------------------------------------------------------------------

uri = "s3://uk-flex-scheduling/emails/"
BUCKET, PREFIX = uri.replace("s3://", "").split("/", 1)


#-- OPENSEARCH CONFIG ------------------------------------------------------------------------------------

OPENSEARCH_ENDPOINT = "search-redcoat-express-wvba3hxtx72luhtzgh7tb56k4i.aos.eu-north-1.on.aws"
INDEX_NAME  = "redcoat-express"
AWS_REGION = "eu-north-1"

MASTER_USER        = "admin"              # the internal username you configured
MASTER_PASSWORD    = "ASINnumber1!"       # the password you set

DIRS_TO_INDEX = [thread_documents_dir, email_chunks_dir, attachment_chunks_dir]

#-- OPEN AI CONFIG -------------------------------------------------------------------------------------------

SECRET_KEY = "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"
MAX_TOKENS = 400   # ideal chunk length
OVERLAP = 50    # tokens of overlap between chunks
ENCODER_NAME = "cl100k_base"  # or whichever matches your 4o embedding

QUERY_MODEL = "gpt-4o"
SUMMARY_MODEL = "gpt-4o"
EMBEDDINGS_MODEL = "text-embedding-ada-002"
EMBEDDINGS_REQUEST_LIMIT = 3000            # Requests / Minute
EMBEDDINGS_TOKENST_LIMIT = 1000000         # Tokens / Minute
llm_instruction = "Answer the following user question based on the email threads provided: "

#-- REPLACE & REMOVE -------------------------------------------------------------------------------------------

SIGNATURE_MARKERS = [
    "best regards",
    "kind regards",
    "warm regards",
    "regards",
    "sincerely",
    "yours sincerely",
    "yours truly",
    "with appreciation",
    "with gratitude",
    "cheers",
    "thank you",
    "thanks",
    "all the best",
    "cordially",
    "respectfully",
    "best wishes",
    "sent from my iphone",
    "sent from my ipad",
    "from my mobile",
    "take care",
    "cheerio",
    "have a great day",
    "all my best",
    "cheers and regards",
    "yours faithfully",
    "in appreciation",
    "warmest regards",
    "with kindest regards",
    "with best wishes",
    "stay safe",
    "many thanks",
    "my best"
]

CHARACTER_REPLACEMENTS = {
    "\r": " ",
    "\u2019": "'",     # Right single quote to apostrophe
    "---": "",
    ">> ": "",
    ">>": "",
    "\u2007": " ",
    "\u034f": "",
    "\u200b": "",
    "\u2007": "", 
    "\u034f": "", 
    "\u2018": "'",     # Left single quote to apostrophe
    "\u201c": '"',     # Left double quote to straight double quote
    "\u201d": '"',     # Right double quote to straight double quote
    "\u2013": "-",     # En dash to hyphen
    "\u2014": "-",     # Em dash to hyphen
    "\u200c": "",      # Zero-width non-joiner (remove)
    "\u034f": "",      # Combining grapheme joiner (remove)
    "\u00a0": " ",     # Non-breaking space to regular space
    "\u2026": "...",   # Ellipsis to three dots
    "\u2122": "TM",    # Trademark symbol
    "\u00ae": "(R)",   # Registered trademark
    "\u00a9": "(C)",   # Copyright
    "\u2022": "*",     # Bullet point
    "\r\n": " ",      # Windows-style newline to space
    "\r": " ",         # Carriage return to space
    "\n": " ",          # Newline to space
    "\u2010": "-",   # Hyphen (unicode “HYPHEN”)
    "\u2011": "-",   # Non-breaking hyphen
    "\u2012": "-",   # Figure dash
    "\u2015": "-",   # Horizontal bar
    "\u2212": "-",   # Minus sign (convert to ASCII hyphen)
    "\u00AB": '"',   # « (left guillemet) → straight quote
    "\u00BB": '"',   # » (right guillemet) → straight quote
    "\u2039": "'",   # ‹ (single left-pointing angle quotation) → apostrophe
    "\u203A": "'",   # › (single right-pointing angle quotation) → apostrophe
    "\u02BC": "'",   # ʻ (modifier letter apostrophe) → apostrophe
    "\u201B": "'",   # ‛ (single high-reversed comma) → apostrophe
    "\u2032": "'",   # ′ (prime) → apostrophe/foot
    "\u2033": '"',   # ″ (double prime) → straight double-quote/inch
    "\u200B": "",    # Zero-width space (remove)
    "\u200D": "",    # Zero-width joiner (remove)
    "\uFEFF": "",    # Zero-width no-break space (BOM) → remove
    "\u200E": "",    # Left-to-right mark (LTR) → remove
    "\u200F": "",    # Right-to-left mark (RTL) → remove
    "\u202A": "",    # Left-to-right embedding → remove
    "\u202B": "",    # Right-to-left embedding → remove
    "\u202C": "",    # Pop directional formatting → remove
    "\u202D": "",    # Left-to-right override → remove
    "\u202E": "",    # Right-to-left override → remove
    "\u00AD": "",    # Soft hyphen (invisible unless line-wrapped) → remove
    "\u00A0": " ",
    "\u00BC": "1/4",   # ¼ → "1/4"
    "\u00BD": "1/2",   # ½ → "1/2"
    "\u00BE": "3/4",   # ¾ → "3/4"
    "\u2150": "1/7",   # ⅐ → "1/7"
    "\u2151": "1/9",   # ⅑ → "1/9"
    "\u2152": "1/10",  # ⅒ → "1/10"
    "\u2025": "..",   # Two dot leader (rare): replace with two periods
    "\u2026": "...",  # Horizontal ellipsis (you already have this)
    "\u2023": "*",   # Triangular bullet → asterisk
    "\u2043": "-",   # Hyphen bullet → hyphen
    "\u2219": ".",   # Bullet operator (·) → period or remove
    "\u25E6": "*",   # White bullet → asterisk
    "\u00B7": "*",   # Middle dot → asterisk or period
    "\u00B0": " degrees ",  # Degree sign → “ degrees ” (optional, if angles/temperatures matter)
    "\u201A": ",",   # Single low-9 quote → comma
    "\u201E": '"',   # Double low-9 quote → straight double quote
    "\u2030": "‰",   # Per mille sign (you can also map to “ per mille ” if desired)
    "\u20AC": "EUR", # Euro sign → “EUR” (only if currency normalization is needed)
    "\u00A3": "GBP", # Pound sterling → “GBP” (similarly optional)
    "\u00A5": "YEN", # Yen sign → “YEN”
    "\x0B": " ",     # Vertical tab → space
    "\x0C": " ",     # Form feed → space
    "\t": " ",       # Tab → space (if you want to collapse tabs)
    "\x00": "",      # Null → remove
    "\x01": "",      # Start of Heading → remove (and so on for other C0 control codes)
    "\uFF07": "'",   # FULLWIDTH APOSTROPHE → ASCII apostrophe
    "\uFF02": '"',   # FULLWIDTH QUOTATION MARK → ASCII double quote
}

BOILERPLATE = [
        # Unsubscribe / Preferences / Manage lists
        "unsubscribe",
        "click here to unsubscribe",
        "manage preferences",
        "update your preferences",
        "update preferences",
        "email preferences",
        "join our mailing list"

        # Legal / privacy / terms
        "privacy policy",
        "terms of service",
        "terms and conditions",
        "all rights reserved",
        "©",
        "© 19",
        "if you no longer wish to receive",

        # App / download prompts
        "download our app",
        "get it on android",
        "download on the app store",
        "available on google play",

        # Social media footers
        "follow us on",
        "find us on"

        # Physical mailing info
        "company inc.",
        "1234",            # street number start (common in addresses)
        "suite",           # e.g. "Suite 100"
        "po box",          # P.O. Box
        "p.o. box",
        "unsubscribe or manage preferences",
        "if this email is not relevant",

        # Standard disclaimers
        "confidentiality notice",
        "privacy statement",
        "disclaimer",
        "view in browser",
        "trouble viewing",
        "let us know at support@",

        # Common footer separators
        "\n--\n",           # double-dash on its own line
        "\n___\n",          # triple underscore on its own line
        "\n***\n",          # triple asterisk on its own line
    ]

SUPPORTED_EXTENSIONS = [
    "pdf",    # Adobe PDF
    "doc",    # Microsoft Word (legacy)
    "docx",   # Microsoft Word (modern)
    "xls",    # Microsoft Excel (legacy)
    "xlsx",   # Microsoft Excel (modern)
    "xlsm",   # Microsoft Excel (macro-enabled)
    "txt",    # Plain text
    "csv",    # Comma-separated values
    "msg",    # Outlook email message
    "rtf",    # Rich Text Format
    "xml",    # XML file
    "jpg",
    "jpeg",
    "png"
]

REMOVAL_EXPRESSIONS = [
    ""
]

#-- OTHER -------------------------------------------------------------------------------------------
id_marker = "_id_"      # Used to identify the "message_id" of each attachment in the attachment's file name