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

    print("\nDATA PROCESSING...\n")
    process_main()                                      # TODO: Some processing is turned currently off currently

    # print("\nDATA EMBEDDING...\n")
    # embed_main()

    # print("\nDATA INDEXING...\n")
    # index_main()

    # print("\nGETTING CHAT READY...\n")
    # answer = query_main()
    # print(answer)