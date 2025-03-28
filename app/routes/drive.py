from datetime import datetime,timezone,timedelta
import io
import threading
import uuid
from zoneinfo import ZoneInfo
from flask import Blueprint, jsonify
from flask import request, redirect, url_for, render_template, flash, send_file
from flask_login import current_user
from werkzeug.utils import secure_filename
import os
import tempfile
import boto3
from flask_socketio import emit
import time
from app.classes.helpers import HelperClass
def create_drive_blp(socketio):

    app = Blueprint('drive', 'drive')


    # Define IST timezone (UTC+5:30)
    
    WASABI_REGION = os.environ.get('WASABI_REGION', 'us-east-1')
    # Configure S3 client for Backblaze B2
    s3_client = boto3.client(
        's3',
        endpoint_url=f'https://s3.{WASABI_REGION}.wasabisys.com',
        aws_access_key_id=os.environ.get('WASABI_ACCESS_KEY'),
        aws_secret_access_key=os.environ.get('WASABI_SECRET_KEY'),
        region_name=WASABI_REGION
    )

    # Configure your bucket name
    BUCKET_NAME = os.environ.get('BUCKET_NAME', 'your-bucket-name')

    def convert_to_ist(dt):
        """Convert datetime to IST timezone and format as string"""    
        # If no timezone info, assume UTC
        IST = timezone(timedelta(hours=5, minutes=30))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        # Convert to IST
        ist_time = dt.astimezone(IST)
        
        # Return formatted string
        return ist_time.strftime('%Y-%m-%d %H:%M IST')


    def is_uuid_prefixed(filename):
        """Check if filename starts with a UUID pattern"""
        parts = filename.split('_', 1)
        if len(parts) < 2:
            return False
        
        uuid_part = parts[0]
        # Simple check to see if the first part could be a UUID
        # (this is not a comprehensive UUID check)
        return len(uuid_part) == 36 and uuid_part.count('-') == 4
    
    @app.route('/', methods=['GET','POST'])
    def index():
        """Fetch the list of files from S3 in real-time."""
        try:
            if current_user.is_authenticated:
                foldername = HelperClass.create_or_get_user_folder(s3_client,current_user.id,current_user.username)
                response = s3_client.list_objects_v2(Bucket=BUCKET_NAME,Prefix=foldername)
                if current_user.isAdmin:
                    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
            files = []

            if 'Contents' in response:
                for item in response['Contents']:
                    file = item['Key']
                    filename = file.split('/')[-1]
                    if filename == '':
                        continue
                    # Check if this is a UUID-prefixed file
                    if is_uuid_prefixed(filename):
                        file_id, original_filename = filename.split('_', 1)
                    else:
                        file_id = "existing"
                        original_filename = filename

                    # Get file metadata
                    try:
                        head_response = s3_client.head_object(Bucket=BUCKET_NAME, Key=filename)
                        content_type = head_response.get('ContentType', 'application/octet-stream')
                    except:
                        content_type = 'application/octet-stream'

                    files.append({
                        'id': file_id,
                        'filename': filename,
                        'original_filename': original_filename,
                        'mimetype': content_type,
                        'size': item.get('Size', 0),
                        'upload_date': convert_to_ist(item.get('LastModified', datetime.now()))
                    })

                # Sort by newest first
                files.sort(key=lambda x: x['upload_date'], reverse=True)

        except Exception as e:
            return jsonify({'error': f'Error retrieving files: {str(e)}'}), 500
            
        if request.method == 'POST':
            return jsonify(files)
        
        return render_template('index.html',files=files)
    
    class ProgressTracker:
        def __init__(self, total_size, filename, original_name, sid):
            self.total_size = total_size
            self.uploaded = 0
            self.filename = filename  # UUID filename
            self.original_name = original_name  # Original filename
            self.sid = sid
            self.start_time = time.time()  # Start time for speed calculation

        def __call__(self, bytes_amount):
            self.uploaded += bytes_amount
            elapsed_time = time.time() - self.start_time  # Time elapsed since start
            speed = self.uploaded / elapsed_time  # Bytes per second

            # Convert speed to human-readable format
            speed_str = f"{speed / 1_000_000:.2f} MB/s" if speed > 1_000_000 else f"{speed / 1_000:.2f} KB/s"

            # Estimate remaining time
            remaining_bytes = self.total_size - self.uploaded
            eta = remaining_bytes / speed if speed > 0 else 0  # Avoid division by zero
            eta_str = time.strftime("%M:%S", time.gmtime(eta))  # Convert seconds to MM:SS

            # Print progress in terminal
            print(f"\rUploading {self.filename}: {self.uploaded}/{self.total_size} bytes "
                f"({self.uploaded/self.total_size*100:.2f}%) - {speed_str} - ETA: {eta_str}",
                end="", flush=True)

            # Emit progress to frontend using Socket.IO
            socketio.emit('upload_progress', {
                'filename': self.filename,  # UUID filename
                'original_name': self.original_name,  # Original filename
                'progress': round((self.uploaded / self.total_size) * 100, 2),
                'speed': speed_str,
                'eta': eta_str,
                'uploaded_size': self.uploaded,
                'total_size': self.total_size
            }, room=self.sid)



    @app.route('/upload', methods=['POST'])
    def upload():
        if current_user.is_authenticated:
            foldername = HelperClass.create_or_get_user_folder(s3_client,current_user.id,current_user.username)
            sid = request.form.get('sid', '')  # Get Socket.IO session ID
            
            if not sid:
                return jsonify({'error': 'Invalid session ID'}), 400
            
            if 'file' not in request.files:
                return jsonify({'error': 'No file part'}), 400
            
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({'error': 'No selected file'}), 400
            
            original_filename = file.filename
            secure_name = secure_filename(file.filename)
            print("Original filename:", original_filename)
            unique_id = str(uuid.uuid4())
            print("Unique ID:", unique_id)
            filename = f"{unique_id}_{secure_name}"  # UUID-prefixed filename
            folder_file = foldername +'/'+ filename
            print("UUID filename:", filename)
            try:
                # Get file size without loading it into memory
                file.seek(0, os.SEEK_END)
                total_size = file.tell()
                file.seek(0)  # Reset position
                
                # Upload with progress tracking
                s3_client.upload_fileobj(
                    file, 
                    BUCKET_NAME, 
                    folder_file,
                    Callback=ProgressTracker(total_size, filename, original_filename, sid)
                )

                # Emit upload complete event
                socketio.emit('upload_complete', {
                    'filename': filename,  # UUID filename
                    'original_name': original_filename  # Original filename
                }, room=sid)
                
                socketio.emit('file_uploaded', {
                'filename': filename,
                'original_name': original_filename
                })

                print("\nUpload complete!")

                return jsonify({'message': 'File uploaded successfully', 'filename': filename}), 200

            except Exception as e:
                print(f"\nError uploading {filename}: {e}")
                socketio.emit('upload_error', {'filename': filename, 'error': str(e)}, room=sid)
                return jsonify({'error': str(e)}), 500


    @app.route('/download/<file_id>/<original_filename>')
    def download(file_id, original_filename):
        filename = f"{file_id}_{original_filename}"
        
        try:
            # Create a temporary file to store the downloaded content
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            
            # Get file metadata to determine content type
            head_response = s3_client.head_object(Bucket=BUCKET_NAME, Key=filename)
            content_type = head_response.get('ContentType', 'application/octet-stream')
            
            # Download the file from Backblaze B2
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
            return redirect(url_for('drive.index'))

    @app.route('/delete/<file_id>/<original_filename>', methods=['POST'])
    def delete(file_id, original_filename):
        filename = f"{file_id}_{original_filename}"
        
        try:
            # Delete file from Backblaze B2
            s3_client.delete_object(
                Bucket=BUCKET_NAME,
                Key=filename
            )
            
            flash('File deleted successfully!')
        except Exception as e:
            flash(f'Error deleting file: {str(e)}')
        
        return redirect(url_for('drive.index'))
    
    return app