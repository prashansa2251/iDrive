import math
import os

import boto3
from flask import flash, get_flashed_messages
from flask_login import current_user
from app.models.requests import Requests
from app.models.user_config import UserConfig
from datetime import datetime, timezone,timedelta
from app.models.users import User

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
class HelperClass():
    @classmethod
    def get_version(cls):
        with open('version.txt', 'r') as file:
            version = file.read().strip()
        return version
    
    @classmethod
    def create_or_get_user_folder(cls,s3_client,user_id):
        folder_name = UserConfig.get_folder_name(user_id)
        check_folder = s3_client.list_objects_v2(Bucket=BUCKET_NAME,Prefix=folder_name + "/", MaxKeys=1)
        folder_exists = "Contents" in check_folder
        if not folder_exists:
            try:
                s3_client.put_object(Bucket=BUCKET_NAME, Key=folder_name)
                return folder_name
            except Exception as e:
                print('Error creating folder',e)
                return None
        return folder_name
    
    @classmethod
    def format_file_size_bytes(cls, bytes):
        if bytes < 1024:
            return f"{bytes} bytes"
        elif bytes < 1048576:  # Less than 1 MB
            return f"{bytes / 1024:.1f} KB"
        elif bytes < 1073741824:  # Less than 1 GB
            return f"{bytes / 1048576:.1f} MB"
        elif bytes < 1099511627776:  # Less than 1 TB
            return f"{bytes / 1073741824:.2f} GB"
        else:  # 1 TB or more
            return f"{bytes / 1099511627776:.2f} TB"
    
    @classmethod
    def convert_to_ist(cls,dt):
        """Convert datetime to IST timezone and format as string"""    
        # If no timezone info, assume UTC
        IST = timezone(timedelta(hours=5, minutes=30))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        # Convert to IST
        ist_time = dt.astimezone(IST)
        
        # Return formatted string
        return ist_time.strftime('%Y-%m-%d %H:%M IST')

    @classmethod
    def is_uuid_prefixed(cls,filename):
        """Check if filename starts with a UUID pattern"""
        parts = filename.split('_', 1)
        if len(parts) < 2:
            return False
        
        uuid_part = parts[0]
        # Simple check to see if the first part could be a UUID
        # (this is not a comprehensive UUID check)
        return len(uuid_part) == 36 and uuid_part.count('-') == 4
    
    @classmethod
    def parse_upload_date(cls,item):
        try:
            return datetime.strptime(item.get('upload_date', '1970-01-01 00:00 IST'), '%Y-%m-%d %H:%M IST')
        except ValueError:
            return datetime(1970, 1, 1, 0, 0)
        
    @classmethod
    def get_message(cls):
        messages = get_flashed_messages()
        if len(messages) > 0:
            message = messages[0]
        else:
            message = ''

        return message
        
        
    @classmethod
    def file_can_be_uploaded(cls,user_id,upload_file_size_in_bytes):
        upload_file_mb = round(float(upload_file_size_in_bytes / (1024 * 1024)),2)  # Convert bytes to MB
        users_data,total_storage = cls.get_users_data(user_id)
        allocated_storage = total_storage['allocated'][2]
        if not allocated_storage:
            message = 'No storage allocated, Contact Admin !!'
            return False,message
        remaining_storage = total_storage['remaining'][2]
        remaining_storage_unit = total_storage['remaining'][1]
        if remaining_storage_unit == 'GB':
            remaining_storage = round(float(remaining_storage * 1024),2)
        elif remaining_storage_unit == 'MB':
            remaining_storage = float(remaining_storage)
        elif remaining_storage_unit == 'TB':
            remaining_storage = round(float(remaining_storage *1024*1024),2)   
            
        if remaining_storage < upload_file_mb+5: #buffer 5mb:
            message = 'Not enough storage, cannot upload !!'
            return False,message
        return True,''
    
    @classmethod
    def get_folder_array(cls,user_id):
        """Get folders name based on user ID."""
        user_folder = UserConfig.get_folder_name(user_id)
        superadmin = User.check_superadmin(user_id)
        if superadmin:
            return [user_folder,],superadmin
        subordinates = User.get_subordinates(user_id,True)
        folder_array = []
        if subordinates:
            users_data = User.get_users_data(subordinates)
            for user in users_data:
                folder_array.append(user['folder_name'])
        return folder_array,superadmin
    
    
    @classmethod
    def get_users_data(cls,user_id):
        subordinates = User.get_subordinates(user_id,False)
        users_data = User.get_users_data(subordinates)
        total_storage_allocated = UserConfig.get_allocated_storage(user_id)
        total_storage_occupied = 0
        for user in users_data:
            reporting_to = User.get_by_id(user['superuser_id'])
            user['reporting_to'] = reporting_to.username
            user['reporting_to_email'] = reporting_to.email
            user['reporting_to_id'] = reporting_to.id
            user['storage_used'] = cls.get_formatted_storage(cls.get_user_storage(user['user_id'])['used'])[0]
            user['storage_allocated'],user['storage_unit'],storage = cls.get_formatted_storage(user['max_size'])
            total_storage_occupied += int(user['max_size'])
            
        user_storage_occupied = 0
        s3_client = get_s3_client()
        folder_name = cls.create_or_get_user_folder(s3_client,user_id)
        folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_name + "/")
        for file in folder_files['Contents']:
            user_storage_occupied += file.get('Size', 0)
        user_storage_occupied = round(float(user_storage_occupied / (1024 * 1024)),2)
        total_storage_occupied = total_storage_occupied + user_storage_occupied
        total_storage_remaining = int(total_storage_allocated) - int(total_storage_occupied)
        total_storage = {'remaining':cls.get_formatted_storage(total_storage_remaining),
                         'allocated':cls.get_formatted_storage(total_storage_allocated),
                         'occupied':cls.get_formatted_storage(total_storage_occupied),
                         'percentage': int((total_storage_occupied/total_storage_allocated)*100)}
        return users_data,total_storage
            

    @classmethod
    def get_formatted_storage(cls,storage):
        storage_int = round(float(storage),2)
        if storage_int < 1024:
            return str(storage_int)+' MB','MB',storage_int
        elif storage_int >= 1024 and storage_int < 1048576:
            return str(round(float(storage_int/1024),2))+' GB','GB',round(float(storage_int/1024),2)
        else:
            return str(round(float(storage_int/1048576),2))+' TB','TB',round(float(storage_int/1048576),2)
        
    @classmethod
    def update_user_storage(cls,data):
        storage_data = data['storage_data']
        original_unit = data['original_unit']
        updated_unit = data['storage_unit']
        updated_storage = data['storage_updated']
        original_storage=data['original_storage']
        
        if original_unit == 'GB' and updated_unit == 'GB':
            original_storage = round(float(original_storage) * 1024,2)
            updated_storage = round(float(updated_storage) * 1024,2)
        elif original_unit == 'GB' and updated_unit == 'MB':
            original_storage = round(float(original_storage) * 1024,2)
        elif original_unit == 'MB' and updated_unit == 'GB':
            updated_storage = round(float(updated_storage) * 1024,2)
        elif original_unit == 'MB' and updated_unit == 'MB':
            pass
        
        diff = updated_storage - original_storage
        if diff == 0:
            flash('No changes made to storage allocation!')
            return True
        
        if diff < 0:
            user_occupied_space = cls.get_user_storage(data['user_id'])
            if user_occupied_space['used'] > updated_storage:
                flash('Cannot reduce storage allocation below used space!')
                return False
        
        remaining_storage = storage_data['remaining'][2]
        remaining_storage_unit = storage_data['remaining'][1]
        if remaining_storage_unit == 'GB':
            remaining_storage = float(remaining_storage) * 1024
            
        elif remaining_storage_unit == 'MB':
            remaining_storage = float(remaining_storage)

        if remaining_storage < diff:
            flash('Not enough storage available to allocate!')
            return False
        else:
            user_update = UserConfig.update_storage(data['user_id'],math.ceil(updated_storage))
            if user_update:
                flash('Storage updated successfully!')
                return True
            else:
                flash('Error updating storage allocation!')
                return False
    
    @classmethod
    def get_user_storage(cls,user_id):
        s3_client = get_s3_client()
        user_ids = User.get_subordinates(user_id,True)
        used_storage_in_bytes = 0 
        for id in user_ids:
            folder_name = cls.create_or_get_user_folder(s3_client,id)
            folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_name + "/")
            for file in folder_files['Contents']:
                    used_storage_in_bytes += file.get('Size', 0)
        used_storage_mb = round(float(used_storage_in_bytes / (1024 * 1024)),2) # Convert bytes to MB
        allocated_storage = UserConfig.get_allocated_storage(user_id)
        storage ={'used':used_storage_mb,'allocated':allocated_storage,'remaining':allocated_storage - used_storage_mb}
        return storage
    
    @classmethod
    def get_storage_status(cls,user_id):
        user_ids = User.get_subordinates(user_id,False)
        user_data = User.get_users_data(user_ids)
        storage_occupied = 0
        users_storage = []
        for user in user_data:
            storage_occupied += float(user['max_size'])
            user_storage = {}
            user_storage['user_id'] = user['user_id']
            user_storage['username'] = user['username']
            user_storage['used'] = cls.get_formatted_storage(user['max_size'])[0]
            users_storage.append(user_storage)
            
        user_storage_occupied = 0
        s3_client = get_s3_client()
        folder_name = cls.create_or_get_user_folder(s3_client,user_id)
        folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_name + "/")
        for file in folder_files['Contents']:
            user_storage_occupied += file.get('Size', 0)
        user_storage_occupied = round(float(user_storage_occupied / (1024 * 1024)),2)
        total_storage_occupied = float(storage_occupied) + float(user_storage_occupied)
        total_storage_allocated = UserConfig.get_allocated_storage(user_id)
        if current_user.superuser_id == 0:
            total_storage_allocated = cls.get_superadmin_storage(user_id)
        total_storage_remaining = float(total_storage_allocated) - float(total_storage_occupied)
        percentage = round(float((total_storage_occupied/total_storage_allocated)*100),2)
        if percentage > 90:
            danger = True
        else:
            danger = False
        users_storage.append({'user_id':user_id,'username':'Self','used':cls.get_formatted_storage(user_storage_occupied)[0]})
        storage = {'remaining':cls.get_formatted_storage(total_storage_remaining)[0],
                   'allocated':cls.get_formatted_storage(total_storage_allocated)[0],
                   'used':cls.get_formatted_storage(total_storage_occupied)[0],
                   'percentage': percentage,'danger':danger,'users_storage':users_storage}
        return storage
        
    @classmethod
    def prepare_multi_progress_bar(cls,data):
        colors = ['#45A29E', '#F6C90E', '#C06C84', '#6C5B7B','#F67280', '#355C7D', '#99B898', '#E8A87C', '#41B3A3']
        users_storage = data['users_storage']
        total_storage = cls.get_storage_in_mb(data['allocated'][:-3],data['allocated'][-2:])
        
        for user in users_storage:
            used_mb = cls.get_storage_in_mb(user['used'][:-3],user['used'][-2:])
            user['percentage'] = round((float(used_mb) / float(total_storage)) * 100,2)
            user['color'] = colors[users_storage.index(user) % len(colors)]
            
        remaining_mb = cls.get_storage_in_mb(data['remaining'][:-3],data['remaining'][-2:])
        percentage = round((float(remaining_mb) / float(total_storage)) * 100,2)
        
        
        users_storage = sorted(users_storage, key=lambda x: x['percentage'], reverse=True)
        users_storage.append({'user_id':0,'username':'Remaining','used':data['remaining'],'percentage':percentage,'color':'#dfe6e9'})
        return users_storage

        
    @classmethod
    def get_superadmin_storage(cls,occupied_storage):
        if occupied_storage/(1024*1024) <= 1:
            occupied_storage = 1048576
        elif occupied_storage/(1024*1024) > 1:
            occupied_storage = math.ceil(round(float(occupied_storage/(1024*1024),2)))
            occupied_storage = occupied_storage * 1024 * 1024
        return occupied_storage
    
    @classmethod 
    def get_storage_in_mb(cls,storage,unit):
        storage = float(storage)
        if unit == 'MB':
            return math.ceil(storage)
        elif unit == 'GB':
            return math.ceil(storage * 1024)
        elif unit == 'TB':
            return math.ceil(storage * 1024 * 1024)
        
        
    @classmethod
    def create_request(cls,user_id,req_size,req_unit):
        user = User.get_by_id(user_id)
        superuser_id = user.superuser_id
        if req_unit == 'GB':
            req_size = math.ceil(float(req_size) * 1024)
        request = Requests(status=False,
                           user_id=user_id,
                           req_size=req_size,
                           marked_read=False,
                           superuser_id=superuser_id)
        request.save_to_db()
        return True
    
    @classmethod
    def get_requests(cls,user_id):
        superadmin = User.check_superadmin(user_id)
        if superadmin:
            user_id = 0
        requests = Requests.get_requests_superuser(user_id)
        unread_requests=0
        if requests:
            for request in requests:
                if not request['marked_read']:
                    unread_requests += 1
                request['display_size'] = cls.get_formatted_storage(request['req_size'])[0]

        return requests,unread_requests
