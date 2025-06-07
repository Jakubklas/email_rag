import boto3
from config import *


def push_to_s3(BUCKET, PREFIX, folder_path):
    client = boto3.client("s3")

    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        raise ValueError(f"The folder path '{folder_path}' does not exist or is not a directory.")

    files = [os.path.join(folder_path, file) for file in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, file))]

    for idx, file in enumerate(files):
        KEY = os.path.basename(file)
        with open(file, "rb") as f:
            client.put_object(
                Bucket=BUCKET,
                Key=os.path.join(PREFIX, KEY),
                Body=f
            )
        if idx % 10 == 0:
            print(f"Pushed {idx} files to S3")

def pull_from_s3(BUCKET, PREFIX, download_dir):
    client = boto3.client("s3")

    if not os.path.exists(download_dir):
        os.makedirs(download_dir)


    response = client.list_objects_v2(Bucket=BUCKET, Prefix=PREFIX)
    if "Contents" not in response:
        print("No files found in the specified S3 bucket and prefix.")
        return

    files = [content["Key"] for content in response["Contents"]]

    for idx, file_key in enumerate(files):

        file_name = os.path.basename(file_key)
        save_to = os.path.join(download_dir, file_name)

        if not file_name:
            continue

        payload = client.get_object(Bucket=BUCKET, Key=file_key)["Body"].read()

        with open(save_to, "wb") as f:
            f.write(payload)

        if idx % 10 == 0:
            print(f"Downloaded {idx + 1} files from S3 to {download_dir}")