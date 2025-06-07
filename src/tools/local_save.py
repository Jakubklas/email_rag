from config import *
import json
import boto3
from bs4 import BeautifulSoup
import re


def save_emails_as_json(output_dir, all_mail):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    for idx, email in enumerate(all_mail):
        file_id = idx
        output_file = os.path.join(output_dir, f"{file_id}.json")
        with open(output_file, "w") as f:
            json.dump(email, f, indent=2)


