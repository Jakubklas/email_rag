import os
import json
import warnings
from config.config import *
from src.utils.safe_step import safe_step
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadWarning
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import pandas as pd
from docx import Document

warnings.filterwarnings("ignore", category=PdfReadWarning)


class AttachmentProcessor:
    
    def __init__(self, classifier=None, parsed_dir=parsed_attachments_dir):
        self.classifier = classifier
        self.parsed_dir = parsed_dir
        self.categories = None
        self.pdf_categories = None
        self.img_categories = None
        
    @safe_step
    def categorize_attachments(self):
        """
        Uses categorizer to put files into different buckets.
        """
        print("Segmenting attachments...")
        self.categories = self.classifier.get_types()
        
        print("Categorizing PDFs...")
        self.pdf_categories = self.classifier.get_scannable_pdfs()
        
        print("Categorizing Images...")
        self.img_categories = self.classifier.get_relevant_images()


    def check_if_categorized(self):
        """
        Makes sure categorization ran before calling anything else.
        """
        if self.categories is None or self.pdf_categories is None or self.img_categories is None:
            raise ValueError("[ERROR]: categorize_attachments() was not yet called!")
    

    @safe_step
    def category_report(self):
        """
        Prints current numbers of files per category bucket.
        """
        for category in self.categories:
            print(f"Count of {category}: {len(self.categories[category])}")
        for category in self.pdf_categories:
            print(f"Count of {category}: {len(self.pdf_categories[category])}")    
        for category in self.img_categories:
            print(f"Count of {category}: {len(self.img_categories[category])}")
            

    @safe_step
    def save_relevant_images(self):
        """
        Saves relevant images to a separate folder.
        """
        print("Saving relevant images...")
        if not self.classifier.save_relevant_images():
            print("Error saving relevant images...")
            return False
        return True
        

    @safe_step
    def parse_scannable_pdfs(self, list_of_paths, document_limit=None):
        """
        Parse PDFs that contain enough digital text.
        """
        os.makedirs(self.parsed_dir, exist_ok=True)

        if not document_limit:
            document_limit = len(list_of_paths)

        for idx, pdf_path in enumerate(list_of_paths[:document_limit]):
            try:
                # Set output dir and read PDF text 
                base_name = os.path.splitext(os.path.basename(pdf_path))[0]
                output_path = os.path.join(self.parsed_dir, base_name + ".txt")

                reader = PdfReader(pdf_path)
                text_chunks = []
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text_chunks.append(extracted)

                full_text = "\n".join(text_chunks)

                # Save text as a txt file
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(full_text)
                
            except Exception as e:
                print(f"Error parsing scannable PDF: {pdf_path} \nbecause {e}")
            
            if idx % VERBOSITY == 0:
                print(f"Parsed {idx}/{len(list_of_paths)} scannable PDFs", flush=True)
        print("Done!\n")
        

    @safe_step
    def parse_image_pdfs(self, list_of_paths, document_limit=None):
        """
        Parse non-scannable PDFs using OCR (Tesseract.exe) & save the text.
        """
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        os.makedirs(self.parsed_dir, exist_ok=True)

        if not document_limit:
            document_limit = len(list_of_paths)

        for idx, pdf_path in enumerate(list_of_paths[:document_limit]):
            try:
                
                filename = os.path.splitext(os.path.basename(pdf_path))[0] + ".txt"
                output_path = os.path.join(self.parsed_dir, filename)

                # Convert PDF to image (Poppler)
                images = convert_from_path(pdf_path, poppler_path=poppler_path)
                text = ""
                for img in images:
                    text += pytesseract.image_to_string(img)

                # Save OCR text as a txt file
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(text)

                if idx % VERBOSITY == 0:
                    print(f"Parsed {idx+1}/{len(list_of_paths)} non-scannable PDFs", flush=True)
        
            except Exception as e:
                print(f"Error parsing non-scannable PDF: {pdf_path} \nbecause {e}")
        print("Done!\n")
        

    @safe_step
    def parse_images(self, list_of_paths, document_limit=None):
        """
        Parse text from relevant images using OCR (Tesseract) & 
        save in a separate directory.
        """
        os.makedirs(self.parsed_dir, exist_ok=True)

        if not document_limit:
            document_limit = len(list_of_paths)

        for idx, img_path in enumerate(list_of_paths[:document_limit]):
            try:
                # Set output dir and read text from images using OCR 
                filename = os.path.splitext(os.path.basename(img_path))[0] + ".txt"
                output_path = os.path.join(self.parsed_dir, filename)

                text = ""
                with Image.open(img_path) as img:
                    text += pytesseract.image_to_string(img)

                # Save the OCR text as a txt file
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(text)

                if idx % VERBOSITY == 0:
                    print(f"Parsed {idx+1}/{len(list_of_paths)} images", flush=True)

            except Exception as e:
                print(f"Error parsing image: {img_path} \nbecause {e}")
        print("Done!\n")
        

    @safe_step
    def parse_tabular(self, list_of_paths, document_limit=None):
        """
        Parsing Excel and CSV files and saving as markdown table
        to be embedded & read by LLM.
        """
        warnings.filterwarnings("ignore", category=UserWarning)
        os.makedirs(self.parsed_dir, exist_ok=True)

        if not document_limit:
            document_limit = len(list_of_paths)

        for idx, tbl_path in enumerate(list_of_paths[:document_limit]):
            try:
                # Get the file tabular data format & create output filename
                ext = os.path.splitext(tbl_path)[1][1:].lower()
                filename = os.path.splitext(os.path.basename(tbl_path))[0] + ".txt"
                output_path = os.path.join(self.parsed_dir, filename)

                # CSV Processing
                if ext == "csv":
                    df = pd.read_csv(tbl_path, on_bad_lines="skip")
                    markdown = df.to_markdown(index=False)
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(markdown)

                # Excel Processing
                elif ext in ["xls", "xlsx", "xlsm"]:
                    excel = pd.ExcelFile(tbl_path)
                    text = {}
                    for sheet in excel.sheet_names:
                        df = excel.parse(sheet)
                        text[f"sheet_{sheet}"] = df.to_markdown(index=False)

                    with open(output_path, "w", encoding="utf-8") as f:
                        json.dump(text, f, indent=2)

            except Exception as e:
                print(f"Error parsing tabular file: {tbl_path} \nbecause {e}")    
            
            if idx % VERBOSITY == 0:
                print(f"Parsed {idx+1}/{len(list_of_paths)} tabular files", flush=True)
        print("Done!\n")
        

    @safe_step
    def parse_word_docs(self, list_of_paths, document_limit=None):
        """
        Parse Word documents as .txt
        """
        os.makedirs(self.parsed_dir, exist_ok=True)

        if not document_limit:
            document_limit = len(list_of_paths)

        for idx, docx_path in enumerate(list_of_paths[:document_limit]):
            try:
                # Create output filename & extract text
                filename   = os.path.splitext(os.path.basename(docx_path))[0]
                output_path = os.path.join(self.parsed_dir, filename + ".txt")

                document = Document(docx_path)
                paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
                full_text  = "\n".join(paragraphs)

                # Write to a .txt file & save it
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(full_text)

                if idx % VERBOSITY == 0:
                    print(f"Parsed {idx+1}/{len(list_of_paths)} Word docs", flush=True)

            except Exception as e:
                print(f"Error parsing Word file: {docx_path} \nbecause {e}")   
        print("Done!\n")
        

    @safe_step
    def save_txt_files(self, list_of_paths, document_limit=None):
        """
        Save plain txt files directly.
        """
        os.makedirs(self.parsed_dir, exist_ok=True)
        
        if not document_limit:
            document_limit = len(list_of_paths)

        for idx, txt_path in enumerate(list_of_paths[:document_limit]):
            try:
                filename = os.path.splitext(os.path.basename(txt_path))[0]
                output_path = os.path.join(self.parsed_dir, filename + ".txt")
                ext = os.path.splitext(txt_path)[1].lower()

                with open(txt_path, "r", encoding="utf-8") as src:
                    content = src.read()

                with open(output_path, "w", encoding="utf-8") as dst:
                    dst.write(content)

                if idx % VERBOSITY == 0:
                    print(f"Parsed {idx+1}/{len(list_of_paths)} txt files", flush=True)
                    
            except Exception as e:
                print(f"Error saving text file: {txt_path} \nbecause {e}")  
        print("Done!\n")
        
        
    def process_all(self, save_rel_img=True, parse_rel_img=True, parse_scan_pdf=True, 
                   parse_non_scan_pdf=True, parse_word=True, parse_tab=True, parse_txt=True):
        """
        Conditionally orchestrates the full attachments pipeline incl.
        categorizing/parsing/saving per each file & format.
        """
        if not self.classifier:
            raise ValueError("[ERROR]: AttachmentClassifier is missing or was not provided.")
            
        os.makedirs(self.parsed_dir, exist_ok=True)
        
        # Categorize attachments & show the numbers per bucket
        self.categorize_attachments()
        self.category_report()
        
        # Process each type based on bool flags
        if save_rel_img:
            self.save_relevant_images()
            
        if parse_rel_img:
            print("Parsing relevant images...")
            self.parse_images(self.img_categories["relevant"])
            
        if parse_scan_pdf:
            print("Parsing scannable PDFs...")
            self.parse_scannable_pdfs(self.pdf_categories["scannable"])
            
        if parse_non_scan_pdf:
            print("Parsing non-scannable PDFs...")
            self.parse_image_pdfs(self.pdf_categories["non_scannable"])
            
        if parse_tab:
            print("Parsing tabular data...")
            self.parse_tabular(self.categories["tabular"])
            
        if parse_word:
            print("Parsing word documents...")
            self.parse_word_docs(self.categories["word_doc"])
            
        if parse_txt:
            print("Parsing text documents...")
            self.save_txt_files(self.categories["text"])