from app.db import db

class UserConfig(db.Model):
    __tablename__ = "user_config"
    
    id = db.Column(db.Integer, primary_key=True)
    folder_name = db.Column(db.String(100))
    max_size = db.Column(db.Integer()) # in MB
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    storage_upgraded = db.Column(db.Boolean,default='False')
    
    user = db.relationship("User", backref=db.backref('users', lazy='dynamic'))
    
    def __init__(self, folder_name, max_size,storage_upgraded,user_id):
        self.folder_name = folder_name
        self.max_size = max_size
        self.user_id = user_id
        self.storage_upgraded = storage_upgraded

    def json(self):
        return {
            'id': self.id,
            'folder_name': self.folder_name,
            'max_size': self.max_size,
            'user_id': self.user_id,
            'storage_upgraded': self.storage_upgraded
        }
    
    def save_to_db(self):
        db.session.add(self)
        db.session.commit()
    
    def update_db(self):
        db.session.commit()
        
        
    @classmethod
    def find_by_folder_name(cls, folder_name):
        return cls.query.filter_by(folder_name=folder_name).first()
    
    @classmethod
    def get_by_user_id(cls, user_id):
        return cls.query.filter_by(user_id=user_id).first()
    
    @classmethod
    def update_storage(cls,user_id,max_size):
        user_config = cls.query.filter_by(user_id=user_id).first()
        user_config.max_size = max_size
        user_config.update_db()
        return True
    
    @classmethod
    def get_folder_name(cls,user_id):
        user_config = cls.query.filter_by(user_id=user_id).first()
        return user_config.folder_name
    
    @classmethod
    def get_allocated_storage(cls,user_id):
        user = cls.query.filter_by(user_id=user_id).first()
        return float(user.max_size)