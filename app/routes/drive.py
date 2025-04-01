from datetime import datetime
import uuid
from flask import Blueprint, Response, jsonify
from flask import request, redirect, url_for, render_template, flash, send_file
from flask_login import current_user
from werkzeug.utils import secure_filename
import os
import tempfile
import boto3
import time
from app.classes.helpers import HelperClass
from app.models.user_config import UserConfig
from dotenv import load_dotenv

def create_drive_blp(socketio):
    load_dotenv()
    blp = Blueprint('drive', 'drive')

    ongoing_uploads = {}  # Dictionary to track ongoing uploads
    
    WASABI_REGION = os.environ.get('WASABI_REGION', 'us-east-1')
    # Configure your bucket name
    BUCKET_NAME = os.environ.get('WASABI_BUCKET_NAME', 'your-bucket-name')
    # Configure S3 client for Backblaze B2
    def get_s3_client():
        return boto3.client(
            's3',
            endpoint_url=f'https://s3.{os.getenv("WASABI_REGION")}.wasabisys.com',
            aws_access_key_id=os.getenv('WASABI_ACCESS_KEY'),
            aws_secret_access_key=os.getenv('WASABI_SECRET_KEY'),
            region_name=os.getenv('WASABI_REGION')
        )
    print(f'https://s3.{WASABI_REGION}.wasabisys.com')
    # print(f"Using endpoint: {s3_client.meta.endpoint_url}")
    # print(f"Using region: {s3_client.meta.region_name}")
    @blp.route('/', methods=['GET', 'POST'])
    def index():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        message = HelperClass.get_message()
        if request.method == 'POST':

            try:
                s3_client = get_s3_client()
                # Get the requested folder path from JSON
                data = request.get_json()
                folder_path = data.get('path', '')

                if current_user.isAdmin and not folder_path:
                    # Admin sees only user directories
                    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Delimiter='/')
                    user_folders = []
                    if 'CommonPrefixes' in response:
                        for prefix in response['CommonPrefixes']:
                            folder_name = prefix['Prefix'].rstrip('/')
                            config = UserConfig.find_by_folder_name(folder_name)
                            allocated_storage = HelperClass.format_allocated_storage(float(config.max_size))
                            parts = folder_name.split('_', 1)
                            if len(parts) == 2 and parts[0].isdigit():
                                folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_name + "/")
                        
                                last_modified = None
                                total_size = 0  # Initialize total size

                                for file in folder_files['Contents']:
                                    if last_modified is None or file['LastModified'] > last_modified:
                                        last_modified = file['LastModified']  # Keep the latest modified date
                                    
                                    total_size += file.get('Size', 0)  # Add file size (handle missing 'Size')
                                    
                                user_folders.append({
                                    'name': parts[1],
                                    'path': folder_name,
                                    'is_directory': True,
                                    'size':HelperClass.format_file_size(total_size) if total_size else None,
                                    'allocated_storage':allocated_storage,
                                    'upload_date': HelperClass.convert_to_ist(last_modified) if last_modified else None
                                })
                    return jsonify(user_folders), 200

                # Fetch directories and files inside the folder
                response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_path)
                folders = set()  # To store unique folder names
                items = []
                user_folder_name = folder_path
                if not folder_path:
                    user_folder_name = HelperClass.create_or_get_user_folder(s3_client,current_user.id)
                    
                if 'Contents' in response:
                    for item in response['Contents']:
                        file_key = item['Key']
                        if user_folder_name not in file_key:
                            continue
                        last_modified = None
                        # Check if this is a subfolder
                        sub_path = file_key.split('/', 1)[-1]
                        if '/' in sub_path:
                            folder_name = sub_path.split('/')[0]
                            if folder_name not in folders:
                                folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_name + "/")
                                last_modified = None
                                if 'Contents' in folder_files:
                                    last_modified = max(
                                        [file['LastModified'] for file in folder_files['Contents']],
                                        default=None
                                    )
                                folders.add(folder_name)
                                items.append({
                                    'name': folder_name,
                                    'path': f"{folder_path}{folder_name}/",
                                    'is_directory': True,
                                    'upload_date': HelperClass.convert_to_ist(last_modified)
                                })
                            continue  # Skip further processing for folders
                        
                        # Process files
                        original_filename = file_key.split('/')[-1]
                        uuid_check = HelperClass.is_uuid_prefixed(original_filename)
                        if uuid_check:
                            filename = original_filename.split('_', 1)[1]
                        if not original_filename:
                            continue

                        items.append({
                            'name': filename,
                            'original_filename':original_filename,
                            'path': file_key,
                            'is_directory': False,
                            'size': HelperClass.format_file_size(item.get('Size', 0)),
                            'upload_date': HelperClass.convert_to_ist(item.get('LastModified', datetime.now()))
                        })
                        # Sort items by upload_date, newest first
                    items.sort(key=lambda x: datetime.strptime(x['upload_date'], '%Y-%m-%d %H:%M IST'), reverse=True)
                        

                return jsonify(items), 200

            except Exception as e:
                print(f"Error: {str(e)}")  # Log the error
                return jsonify({'error': str(e)}), 500

        return render_template('index.html', home_page=True,flash_message = message)
    
    
    @blp.route('/upload', methods=['GET'])
    def upload_get():
        """Render the upload page."""
        if current_user.is_authenticated:
            return render_template('upload.html')
        else:
            flash('You have to login to view this page !!')
            return redirect(url_for('auth.login'))
    
    class ProgressTracker:
        def __init__(self, total_size, filename, original_name, sid,path):
            self.total_size = total_size
            self.uploaded = 0
            self.filename = filename  # UUID filename
            self.original_name = original_name  # Original filename
            self.sid = sid
            self.path = path
            self.start_time = time.time()
            self.should_cancel = False # Start time for speed calculation
            
                    # Register this upload in ongoing uploads
            ongoing_uploads[sid] = {
                'path': path,
                'filename': filename,
                'original_filename': original_name,
                'cancelled': False,
                'total_size': total_size,
                'tracker': self
            }

        def __call__(self, bytes_amount):
            if (self.should_cancel or 
            ongoing_uploads.get(self.sid, {}).get('cancelled', False)):
            # Raise a custom exception to halt upload
                raise CancelUploadException("Upload cancelled")
            
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
                'path' :self.path,
                'filename': self.filename,  # UUID filename
                'original_name': self.original_name,  # Original filename
                'progress': round((self.uploaded / self.total_size) * 100, 2),
                'speed': speed_str,
                'eta': eta_str,
                'uploaded_size': self.uploaded,
                'total_size': self.total_size
            }, room=self.sid)
        
        def cancel(self):
            """Method to explicitly set cancellation flag"""
            self.should_cancel = True
            # Also update the global tracking
            if self.sid in ongoing_uploads:
                ongoing_uploads[self.sid]['cancelled'] = True

    class CancelUploadException(Exception):
        pass

    @blp.route('/upload', methods=['POST'])
    def upload_post():
        if current_user.is_authenticated:
            try:
                s3_client = get_s3_client()
                foldername = HelperClass.create_or_get_user_folder(s3_client,current_user.id)
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
                unique_id = str(uuid.uuid4())
                filename = f"{unique_id}_{secure_name}"  # UUID-prefixed filename
                folder_file = foldername +'/'+ filename
                try:
                    try:
                        # Get file size without loading it into memory
                        file.seek(0, os.SEEK_END)
                        total_size = file.tell()
                        file.seek(0)  # Reset position
                        can_be_uploaded,message = HelperClass.file_can_be_uploaded(s3_client,current_user.id,total_size)
                        if not can_be_uploaded:
                            flash(message)
                            return jsonify({'message':'No Storage'}),200
                        # Upload with progress tracking
                        s3_client.upload_fileobj(
                            file, 
                            BUCKET_NAME, 
                            folder_file,
                            Callback=ProgressTracker(total_size, filename, original_filename, sid,folder_file)
                        )
                    
                    except CancelUploadException:
                    # Handle intentional cancellation
                        socketio.emit('upload_cancelled', {
                            'message': 'Upload cancelled', 
                            'filename': filename,
                            'original_name': original_filename
                        }, room=sid)
                        return jsonify({'error': 'Upload cancelled'}), 400

                    # Emit upload complete event
                    socketio.emit('upload_complete', {
                        'path': folder_file,
                        'filename': filename,  # UUID filename
                        'original_name': original_filename  # Original filename
                    }, room=sid)
                    
                    socketio.emit('file_uploaded', {
                    'path': folder_file,
                    'filename': filename,
                    'original_name': original_filename
                    })
                    
                    if sid in ongoing_uploads:
                        del ongoing_uploads[sid]

                    print("\nUpload complete!")

                    return jsonify({'message': 'File uploaded successfully', 'filename': filename}), 200
                except Exception as e:
                    # Check if upload was intentionally cancelled
                    if sid in ongoing_uploads and ongoing_uploads[sid].get('cancelled', False):
                        socketio.emit('upload_cancelled', {'message': 'Upload cancelled'}, room=sid)
                        return jsonify({'error': 'Upload cancelled'}), 400
                    
                    # Handle other upload errors
                    print(f"Upload error for {filename}: {e}")
                    socketio.emit('upload_error', {
                        'filename': filename, 
                        'original_name': original_filename,
                        'error': str(e)
                    }, room=sid)
                
                    return jsonify({'error': str(e)}), 500
                
            except Exception as e:
                print(f"\nError uploading {filename}: {e}")
                socketio.emit('upload_error', {'filename': filename, 'error': str(e)}, room=sid)
                return jsonify({'error': str(e)}), 500
                
            
    @blp.route('/cancel_upload/<sid>', methods=['POST'])
    def cancel_upload_by_sid(sid):
        """Cancel the upload for a specific session ID."""
        if not sid:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        if sid in ongoing_uploads:
            try:
                s3_client = get_s3_client()
                upload_info = ongoing_uploads[sid]
                
                # Use the tracker's cancel method if exists
                tracker = upload_info.get('tracker')
                if tracker:
                    tracker.cancel()
                
                # Attempt to delete partial upload
                path = upload_info['path']
                try:
                    s3_client.delete_object(
                        Bucket=BUCKET_NAME,
                        Key=path
                    )
                except Exception as e:
                    print(f"Error removing partial upload: {e}")
                
                # Emit cancellation event
                socketio.emit('upload_cancelled', {
                    'message': 'Upload cancelled', 
                    'filename': upload_info['filename'],
                    'original_name': upload_info['original_filename']
                }, room=sid)
                
                # Remove from ongoing uploads
                del ongoing_uploads[sid]
                
                return jsonify({'message': 'Upload cancelled successfully'}), 200
            
            except Exception as e:
                print(f"Unexpected error during cancellation: {e}")
                return jsonify({'error': 'Error during cancellation'}), 500
        
        return jsonify({'error': 'No ongoing upload found'}), 404
    
    @blp.route('/download/<folder_name>/<original_filename>')
    def download(folder_name, original_filename):
        filename = f"{folder_name}/{original_filename}"
        
        try:
            s3_client = get_s3_client()
            # Create a temporary file to store the downloaded content
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            
            # Get file metadata to determine content type
            head_response = s3_client.head_object(Bucket=BUCKET_NAME, Key=filename)
            content_type = head_response.get('ContentType', 'application/octet-stream')
            
            # Download the file from Backblaze B2
            s3_client.download_file(BUCKET_NAME, filename, temp_file.name)
            filename = original_filename.split('_', 1)[1]
            
            # Return the file to the client
            return send_file(
                temp_file.name,
                mimetype=content_type,
                as_attachment=True,
                download_name=filename
            )
        except Exception as e:
            flash(f'Error downloading file: {str(e)}')
            return redirect(url_for('drive.index'))
        
    @blp.route('/stream_download/<folder_name>/<filename>')
    def stream_download(folder_name, filename):
        if current_user.is_authenticated:
            try:
                file_path = f"{folder_name}/{filename}"
                s3_client = get_s3_client()
                # Get file metadata for content type and size
                head_response = s3_client.head_object(Bucket=BUCKET_NAME, Key=file_path)
                content_type = head_response.get('ContentType', 'application/octet-stream')
                file_size = head_response.get('ContentLength', 0)
                
                # Extract original filename if needed
                original_filename = filename
                if '_' in filename:
                    original_filename = filename.split('_', 1)[1]
                
                # Define a generator to stream the file in chunks
                def generate():
                    # Get file object from S3
                    response = s3_client.get_object(Bucket=BUCKET_NAME, Key=file_path)
                    stream = response['Body']
                    
                    # Stream in chunks
                    chunk_size = 8192  # 8KB chunks
                    while True:
                        chunk = stream.read(chunk_size)
                        if not chunk:
                            break
                        yield chunk
                
                # Create a streaming response
                response = Response(
                    generate(),
                    headers={
                        'Content-Disposition': f'attachment; filename="{original_filename}"',
                        'Content-Type': content_type,
                        'Content-Length': str(file_size)
                    }
                )
                
                return response
                
            except Exception as e:
                print(f"\nError streaming download for {filename}: {e}")
                flash(f'Error downloading file: {str(e)}')
                return redirect(url_for('drive.index'))
        
        return jsonify({'error': 'Unauthorized'}), 401

    @blp.route('/delete/<folder_name>/<file_name>', methods=['POST'])
    def delete(folder_name,file_name):
        key = folder_name + '/' + file_name
        
        try:
            s3_client = get_s3_client()
            # Delete file from Backblaze B2
            s3_client.delete_object(
                Bucket=BUCKET_NAME,
                Key=key
            )
            
            flash('File deleted successfully!')
            return jsonify({'message': 'File deleted successfully!'}), 200
        except Exception as e:
            flash(f'Error deleting file: {str(e)}')
        
        # return redirect(url_for('drive.index'))
    
    @blp.route('/storage_status',methods=['POST'])
    def storage_status():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        s3_client = get_s3_client()
        storage_status = HelperClass.check_remaining_storage(s3_client,current_user.id)
        return jsonify(storage_status),200
    
    @blp.route('/version')
    def version():
        version = HelperClass.get_version()
        return {"version": version}
    return blp

