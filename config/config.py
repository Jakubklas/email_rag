from dotenv import load_dotenv
load_dotenv()
import os
import re

#-- SECRETS -----------------------------------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY")                        # OpenAI API
MASTER_USER = os.getenv("MASTER_USER")                      # OpenSearch
MASTER_PASSWORD = os.getenv("MASTER_PASSWORD")              # OpenSearch
OPENSEARCH_ENDPOINT = os.getenv("OPENSEARCH_ENDPOINT")      # OpenSearch
AWS_REGION = "eu-north-1"                                   # AWS
AWS_PUBLIC_KEY = None                                       # AWS --> No keys required    
AWS_SECRET_KEY = None                                       # AWS --> No keys required

#-- IMAP CONFIG -----------------------------------------------------------------------------------------

all_mail = []
output_file = os.path.join(os.getcwd(), "emails")

#-- DATA EXTRACTION & PROCESSING --------------------------------------------------------------------------

cwd = os.getcwd()
mbox_path= os.path.join(cwd, "mbox_files")
data_dir = os.path.join(cwd, "data")
apps_dir = os.path.join(cwd, "applications")

emails_dir = os.path.join(data_dir, "emails")
attachments_dir = os.path.join(data_dir, "attachments")                        
relevant_images_dir = os.path.join(attachments_dir, "relevant_images")          
parsed_attachments_dir = os.path.join(data_dir, "parsed_attachments")          
email_chunks_dir = os.path.join(data_dir, "chunked_emails")                    
attachment_chunks_dir = os.path.join(data_dir, "chunked_attachments")            
thread_documents_dir = os.path.join(data_dir, "thread_documents")             
stripped_emails_dir = os.path.join(data_dir, "stripped_emails")
email_attachment_dir = os.path.join(data_dir, "email_attachment_doc")  

poppler_path = os.path.join(apps_dir, "poppler", "Release-24.08.0-0", "poppler-24.08.0", "Library", "bin")
tesseract_path = os.path.join(apps_dir, "tesseract", "tesseract.exe")

num_emails= 5000                               # Emails limit for testing
n_char=None                                    # Character limit for long emails
VERBOSITY = 100                                # Progress logging frequency


#-- S3 CONFIG -------------------------------------------------------------------------------------------

uri = "s3://rag-raw-data/mbox-files/"
BUCKET, PREFIX = uri.replace("s3://", "").split("/", 1)


#-- OPEN SEARCH CONFIG ------------------------------------------------------------------------------------

THREADS_INDEX  = "thread_documents"
EMAILS_INDEX = "email_documents"
DIRS_TO_INDEX = [thread_documents_dir, email_attachment_dir]        # TODO: Check if we actually need this of if it's redundand

#-- OPEN AI CONFIG -------------------------------------------------------------------------------------------

CHUNK_TOKENS = 400                            # Commonly used chunk lenght to preserve context for embedding
CHUNK_OVERLAP = 50                            # Tokens of overlap between chunks
ENCODER_NAME = "cl100k_base"                  # Encoder used bu OpenAI models

SMALL_MODEL = "gpt-3.5-turbo"                 # 4000 token window
MEDIUM_MODEL = "gpt-3.5-turbo-16k"            # 16K token window
LARGE_MODEL = "gpt-4-32k"                     # 32K token window
VERY_LARGE_MODEL = "gpt-4o-mini"              # 100K token window
SUMMARY_MODEL = "gpt-4.1-nano"                # Used for thread summaries before embedding
EMB_MODEL = "text-embedding-ada-002"
MEMORY_MODEL = "gpt-3.5-turbo-16k"            # 16K token window

#-- REPLACE & REMOVE -------------------------------------------------------------------------------------------

WEEKDAY_SPLITTER = re.compile(r"On (Mon|Tue|Wed|Thu|Fri|Sat|Sun),")
HEADER_SPLITTER   = re.compile(r"(?:From|Sent|To|Subject):")

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
    # Non-recognizeable chars polluting context
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
        # Boilerplate text polluting context
        "unsubscribe",
        "click here to unsubscribe",
        "manage preferences",
        "update your preferences",
        "update preferences",
        "email preferences",
        "join our mailing list"
        "privacy policy",
        "terms of service",
        "terms and conditions",
        "all rights reserved",
        "©",
        "© 19",
        "if you no longer wish to receive",
        "download our app",
        "get it on android",
        "download on the app store",
        "available on google play",
        "follow us on",
        "find us on"
        "company inc.",
        "po box",
        "p.o. box",
        "unsubscribe or manage preferences",
        "if this email is not relevant",
        "confidentiality notice",
        "privacy statement",
        "disclaimer",
        "view in browser",
        "trouble viewing",
        "let us know at support@",
        "\n--\n",
        "\n___\n",
        "\n***\n",
    ]

SUPPORTED_EXTENSIONS = [
    # Attachments parsing for text/image/tabular data
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

EDGE_CASE_EXTENSIONS = {
    "plain": "txt",
    "msword": "doc",
    "vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "vnd.ms-excel": "xls",
    "vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx"
}

#-- OTHER -------------------------------------------------------------------------------------------

id_marker = "_id_"      # Used as a separator in "message_id" of each attachment's file name

# For asynchronous LLM summarizing 
MAX_CONCURRENT = 20
BATCH_SIZE = MAX_CONCURRENT * 2
MAX_TOKENS_PER_PROMPT = 3000
