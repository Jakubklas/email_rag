from opensearchpy import OpenSearch, RequestsHttpConnection

from src.utils.safe_step import safe_step
from config.config import *


@safe_step
def create_os_client():
    """
    Authenticates with & creates a client for OpenSearch
    vector store.
    """
    # Create the client
    client = OpenSearch(
        hosts=[{"host": OPENSEARCH_ENDPOINT.replace("https://", ""), "port": 443}],
        http_auth=(MASTER_USER, MASTER_PASSWORD),
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
        max_retries=3,
        retry_on_timeout=True,
    )

    # Testing that it works
    indecies = client.cat.indices(format="json")
    for i in indecies[:1]:
        if i:
            print("Client created successfully.")
            return client
        else:
            print("Error. Client creation failed.")
            return False

