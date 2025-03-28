from datetime import datetime
import uuid
from flask import Blueprint, jsonify
from flask import request, redirect, url_for, render_template, flash, send_file
from flask_login import current_user
from werkzeug.utils import secure_filename
import os
import tempfile
import boto3
import time
from app.classes.helpers import HelperClass

def create_drive_blp(socketio):

    blp = Blueprint('drive', 'drive')

    ongoing_uploads = {}  # Dictionary to track ongoing uploads
    
    WASABI_REGION = os.environ.get('WASABI_REGION', 'us-east-1')
    # Configure your bucket name
    BUCKET_NAME = os.environ.get('BUCKET_NAME', 'your-bucket-name')
    # Configure S3 client for Backblaze B2
    s3_client = boto3.client(
        's3',
        endpoint_url=f'https://s3.{WASABI_REGION}.wasabisys.com',
        aws_access_key_id=os.environ.get('WASABI_ACCESS_KEY'),
        aws_secret_access_key=os.environ.get('WASABI_SECRET_KEY'),
        region_name=WASABI_REGION
    )

    @blp.route('/', methods=['GET', 'POST'])
    def index():
        if request.method == 'POST':

            try:
                if not current_user.is_authenticated:
                    return jsonify({'error': 'Unauthorized'}), 403

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
                            parts = folder_name.split('_', 1)
                            if len(parts) == 2 and parts[0].isdigit():
                                folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_name + "/")
                        
                                last_modified = None
                                if 'Contents' in folder_files:
                                    last_modified = max(
                                        [file['LastModified'] for file in folder_files['Contents']],
                                        default=None
                                    )
                                user_folders.append({
                                    'name': parts[1],
                                    'path': folder_name,
                                    'is_directory': True,
                                    'upload_date': HelperClass.convert_to_ist(last_modified) if last_modified else None
                                })
                    return jsonify(user_folders), 200

                # Fetch directories and files inside the folder
                response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_path)
                folders = set()  # To store unique folder names
                items = []

                if 'Contents' in response:
                    for item in response['Contents']:
                        file_key = item['Key']
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

        return render_template('index.html', home_page=True)
    
    
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
        print(Exception)

    @blp.route('/upload', methods=['POST'])
    def upload_post():
        if current_user.is_authenticated:
            try:
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
                unique_id = str(uuid.uuid4())
                filename = f"{unique_id}_{secure_name}"  # UUID-prefixed filename
                folder_file = foldername +'/'+ filename
                try:
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
    
    @blp.route('/download/<file_id>/<original_filename>')
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

    @blp.route('/delete/<file_id>/<original_filename>', methods=['POST'])
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
    

        
    return blp

