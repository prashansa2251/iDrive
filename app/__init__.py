from flask import Flask, request
from flask_login import LoginManager
from flask_migrate import Migrate
from app.routes.drive import create_drive_blp
from app.routes.wasabi_drive import app as wasabi_drive_blp
from app.routes.auth import blp as auth_blp
import os 
from app.db import db
from app.models.users import User
from flask_socketio import SocketIO
from dotenv import load_dotenv
socketio = SocketIO()

def create_app():
# Initialize Flask app
    app = Flask(__name__)
    load_dotenv()
    app.config['SECRET_KEY'] = 'simple-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URI')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    socketio.init_app(app, cors_allowed_origins="*")
    #db register
    db.init_app(app)
    current_directory = os.getcwd()
    migrations_directory = current_directory + '/migrations'
    migrate = Migrate(app, db, directory=migrations_directory)
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Socket.IO connection handling
    @socketio.on('connect')
    def handle_connect():
        print(f'Client connected: {request.sid}')

    @socketio.on('disconnect')
    def handle_disconnect():
        print(f'Client disconnected: {request.sid}')
        
    app.register_blueprint(create_drive_blp(socketio))
    app.register_blueprint(wasabi_drive_blp,url_prefix='/wasabi')
    app.register_blueprint(auth_blp,url_prefix='/auth')
    
    return app
