import os
import json
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from requests_aws4auth import AWS4Auth
from openai import OpenAI
from config import *
from src.tools.reconstruct_thread import create_llm_client, create_os_client

os_client = create_os_client(OPENSEARCH_ENDPOINT)
llm_client = create_llm_client()

def knn_search(query_text, llm_client=llm_client, os_client=os_client, size=5):
    """
    Queries OpenSearch for thread documents using the KNN vector search and returns
    the full JSON document.
    """
    q_vec = llm_client.embeddings.create(
        model="text-embedding-ada-002",
        input=query_text
    ).data[0].embedding

    body = {
        "size": size,
        "query": {
            "bool": {
                "filter": [
                    { "term": { "type": "thread" } }
                ],
                "must": [
                    {
                        "knn": {
                            "embedding": {
                                "vector": q_vec,
                                "k": size
                            }
                        }
                    }
                ]
            }
        }
    }
    return os_client.search(index=INDEX_NAME, body=body)["hits"]["hits"]


def reconstruct_thread(INDEX_NAME, thread_id, max_chunks=1000):
    """
    Queries OpenSearch for email and attachment chunks based on the provided "thread_id"
    and reconstruct the full thread in a chronological order as a list of strigs. Each 
    string contains of email headers + email body + email links + attachment chunks.
    """
    os_client = create_os_client(OPENSEARCH_ENDPOINT)

    response = os_client.search(
        index=INDEX_NAME,
        body={
            "size": max_chunks,
            "query": {
                "bool": {
                    "must": [
                        {"terms": {"type":      ["email", "attachment"]}},
                        {"term":  {"thread_id": thread_id}}
                    ]
                }
            },
            "sort": [
                {"date":        {"order": "asc"}},    # earliest first
                {"message_id":  {"order": "asc"}},    # group docs by message
                {"type":        {"order": "desc"}},   # email before attachment
                {"chunk_index": {"order": "asc"}}     # then by chunk
            ]
        }
    )

    hits = response["hits"]["hits"]
    messages = []
    msg_index_by_id = {}                          # CHANGED: map message_id → index in messages

    for hit in hits:
        src = hit["_source"]

        if src["type"] == "email":
            # Format the email header/body
            attachment_files = [a.split("_id_")[2] for a in src.get("attachments", [])]

            block = [
                f"From: {src.get('from')}",
                f"To: {src.get('to')}",
                f"CC: {src.get('cc')}",
                f"Date: {src.get('date')}",
                f"Subject: {src.get('subject')}",
                f"Attachments: {attachment_files}",
                "",
                src.get('chunk_text', '').replace("<END OF MESSAGE>", "").strip()
            ]
            text_block = "\n".join(block) + "\n"

            # Single URL section
            if src.get("links"):
                text_block += "\n--- Included URL Links ---\n"
                for key, val in src["links"].items():
                    text_block += f"{key}: {val}\n"

            # Append and record where this email landed
            messages.append(text_block)
            msg_index_by_id[src["message_id"]] = len(messages) - 1  # CHANGED

        elif src["type"] == "attachment":
            # Look up the correct email index
            idx = msg_index_by_id.get(src["message_id"], None)      # CHANGED
            if idx is None:
                # no parent email found? skip or handle error
                continue

            sep = f"\n--- Attachment: {src.get('filename')} (chunk {src.get('chunk_index')}) ---\n"
            messages[idx] += sep + src.get("chunk_text", "")       # CHANGED

    return messages


def construct_prompt(query_text, llm_instruction, llm_client=llm_client, os_client=llm_client):
    """
    Creates  LLM instructions, user query, threads/email/ettachments, etc.)
    """
    # Search for relevant threads based user query
    thread_ids = []
    for i in knn_search(query_text):
        block = {
            "thread_id" : i["_source"].get("thread_id"),
            "summary" : i["_source"].get("summary_text")
        }

        thread_ids.append(block)

    # Construct one big prompt incl. all summaries and chronologically reconstructed threads 
    full_text = []
    for idx, thread in enumerate(thread_ids, start=1):
        header = "\n\n" + "---- " + "Thread Number " + str(idx) + " ----" + "\nSummary: " + block["summary"] + "\n\n"
        text = "".join(reconstruct_thread(INDEX_NAME, thread["thread_id"]))
        full_text.append(header + text)

    return llm_instruction + query_text + "\n\n".join(full_text)


def answer_query(query_text, llm_client=llm_client):
    """
    Submits the fully loaded prompt (incl. LLM instructions, user query, threads/email/ettachments, etc.)
    and returns an answer from LLM.
    """
    prompt = construct_prompt(query_text, llm_instruction)
    
    chat_response   = llm_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {"role":"system",
                        "content":"Follow the instructions provided in the query text and briefly state your sources."},
                        {"role":"user", "content": prompt}
                    ],
                    temperature=0.2,
                )
    
    return chat_response.choices[0].message.content



def main():
    query_text = input("Enter your query: ")
    answer = answer_query(query_text)
    return answer
