from datetime import datetime, timezone, timedelta
import uuid
from flask import Blueprint
from flask import request, redirect, url_for, render_template, flash, send_file
from werkzeug.utils import secure_filename
import os
import tempfile
import boto3
from dateutil.tz import tzlocal

app = Blueprint('wasabi_drive', 'wasabi_drive')

# Wasabi configuration
WASABI_ACCESS_KEY = os.environ.get('WASABI_ACCESS_KEY')
WASABI_SECRET_KEY = os.environ.get('WASABI_SECRET_KEY')
WASABI_BUCKET_NAME = os.environ.get('WASABI_BUCKET_NAME', 'wascadrive')
WASABI_REGION = os.environ.get('WASABI_REGION', 'us-east-1')  # Choose appropriate region
UPLOAD_FOLDER = '../static/uploads'

# Define IST timezone (UTC+5:30)
IST = timezone(timedelta(hours=5, minutes=30))

# Configure S3 client for Wasabi
s3_client = boto3.client(
    's3',
    endpoint_url=f'https://s3.{WASABI_REGION}.wasabisys.com',
    aws_access_key_id=WASABI_ACCESS_KEY,
    aws_secret_access_key=WASABI_SECRET_KEY,
    region_name=WASABI_REGION
)

# Bucket name from environment variable or use default
BUCKET_NAME = WASABI_BUCKET_NAME

def convert_to_ist(dt):
    """Convert datetime to IST timezone"""
    if dt.tzinfo is None:
        # If no timezone info, assume UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def is_uuid_prefixed(filename):
    """Check if filename starts with a UUID pattern"""
    parts = filename.split('_', 1)
    if len(parts) < 2:
        return False
    
    uuid_part = parts[0]
    # Simple check to see if the first part could be a UUID
    # (this is not a comprehensive UUID check)
    return len(uuid_part) == 36 and uuid_part.count('-') == 4

@app.route('/')
def index():
    # Get list of files from Wasabi
    try:
        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
        files = []
        
        if 'Contents' in response:
            for item in response['Contents']:
                filename = item['Key']
                
                # Check if this is a UUID-prefixed file
                if is_uuid_prefixed(filename):
                    # Parse the unique ID and original filename
                    file_id, original_filename = filename.split('_', 1)
                else:
                    # For existing files without UUID prefix, use the filename itself
                    file_id = "existing"
                    original_filename = filename
                
                # Get additional file metadata
                try:
                    head_response = s3_client.head_object(Bucket=BUCKET_NAME, Key=filename)
                    content_type = head_response.get('ContentType', 'application/octet-stream')
                except:
                    # Default content type if we can't determine it
                    content_type = 'application/octet-stream'
                
                files.append({
                    'id': file_id,
                    'filename': filename,
                    'original_filename': original_filename,
                    'mimetype': content_type,
                    'size': item.get('Size', 0),
                    'upload_date': convert_to_ist(item.get('LastModified', datetime.now()))
                })
            
            # Sort files by upload date (newest first)
            files.sort(key=lambda x: x['upload_date'], reverse=True)
    
    except Exception as e:
        flash(f'Error retrieving files: {str(e)}')
        files = []
    
    return render_template('wasabi_index.html', files=files)

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('wasabi_drive.index'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('wasabi_drive.index'))
    
    # Generate a unique filename to avoid collisions
    original_filename = secure_filename(file.filename)
    unique_id = str(uuid.uuid4())
    filename = f"{unique_id}_{original_filename}"
    
    try:
        # Upload to Wasabi
        s3_client.upload_fileobj(
            file,
            BUCKET_NAME,
            filename,
            ExtraArgs={'ContentType': file.content_type}
        )
        
        flash('File uploaded successfully!')
    except Exception as e:
        flash(f'Error uploading file: {str(e)}')
    
    return redirect(url_for('wasabi_drive.index'))

@app.route('/download/<file_id>/<original_filename>')
def download(file_id, original_filename):
    filename = f"{file_id}_{original_filename}"
    
    try:
        # Create a temporary file to store the downloaded content
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        
        # Get file metadata to determine content type
        head_response = s3_client.head_object(Bucket=BUCKET_NAME, Key=filename)
        content_type = head_response.get('ContentType', 'application/octet-stream')
        
        # Download the file from Wasabi
        s3_client.download_file(BUCKET_NAME, filename, temp_file.name)
        
        # Return the file to the client
        return send_file(
            temp_file.name,
            mimetype=content_type,
            as_attachment=True,
            download_name=original_filename
        )
    except Exception as e:
        flash(f'Error downloading file: {str(e)}')
        return redirect(url_for('wasabi_drive.index'))

@app.route('/delete/<file_id>/<original_filename>', methods=['POST'])
def delete(file_id, original_filename):
    filename = f"{file_id}_{original_filename}"
    
    try:
        # Delete file from Wasabi
        s3_client.delete_object(
            Bucket=BUCKET_NAME,
            Key=filename
        )
        
        flash('File deleted successfully!')
    except Exception as e:
        flash(f'Error deleting file: {str(e)}')
    
    return redirect(url_for('wasabi_drive.index'))