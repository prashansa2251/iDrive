from flask_login import UserMixin
from sqlalchemy import ARRAY, case, func
from app.db import db
from passlib.hash import pbkdf2_sha256

from app.models.user_config import UserConfig

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    email = db.Column(db.String(100))
    password = db.Column(db.String(300))
    isActive = db.Column(db.Boolean, nullable=False, default=False)
    isAdmin = db.Column(db.Boolean, nullable=False, default=False)
    superuser_id = db.Column(db.Integer)
    
    def __init__(self, username,email, password,isActive,isAdmin,superuser_id):
        self.email = email
        self.username = username
        self.password = password
        self.isActive = isActive
        self.isAdmin = isAdmin
        self.superuser_id = superuser_id

    def json(self):
        return {
            'id': self.id,
            'username': self.username,
            'isActive': self.isActive,
            'isAdmin': self.isAdmin,
            'email': self.email,
            'superuser_id': self.superuser_id
        }
    
    def save_to_db(self):
        db.session.add(self)
        db.session.commit()
    
    def update_db(self):
        db.session.commit()

    def set_password(self, password):
        self.password = pbkdf2_sha256.hash(password)
    
    def check_password(self, password):
        return pbkdf2_sha256.verify(password, self.password)

    @classmethod
    def check_superadmin(cls, user_id):
        query = cls.query.filter_by(id=user_id).first()
        if query.superuser_id == -1:
            return True
        else:
            return False

    @classmethod
    def get_users_under_superuser(cls, user_id):
        query = db.session.query(
            cls.id,
            cls.username,
            cls.isActive,
            cls.email,
            cls.superuser_id,
            UserConfig.folder_name,
            UserConfig.storage_upgraded,
            UserConfig.user_id,
            UserConfig.id,
            UserConfig.max_size
            ).filter_by(superuser_id=user_id).join(UserConfig,cls.id==UserConfig.user_id).all()
        if query:
            json_data = [{'id':item.id,
                    'username':item.username,
                    'isActive':item.isActive,
                    'email':item.email,
                    'superuser_id':item.superuser_id,
                    'folder_name':item.folder_name,
                    'storage_upgraded':item.storage_upgraded,
                    'user_id':item.user_id,
                    'config_id':item.id,
                    'max_size':item.max_size
                        } for item in query]
            return json_data

        return None
    
    @classmethod
    def find_by_email(cls, email):
        return cls.query.filter_by(email=email).first()
    
    @classmethod
    def get_all(cls):
        query = db.session.query(
            cls.id, 
            cls.username,
            cls.isActive,
            cls.email,
            UserConfig.max_size
        ).join(UserConfig, cls.id == UserConfig.user_id
        ).order_by(cls.id)
        
        results = query.all()
        
        if results:
            json_data = [{
                'id': item.id,
                'username': item.username,
                'is_active': item.isActive,
                'email':item.email,
                'storage_volume': item.max_size
            } for item in results]
            
        
        return json_data
    
    @classmethod
    def get_by_id(cls, id):
        return cls.query.filter(cls.id==id).first()
    
    @classmethod
    def check_active(cls,user_id):
        query = cls.query.filter_by(id=user_id).first()
        if query:
            return query.isActive
        else:
            return False
    
    @classmethod
    def get_active_count(cls):
        counts = db.session.query(
            func.count(case((cls.isActive == 'True', 1))).label('active_users'),
            func.count(case((cls.isActive == 'False', 1))).label('inactive_users')
        ).one()

        return {
            'active_users': counts.active_users,
            'inactive_users': counts.inactive_users
        }
    
    @classmethod
    def toggle_user_status(cls,user_id):
        user = cls.query.filter_by(id=user_id).first()
        user.isActive = not user.isActive
        user.update_db()
        return True
    