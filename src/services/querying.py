import os
import json
import logging
import time
from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
from opensearchpy.exceptions import TransportError, ConnectionError as OSCxnError
from requests_aws4auth import AWS4Auth
from openai import OpenAI, OpenAIError
from config import *
from src.tools.reconstruct_thread import create_llm_client, create_os_client

os_client = create_os_client(OPENSEARCH_ENDPOINT)
llm_client = create_llm_client()


def knn_search(
    query_text,
    retrieved_ids=None,
    llm_client=llm_client,
    os_client=os_client,
    size=5,
    retries=3,
    backoff=2
):
    retrieved_ids = retrieved_ids or []

    # 1) Embed the query
    try:
        q_vec = llm_client.embeddings.create(
            model=EMBEDDINGS_MODEL,
            input=query_text
        ).data[0].embedding
    except OpenAIError as e:
        logging.error(f"[knn_search] Embedding failed: {e}")
        return [], []

    # 2) Prefilter: exclude any _id in `retrieved_ids` using an ids query
    prefilter_body = {
        "size": size * 10,
        "_source": False,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"type": "thread"}}
                ],
                "must_not": [
                    # Simplest way to exclude prior docs by their _id
                    {"ids": {"values": retrieved_ids}}
                ]
            }
        }
    }
    pf_resp = os_client.search(index=INDEX_NAME, body=prefilter_body)
    candidate_ids = [hit["_id"] for hit in pf_resp["hits"]["hits"]]
    if not candidate_ids:
        return [], []

    # 3) k-NN search using the new DSL
    knn_body = {
        "size": size,
        "query": {
            "bool": {
                "must": [
                    {
                        "knn": {
                            "embedding": {
                                "vector": q_vec,
                                "k": size,
                                "method_parameters": {"ef_search": size * 10}
                            }
                        }
                    }
                ],
                "filter": [
                    {"ids": {"values": candidate_ids}}
                ]
            }
        }
    }

    # 4) Execute with retries
    attempt = 0
    while attempt < retries:
        try:
            resp = os_client.search(
                index=INDEX_NAME,
                body=knn_body,
                request_timeout=10
            )
            hits = resp.get("hits", {}).get("hits", [])
            ids = ids = [hit["_id"] for hit in hits]
        
            return hits, ids
        
        except (TransportError, OSCxnError) as e:
            logging.warning(f"[knn_search] attempt {attempt+1} failed: {e}")
            time.sleep(backoff ** attempt)
            attempt += 1

    logging.error("[knn_search] Failed after multiple attempts.")
    return [], []


def reconstruct_thread(index_name, thread_id, max_msgs=1000, os_client=os_client):
    """
    Fetches every full email (with inlined attachments) for a given thread_id,
    sorted by date, and returns a list of header+body strings.
    """
    resp = os_client.search(
        index=index_name,
        body={
            "size": max_msgs,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"thread_id": thread_id}},
                        {"term": {"type": "email"}}
                    ]
                }
            },
            "sort": [{"date": {"order": "asc"}}]
        }
    )

    messages = []
    for hit in resp["hits"]["hits"]:
        src = hit["_source"]
        headers = (
            f"\n\nFrom: {src.get('from')}"
            f"\nTo:   {src.get('to')}"
            f"\nCC:   {src.get('cc')}"
            f"\nDate: {src.get('date')}"
            f"\nSubject: {src.get('subject')}\n\n"
        )
        # `body` now contains original email + all attachment texts
        messages.append(headers + src.get("body", ""))
    return messages


