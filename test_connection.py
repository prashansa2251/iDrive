import boto3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Print credentials (first few characters only for security)
print(f"Access Key ID: {os.environ.get('WASABI_ACCESS_KEY')[:5]}...")
print(f"Bucket: {os.environ.get('WASABI_BUCKET_NAME')}")
WASABI_REGION = os.environ.get('WASABI_REGION')
# Initialize S3 client
s3_client = boto3.client(
        's3',
        endpoint_url=f'https://s3.{WASABI_REGION}.wasabisys.com',
        aws_access_key_id=os.environ.get('WASABI_ACCESS_KEY'),
        aws_secret_access_key=os.environ.get('WASABI_SECRET_KEY'),
        region_name=WASABI_REGION
    )

# Try to list objects in the bucket
try:
    response = s3_client.list_objects_v2(Bucket=os.environ.get('WASABI_BUCKET_NAME'),MaxKeys=1)
    print("Connection successful!")
    print(f"Found {len(response.get('Contents', []))} objects in bucket")
except Exception as e:
    print(f"Error connecting to Backblaze B2: {str(e)}")
