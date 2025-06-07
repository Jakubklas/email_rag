from config import *
from src.tools.chunking import chunk_text
from src.tools.attachemnt_classifier import AttachmentClassifier
from src.tools.parsing import parse_scannable_pdfs, parse_image_pdf, parse_images, parse_tabular, parse_word_docs, save_txt_files
import json


def chunk_emails():
    try:
        os.makedirs(chunks_dir, exist_ok=True)
        path = os.listdir(email_dir)

        try:
            for file_idx, file in enumerate(path):
                filename = os.path.join(email_dir, file)
                with open(filename, "r", encoding="utf-8") as f:
                    original = json.load(f)
                    chunks = chunk_text(original["body"])           # Chunk the email body

                for chunk_idx, chunk in enumerate(chunks):                    # For each chunk, save the same JSON but replace the "body" with the chunk
                    modified = original.copy()
                    modified.pop("body", None)
                    modified["chunk_text"] = chunk
                    modified["chunk_index"] = chunk_idx

                    base, _ = os.path.splitext(file)
                    chunk_filename = f"{base}_chunk_{chunk_idx}.json"
                    output_path = os.path.join(chunks_dir, chunk_filename)
                    with open(output_path, "w", encoding="utf-8") as out_f:
                        json.dump(modified, out_f, ensure_ascii=False, indent=2)
                    
                if file_idx % verbosity == 0:
                    print(f"Chunked {file_idx+1}/{len(path)} emails", flush=True)
                
        except Exception as e:
            print(e)
        return True
    except Exception as e:
        print(e)
        return False


def process_attachments():
    classifier = AttachmentClassifier(attachments_dir, SUPPORTED_EXTENSIONS)

    # -----CATEGORIZING---------------------------------
    print("Segmenting attachments...")
    categories = classifier.get_types()                         # Segments all attachments into categories (e.g. images, pdf, tabular)
    print("Categorizing PDFs...")
    pdf_categories = classifier.get_scannable_pdfs()            # Segments all PDFs into scannable or not_scannable
    print("Categorizing Images...")
    img_categories = classifier.get_relevant_images()           # Segments all images into relevant (with text) and not_relevent (logos, not text, small resoluton, etc.)

    # -----CAT. REPORTS---------------------------------
    for i in categories:
        print(f"Count of {i}: {len(categories[i])}")
    print()
    for i in pdf_categories:
        print(f"Count of {i}: {len(pdf_categories[i])}")    
    print()
    for i in img_categories:
        print(f"Count of {i}: {len(img_categories[i])}")

    os.makedirs(parsed_attachments_dir, exist_ok=True)

    # -----SAVING RELEVANT IMAGES---------------------------------
    print("Saving relevant images...")
    if not classifier.save_relevant_images():
        print("Error saving relevant images...")
    
    # # -----PARSING RELEVANT IMAGES---------------------------------
    print("Parsing relevant images...")
    parse_images(img_categories["relevant"], parsed_attachments_dir)

    # # -----PARSING SCANNABLE---------------------------------
    print("Parsing scannable PDFs...")
    parse_scannable_pdfs(pdf_categories["scannable"], parsed_attachments_dir)

    # # -----PARSING NON-SCANNABLE---------------------------------
    print("Parsing non-scannable PDFs...")
    parse_image_pdf(pdf_categories["non_scannable"], parsed_attachments_dir)

    # -----PARSING TABULAR DATA---------------------------------
    print("Parsing tabular data...")
    parse_tabular(categories["tabular"], parsed_attachments_dir)

    # -----PARSING WORD DOCUMNETS---------------------------------
    print("Parsing word documents...")
    parse_word_docs(categories["word_doc"], parsed_attachments_dir)

    # -----SAVING TXT DOCUMNETS---------------------------------
    print("Parsing text documents...")
    save_txt_files(categories["text"], parsed_attachments_dir)


def chunk_attachments():
    try:
        os.makedirs(chunks_dir, exist_ok=True)
        path = os.listdir(parsed_attachments_dir)

        for file_idx, file in enumerate(path):                         # Iterating through the parsed attachments dir
            try:
                full_path = os.path.join(parsed_attachments_dir, file)

                attachment_dict = {
                    "thread_id": None,
                    "message_id": file.split(id_marker)[1],                        # Select the "message_id" part of the attachment's filename
                    "filename": file.split(id_marker)[2],
                    "chunk_index": None,
                    "chunk_text": None
                }               

                with open(full_path, "r", encoding="utf-8") as f:
                    text = f.read()
                chunks = chunk_text(text)                                        # Chunk the attachement text body

                for chunk_idx, chunk in enumerate(chunks):                         # For each chunk, save the same JSON but replace the "body" with the chunk
                    modified = attachment_dict.copy()
                    modified["chunk_text"] = chunk
                    modified["chunk_index"] = chunk_idx

                    chunk_filename = f"{attachment_dict["filename"]}_chunk_{chunk_idx}.json"            # Name each chunk file "{attachment_name}_{chunk_idx}.json"
                    output_path = os.path.join(chunks_dir, chunk_filename)
                    with open(output_path, "w", encoding="utf-8") as out_f:
                        json.dump(modified, out_f, ensure_ascii=False, indent=2)
                    
                if file_idx % verbosity == 0:
                    print(f"Chunked {file_idx}/{len(path)} attachments.", flush=True)  
            except Exception as e:
                raise
      
    except Exception as e:
        raise
        return False

def main():
    print("Breaking emails into small chunks:")
    chunk_emails()
    print()
    print()
    print("Processing attachments:")
    process_attachments()
    print("Breaking attachments into small chunks:")
    chunk_attachments()



if __name__ == "__main__":
    main()


# python -m src.services.data_processing
