import math
import os

import boto3
from flask import flash, get_flashed_messages
from flask_login import current_user
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
    def format_file_size(cls, bytes):
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
    def check_remaining_storage(cls,s3_client,user_id):
        
        if current_user.isAdmin:
            folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME)
        else:
            allocated_storage = UserConfig.get_allocated_storage(user_id)
            folder_name = cls.create_or_get_user_folder(s3_client,user_id)
            folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_name + "/")
            
        used_storage = 0  
        if not folder_files['KeyCount']:
            storage_info = {'used':'0 MB','allocated':allocated_storage,'danger':False,'percentage':0}
            return storage_info
        for file in folder_files['Contents']:
            used_storage += file.get('Size', 0)
                
        used_storage = cls.format_file_size(used_storage)
        
        if current_user.isAdmin:
            percentage,allocated_storage = cls.calculate_total_storage_and_percentage(used_storage)
        else:
            percentage,allocated_storage = cls.calculate_total_storage_and_percentage(used_storage,allocated_storage)
        
        allocated_storage = cls.format_allocated_storage(allocated_storage)
            
        danger = False
        if percentage > 90:
            danger = True
            
        storage_info = {'used':used_storage,'allocated':allocated_storage,'danger':danger,'percentage':percentage}
        return storage_info
    
    @classmethod 
    def calculate_total_storage_and_percentage(cls,storage_str, total_storage=None):
        """Convert storage input (KB, MB, GB, TB) to TB and calculate percentage usage."""
        
        # Conversion factors to TB
        conversion_factors = {
            "KB": 1 / (1024 ** 3),  # Convert KB to TB
            "MB": 1 / (1024 ** 2),  # Convert MB to TB
            "GB": 1 / 1024,         # Convert GB to TB
            "TB": 1                 # TB remains TB
        }

        # Extract numeric value and unit from input
        parts = storage_str.split()
        if len(parts) != 2:
            raise ValueError("Invalid format. Example: '10 KB', '100 GB', '1.5 TB'")

        try:
            value = float(parts[0])  # Convert numeric part to float
            unit = parts[1].upper()  # Normalize unit to uppercase
        except ValueError:
            raise ValueError("Invalid numeric value in storage input.")

        if unit not in conversion_factors:
            raise ValueError("Invalid storage unit. Allowed: KB, MB, GB, TB")

        # Convert to TB
        storage_in_tb = value * conversion_factors[unit]

        # Apply rounding logic
        if storage_in_tb < 1:
            final_tb = 1  # Ensure minimum of 1 TB
        elif storage_in_tb == int(storage_in_tb):  
            final_tb = int(storage_in_tb) + 1  # If already a whole number, increase by 1 TB
        else:
            final_tb = math.ceil(storage_in_tb)  # Round up to the next TB
        
        # Calculate percentage used based on allocated TB
        percentage_used = int((storage_in_tb / final_tb) * 100)

        # If total_storage is provided, use it for percentage calculation
        if total_storage:
            percentage_used = int((storage_in_tb / total_storage) * 100)
            return percentage_used, total_storage
        
        return percentage_used, final_tb  # Return percentage & allocated TB
    
    @classmethod
    def file_can_be_uploaded(cls,s3_client,user_id,upload_file_size_in_bytes):
        allocated_storage = UserConfig.get_allocated_storage(user_id)
        if not allocated_storage:
            message = 'No storage allocated, Contact Admin !!'
            return False,message
        folder_name = cls.create_or_get_user_folder(s3_client,user_id)
        folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_name + "/")
        allocated_storage_in_bytes = int(allocated_storage*1099511627776)  
        used_storage_in_bytes = 0 
        if not used_storage_in_bytes:
            return True,''
        for file in folder_files['Contents']:
                used_storage_in_bytes += file.get('Size', 0)
        buffer_10_kb_in_bytes = 10240 # to insure 10 KB is left after upload
        total_bytes_after_upload = used_storage_in_bytes + upload_file_size_in_bytes + buffer_10_kb_in_bytes
        if total_bytes_after_upload > allocated_storage_in_bytes:   
            message = 'Not enough storage, cannot upload !!'
            return False,message
        return True,''
        
    @classmethod 
    def format_allocated_storage(cls,storage_tb):
        """Convert and return used storage in GB if <1TB, otherwise in TB."""
        if storage_tb < 1:
            if storage_tb * 1024 < 1:
                return f"{round(storage_tb * 1024 * 1024)} MB"
            return f"{round(storage_tb * 1024)} GB"  # Convert TB to GB
        return f"{storage_tb} TB"  # Keep TB as it is, rounded
    
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
            user['storage_used'] = cls.get_formatted_storage(cls.get_user_storage(user['user_id'])['used'])[0]
            user['storage_allocated'],user['storage_unit'] = cls.get_formatted_storage(user['max_size'])
            total_storage_occupied += int(user['max_size'])
        total_storage_occupied = total_storage_occupied
        total_storage_remaining = int(total_storage_allocated) - int(total_storage_occupied)
        total_storage = {'remaining':cls.get_formatted_storage(total_storage_remaining),
                         'allocated':cls.get_formatted_storage(total_storage_allocated),
                         'occupied':cls.get_formatted_storage(total_storage_occupied),
                         'percentage': int((total_storage_occupied/total_storage_allocated)*100)}
        return users_data,total_storage
            

    @classmethod
    def get_formatted_storage(cls,storage):
        storage_int = int(storage)
        if storage_int < 1024:
            return str(storage_int)+' MB','MB'
        elif storage_int >= 1024:
            return str(int(storage_int/1024))+' GB','GB'
        
    @classmethod
    def update_user_storage(cls,data):
        storage_data = data['storage_data']
        original_unit = data['original_unit']
        updated_unit = data['storage_unit']
        updated_storage = data['storage_updated']
        original_storage=data['original_storage']
        
        if original_unit == 'GB' and updated_unit == 'GB':
            original_storage = int(original_storage) * 1024
            updated_storage = int(updated_storage) * 1024
        elif original_unit == 'GB' and updated_unit == 'MB':
            original_storage = int(original_storage) * 1024
        elif original_unit == 'MB' and updated_unit == 'GB':
            updated_storage = int(updated_storage) * 1024
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
        
        remaining_storage = storage_data['remaining'][0]
        remaining_storage_unit = storage_data['remaining'][1]
        if remaining_storage_unit == 'GB':
            remaining_storage = int(remaining_storage[:-3]) * 1024
            
        elif remaining_storage_unit == 'MB':
            remaining_storage = int(remaining_storage[:-3])

        if remaining_storage < diff:
            flash('Not enough storage available to allocate!')
            return False
        else:
            user_update = UserConfig.update_storage(data['user_id'],updated_storage)
            if user_update:
                flash('Storage updated successfully!')
                return True
            else:
                flash('Error updating storage allocation!')
                return False
    
    @classmethod
    def get_user_storage(cls,user_id):
        s3_client = get_s3_client()
        folder_name = cls.create_or_get_user_folder(s3_client,user_id)
        folder_files = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_name + "/")
        used_storage_in_bytes = 0 
        for file in folder_files['Contents']:
                used_storage_in_bytes += file.get('Size', 0)
        used_storage_mb = int(used_storage_in_bytes / (1024 * 1024)) # Convert bytes to MB
        allocated_storage = UserConfig.get_allocated_storage(user_id)
        storage ={'used':used_storage_mb,'allocated':allocated_storage,'remaining':allocated_storage - used_storage_mb}
        return storage