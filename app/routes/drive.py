from datetime import datetime
import uuid
from flask import Blueprint, Response, jsonify
from flask import request, redirect, url_for, render_template, flash, send_file
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
import os
import tempfile
import boto3
import time
from app.classes.helpers import HelperClass
from app.models.user_config import UserConfig
from dotenv import load_dotenv
ongoing_uploads = {}  # Dictionary to track ongoing uploads

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
    
def create_drive_blp(socketio):
    load_dotenv()
    blp = Blueprint('drive', 'drive')
    # print(f"Using endpoint: {s3_client.meta.endpoint_url}")
    # print(f"Using region: {s3_client.meta.region_name}")
    
    @blp.route('/', methods=['GET', 'POST'])
    @login_required
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
                        sizebytes=item['Size']
                        if sizebytes:
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
                                'sizebytes':sizebytes,
                                'path': file_key,
                                'is_directory': False,
                                'size': HelperClass.format_file_size(item.get('Size', 0)),
                                'upload_date': HelperClass.convert_to_ist(item.get('LastModified', datetime.now()))
                            })
                        # Sort items by upload_date, newest first
                    if items:
                        items.sort(key=lambda x: datetime.strptime(x['upload_date'], '%Y-%m-%d %H:%M IST'), reverse=True)
                    return jsonify(items), 200

            except Exception as e:
                print(f"Error: {str(e)}")  # Log the error
                return jsonify({'error': str(e)}), 500
            
        if current_user.is_authenticated:
            if current_user.isAdmin:
                folder_path = ''
            else:
                folder_path = HelperClass.create_or_get_user_folder(get_s3_client(),current_user.id)
        return render_template('index.html', home_page=True,flash_message = message,folder_path=folder_path)
    
    
    @blp.route('/upload', methods=['GET'])
    def upload_get():
        """Render the upload page."""
        if current_user.is_authenticated:
            return render_template('upload.html')
        else:
            flash('You have to login to view this page !!')
            return redirect(url_for('auth.login'))
    
    @blp.route('/get_presigned_url', methods=['POST'])
    def get_presigned_url():
        """Generate a presigned URL for direct S3 upload."""
        if not current_user.is_authenticated:
            return jsonify({'error': 'Authentication required'}), 401
        
        try:
            # Get info about the file to be uploaded
            original_filename = request.form.get('filename', '')
            total_size = int(request.form.get('filesize', 0))
            sid = request.form.get('sid', '')
            
            if not original_filename or not total_size or not sid:
                return jsonify({'error': 'Missing required parameters'}), 400
            
            # Generate secure filename
            s3_client = get_s3_client()
            foldername = HelperClass.create_or_get_user_folder(s3_client, current_user.id)
            
            # Check if file can be uploaded (storage limits)
            can_be_uploaded, message = HelperClass.file_can_be_uploaded(s3_client, current_user.id, total_size)
            if not can_be_uploaded:
                return jsonify({'message': 'No Storage'}), 200
            
            # Create unique filename
            secure_name = secure_filename(original_filename)
            unique_id = str(uuid.uuid4())
            filename = f"{unique_id}_{secure_name}"  # UUID-prefixed filename
            folder_file = foldername + '/' + filename
            
            # Generate presigned URL
            presigned_url = create_presigned_post(s3_client, BUCKET_NAME, folder_file, 
                                                fields=None, conditions=None, expiration=3600)
            
            # Register this pending upload
            ongoing_uploads[sid] = {
                'path': folder_file,
                'filename': filename,
                'original_filename': original_filename,
                'cancelled': False,
                'total_size': total_size
            }
            
            # Add path to response for client reference
            presigned_url['path'] = folder_file
            presigned_url['filename'] = filename
            
            return jsonify(presigned_url), 200
            
        except Exception as e:
            print(f"Error generating presigned URL: {e}")
            return jsonify({'error': str(e)}), 500


    def create_presigned_post(s3_client, bucket_name, object_name, fields=None, conditions=None, expiration=3600):
        """Generate a presigned URL for uploading a file directly to S3."""
        try:
            response = s3_client.generate_presigned_post(
                Bucket=bucket_name,
                Key=object_name,
                Fields=fields,
                Conditions=conditions,
                ExpiresIn=expiration
            )
            return response
        except Exception as e:
            print(f"Error creating presigned POST URL: {e}")
            raise e
        
    @blp.route('/get-presigned-url')
    def get_presigned_url_download():
        file_path = request.args.get('file_path')
        
        if not file_path:
            return jsonify({"error": "No file path provided"}), 400
        
        try:
            s3_client = get_s3_client()
            
            # Get original filename without prefixes
            parts = file_path.split('/')
            original_filename = parts[-1]
            clean_filename = original_filename.split('_', 1)[1] if '_' in original_filename else original_filename
            
            # Generate pre-signed URL with a 1-hour expiration
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': BUCKET_NAME,
                    'Key': file_path
                },
                ExpiresIn=3600  # URL valid for 1 hour
            )
            
            return jsonify({
                "url": url,
                "filename": clean_filename
            })
        
        except Exception as e:
            return jsonify({"error": f"Error generating URL: {str(e)}"}), 500
        
    @blp.route('/bulk-delete', methods=['POST'])
    def bulk_delete():
        file_paths = request.json.get('files', [])
        
        if not file_paths:
            return jsonify({"error": "No files selected"}), 400
        
        try:
            s3_client = get_s3_client()
            
            # Prepare objects for deletion
            objects_to_delete = [{'Key': path} for path in file_paths]
            
            # Delete objects from S3
            s3_client.delete_objects(
                Bucket=BUCKET_NAME,
                Delete={
                    'Objects': objects_to_delete,
                    'Quiet': False
                }
            )
            flash('Files deleted successfully!')
            return jsonify({
                "success": True,
                "message": f"Successfully deleted {len(file_paths)} files",
                "deleted_files": file_paths
            })
        
        except Exception as e:
            return jsonify({"error": f"Error deleting files: {str(e)}"}), 500

    # Update existing cancel_upload route to handle client-side cancellation
    @blp.route('/cancel_upload/<sid>', methods=['POST'])
    def cancel_upload_by_sid(sid):
        """Cancel the upload for a specific session ID."""
        if not sid:
            return jsonify({'error': 'Invalid session ID'}), 400
        
        if sid in ongoing_uploads:
            try:
                s3_client = get_s3_client()
                upload_info = ongoing_uploads[sid]
                
                # Mark as cancelled first
                upload_info['cancelled'] = True
                
                # Attempt to delete partial upload if it exists
                path = upload_info['path']
                try:
                    s3_client.delete_object(
                        Bucket=BUCKET_NAME,
                        Key=path
                    )
                except Exception as e:
                    print(f"Error removing partial upload: {e}")
                
                # Remove from ongoing uploads
                del ongoing_uploads[sid]
                
                return jsonify({'message': 'Upload cancelled successfully'}), 200
            
            except Exception as e:
                print(f"Unexpected error during cancellation: {e}")
                return jsonify({'error': 'Error during cancellation'}), 500
        
        return jsonify({'error': 'No ongoing upload found'}), 404


    # Add Socket.IO event handlers for client progress updates
    @socketio.on('client_upload_progress')
    def handle_client_progress(data):
        """Handle upload progress updates from client."""
        # Optional: Log or process the progress data
        # You can also broadcast this to other connected clients if needed
        pass


    @socketio.on('client_upload_complete')
    def handle_client_upload_complete(data):
        """Handle upload completion notification from client."""
        # Update any server-side records
        sid = request.sid
        if sid in ongoing_uploads:
            del ongoing_uploads[sid]
        
        # Emit to all connected clients that a new file was uploaded
        socketio.emit('file_uploaded', {
            'path': data.get('path'),
            'filename': data.get('filename'),
            'original_name': data.get('original_name')
        })
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

