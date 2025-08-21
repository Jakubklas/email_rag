from config.config import *


def rewrite_query(raw_query: str, mem_summary: str, llm_client) -> str:
    """
    If the user's query is a pronoun-heavy follow-up, 
    expand it using the mid-term memory summary.
    """
    # Only fire when it looks like a follow-up
    if True:  # raw_query.lower().startswith(("what about", "and", "also", "how about")):
        resp = llm_client.chat.completions.create(
            model=MEDIUM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a query-rewriter. Rewrite the user's follow-up question as it relates to"
                        "the conversation summary. Write a short, standalone question optimized for semantic search retrieval."
                    )
                },
                {"role": "system", "content": f"[Conversation Summary]\n{mem_summary or ''}"},
                {"role": "user", "content": raw_query}
            ],
            temperature=0.0,
            max_tokens=64
        )
        return resp.choices[0].message.content.strip()
    else:
        return raw_query