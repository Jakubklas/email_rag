from config import *
from src.services.data_extraction import main as extract_main
from src.services.data_processing import main as process_main
from src.services.data_embedding import main as embed_main
from src.services.opensearch_indexing import main as index_main
from src.services.querying import main as query_main


if __name__ == "__main__":
    print("Email processor is running...")

    print("Starting Email Extraction...\n")
    extract_main()

    print("\nStarting Data Processing...\n")
    process_main()

    # print("\nStarting Data Embedding...\n")
    # embed_main()

    # print("\nStarting Data Indexing...\n")
    # index_main()

    # print("\nGetting the chat ready...\n")
    # answer = query_main()
    # print(answer)