from typing import List


def reconstruct_thread(index_name, thread_id, os_client, max_msgs=30):
    """
    Rebuilds the full thread based on its id. Fetches individual emails incl.
    thier parsed attachment texts based on a thread_id, sorts by date, and
    returns a list of header & body strings.
    """
    # Query the emails index with the thread_id & sort chronologically
    resp = os_client.search(
        index=index_name,
        body={
            "size": max_msgs,
            "query": {
                "bool": {
                    "must": [
                        {"term": {"thread_id": thread_id}}
                    ]
                }
            },
            "sort": [{"date": {"order": "asc"}}]
        }
    )

    # Format each hit for concatenation & add to list
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
        messages.append(headers + src.get("body", ""))
    return messages