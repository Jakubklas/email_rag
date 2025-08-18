from config.config import *
from src.ingestion.data_extraction import main as extract_main
from src.ingestion.data_processing import main as process_main
from src.ingestion.data_embedding import main as embed_main
from src.ingestion.opensearch_indexing import main as index_main
from src.querying.querying import main as query_main
import warnings
warnings.filterwarnings("ignore")   

if __name__ == "__main__":

    print("\nEMAIL EXTRACTION...\n")
    extract_main()

    print("\nDATA PROCESSING...\n")
    process_main(get_attachments=True, get_threads=True, sum_threads=True, join_emails_attachments=True)   

    print("\nDATA EMBEDDING...\n")
    embed_main(doc_limit=None)

    print("\nDATA INDEXING...\n")
    index_main()

    print("\nPIPELINE COMPLETE!\n")
    
    # Uncomment to test querying:
    # print("\nTESTING QUERY...\n")
    # answer = query_main()
    # print(answer)