import os
from config import *
from PyPDF2 import PdfReader                                    # Reading PDFs
import warnings                                                 # PDF warnings
from PyPDF2.errors import PdfReadWarning                        # PDF warnings
warnings.filterwarnings("ignore", category=PdfReadWarning)          
from pdf2image import convert_from_path                         # PDF warnings
import pytesseract                                              # Optical text recognition
from pathlib import Path                                        # Converting strings to paths
from PIL import Image                                           # Image handling (e.g. opening images, metadata extraction)
import pandas as pd                                             # Tabular data handling

class AttachmentClassifier():
    def __init__(self, path, supported_formats, document_limit=None):
        self.path = path
        self.document_limit = document_limit
        self.supported_formats = supported_formats
        self.files = os.listdir(path)

    def get_types(self):
        """
        Returns a dictionary of paths indexed by their extension.
        If extension not int self.supported_formats, removes it.
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
            path = os.path.join(self.path, file)
            try:
                ext = os.path.splitext(file)[1][1:].lower()
                if ext in ["pdf"]:
                    self.file_types["pdf"].append(path)
                elif ext in ["jpg", "jpeg", "png"]:
                    self.file_types["images"].append(path)
                elif ext in ["csv", "xls", "xlsx", "xlsm"]:
                    self.file_types["tabular"].append(path)
                elif ext in ["docx", "doc"]:
                    self.file_types["text"].append(path)
                elif ext in [".txt"]:
                    self.file_types["text"].append(path)
                elif ext in ["msg"]:
                    self.file_types["email"].append(path)
                else: 
                    continue
            except Exception as e:
                print(e)

        return self.file_types
    
    def get_scannable_pdfs(self, min_char=10, document_limit=None, print_text=False):
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

        try:
            for filename in all_files[:document_limit]:
                file_path = os.path.join(self.path, filename)
            
                with open(file_path, "rb") as f:
                    try:                                    # Error handling added to the inner loops since some PDFs were "broken"
                        reader = PdfReader(f)
                        text = ""
                        for page in reader.pages[:2]:
                            text += page.extract_text() or ""

                        if print_text:
                            print(f"\n{file_path}\n{text}\n")

                        if len(text.strip()) >= min_char:                           # PDF Contained Digital text
                            pdf_attachments["scannable"].append(file_path)
                        else:
                            pdf_attachments["non_scannable"].append(file_path)      # PDF did NOT Contained Digital text --> Will be scanned by Tesseract later
                    except:
                        pdf_attachments["broken"].append(file_path)
                        
            return pdf_attachments

        except Exception as e:
            pdf_attachments["non_scannable"].append(file_path)
            print(f"❌ Error: {e}")

    def get_relevant_images(self, min_file_size = 20, min_width=300.0, min_height=200.0, min_words=10, document_limit=None):
        """
        Applies policies to identify, whether PNG/JPS/JPEG attachements
        contain any relevant text to parse. Otherwise removes them.
        """
        pytesseract.pytesseract.tesseract_cmd = tesseract_path  # Path to Tesseract executable

        self.images = {
            "relevant": [],
            "not_relevant": [],
            "failed": []
        }
        
        all_files = self.file_types["images"]

        if not document_limit:
            document_limit = len(self.file_types["images"])


        try:
            for file in all_files[:document_limit]:
                file_path = os.path.join(self.path, file)

                # Check filesize
                file_size = os.path.getsize(file_path) / 1024
                if file_size < min_file_size:
                    self.images["not_relevant"].append(file_path)
                    continue

                with Image.open(file_path) as img:

                    # Check size
                    width, height = img.size
                    if width < min_width or height < min_height:
                        self.images["not_relevant"].append(file_path)
                        continue

                    # Check aspect ratio
                    a_ratio = height / width
                    if 0.9 < a_ratio < 1.1:
                        self.images["not_relevant"].append(file_path)
                        continue

                    # Check if file has enough text
                    text = pytesseract.image_to_string(file_path)
                    words = len(text.strip().split())
                    if words < min_words:
                        self.images["not_relevant"].append(file_path)
                        continue

                self.images["relevant"].append(file_path)

        except Exception as e:
            self.images["failed"].append(file_path)
            print(e)

        return self.images
    
    def save_relevant_images(self):
        """Save each image path in self.images['relevant'] into the configured output directory."""
        try:
            # Ensure the output directory exists
            os.makedirs(relevant_images_dir, exist_ok=True)

            # Iterate through all relevant image file paths
            for img_path in self.images.get("relevant", []):
                # Derive filename and output path
                filename = os.path.basename(img_path)
                output_path = os.path.join(relevant_images_dir, filename)

                # Open and save the image
                with Image.open(img_path) as img:
                    img.save(output_path)
            return True
        except Exception as e:
            print(f"Error saving relevant images: {e}")
            return False