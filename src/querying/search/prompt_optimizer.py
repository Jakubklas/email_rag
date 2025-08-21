from config.config import *


def optimize_prompt(raw_query, mem_summary, llm_client):
    """
    Rewrites user's query for optimal retrieval and combines
    it with the current conversation memory for context.
    """
    try:
        resp = llm_client.chat.completions.create(
            model=MEDIUM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a prompt-engineer. Rewrite the user's follow-up question as it relates to"
                        "the conversation summary. Write a short, standalone question optimized for semantic search retrieval."
                    )
                },
                {"role": "system", "content": f"[Prior Conversation Summary]\n{mem_summary or ''}"},
                {"role": "user", "content": raw_query}
            ],
            temperature=0.0,
            max_tokens=64
        )
        return resp.choices[0].message.content.strip()
    except:
        return raw_query