from config import *
from src.tools.safe_step import *
from src.tools.chunking import chunk_text
from src.tools.attachemnt_classifier import AttachmentClassifier
from src.tools.parsing import parse_scannable_pdfs, parse_image_pdf, parse_images, parse_tabular, parse_word_docs, save_txt_files
from src.tools.thread_summaries import build_thread_docs, build_thread_map, normalize_id
from src.tools.async_thread_summaries import *
import json
from collections import defaultdict
from openai import OpenAI


@safe_step
def process_attachments(save_rel_img=True, parse_rel_img=True, parse_scan_pdf=True, parse_non_scan_pdf=True, parse_word=True, parse_tab=True, parse_txt=True):
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
    if save_rel_img:
        print("Saving relevant images...")
        if not classifier.save_relevant_images():
            print("Error saving relevant images...")
    
    # # -----PARSING RELEVANT IMAGES---------------------------------
    if parse_rel_img:
        print("Parsing relevant images...")
        parse_images(img_categories["relevant"], parsed_attachments_dir)

    # # -----PARSING SCANNABLE PDFs---------------------------------
    if parse_scan_pdf:
        print("Parsing scannable PDFs...")
        parse_scannable_pdfs(pdf_categories["scannable"], parsed_attachments_dir)

    # # -----PARSING NON-SCANNABLE PDFs---------------------------------
    if parse_non_scan_pdf:
        print("Parsing non-scannable PDFs...")
        parse_image_pdf(pdf_categories["non_scannable"], parsed_attachments_dir)

    # -----PARSING TABULAR DATA---------------------------------
    if parse_tab:
        print("Parsing tabular data...")
        parse_tabular(categories["tabular"], parsed_attachments_dir)

    # -----PARSING WORD DOCUMNETS---------------------------------
    if parse_word:
        print("Parsing word documents...")
        parse_word_docs(categories["word_doc"], parsed_attachments_dir)

    # -----SAVING TXT DOCUMNETS---------------------------------
    if parse_txt:
        print("Parsing text documents...")
        save_txt_files(categories["text"], parsed_attachments_dir)


@safe_step
def annotate_threads(emails_dir: str, thread_map: dict[str, str]) -> None:
    """
    Reads each email JSON in emails_dir, looks up its thread_id
    in thread_map, and writes it back into the file.
    """
    for fn in os.listdir(emails_dir):
        if not fn.endswith(".json"):
            continue

        path = os.path.join(emails_dir, fn)
        with open(path, "r+", encoding="utf-8") as f:
            content = json.load(f)

            # normalize exactly as in build_thread_map
            msg_id = (content.get("message_id") or "").strip("<>").lower()
            content["thread_id"] = thread_map.get(msg_id)

            # overwrite with new thread_id
            f.seek(0)
            f.truncate()
            json.dump(content, f, ensure_ascii=False, indent=2)


@safe_step
def merge_emails_and_attachments():
    """
    For each email JSON in `emails_dir`, find all .txt files in `parsed_attachments_dir`
    whose filename embeds that email's message_id (_id_<message_id>_id_*.txt),
    read their text, append under separators, and write a merged JSON to `email_attachment_dir`.
    """
    os.makedirs(email_attachment_dir, exist_ok=True)

    # Build map: message_id_normalized → [parsed txt attachment paths]
    attach_map: dict[str, list[str]] = defaultdict(list)
    for fn in os.listdir(parsed_attachments_dir):
        if not fn.endswith(".txt"):
            continue
        parts = fn.split("_id_")
        if len(parts) < 3:
            continue
        raw_msg_id = parts[1]
        msg_id = normalize_id(raw_msg_id)
        attach_map[msg_id].append(os.path.join(parsed_attachments_dir, fn))

    # Process each email
    email_files = [f for f in os.listdir(emails_dir) if f.endswith(".json")]
    for idx, fn in enumerate(email_files, start=1):
        email_path = os.path.join(emails_dir, fn)
        with open(email_path, "r", encoding="utf-8") as f:
            email = json.load(f)

        # normalize the message_id the same way
        msg_id = normalize_id(email.get("message_id", ""))

        # Start with the original body
        merged_body = email.get("body", "")

        # Append every parsed‐attachment text for this message
        for att_path in attach_map.get(msg_id, []):
            try:
                with open(att_path, "r", encoding="utf-8") as af:
                    att_text = af.read()
                merged_body += (
                    f"\n\n--- Attachment: {os.path.basename(att_path)} ---\n"
                    f"{att_text}"
                )
            except UnicodeDecodeError:
                continue

        # Rebuild the document with the merged body
        merged = {
            **{k: v for k, v in email.items() if k != "body"},
            "body": merged_body,
            "doc_id": f"e_{msg_id}"
        }

        out_path = os.path.join(email_attachment_dir, fn)
        with open(out_path, "w", encoding="utf-8") as outf:
            json.dump(merged, outf, ensure_ascii=False, indent=2)

        if idx % 100 == 0:
            print(f"   → Merged {idx}/{len(email_files)} emails")

    print(f"Done: merged {len(email_files)} emails → {email_attachment_dir}")
    

