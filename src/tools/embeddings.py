from openai import OpenAI
import os
import json
from config import *

def get_embeddings(num_docs=99999, email_dir = emails_dir):
    client = OpenAI(api_key=SECRET_KEY)
    docs = []

    # Get and sort files to get the same order each time
    filenames = sorted(os.listdir(email_dir))
    print(f"Extracted {len(filenames)} email files.")

    # Iterate through sorted files
    for idx, filename in enumerate(filenames):
        file_path = os.path.join(email_dir, filename)
        
        # Read each JSON and parse convert to a string (for a more natural embedding)
        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
            docs.append(f"From: {data['from']}\nTo: {data['to']}\nSubject: {data['subject']}\nBody: {data['body']}")
        
        # Limit the number of processed emails if needed
        if idx == num_docs - 1:
            break

    print(f"Number of emails in list: {len(docs)}")

    # Generate embeddings 
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=docs
    )
    
    print(f"Number of embeddings created: {len(response.data)}")

    # Add the new embeddings to the email files 
    for idx, filename in enumerate(filenames):
        file_path = os.path.join(email_dir, filename)

        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)
        
        data["embedding"] = response.data[idx].embedding

        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
        
        if idx == num_docs - 1:
            print("JSON files were updated with embeddings")
            break
