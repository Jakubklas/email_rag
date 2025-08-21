import logging
from typing import List, Tuple
from .query_service import QueryService, answer_query as service_answer_query
from .memory.memory_manager import Memory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)


def answer_query(query_text, retrieved_ids = None, memory=None):
    """
    Main query answering function - orchestrates client creation, 
    user prompts & prompt optimization, knn search & retrieval,
    context reconstruction, memory & memory updates response
    generation.
    """
    return service_answer_query(query_text, retrieved_ids, memory)


def main(query):
    try:
        result = answer_query(query)
        print(f"Query result: {result[1]}")
        return result
    except Exception as e:
        print(f"Query failed: {e}")
        return None


if __name__ == "__main__":
    main()