# @safe_step
# def chunk_emails():
#     try:
#         os.makedirs(email_chunks_dir, exist_ok=True)
#         path = os.listdir(emails_dir)

#         for file_idx, file in enumerate(path):
#             try:
#                 filename = os.path.join(emails_dir, file)
#                 base, _ = os.path.splitext(file)


#                 with open(filename, "r", encoding="utf-8") as f:
#                     original = json.load(f)
#                     chunks = chunk_text(original["body"])                   # Chunk the email body

#                 for chunk_idx, chunk in enumerate(chunks):                  # For each chunk, save the same JSON but replace the "body" with the chunk
#                     doc_id = f"e_{original["message_id"]}_chunk_{chunk_idx}"

#                     modified = original.copy()
#                     modified.pop("body", None)
#                     modified["chunk_text"] = chunk
#                     modified["chunk_index"] = chunk_idx
#                     modified["doc_id"] = doc_id

#                     chunk_filename = f"{doc_id}.json"
#                     output_path = os.path.join(email_chunks_dir, chunk_filename)
#                     with open(output_path, "w", encoding="utf-8") as out_f:
#                         json.dump(modified, out_f, ensure_ascii=False, indent=2)
                    
#                 if file_idx % verbosity == 0:
#                     print(f"Chunked {file_idx+1}/{len(path)} emails", flush=True)
                    
#             except Exception as e:
#                 print(f"Failed to chunk email {filename} \nbecause {e}")

#     except Exception as e:
#         print(f"Failed Email chunking \nbecause {e}")


# @safe_step
# def chunk_attachments(thread_map):
#     try:
#         os.makedirs(attachment_chunks_dir, exist_ok=True)
#         path = os.listdir(parsed_attachments_dir)

#         for file_idx, file in enumerate(path):                         # Iterating through the parsed attachments dir
#             try:
#                 full_path = os.path.join(parsed_attachments_dir, file) 

#                 attachment_dict = {
#                     "type": "attachment",
#                     "message_id": file.split(id_marker)[1],                        # Select the "message_id" part of the attachment's filename
#                     "filename": file.split(id_marker)[2],
#                     "file_type": file.split(".")[1],
#                     "chunk_index": None,
#                     "chunk_text": None
#                 }               

#                 attachment_dict["thread_id"] = thread_map.get(attachment_dict["message_id"])        # Find thte thread_id for that attachment

#                 with open(full_path, "r", encoding="utf-8") as f:
#                     text = f.read()
#                 chunks = chunk_text(text)                                        # Chunk the attachement text body

#                 for chunk_idx, chunk in enumerate(chunks):                         # For each chunk, save the same JSON but replace the "body" with the chunk
#                     modified = attachment_dict.copy()
#                     modified["chunk_text"] = chunk
#                     modified["chunk_index"] = chunk_idx

#                     doc_id = f"a_{attachment_dict["message_id"]}_{attachment_dict["filename"]}_chunk_{chunk_idx}"
#                     attachment_dict["doc_id"] = doc_id

#                     chunk_filename = f"{doc_id}.json"            # Name each chunk file "{attachment_name}_{chunk_idx}.json"
#                     output_path = os.path.join(attachment_chunks_dir, chunk_filename)
#                     with open(output_path, "w", encoding="utf-8") as out_f:
#                         json.dump(modified, out_f, ensure_ascii=False, indent=2)
                    
#                 if file_idx % verbosity == 0:
#                     print(f"Chunked {file_idx}/{len(path)} attachments.", flush=True)

#             except Exception as e:
#                 print(f"Failed to chunk attachment {full_path} \nbecause {e}")
      
#     except Exception as e:
#         print(f"Failed Attachemnt chunking \nbecause {e}")



def main(get_attachments=True, get_threads=True, sum_threads=True, join_emails_attachemnts=True, get_email_chunks=False, get_att_chunks=False):
    # ---READING ATTACHMENTS------------------------------

    if get_attachments:
        print("Processing attachments:")
        process_attachments()
        print()

    # ---ADDING THREAD_IDs--------------------------------

    if get_threads:
        print("Identifying email threads...\n")
        thread_map = build_thread_map(emails_dir)
        annotate_threads(emails_dir, thread_map)
        print()

        # ---CREATING THREAD SUMMARIES------------------------

        if sum_threads:
            print("Building thread documents...")
            thread_docs = build_thread_docs(emails_dir, parsed_attachments_dir, thread_map)
            print("Asynchronously summarizing threads...")
            asyncio.run(async_assemble_and_summarize(thread_docs, thread_documents_dir))           
            print()

    # ---MERGING EMAIL + ATTACHMENT BODIES-----------------------------------------
    if join_emails_attachemnts:
        print("Joining email bodies and attachments...")
        merge_emails_and_attachments()
        print()


    # if get_email_chunks:
    #     print("Breaking emails into small chunks...")
    #     chunk_emails()
    #     print()

    # if get_att_chunks:
    #     print("Breaking attachments into small chunks:")
    #     chunk_attachments(thread_map)

if __name__ == "__main__":
    main()
