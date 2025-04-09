from datetime import datetime
import uuid
from flask import Blueprint, Response, jsonify, session
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

from app.models.users import User
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
    
def format_folder_name(name):
    return ' '.join(word.capitalize() for word in name.split('_'))

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
                session['current_path'] = folder_path
                # If a specific folder path is provided, this is a directory browsing request
                if folder_path:
                    # First, determine if this is the user's main folder
                    user_folder = HelperClass.create_or_get_user_folder(s3_client, current_user.id)
                    user_folder_path = user_folder + "/"
                    folder_array, superadmin = HelperClass.get_folder_array(current_user.id)
                    
                    # Check if the requested path is the user's main folder
                    is_user_main_folder = folder_path == user_folder_path
                    
                    # If admin with superadmin privileges and path is root, show all user directories
                    if current_user.isAdmin and superadmin and folder_path == '/':
                        user_folders = []
                        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Delimiter='/')
                        if 'CommonPrefixes' in response:
                            for prefix in response['CommonPrefixes']:
                                folder_name = prefix['Prefix'].rstrip('/')
                                
                                config = UserConfig.find_by_folder_name(folder_name)
                                if config:
                                    superadmin_folders = User.get_superadmin_folders()
                                    if folder_name in superadmin_folders:
                                        allocated_storage = HelperClass.get_storage_status(current_user.id)['allocated']
                                    else:
                                        allocated_storage = HelperClass.get_formatted_storage(float(config.max_size))[0]
                                    parts = folder_name.split('_', 1)
                                    if len(parts) == 2 and parts[0].isdigit():
                                        folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_name + "/")
                                        last_modified = None
                                        total_size = 0
                                        
                                        if 'Contents' in folder_files:
                                            for file in folder_files['Contents']:
                                                if last_modified is None or file['LastModified'] > last_modified:
                                                    last_modified = file['LastModified']
                                                total_size += file.get('Size', 0)
                                        
                                        user_folders.append({
                                            'name': format_folder_name(parts[1]),
                                            'path': folder_name + "/",
                                            'is_directory': True,
                                            'owner': True,
                                            'user_folder':True,
                                            'size': HelperClass.format_file_size_bytes(total_size) if total_size else None,
                                            'allocated_storage': allocated_storage,
                                            'upload_date': HelperClass.convert_to_ist(last_modified) if last_modified else None
                                        })
                        return jsonify(user_folders), 200
                    
                    # Check if this is the user's main folder - if so, we need to show both contents and subordinate folders
                    elif is_user_main_folder:
                        items = []
                        
                        # First get subfolders and files in the user's own folder
                        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_path)
                        
                        if 'Contents' in response:
                            subfolders = set()
                            
                            for item in response['Contents']:
                                sizebytes = item['Size']
                                file_key = item['Key']
                                
                                # Skip the folder entry itself
                                if file_key == folder_path:
                                    continue
                                    
                                # Extract relative path after the folder prefix
                                relative_path = file_key[len(folder_path):]
                                
                                # Check if this is a subfolder
                                if '/' in relative_path:
                                    subfolder_name = relative_path.split('/')[0]
                                    if subfolder_name and subfolder_name not in subfolders:
                                        subfolders.add(subfolder_name)
                                        subfolder_prefix = folder_path + subfolder_name + "/"
                                        subfolder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=subfolder_prefix)
                                        
                                        last_modified = None
                                        total_size = 0
                                        if 'Contents' in subfolder_files:
                                            for file in subfolder_files['Contents']:
                                                if last_modified is None or file['LastModified'] > last_modified:
                                                    last_modified = file['LastModified']
                                                total_size += file.get('Size', 0)
                                        
                                        items.append({
                                            'name':  format_folder_name(subfolder_name),
                                            'path': subfolder_prefix,
                                            'owner':True,
                                            'size': HelperClass.format_file_size_bytes(total_size),
                                            'is_directory': True,
                                            'upload_date': HelperClass.convert_to_ist(last_modified) if last_modified else None
                                        })
                                    continue
                                
                                # Process regular files
                                if sizebytes > 0:
                                    original_filename = file_key.split('/')[-1]
                                    if not original_filename:
                                        continue
                                        
                                    uuid_check = HelperClass.is_uuid_prefixed(original_filename)
                                    filename = original_filename.split('_', 1)[1] if uuid_check else original_filename
                                    
                                    items.append({
                                        'name': filename,
                                        'original_filename': original_filename,
                                        'sizebytes': sizebytes,
                                        'path': file_key,
                                        'owner': True,
                                        'is_directory': False,
                                        'size': HelperClass.format_file_size_bytes(sizebytes),
                                        'upload_date': HelperClass.convert_to_ist(item.get('LastModified', datetime.now()))
                                    })
                        
                        # Then add other subordinate folders from the folder_array (positions 1+)
                        for folder_name in folder_array[1:]:
                            folder_path_sub = folder_name + "/"  # Ensure trailing slash
                            folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_path_sub)
                            
                            last_modified = None
                            total_size = 0
                            config = UserConfig.find_by_folder_name(folder_name)
                            allocated_storage = HelperClass.get_formatted_storage(float(config.max_size))[0] if config else None
                            
                            if 'Contents' in folder_files:
                                for file in folder_files['Contents']:
                                    if last_modified is None or file['LastModified'] > last_modified:
                                        last_modified = file['LastModified']
                                    total_size += file.get('Size', 0)
                            
                            parts = folder_name.split('_', 1)
                            display_name = parts[1] if len(parts) == 2 and parts[0].isdigit() else folder_name
                            
                            items.append({
                                'name':  format_folder_name(display_name),
                                'owner': False,
                                'path': folder_path_sub,
                                'is_directory': True,
                                'user_folder':True,
                                'size': HelperClass.format_file_size_bytes(total_size) if total_size else None,
                                'allocated_storage': allocated_storage,
                                'upload_date': HelperClass.convert_to_ist(last_modified) if last_modified else None
                            })
                        
                        # Sort items by upload_date, newest first
                        if items:
                            items.sort(
                                key=lambda x: (x['is_directory'], datetime.strptime(x['upload_date'], '%Y-%m-%d %H:%M IST') if x['upload_date'] else datetime.min),
                                reverse=True
                            )
                        
                        return jsonify(items), 200
                    
                    else:
                        # Regular directory browsing for a specific path that is not the user's main folder
                        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_path)
                        folders = set()
                        items = []
                        
                        if 'Contents' in response:
                            for item in response['Contents']:
                                sizebytes = item['Size']
                                file_key = item['Key']
                                # Skip the folder entry itself (ends with /)
                                if file_key == folder_path:
                                    continue
                                    
                                # Extract the relative path after the folder prefix
                                relative_path = file_key[len(folder_path):]
                                
                                # Check if this is a subfolder entry
                                if '/' in relative_path:
                                    subfolder_name = relative_path.split('/')[0]
                                    if subfolder_name and subfolder_name not in folders:
                                        folders.add(subfolder_name)
                                        # Get information about the subfolder
                                        subfolder_prefix = folder_path + subfolder_name + "/"
                                        subfolder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=subfolder_prefix)
                                        
                                        last_modified = None
                                        total_size = 0
                                        if 'Contents' in subfolder_files:
                                            for file in subfolder_files['Contents']:
                                                if last_modified is None or file['LastModified'] > last_modified:
                                                    last_modified = file['LastModified']
                                                total_size += file.get('Size', 0)
                                        
                                        items.append({
                                            'name':  format_folder_name(subfolder_name),
                                            'path': subfolder_prefix,
                                            'size': HelperClass.format_file_size_bytes(total_size),
                                            'is_directory': True,
                                            'upload_date': HelperClass.convert_to_ist(last_modified) if last_modified else None
                                        })
                                    continue  # Skip further processing for subfolders
                                
                                # Process regular files (no additional / in the path)
                                original_filename = file_key.split('/')[-1]
                                if not original_filename:
                                    continue
                                    
                                uuid_check = HelperClass.is_uuid_prefixed(original_filename)
                                filename = original_filename.split('_', 1)[1] if uuid_check else original_filename

                                items.append({
                                    'name': filename,
                                    'original_filename': original_filename,
                                    'sizebytes': sizebytes,
                                    'path': file_key,
                                    'is_directory': False,
                                    'size': HelperClass.format_file_size_bytes(sizebytes),
                                    'upload_date': HelperClass.convert_to_ist(item.get('LastModified', datetime.now()))
                                })
                        
                        # Sort items by upload_date, newest first
                        if items:
                            items.sort(
                                key=lambda x: (x['is_directory'], datetime.strptime(x['upload_date'], '%Y-%m-%d %H:%M IST') if x['upload_date'] else datetime.min),
                                reverse=True
                            )
                        return jsonify(items), 200
                
                else:
                    # No path provided - return the root listing for the user
                    folder_array, superadmin = HelperClass.get_folder_array(current_user.id)
                    
                    if current_user.isAdmin and superadmin:
                        # Admin with no specific folders - show all user directories
                        user_folders = []
                        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Delimiter='/')
                        if 'CommonPrefixes' in response:
                            for prefix in response['CommonPrefixes']:
                                folder_name = prefix['Prefix'].rstrip('/')
                                
                                config = UserConfig.find_by_folder_name(folder_name)
                                if config:
                                    superadmin_folders = User.get_superadmin_folders()
                                    if folder_name in superadmin_folders:
                                        allocated_storage = HelperClass.get_storage_status(current_user.id)['allocated']
                                    else:
                                        allocated_storage = HelperClass.get_formatted_storage(float(config.max_size))[0]
                                    parts = folder_name.split('_', 1)
                                    if len(parts) == 2 and parts[0].isdigit():
                                        folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_name + "/")
                                        last_modified = None
                                        total_size = 0
                                        
                                        if 'Contents' in folder_files:
                                            for file in folder_files['Contents']:
                                                if last_modified is None or file['LastModified'] > last_modified:
                                                    last_modified = file['LastModified']
                                                total_size += file.get('Size', 0)
                                        
                                        user_folders.append({
                                            'name':  format_folder_name(parts[1]),
                                            'path': folder_name + "/",
                                            'owner':True,
                                            'is_directory': True,
                                            'size': HelperClass.format_file_size_bytes(total_size) if total_size else None,
                                            'allocated_storage': allocated_storage,
                                            'upload_date': HelperClass.convert_to_ist(last_modified) if last_modified else None
                                        })
                        return jsonify(user_folders), 200
                    
                    else:
                        # Regular user or admin with specific folders in array
                        user_folder_items = []
                        
                        if not folder_array:
                            # Create user folder if not in array
                            user_folder = HelperClass.create_or_get_user_folder(s3_client, current_user.id)
                            folder_array = [user_folder]
                        
                        # First, list files and folders in the user's own folder (position 0)
                        user_folder = folder_array[0]
                        user_folder_path = user_folder + "/"  # Ensure trailing slash
                        response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=user_folder_path)
                        
                        if 'Contents' in response:
                            subfolders = set()
                            
                            for item in response['Contents']:
                                sizebytes = item['Size']
                                file_key = item['Key']
                                
                                # Skip the folder entry itself
                                if file_key == user_folder_path:
                                    continue
                                    
                                # Extract relative path after the user folder prefix
                                relative_path = file_key[len(user_folder_path):]
                                
                                # Check if this is a subfolder
                                if '/' in relative_path:
                                    subfolder_name = relative_path.split('/')[0]
                                    if subfolder_name and subfolder_name not in subfolders:
                                        subfolders.add(subfolder_name)
                                        subfolder_prefix = user_folder_path + subfolder_name + "/"
                                        subfolder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=subfolder_prefix)
                                        
                                        last_modified = None
                                        total_size = 0
                                        if 'Contents' in subfolder_files:
                                            for file in subfolder_files['Contents']:
                                                if last_modified is None or file['LastModified'] > last_modified:
                                                    last_modified = file['LastModified']
                                                total_size += file.get('Size', 0)
                                        
                                        user_folder_items.append({
                                            'name':  format_folder_name(subfolder_name),
                                            'path': subfolder_prefix,
                                            'owner':True,
                                            'is_directory': True,
                                            'size': HelperClass.format_file_size_bytes(total_size),
                                            'upload_date': HelperClass.convert_to_ist(last_modified) if last_modified else None
                                        })
                                    continue
                                
                                # Process regular files
                                if sizebytes > 0:
                                    original_filename = file_key.split('/')[-1]
                                    if not original_filename:
                                        continue
                                        
                                    uuid_check = HelperClass.is_uuid_prefixed(original_filename)
                                    filename = original_filename.split('_', 1)[1] if uuid_check else original_filename
                                    
                                    user_folder_items.append({
                                        'name': filename,
                                        'original_filename': original_filename,
                                        'sizebytes': sizebytes,
                                        'owner':True,
                                        'path': file_key,
                                        'is_directory': False,
                                        'size': HelperClass.format_file_size_bytes(sizebytes),
                                        'upload_date': HelperClass.convert_to_ist(item.get('LastModified', datetime.now()))
                                    })
                        
                        # Then add other folders from the folder_array (positions 1+)
                        for folder_name in folder_array[1:]:
                            folder_path = folder_name + "/"  # Ensure trailing slash
                            folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_path)
                            
                            last_modified = None
                            total_size = 0
                            config = UserConfig.find_by_folder_name(folder_name)
                            allocated_storage = HelperClass.get_formatted_storage(float(config.max_size))[0] if config else None
                            
                            if 'Contents' in folder_files:
                                for file in folder_files['Contents']:
                                    if last_modified is None or file['LastModified'] > last_modified:
                                        last_modified = file['LastModified']
                                    total_size += file.get('Size', 0)
                            
                            parts = folder_name.split('_', 1)
                            display_name = parts[1] if len(parts) == 2 and parts[0].isdigit() else folder_name
                            
                            user_folder_items.append({
                                'name':  format_folder_name(display_name),
                                'path': folder_path,
                                'is_directory': True,
                                'owner': False,
                                'user_folder':True,
                                'size': HelperClass.format_file_size_bytes(total_size) if total_size else None,
                                'allocated_storage': allocated_storage,
                                'upload_date': HelperClass.convert_to_ist(last_modified) if last_modified else None
                            })
                        
                        # Sort items by upload_date, newest first
                        if user_folder_items:
                            user_folder_items.sort(
                                key=lambda x: (x['is_directory'], datetime.strptime(x['upload_date'], '%Y-%m-%d %H:%M IST') if x['upload_date'] else datetime.min),
                                reverse=True
                            )
                        
                        return jsonify(user_folder_items), 200
            
            except Exception as e:
                print(f"Error: {str(e)}")  # Log the error
                return jsonify({'error': str(e)}), 500
        
        # GET request handling - render the template
        if current_user.is_authenticated:
            if current_user.isAdmin and current_user.superuser_id == 0:
                folder_path = '/'
            else:
                folder_path = HelperClass.create_or_get_user_folder(get_s3_client(), current_user.id) + "/"
        
        return render_template('index.html', home_page=True, flash_message=message, folder_path=folder_path)
        
    
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
            foldername = session.get('current_path', '')
            if not foldername:
                foldername = HelperClass.create_or_get_user_folder(s3_client, current_user.id)+'/'
            
            
            # Check if file can be uploaded (storage limits)
            can_be_uploaded, message = HelperClass.file_can_be_uploaded(current_user.id, total_size)
            if not can_be_uploaded:
                flash(message)
                return jsonify({'message': 'No Storage'}), 200
            
            # Create unique filename
            secure_name = secure_filename(original_filename)
            unique_id = str(uuid.uuid4())
            filename = f"{unique_id}_{secure_name}"  # UUID-prefixed filename
            folder_file = foldername + filename
            
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
        
    @blp.route('/stream_download/<path:file_path>')
    def stream_download(file_path):
        if current_user.is_authenticated:
            try:
                s3_client = get_s3_client()
                
                # Get file metadata for content type and size
                head_response = s3_client.head_object(Bucket=BUCKET_NAME, Key=file_path)
                content_type = head_response.get('ContentType', 'application/octet-stream')
                file_size = head_response.get('ContentLength', 0)
                
                # Extract filename from the path
                filename = file_path.split('/')[-1]
                
                # Extract original filename if needed (removing UUID prefix if present)
                original_filename = filename
                if HelperClass.is_uuid_prefixed(filename):
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
                print(f"\nError streaming download for {file_path}: {e}")
                flash(f'Error downloading file: {str(e)}')
                return redirect(url_for('drive.index'))
        
        return jsonify({'error': 'Unauthorized'}), 401

    @blp.route('/delete/<path:file_path>', methods=['POST'])
    def delete(file_path):
        try:
            s3_client = get_s3_client()
            if '.folder_init' in file_path:
                return jsonify({'message': 'Cannot delete initialization file.'}), 200
            # Delete file from Backblaze B2
            s3_client.delete_object(
                Bucket=BUCKET_NAME,
                Key=file_path
            )
            
            return jsonify({'message': 'File deleted successfully!'}), 200
        except Exception as e:
            flash('Error deleting file')
            return jsonify({'error': str(e)}), 500
        
        # return redirect(url_for('drive.index'))
    
    @blp.route('/storage_status',methods=['POST'])
    def storage_status():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        s3_client = get_s3_client()
        storage_status = HelperClass.get_storage_status(current_user.id)
        return jsonify(storage_status),200
    
    @blp.route('/create_folder', methods=['POST'])
    @login_required
    def create_folder():
        try:
            s3_client = get_s3_client()
            
            current_path = request.form.get('current_path')
            folder_name = request.form.get('folder_name')
            if not current_path or not current_path.strip():
                current_path = HelperClass.create_or_get_user_folder(s3_client, current_user.id)
            
            # Validate folder name
            if not folder_name or '/' in folder_name:
                flash('Invalid folder name. Folder name cannot be empty or contain slashes.')
                return redirect(url_for('drive.index'))
            
            # Construct the new folder path
            # If current_path ends with /, don't add another /
            if current_path and not current_path.endswith('/'):
                current_path += '/'
                
            new_folder_path = f"{current_path}{folder_name}/"
            
            # Create only the folder marker object with a single API call
            # This is more efficient than creating multiple objects
            s3_client.put_object(
                Bucket=BUCKET_NAME,
                Key=new_folder_path,
                Body='',
                Metadata={
                    'creator': current_user.username,
                    'created_on': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            )
            
            flash('Folder created successfully!')
            
            
            return redirect(url_for('drive.index'))
            
        except Exception as e:
            print(f"Error creating folder: {str(e)}")
            flash('Error creating folder')
                        
            return redirect(url_for('drive.index'))
    
    @blp.route('/rename',methods=['POST'])
    def rename():
        rename_path = request.form.get('rename_path')
        is_directory = request.form.get('is_directory') == 'true'
        original_name = request.form.get('original_name')
        old_name = request.form.get('old_name')
        new_name = request.form.get('rename_name')
        extension = request.form.get('file_extension', '')

        if not rename_path or not new_name:
            flash("Invalid rename request.", "danger")
            return redirect(url_for('your_main_view'))

        # Final new name (add extension back for files)
        if not is_directory:
            secure_name = secure_filename(new_name)
            unique_id = str(uuid.uuid4())
            new_name = f"{unique_id}_{secure_name}"
            final_new_name = f"{new_name}{extension}"
            base_path = rename_path.replace(original_name,'')
            new_path = f"{base_path}{final_new_name}"
        else:
            # For directories, just use the new name
            final_new_name = new_name
            base_path = rename_path.replace(old_name+'/','')
            new_path = f"{base_path}{final_new_name}/"
            
        # Generate new path
        try:
            s3 = get_s3_client()
            if is_directory:
                # Get all objects under this "folder"
                paginator = s3.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=BUCKET_NAME, Prefix=rename_path)

                for page in pages:
                    for obj in page.get('Contents', []):
                        old_key = obj['Key']
                        # Replace only the initial folder part with the new name
                        suffix = old_key[len(rename_path):]
                        new_key = new_path + suffix

                        # Copy the object
                        s3.copy_object(Bucket=BUCKET_NAME, CopySource={'Bucket': BUCKET_NAME, 'Key': old_key}, Key=new_key)

                        # Delete original
                        s3.delete_object(Bucket=BUCKET_NAME, Key=old_key)

            else:
                pass
                # For a file
                s3.copy_object(
                    Bucket=BUCKET_NAME,
                    CopySource={'Bucket': BUCKET_NAME, 'Key': rename_path},
                    Key=new_path
                )
                s3.delete_object(Bucket=BUCKET_NAME, Key=rename_path)

            flash("Renamed successfully!")
        except Exception as e:
            flash("Rename failed")

        return redirect(url_for('drive.index'))
    
    
    @blp.route('/list_folder_files')
    def list_folder_files():
        folder_path = request.args.get('folder_path')
        if not folder_path:
            return jsonify({'error': 'folder_path is required'}), 400

        if not folder_path.endswith('/'):
            folder_path += '/'
        s3 = get_s3_client()
        response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_path)
        files = []
        for item in response.get('Contents', []):
            if item['Key'].endswith('/'):  # skip folders
                continue
            files.append({
                'path': item['Key'],
                'name': os.path.basename(item['Key']),
                'size': item['Size']
            })

        return jsonify(files)
    
    @blp.route('/delete_folder/<path:folder_path>', methods=['POST'])
    def delete_folder(folder_path):
        if not folder_path.endswith('/'):
            folder_path += '/'

        s3 = get_s3_client()

        try:
            # List all objects under the folder
            response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_path)
            contents = response.get('Contents', [])

            if contents:
                # Delete all objects under the folder
                delete_items = [{'Key': obj['Key']} for obj in contents]
                s3.delete_objects(
                    Bucket=BUCKET_NAME,
                    Delete={'Objects': delete_items}
                )
                return jsonify({'message': f'Folder deleted successfully.'}), 200

        except Exception as e:
            return jsonify({'error': str(e)}), 500
        
        
    @blp.route('/version')
    def version():
        version = HelperClass.get_version()
        return {"version": version}
    return blp

