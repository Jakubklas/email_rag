import os
import json
from config import *
from PyPDF2 import PdfReader
import warnings                                                 # PDF warnings
from PyPDF2.errors import PdfReadWarning                        # PDF warnings
warnings.filterwarnings("ignore", category=PdfReadWarning)          
from pdf2image import convert_from_path                         # PDF warnings
import pytesseract                                              # Optical text recognition
from PIL import Image                                           # Image handling (e.g. opening images, metadata extraction)
import pandas as pd                                             # Tabular data handling
from docx import Document

def parse_scannable_pdfs(list_of_paths, text_output_dir, document_limit=None):
    os.makedirs(text_output_dir, exist_ok=True)

    if not document_limit:
        document_limit = len(list_of_paths)

    for idx, pdf_path in enumerate(list_of_paths[:document_limit]):
        # create output filename based on PDF name
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_path = os.path.join(text_output_dir, base_name + ".txt")

        # read and extract text
        reader = PdfReader(pdf_path)
        text_chunks = []
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text_chunks.append(extracted)

        full_text = "\n".join(text_chunks)

        # write the extracted digital text to .txt file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_text)
        
        if idx % verbosity == 0:
            print(f"Parsed {idx}/{len(list_of_paths)} scannable PDFs", flush=True)
    print("Done!\n")



def parse_image_pdf(list_of_paths, text_output_dir, document_limit=None):
    pytesseract.pytesseract.tesseract_cmd = tesseract_path  # Path to Tesseract executable
    os.makedirs(text_output_dir, exist_ok=True)

    if not document_limit:
        document_limit = len(list_of_paths)

    for idx, pdf_path in enumerate(list_of_paths[:document_limit]):
        # Create output filename based on PDF name
        filename = os.path.splitext(os.path.basename(pdf_path))[0] + ".txt"
        output_path = os.path.join(text_output_dir, filename)

        # Convert PDF to images using Poppler
        images = convert_from_path(pdf_path, poppler_path=poppler_path)
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img)

        # Write the full OCR text to output .txt file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)
        if idx % verbosity == 0:
            print(f"Parsed {idx+1}/{len(list_of_paths)} non-scannable PDFs", flush=True)
    print("Done!\n")



def parse_images(list_of_paths, text_output_dir, document_limit=None):
    os.makedirs(text_output_dir, exist_ok=True)

    if not document_limit:
        document_limit = len(list_of_paths)

    for idx, img_path in enumerate(list_of_paths[:document_limit]):
        # Create output filename based on img name
        filename = os.path.splitext(os.path.basename(img_path))[0] + ".txt"
        output_path = os.path.join(text_output_dir, filename)

        # Convert image using tesseract
        text = ""
        with Image.open(img_path) as img:
            text += pytesseract.image_to_string(img)

        # Write the full OCR text to output .txt file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(text)

        if idx % verbosity == 0:
            print(f"Parsed {idx+1}/{len(list_of_paths)} images", flush=True)
    print("Done!\n")


def parse_tabular(list_of_paths, text_output_dir, document_limit=None):
    warnings.filterwarnings("ignore", category=UserWarning)
    os.makedirs(text_output_dir, exist_ok=True)

    if not document_limit:
        document_limit = len(list_of_paths)

    for idx, tbl_path in enumerate(list_of_paths[:document_limit]):
        # Get the extension
        ext = os.path.splitext(tbl_path)[1][1:].lower()

        # Create output filename based on table name
        filename = os.path.splitext(os.path.basename(tbl_path))[0] + ".txt"
        output_path = os.path.join(text_output_dir, filename)

        # Convert tables to markdown texts
        # For CSV
        if ext == "csv":
            df = pd.read_csv(tbl_path, on_bad_lines="skip")
            md = df.to_markdown(index=False)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(md)

        # For Excel
        elif ext in ["xls", "xlsx", "xlsm"]:
            excel = pd.ExcelFile(tbl_path)
            text = {}

            for sheet in excel.sheet_names:
                df = excel.parse(sheet)
                text[f"sheet_{sheet}"] = df.to_markdown(index=False)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(text, f, indent=2)
        
        if idx % verbosity == 0:
            print(f"Parsed {idx+1}/{len(list_of_paths)} tabular files", flush=True)
    print("Done!\n")


def parse_word_docs(list_of_paths, text_output_dir, document_limit=None):
    os.makedirs(text_output_dir, exist_ok=True)

    if not document_limit:
        document_limit = len(list_of_paths)

    for idx, docx_path in enumerate(list_of_paths[:document_limit]):
        # create output filename based on DOCX name
        filename   = os.path.splitext(os.path.basename(docx_path))[0]
        output_path = os.path.join(text_output_dir, filename + ".txt")

        # read and extract text
        document = Document(docx_path)
        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        full_text  = "\n".join(paragraphs)

        # write the extracted text to .txt file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        if idx % verbosity == 0:
            print(f"Parsed {idx+1}/{len(list_of_paths)} Word docs", flush=True)
    print("Done!\n")


def save_txt_files(list_of_paths, text_output_dir, document_limit=None):
    os.makedirs(text_output_dir, exist_ok=True)
    
    if not document_limit:
        document_limit = len(list_of_paths)

    for idx, txt_path in enumerate(list_of_paths[:document_limit]):
        filename = os.path.splitext(os.path.basename(txt_path))[0]
        output_path = os.path.join(text_output_dir, filename + ".txt")

        with open(txt_path, "r", encoding="utf-8") as src:
            content = src.read()

        with open(output_path, "w", encoding="utf-8") as dst:
            dst.write(content)

        if idx % verbosity == 0:
            print(f"Copied {idx+1}/{len(list_of_paths)} txt files", flush=True)
    print("Done!\n")