import boto3
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Print credentials (first few characters only for security)
print(f"Access Key ID: {os.environ.get('AWS_ACCESS_KEY_ID')[:5]}...")
print(f"Bucket: {os.environ.get('BUCKET_NAME')}")
print(f"Endpoint: {os.environ.get('AWS_ENDPOINT_URL')}")

# Initialize S3 client
s3_client = boto3.client(
    's3',
    endpoint_url=os.environ.get('AWS_ENDPOINT_URL'),
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
)

# Try to list objects in the bucket
try:
    response = s3_client.list_objects_v2(Bucket=os.environ.get('BUCKET_NAME'))
    print("Connection successful!")
    print(f"Found {len(response.get('Contents', []))} objects in bucket")
except Exception as e:
    print(f"Error connecting to Backblaze B2: {str(e)}")