def construct_prompt(query_text, memory, retrieved_ids):
    """
    Creates LLM instructions, user query, threads/email/ettachments, etc.)
    """

    # Rebuild the memory
    if (memory is None) or (memory == ""):
        context = ""
    else:
        context = f"Summary of the most recent converstion: {memory}\n\n" + "Here is the latest query from the user: "

    # Search for relevant threads based user query
    thread_ids = []
    retrieved_ids = retrieved_ids or []

    hits, new_ids = knn_search(query_text=query_text, retrieved_ids=retrieved_ids)

    for hit, doc_id in zip(hits, new_ids):
        block = {
            "thread_id" : hit["_source"].get("thread_id"),
            "summary" : hit["_source"].get("summary_text")
        }

        thread_ids.append(block)
        retrieved_ids.append(doc_id)


    # Construct one big prompt incl. all summaries and chronologically reconstructed threads 
    full_text = []
    for idx, thread in enumerate(thread_ids, start=1):
        header = "\n\n" + "---- " + "Thread Number " + str(idx) + " ----" + "\nSummary: " + thread["summary"] + "\n\n"
        text = "".join(reconstruct_thread(INDEX_NAME, thread["thread_id"]))
        full_text.append(header + text)

    prompt = context + query_text + "\n\n".join(full_text)

    return prompt, retrieved_ids


def answer_query(query_text, memory = None, retrieved_ids=None, llm_client=llm_client):
    """
    Submits the fully loaded prompt (incl. LLM instructions, user query, threads/email/ettachments, etc.)
    and returns an answer from LLM.
    """

    # Build the prompt (Context + Instruction + Query + KNN)
    retrieved_ids = retrieved_ids or []
    prompt, retrieved_ids = construct_prompt(query_text=query_text, memory=memory, retrieved_ids=retrieved_ids)


    chat_response = llm_client.chat.completions.create(
        model=QUERY_MODEL,
        messages=[
            {
                "role": "system",
                "content": 
                    "You are a professional assistant for Redcoat Express, tasked with answering user questions strictly using internal company email threads retrieved via semantic search. " +
                    "When responding:\n\n" +
                    " • Reference only the information available to you from the provided emails. If the answer can’t be found, say so clearly.\n" +
                    " • Cite each source by naming the participants, subject line, and date (or a brief description) from which you drew your answer.\n" +
                    " • You may draft SOPs, summarize policies, or provide in‐depth explanations based solely on those emails.\n" +
                    " • Always refer to the emails as “the information available to me” (never mention that emails were provided to you directly).\n" +
                    " • Be concise, professional, and helpful. Use paragraphs to break your answer into logical sections.\n"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.2,
    )
    response = chat_response.choices[0].message.content

    memory = rebuild_memory(latest_memory=memory, latest_prompt=prompt, latest_response=response)

    return prompt, response, memory, retrieved_ids


def rebuild_memory(latest_memory = "No summery yet.", latest_prompt = "", latest_response = "", llm_client=llm_client):
    """
    Builds a running memorsummary of the chat after each user prompt by combining
    the latest memory summary + most recent prompt + most recent LLM response
    """
    prompt = (
        "Below is a brief summary of the earlier conversation between the user and the assistant:\n\n"
        f"{latest_memory}\n\n"
        "Now, here’s the most recent exchange:\n"
        f"User: {latest_prompt}\n"
        f"Assistant: {latest_response}\n\n"
        "Produce an updated, concise yet very detailed summary that integrates the prior context "
        "with this latest interaction, suitable for efficient future retrieval."
    )

    
    chat_response = llm_client.chat.completions.create(
        model=MEMORY_MODEL,
        messages=[
            {
                "role": "system",
                "content": 
                    "You are a professional assistant for Redcoat Express, tasked with answering user questions strictly using internal company email threads retrieved via semantic search. " +
                    "When responding:\n\n" +
                    " • Reference only the information available to you from the provided emails. If the answer can’t be found, say so clearly.\n" +
                    " • Cite each source by naming the participants, subject line, and date (or a brief description) from which you drew your answer.\n" +
                    " • You may draft SOPs, summarize policies, or provide in‐depth explanations based solely on those emails.\n" +
                    " • Always refer to the emails as “the information available to me” (never mention that emails were provided to you directly).\n" +
                    " • Be concise, professional, and helpful. Use paragraphs to break your answer into logical sections.\n"
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0.0,
    )

    return chat_response.choices[0].message.content


def main():
    query_text = input("Enter your query: ")
    prompt, response, memory = answer_query(query_text)
    return prompt, response, memory
