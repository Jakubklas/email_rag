from config.config import *
from src.utils.safe_step import *
from src.utils.attachment_classifier import AttachmentClassifier
from src.utils.attachment_processor import AttachmentProcessor
from src.utils.thread_processor import ThreadProcessor


@safe_step
def process_attachments(save_rel_img=True, parse_rel_img=True, parse_scan_pdf=True, parse_non_scan_pdf=True, parse_word=True, parse_tabular=True, parse_txt=True):
    """
    Uses AttachmentClassifier to create categories of attachments (e.g. relevant/
    non-relevant images, scannable/non-scannable PDFs, etc.). Then uses AttachmentProcessor
    to parse relevant attachments into text documents.
    """
    # Create Classifier & Processor
    classifier = AttachmentClassifier(attachments_dir, SUPPORTED_EXTENSIONS)
    processor = AttachmentProcessor(classifier=classifier)
    
    # Call methods for each file type
    processor.process_all(
        save_rel_img,
        parse_rel_img,
        parse_scan_pdf, 
        parse_non_scan_pdf,
        parse_word,
        parse_tabular,
        parse_txt
        )


def main(get_attachments=True, get_threads=True, sum_threads=True, join_emails_attachments=True):
    """
    1.) Produces LLM readable text from attached files & appends to email body
    2.) Creates 'Threads' JSONs to hold context of a full email thread
    3.) Calls LLM per each 'Thread' to produce short text summary for later embeddings step   
    """
    # Parse & Process Attachments
    if get_attachments:
        print("Processing attachments:")
        process_attachments()
        print()

    # Create Thread JSONs & generate summary per thread (used for embedding later)
    if get_threads or join_emails_attachments:
        thread_processor = ThreadProcessor()
        
        if get_threads:
            thread_processor.process_threads(summarize=sum_threads)
            print()
        
        # Append parsed attachment text to email bodies
        if join_emails_attachments:
            print("Joining email bodies and attachments...")
            thread_processor.merge_emails_and_attachments()
            print()


if __name__ == "__main__":
    main()
