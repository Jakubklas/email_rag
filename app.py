from config import *
from src.services.data_extraction import main as extract_main
from src.services.data_processing import main as process_main

if __name__ == "__main__":
    print("Email processor is running...")
    print("Starting Email Extraction...\n")
    extract_main()
    print("\nStarting Email Processing...\n")
    process_main()