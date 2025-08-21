from typing import List


def reconstruct_thread(
    index_name: str, 
    thread_id: str, 
    os_client,
    max_msgs: int = 1000
) -> List[str]:
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
                        {"term": {"thread_id": thread_id}}
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
        messages.append(headers + src.get("body", ""))
    return messages