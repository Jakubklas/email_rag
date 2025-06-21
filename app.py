from config import *
from src.services.data_extraction import main as extract_main
from src.services.data_processing import main as process_main
from src.services.data_embedding import main as embed_main
from src.services.opensearch_indexing import main as index_main
from src.services.querying import main as query_main
import warnings
warnings.filterwarnings("ignore")   

if __name__ == "__main__":
    print("\nEmail processor is running...")

    # print("\nEMAIL EXTRACTION...\n")
    # extract_main()

    # print("\nDATA PROCESSING...PARSING ATTACHMENTS\n")
    # process_main(get_attachments=True, get_threads=False, sum_threads=False, join_emails_attachemnts=False, get_email_chunks=False, get_att_chunks=False)   

    # print("\nDATA PROCESSING...BUILDING THREADS\n")
    # process_main(get_attachments=False, get_threads=True, sum_threads=True, join_emails_attachemnts=True, get_email_chunks=False, get_att_chunks=False)   

    # print("\nDATA EMBEDDING...\n")
    # embed_main(embed_chunks=False, doc_limit=None)

    # print("\nDATA INDEXING...\n")
    # index_main()

    # print("\nGETTING CHAT READY...\n")
    # answer = query_main()
    # print(answer)