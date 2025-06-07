import boto3
import json
from config import *
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth


# AWS Authentication
session = boto3.Session()
credentials = session.get_credentials()
aws_auth = AWS4Auth(credentials.access_key, credentials.secret_key, AWS_REGION, "es", session_token=credentials.token) #TODO Get around this

# Initialize OpenSearch client
opensearch_client = OpenSearch(
    hosts=[{"host": OPENSEARCH_ENDPOINT, "port": 443}],
    http_auth=aws_auth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
)

# Initialize S3 client
s3_client = boto3.client("s3")

def retrieve_files_from_s3(bucket_name):
    """Retrieve JSON files from S3."""
    response = s3_client.list_objects_v2(Bucket=bucket_name)
    for obj in response.get("Contents", []):
        file_key = obj["Key"]
        if file_key.endswith(".json"):
            file_content = s3_client.get_object(Bucket=bucket_name, Key=file_key)["Body"].read().decode("utf-8")
            yield json.loads(file_content)

def push_to_opensearch(index_name, documents):
    """Push documents to OpenSearch."""
    for doc_id, document in enumerate(documents):
        response = opensearch_client.index(
            index=index_name,
            id=doc_id,
            body=document,
        )
        print(f"Document {doc_id} indexed: {response}")

def knn_search(index_name, query_vector, top_n=5):
    """Perform KNN search in OpenSearch."""
    query = {
        "size": top_n,
        "query": {
            "knn": {
                "embeddings": {
                    "vector": query_vector,
                    "k": top_n
                }
            }
        }
    }
    response = opensearch_client.search(index=index_name, body=query)
    return response["hits"]["hits"]

def main():
    # Step 1: Retrieve files from S3
    print("Retrieving files from S3...")
    documents = retrieve_files_from_s3(S3_BUCKET_NAME)

    # Step 2: Push documents to OpenSearch
    print("Pushing documents to OpenSearch...")
    push_to_opensearch(INDEX_NAME, documents)

    # Step 3: Perform KNN search (example query)
    print("Performing KNN search...")
    example_query_vector = [0.1, 0.2, 0.3, 0.4, 0.5]  # Replace with your query vector
    results = knn_search(INDEX_NAME, example_query_vector, top_n=5)
    print("Search results:", results)

if __name__ == "__main__":
    main()