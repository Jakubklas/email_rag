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

# Legacy compatibility - expose the service's answer_query function
def answer_query(
    query_text: str,
    retrieved_ids: List[str] = None,
    memory: Memory = None
) -> Tuple[str, str, str, List[str], List[float]]:
    """
    Main query answering function - refactored but maintains same interface.
    """
    return service_answer_query(query_text, retrieved_ids, memory)


def main():
    """
    Test function for querying functionality.
    """
    test_query = "What are the main topics discussed in recent emails?"
    print(f"Testing query: {test_query}")
    
    try:
        result = answer_query(test_query)
        print(f"Query result: {result[1]}")  # response is at index 1
        return result
    except Exception as e:
        print(f"Query failed: {e}")
        return None


if __name__ == "__main__":
    main()