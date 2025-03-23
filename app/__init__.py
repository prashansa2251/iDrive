from flask import Flask
from app.routes.drive import app as drive_blp
def create_app():
# Initialize Flask app
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'simple-secret-key'
    app.register_blueprint(drive_blp)
    return app