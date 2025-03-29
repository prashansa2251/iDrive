from flask import Blueprint, flash, get_flashed_messages, json, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from app.models.user_config import UserConfig
from app.models.users import User
from app.classes.helpers import HelperClass
blp = Blueprint("auth","auth")


@blp.route('/register', methods=['POST','GET'])
def register():
    message = HelperClass.get_message()
    if request.method=='POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        user = User.find_by_email(email.lower())
        if user:
            flash('Email already registered!')
            return redirect(url_for('auth.register'))

        user = User(username,email.lower(),password,False,False)
        user.set_password(password)
        user.save_to_db()
        user = User.find_by_email(email.lower())
        folder_name = str(user.id)+'_'+user.username.lower().replace(' ','_')
        user_config = UserConfig(folder_name,0.0,user.id)
        user_config.save_to_db()
        flash('Registered successfully!')
        return redirect(url_for('auth.login'))
    return render_template("auth/register.html", 
                           flash_message=message)

@blp.route('/login', methods=['POST','GET'])
def login():
    if request.method=='POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:        
            user = User.query.filter_by(email=email.lower()).first()
            if user and User.check_password(user, password) and user.isActive:
                login_user(user)
                
                return redirect(url_for('drive.index'))
            elif user is None:
                flash('User does not exist!')
            elif not User.check_password(user, password):
                flash('Password is incorrect')
            elif not user.isActive:
                flash('User is not authorized. Please contact admin !!')
        except Exception as e:
            flash('There was an error while connecting to database!')
            print(e)
    message = HelperClass.get_message()
    return render_template('auth/login.html', flash_message = message)

@blp.route('/logout')
def logout():
    logout_user()
    session.clear()
    session['logged_out']=True
    return redirect(url_for('.login'))

@blp.route('/change_password', methods=['POST','GET'])
@login_required
def change_password():
    if request.method=='POST':
        password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        try:
            user = User.query.filter_by(id=current_user.id).first()
            if user and User.check_password(user, password) and user.isActive:
                if new_password == confirm_password:
                    user.set_password(new_password)
                    user.update_db()
                    flash('Password changed successfully! Please login with new password!')
                    return redirect(url_for('auth.logout'))
                else:
                    flash('new and confirm password do not match!')
                    return redirect(url_for('auth.change_password'))
            elif user is None:
                flash('User does not exist!')
            elif not User.check_password(user, password):
                flash('Old password is incorrect')
            elif not user.isActive:
                flash('User is not active. Please contact State Coordinator')
        except Exception as e:
            flash('There was an error while connecting to database!')
            print(e)    
    message = HelperClass.get_message()
    return render_template("auth/change_password.html", flash_message = message)

@blp.route('/forgot_password')
@login_required
def forgot_password():
    return render_template("auth/forgot_password.html")

@blp.route('/reset_password', methods=['POST','GET'])
@login_required
def reset_password():
    if current_user.isAdmin: 
        users = User.get_all()           
        if request.method=='POST':
            try:
                json_data = request.json
                user = User.query.filter_by(id=json_data['id']).first()
                if user and user.isActive:
                    reset_pwd = user.username[:4] + '_123'
                    user.set_password(reset_pwd)
                    user.update_db()
                    flash('Password reset successfully! Please login with new password!')
                    return {'redirect_url' : url_for('auth.approve')}
                elif user is None:
                    flash('User does not exist!')
                elif not user.isActive:
                    flash('User is not active!')
            except Exception as e:
                flash('There was an error connecting to database!')
                print(e)        
        # return render_template("auth/reset_password.html")
    else:
        flash("Only admin can reset password!")
    message = HelperClass.get_message()
    return render_template("auth/reset_password.html",
                           post_url = url_for('.reset_password'),
                           flash_message = message,
                           users=users,
                           user_data=json.dumps(users))
    

@blp.route('/manage_users', methods=['POST','GET'])
@login_required
def manage_users():
    if request.method =='POST':
        json_data = request.json
        for item in json_data:
            if item['id']:
                user_object = User.get_by_id(item['id'])
                user_object.isActive = bool(item['isActive'])
                user_object.update_db()
        flash("The user(s) is/are approved!!")
        return jsonify({'redirect_url': url_for('drive.index')})
    if current_user.isAdmin:
        users = User.get_all()
        # states = State.get_all()
        message = HelperClass.get_message()
        return render_template('auth/manage_users.html',
                            flash_message = message,
                            users=users,
                            user_data=json.dumps(users))
    else: 
        flash('You must be admin to view this page!')
        return redirect(url_for('auth.login'))
    
@blp.route('/update_storage',methods=['POST','GET'])
@login_required
def update_storage():
    if current_user.is_authenticated:
        if current_user.isAdmin:
            if request.method=='POST':
                json_data = request.json
                user_update = UserConfig.update_storage(json_data['user_id'],json_data['storage_volume'])
                if user_update:
                    return jsonify({'response':True})
                else:
                    return jsonify({'response':False})
        flash('You must be admin to view this page!')
        return redirect(url_for('auth.login'))
    flash('You must be logged in to view this page!')
    return redirect(url_for('auth.login'))

@blp.route('/toggle_user_status',methods=['POST','GET'])
@login_required
def toggle_user_status():
    if current_user.is_authenticated:
        if current_user.isAdmin:
            if request.method=='POST':
                json_data = request.json
                user_update = User.toggle_user_status(json_data['user_id'])
                if user_update:
                    return jsonify({'response':True})
                else:
                    return jsonify({'response':False})
        flash('You must be admin to view this page!')
        return redirect(url_for('auth.login'))
    flash('You must be logged in to view this page!')
    return redirect(url_for('auth.login'))

