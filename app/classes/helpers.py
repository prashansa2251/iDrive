import os
from app.models.user_config import UserConfig
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