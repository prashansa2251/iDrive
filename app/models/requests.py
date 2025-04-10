from app.db import db
from app.models.user_config import UserConfig
from app.models.users import User

class Requests(db.Model):
    __tablename__ = "requests"
    
    id = db.Column(db.Integer, primary_key=True)
    req_size = db.Column(db.Integer())
    status = db.Column(db.String(),nullable = False, default = False)
    remarks = db.Column(db.String())
    marked_read = db.Column(db.Boolean,nullable=False,default = False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    superuser_id = db.Column(db.Integer, nullable=False)
    requested_on = db.Column(db.DateTime, nullable=False)
    approved_size = db.Column(db.Integer, default=0)
    
    user_rel = db.relationship("User", backref=db.backref('users_requests', lazy='dynamic'))
    
    def __init__(self, status, user_id,req_size,marked_read,superuser_id,requested_on,remarks,approved_size=0):
        self.approved_size = approved_size
        self.status = status
        self.user_id = user_id
        self.req_size = req_size
        self.remarks = remarks
        self.marked_read = marked_read
        self.superuser_id = superuser_id
        self.requested_on = requested_on
        

    def json(self):
        return {
            'id': self.id,
            'approved_size': self.approved_size,
            'remarks': self.remarks,
            'status': self.status,
            'req_size':self.req_size,
            'user_id': self.user_id,
            'superuser_id': self.superuser_id,
            'marked_read': self.marked_read,
            'requested_on': self.requested_on,
        }
    
    @classmethod
    def get_user_requests(cls,user_id):
        results = db.session.query(
            cls.id,
            cls.req_size,
            cls.status,
            cls.remarks,
            cls.superuser_id,
            cls.user_id,
            cls.marked_read,
            cls.requested_on,
            cls.approved_size,
            User.username,
            User.email,
            UserConfig.folder_name,
            UserConfig.max_size.label('size')
        ).join(User, cls.user_id == User.id
        ).join(UserConfig, User.id == UserConfig.user_id
        ).filter(cls.user_id == user_id
        ).all()
        
        if results:
            json_data = [{'user_id': result.user_id,
                        'superuser_id': result.superuser_id,
                        'marked_read': result.marked_read,
                        'req_size': result.req_size,
                        'status': result.status,
                        'remarks': result.remarks,
                        'username': result.username,
                        'email': result.email,
                        'folder_name': result.folder_name,
                        'size': result.size,
                        'requested_on': result.requested_on,
                        'approved_size': result.approved_size,
                        'id': result.id
                    } for result in results]
            return json_data
        return None
    
    @classmethod
    def get_requests_superuser(cls,user_id):
        results = db.session.query(
            cls.id,
            cls.approved_size,
            cls.req_size,
            cls.status,
            cls.remarks,
            cls.superuser_id,
            cls.user_id,
            cls.marked_read,
            cls.requested_on,
            User.username,
            User.email,
            UserConfig.folder_name,
            UserConfig.max_size.label('size')
        ).join(User, cls.user_id == User.id
        ).join(UserConfig, User.id == UserConfig.user_id
        ).filter(cls.superuser_id == user_id
        ).all()
        
        if results:
            json_data = [{'user_id': result.user_id,
                        'superuser_id': result.superuser_id,
                        'marked_read': result.marked_read,
                        'req_size': result.req_size,
                        'status': result.status,
                        'remarks': result.remarks,
                        'username': result.username,
                        'email': result.email,
                        'folder_name': result.folder_name,
                        'size': result.size,
                        'requested_on': result.requested_on,
                        'approved_size': result.approved_size,
                        'id': result.id
                    } for result in results]
            return json_data
                
    @classmethod
    def get_by_id(cls, id):
        result = cls.query.filter_by(id=id).first()
        if result:
            return result
        return None
    
    def save_to_db(self):
        db.session.add(self)
        db.session.commit()
    
    def update_db(self):
        db.session.commit()
        
        