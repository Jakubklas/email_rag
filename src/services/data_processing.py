from config import *
from src.tools.chunking import chunk_text
from src.tools.attachemnt_classifier import AttachmentClassifier
from src.tools.parsing import parse_scannable_pdfs, parse_image_pdf, parse_images, parse_tabular, parse_word_docs, save_txt_files
from src.tools.thread_map import build_thread_map
from src.tools.thread_summaries import build_thread_docs
import json
from openai import OpenAI



def annotate_threads(emails_dir, thread_map):
    for filename in os.listdir(emails_dir):
        full_path = os.path.join(emails_dir, filename)

        with open(full_path, "r+", encoding="utf-8") as f:
            content = json.load(f)
            msg_id = (content.get("message_id") or "").strip("<>").lower()
            content["thread_id"] = thread_map.get(msg_id)
            # overwrite
            f.seek(0); f.truncate()                                                         # TODO: How does this overwriting work?
            json.dump(content, f, ensure_ascii=False, indent=2)


def chunk_emails():
    try:
        os.makedirs(email_chunks_dir, exist_ok=True)
        path = os.listdir(emails_dir)

        try:
            for file_idx, file in enumerate(path):
                filename = os.path.join(emails_dir, file)
                base, _ = os.path.splitext(file)


                with open(filename, "r", encoding="utf-8") as f:
                    original = json.load(f)
                    chunks = chunk_text(original["body"])           # Chunk the email body

                for chunk_idx, chunk in enumerate(chunks):                  # For each chunk, save the same JSON but replace the "body" with the chunk
                    doc_id = f"{base}_chunk_{chunk_idx}"
                    
                    modified = original.copy()
                    modified.pop("body", None)
                    modified["chunk_text"] = chunk
                    modified["chunk_index"] = chunk_idx
                    modified["doc_id"] = doc_id

                    chunk_filename = f"{doc_id}.json"
                    output_path = os.path.join(email_chunks_dir, chunk_filename)
                    with open(output_path, "w", encoding="utf-8") as out_f:
                        json.dump(modified, out_f, ensure_ascii=False, indent=2)
                    
                if file_idx % verbosity == 0:
                    print(f"Chunked {file_idx+1}/{len(path)} emails", flush=True)
                
        except Exception as e:
            print("[ERROR]:")
            print(e)
        return True
    except Exception as e:
        print("[ERROR]:")
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


def chunk_attachments(thread_map):
    try:
        os.makedirs(attachment_chunks_dir, exist_ok=True)
        path = os.listdir(parsed_attachments_dir)

        for file_idx, file in enumerate(path):                         # Iterating through the parsed attachments dir
            try:
                full_path = os.path.join(parsed_attachments_dir, file) 

                attachment_dict = {
                    "type": "attachment",
                    "message_id": file.split(id_marker)[1],                        # Select the "message_id" part of the attachment's filename
                    "filename": file.split(id_marker)[2],
                    "file_type": file.split(".")[1],
                    "chunk_index": None,
                    "chunk_text": None
                }               

                attachment_dict["thread_id"] = thread_map.get(attachment_dict["message_id"])        # Find thte thread_id for that attachment

                with open(full_path, "r", encoding="utf-8") as f:
                    text = f.read()
                chunks = chunk_text(text)                                        # Chunk the attachement text body

                for chunk_idx, chunk in enumerate(chunks):                         # For each chunk, save the same JSON but replace the "body" with the chunk
                    modified = attachment_dict.copy()
                    modified["chunk_text"] = chunk
                    modified["chunk_index"] = chunk_idx

                    doc_id = f"{attachment_dict["filename"]}_chunk_{chunk_idx}"
                    attachment_dict["doc_id"] = doc_id

                    chunk_filename = f"{doc_id}.json"            # Name each chunk file "{attachment_name}_{chunk_idx}.json"
                    output_path = os.path.join(attachment_chunks_dir, chunk_filename)
                    with open(output_path, "w", encoding="utf-8") as out_f:
                        json.dump(modified, out_f, ensure_ascii=False, indent=2)
                    
                if file_idx % verbosity == 0:
                    print(f"Chunked {file_idx}/{len(path)} attachments.", flush=True)  
            except Exception as e:
                raise
      
    except Exception as e:
        raise
        return False


def assemble_and_summarize(threads, thread_documents_dir):
    """
    Saves each thread as a JSON file and replaces the texts with a
    LLM generated summary.
    """
    os.makedirs(thread_documents_dir, exist_ok=True)
    client = OpenAI(api_key=SECRET_KEY)
    counter = 0

    for thread_id, data in threads.items():
        try:
            # 1) Compute metadata
            first_date   = min(data["dates"]).isoformat()
            last_date    = max(data["dates"]).isoformat()
            subject      = next(iter(data["subjects"]))  # pick one
            participants = list(data["participants"])

            # 2) Build the full concatenated text
            full_text = "\n\n".join(data["texts"])

            # 3) Summarize with GPT-4o

            chat_response   = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role":"system",
                    "content":"Write a concise 2–3 sentence summary of this email thread, containing messages and attachemnts in a chronological order. Each block is labeled."},
                    {"role":"user", "content": full_text[:15000]}
                ],
                temperature=0.2,
            )

            summary_text = chat_response.choices[0].message.content.strip()

            thread_doc = {
                "type":             "thread",
                "thread_id":        thread_id,
                "subject":          subject,
                "participants":     participants,
                "first_date":       first_date,
                "last_date":        last_date,
                "summary_text":     summary_text,
                "doc_id":           f"{thread_id}_{counter}"
            }

            out_path = os.path.join(thread_documents_dir, f"{thread_id}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(thread_doc, f, ensure_ascii=False, indent=2)
            
            counter +=1
            if counter % verbosity == 0:
                print(f"Threads summarized {counter+1}/{len(threads)}")
        
        except Exception as e:
            print(e)


def main():
    # ---READING ATTACHMENTS------------------------------

    print("Processing attachments:")
    process_attachments()
    print()

    # ---ADDING THREAD_IDs--------------------------------

    print("Identifying email threads...\n")
    thread_map = build_thread_map(emails_dir)
    annotate_threads(emails_dir, thread_map)
    print()

    # ---CREATING THREAD SUMMARIES------------------------

    print("Mapping and summarizing threads...")
    thread_docs = build_thread_docs()
    assemble_and_summarize(thread_docs, thread_documents_dir)
    print()

    # ---CHUNKING-----------------------------------------

    print("Breaking emails into small chunks...")
    chunk_emails()
    print()

    print("Breaking attachments into small chunks:")
    chunk_attachments(thread_map)

if __name__ == "__main__":
    main()


# python -m src.services.data_processing
