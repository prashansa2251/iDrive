import os

from flask import get_flashed_messages
from app.models.user_config import UserConfig
from datetime import datetime, timezone,timedelta

BUCKET_NAME = os.environ.get('BUCKET_NAME', 'your-bucket-name')

class HelperClass():
    
    @classmethod
    def create_or_get_user_folder(cls,s3_client,user_id,username):
        folder_name = UserConfig.get_folder_name(user_id)
        check_folder = s3_client.list_objects_v2(Bucket=BUCKET_NAME, MaxKeys=1)
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