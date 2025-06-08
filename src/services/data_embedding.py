import os
import json
from openai import OpenAI
from config import *

def main():
    client = OpenAI(api_key=SECRET_KEY)

    for location in [email_chunks_dir, attachment_chunks_dir, thread_documents_dir]:
        print(f"Embedding files in {location!r}…")
        
        files = [f for f in os.listdir(location) if f.endswith(".json")]
        total = len(files)
        if total == 0:
            print("  (no JSON files found)")
            continue

        for idx, filename in enumerate(files):
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
                    model="text-embedding-ada-002",
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
                if (idx + 1) % verbosity == 0 or (idx + 1) == total:
                    print(f"  → {idx+1}/{total} files processed")
            
            except Exception as e:
                print(e)

    print("All Embeddings were generated.")
    print("Ready to push to OpenSearch!")

if __name__ == "__main__":
    main()
