from typing import List, Dict, Any
from ..search.thread_retrieval import reconstruct_thread


def format_threads(hits: List[Dict[str, Any]], index_name: str, os_client) -> str:
    """
    Joins together retrieved threads in a worable format for LLM
    and adds the individual email texts using reconstruct_thread() func.
    Returns a single string of retrieved information.
    """
    blocks = []
    for idx, hit in enumerate(hits, start=1):
        summary = hit["_source"].get("summary_text")
        thread_id = hit["_source"].get("thread_id")
        header = (
            f"\n\n---- Thread Number {idx} ----\n"
            f"Summary: {summary}\n\n"
        )
        body = "".join(reconstruct_thread(index_name, thread_id, os_client))
        blocks.append(header + body)
    return "".join(blocks)