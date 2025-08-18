import os
import warnings
from pathlib import Path
import pandas as pd

from config.config import *
from src.utils.safe_step import *
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadWarning
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

warnings.filterwarnings("ignore")


class AttachmentClassifier():
    def __init__(self, path, supported_formats, document_limit=None):
        self.path = path
        self.document_limit = document_limit
        self.supported_formats = supported_formats
        self.files = os.listdir(path)

    @safe_step
    def get_types(self):
        """
        Returns a dict of file paths indexed extension. If extension not in
        supported_formats, removes the file.
        """
        self.file_types = {
            "pdf": [],
            "images": [],
            "tabular": [],
            "word_doc": [],
            "text": [],
            "email": [],
            "errors": []
        }
        for file in self.files:
            try:
                path = os.path.join(self.path, file)
                ext = os.path.splitext(file)[1][1:].lower()
                if ext not in self.supported_formats:
                    continue
                if ext in ["pdf"]:
                    self.file_types["pdf"].append(path)
                elif ext in ["jpg", "jpeg", "png"]:
                    self.file_types["images"].append(path)
                elif ext in ["csv", "xls", "xlsx", "xlsm"]:
                    self.file_types["tabular"].append(path)
                elif ext in ["docx", "doc"]:
                    self.file_types["word_doc"].append(path)
                elif ext in ["txt"]:
                    self.file_types["text"].append(path)
                elif ext in ["msg"]:
                    self.file_types["email"].append(path)
                else: 
                    continue
            except Exception as e:
                print(f"Error getting filetype from: {path} , because:\n {e}")

        return self.file_types
    

    @safe_step
    def get_scannable_pdfs(self, min_char=10, document_limit=None):
        """
        Identifies which PDFs contain digital text and divides them into
        'scannable' (no OCR needed), 'non-scannable' (OCR) and 'broken' (non-readable).
        """
        warnings.filterwarnings("ignore", category=PdfReadWarning)                      # Turning off the warnings

        pdf_attachments = {
            "scannable": [],
            "non_scannable": [],
            "broken": [] 
        }

        all_files = self.file_types["pdf"]
        skipped = 0
        
        if not document_limit:
            document_limit = len(all_files)

        # Try reading the PDF
        try:
            for file_path in all_files[:document_limit]:
                try:
                    # Check if PDF contains text on the first 2 pages, if not -> 'non-scanable'
                    with open(file_path, "rb") as f:
                            reader = PdfReader(f)
                            text = ""
                            for page in reader.pages[:2]:
                                text += page.extract_text() or ""

                            if len(text.strip()) >= min_char:
                                pdf_attachments["scannable"].append(file_path)
                            else:
                                pdf_attachments["non_scannable"].append(file_path)
                
                # If we can't open it -> 'broken'
                except Exception as e:
                    pdf_attachments["broken"].append(file_path)
                    print(f"[ERROR] Failed to open PDF {file_path} and moving to 'broken' because:\n {e}")
                        
            return pdf_attachments

        # If we couldn't read anything -> 'non-scannable'
        except Exception as e:
            print(f"[ERROR] Can't read PDF: {e}")
            return pdf_attachments


    @safe_step
    def get_relevant_images(self, min_file_size = 20, min_width=300.0, min_height=200.0, min_words=10, document_limit=None):
        """
        Applies set of rules (e.g. size, text, resolution, etc.) to see if
        image attachements contain any relevant text to parse. Creates map
        of filepaths with 'relevant', 'not_relevant', or otherwise 'failed'.
        """
        # Path to Tesseract.exe (OCR)
        pytesseract.pytesseract.tesseract_cmd = tesseract_path 

        self.images = {
            "relevant": [],
            "not_relevant": [],
            "failed": []
        }
        all_files = self.file_types["images"]

        if not document_limit:
            document_limit = len(self.file_types["images"])

        for file_path in all_files[:document_limit]:
            try:

                # Remove images with small file size
                file_size = os.path.getsize(file_path) / 1024
                if file_size < min_file_size:
                    self.images["not_relevant"].append(file_path)
                    continue

                with Image.open(file_path) as img:

                    # Remove low resolution images
                    width, height = img.size
                    if width < min_width or height < min_height:
                        self.images["not_relevant"].append(file_path)
                        continue

                    # Remove square images (logos)
                    a_ratio = height / width
                    if 0.9 < a_ratio < 1.1:
                        self.images["not_relevant"].append(file_path)
                        continue

                    # Use OCR & remove if too little text
                    text = pytesseract.image_to_string(file_path)
                    words = len(text.strip().split())
                    if words < min_words:
                        self.images["not_relevant"].append(file_path)
                        continue

                self.images["relevant"].append(file_path)

            except Exception as e:
                self.images["failed"].append(file_path)
                print(f"[ERROR]: Failed to identify image {file_path} & adding to 'failed' because: \n{e}")

        return self.images
    

    @safe_step
    def save_relevant_images(self):
        """
        Saves each 'relevant' images in a separate directory
        for bulk OCR later.
        """
        try:
            os.makedirs(relevant_images_dir, exist_ok=True)

            # Iterate through all relevant image file paths & save files
            for img_path in self.images.get("relevant", []):
                try:
                    filename = os.path.basename(img_path)
                    output_path = os.path.join(relevant_images_dir, filename)
                    with Image.open(img_path) as img:
                        img.save(output_path)
                
                except Exception as e:
                    print(f"[ERROR] Problem saving relevant image: {img_path} because: \n{e}")
                
            return True
        
        except Exception as e:
            print(f"[ERROR] Saving relevant images failed due to:\n {e}")
            return False