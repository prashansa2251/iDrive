from flask_login import UserMixin
from sqlalchemy import ARRAY, case, func, text
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
    
    def __init__(self, username,email, password,isActive,isAdmin,superuser_id=1):
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
        if query.superuser_id == 0:
            return True
        else:
            return False

    @classmethod
    def get_superusers(cls,current_user_id):
        check_superadmin = cls.check_superadmin(current_user_id)
        if check_superadmin:
                query = db.session.query(
                    cls.id,
                    cls.username,
                    cls.isActive,
                    cls.email,
                    cls.superuser_id
                ).filter(cls.isAdmin == True).order_by(cls.id).all()
        else:
                query = db.session.query(
                    cls.id,
                    cls.username,
                    cls.isActive,
                    cls.email,
                    cls.superuser_id
                ).filter(cls.isAdmin == True, cls.superuser_id != 0).order_by(cls.id).all()
        
        if query:
            json_data = [{
                'id': item.id,
                'username': item.username,
                'is_active': item.isActive,
                'email':item.email,
                'superuser_id':item.superuser_id
            } for item in query]
            
        return json_data
    
    @classmethod
    def get_users_data(cls, user_id_array):
        json_data = []
        for id in user_id_array:
            query = db.session.query(
                cls.id,
                cls.username,
                cls.isActive,
                cls.isAdmin,
                cls.email,
                cls.superuser_id,
                UserConfig.folder_name,
                UserConfig.storage_upgraded,
                UserConfig.user_id,
                UserConfig.max_size
            ).filter_by(id=id).join(UserConfig,cls.id==UserConfig.user_id).first()
            if query:
                json_data.append({'id':query.id,
                        'username':query.username,
                        'is_active':query.isActive,
                        'is_admin':query.isAdmin,
                        'email':query.email,
                        'folder_name':query.folder_name,
                        'storage_upgraded':query.storage_upgraded,
                        'user_id':query.user_id,
                        'max_size':query.max_size,
                        'superuser_id':query.superuser_id
                            })
        return json_data
    
    @classmethod
    def find_by_email(cls, email):
        return cls.query.filter_by(email=email).first()
    
    @classmethod
    def find_by_username(cls, username):
        return cls.query.filter_by(username=username).first()
    
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
    def get_superadmin_folders(cls):
        query = db.session.query(
            UserConfig.folder_name,
        ).select_from(cls).join(UserConfig,cls.id == UserConfig.user_id).filter(cls.superuser_id==0).all()
        
        if query:
            json_data = [item.folder_name for item in query]
            
        return json_data
    
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
    
    @classmethod
    def toggle_admin_status(cls,user_id):
        user = cls.query.filter_by(id=user_id).first()
        user.isAdmin = not user.isAdmin
        user.update_db()
        return True
    
    @classmethod
    def update_reporting(cls,user_id,superuser_id):
        user = cls.query.filter_by(id=user_id).first()
        user.superuser_id = superuser_id
        user.update_db()
        return True
    
    @classmethod
    def get_only_users(cls):
        return cls.query.filter(cls.superuser_id != 0).all()
    
    @classmethod
    def get_subordinates(cls,user_id,folders):
        
        query = text("""
            WITH RECURSIVE subordinates AS (
                SELECT id
                FROM users
                WHERE superuser_id = :user_id
                
                UNION ALL
                
                SELECT u.id
                FROM users u
                INNER JOIN subordinates s ON u.superuser_id = s.id
            )
            SELECT id FROM subordinates;
        """)
        if folders:
            id_array = [user_id,]
        else:
            id_array = []
        super_admin = cls.check_superadmin(user_id)
        if super_admin:
            result = cls.get_only_users()
        else:
            result = db.session.execute(query, {"user_id": user_id})
        for row in result:
            id_array.append(row.id)
        return id_array
    
    
    