import os
import json
import time
from openai import OpenAI
from src.tools.safe_step import *
from config import *

@safe_step
def main(embed_chunks=False):
    client = OpenAI(api_key=SECRET_KEY)

    # Switch on/off embedding of chunks to speed up processing
    if embed_chunks:
        docs = [email_chunks_dir, attachment_chunks_dir, thread_documents_dir]
    else:
        print("[INFO] Skipping email/atatchemnt embeddings for a faste processing")
        docs = [thread_documents_dir]

    for location in docs:
        try:
            print(f"Embedding files in {location!r}…")
            
            files = [f for f in os.listdir(location) if f.endswith(".json")]
            total = len(files)
            if total == 0:
                print("  (no JSON files found)")
                continue

            for idx, filename in enumerate(files, start=1):
                try:
                    full_path = os.path.join(location, filename)

                    with open(full_path, "r", encoding="utf-8") as f_in:
                        doc = json.load(f_in)

                    doc_type = doc.get("type")
                    if doc_type in ["email", "attachment"]:
                        text = doc.get("chunk_text")
                    elif doc_type in ["thread"]:
                        text = doc.get("summary_text")
                    else:
                        text =None
                    if not text:
                        print(f"  [!] {filename} has no 'chunk_text' or 'summary_text'  field; skipping.")
                        continue

                    # Calling the Embeddings LLM model
                    resp = client.embeddings.create(
                        model=EMBEDDINGS_MODEL,
                        input=text
                    )
                    
                    # Extract the embedding vector
                    vector = resp.data[0].embedding

                    # Append vectors to the document
                    doc["embedding"] = vector

                    # Modify the original file
                    with open(full_path, "w", encoding="utf-8") as f_out:
                        json.dump(doc, f_out, ensure_ascii=False, indent=2)

                    # Report progress
                    if idx % verbosity == 0 or idx == total:
                        print(f"  → {idx}/{total} files embedded.")
                
                except Exception as e:
                    print(e)
                    print("[INFO] Sleeping 90 seconds...")
                    time.sleep(90)

        except Exception as e:
            print(f"[INFO] Failed to embed location {location}")
            print(e)

    print("All Embeddings were generated.")
    print("Ready to push to OpenSearch!")

if __name__ == "__main__":
    main()
