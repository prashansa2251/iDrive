from app.db import db

class Requests(db.Model):
    __tablename__ = "requests"
    
    id = db.Column(db.Integer, primary_key=True)
    req_size = db.Column(db.String(100))
    status = db.Column(db.Boolean,nullable = False, default = False)
    remarks = db.Column(db.String())
    marked_read = db.Column(db.Boolean,nullable=False,default = False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    
    
    user_rel = db.relationship("User", backref=db.backref('users_requests', lazy='dynamic'))
    
    def __init__(self, status, user_id,req_size,marked_read,remarks = None):
        self.status = status
        self.user_id = user_id
        self.req_size = req_size
        self.remarks = remarks
        self.marked_read = marked_read

    def json(self):
        return {
            'id': self.id,
            'remarks': self.remarks,
            'status': self.status,
            'req_size':self.req_size,
            'user_id': self.user_id,
            'marked_read': self.marked_read
        }
    
    def save_to_db(self):
        db.session.add(self)
        db.session.commit()
    
    def update_db(self):
        db.session.commit()
        
        