from flask import Blueprint, flash, json, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user
from app.models.user_config import UserConfig
from app.models.users import User
from app.classes.helpers import HelperClass
from app.models.requests import Requests
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
        HelperClass.create_or_get_user_folder(user.id)
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
    print(message)
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
                    return redirect(url_for('auth.login'))
                else:
                    flash('New and confirm password do not match!')
                    return redirect(url_for('auth.change_password'))
            elif user is None:
                flash('User does not exist!')
            elif not User.check_password(user, password):
                flash('Old password is incorrect')
            elif not user.isActive:
                flash('User is not active. Please contact Admin')
        except Exception as e:
            flash('There was an error while connecting to database!')
            print(e)    
    message = HelperClass.get_message()
    return render_template("auth/change_password.html", flash_message = message)

@blp.route('/storage_details')
@login_required
def storage_details():
    storage_info = HelperClass.get_storage_status(current_user.id)
    users_storage = HelperClass.prepare_multi_progress_bar(storage_info)
    return render_template('auth/storage_details.html',storage_info = storage_info,users_storage=users_storage)

@blp.route('/request_storage', methods=['GET','POST'])
@login_required
def request_storage():
    if not current_user.is_authenticated:
        flash('You must be logged in to view this page!')
        return redirect(url_for('auth.login'))
    
    if request.method=='POST':
        request_size = request.form.get('request_size')
        storage_unit = request.form.get('storage_unit')
        
        requests= HelperClass.create_request(current_user.id,request_size,storage_unit)
        if requests:
            flash('Storage upgrade request created successfully!')
            return redirect(url_for('auth.request_storage'))
        flash('You must be logged in to view this page!')
        return redirect(url_for('auth.login'))
    
    requests,allocated_storage = HelperClass.get_user_requests(current_user.id)
    
    return render_template('auth/request_storage.html',requests = requests,allocated_storage=allocated_storage)
    
    
@blp.route('/approve_request',methods=['POST'])
@login_required
def approve_request():
    if not current_user.is_authenticated:
        flash('You must be logged in to view this page!')
        return redirect(url_for('auth.login'))
    
    req_size = request.form.get('req_size')
    storage_unit = request.form.get('storage_unit')
    user_id = request.form.get('user_id')
    request_id = request.form.get('request_id')
    remarks = request.form.get('remarks')
    storage = HelperClass.get_users_data(current_user.id)[1]
    data = {
        'req_size': req_size,
        'storage_unit': storage_unit,
        'user_id': user_id,
        'request_id': request_id,
        'remarks': remarks,
        'storage_data': storage
    }
    approved = HelperClass.approve_request(data)
    if approved:
        flash('Request approved successfully!')
        return redirect(url_for('auth.requests'))
    else:
        flash('There was an error while approving request!')
        return redirect(url_for('auth.requests'))

    
@blp.route('/reject_request',methods=['POST'])
@login_required
def reject_request():
    if not current_user.is_authenticated:
        flash('You must be logged in to view this page!')
        return redirect(url_for('auth.login'))
    
    req_size = request.form.get('req_size')
    user_id = request.form.get('user_id')
    request_id = request.form.get('request_id')
    remarks = request.form.get('remarks')
    
    data = {
        'req_size': req_size,
        'user_id': user_id,
        'request_id': request_id,
        'remarks': remarks
    }
    rejected = HelperClass.reject_request(data)
    if rejected:
        flash('Request approved successfully!')
        return redirect(url_for('auth.requests'))
    else:
        flash('There was an error while approving request!')
        return redirect(url_for('auth.requests'))
    
@blp.route('/cancel_request/<int:request_id>')
@login_required
def cancel_request(request_id):
    try:
        request_obj = HelperClass.cancel_request(request_id)
        if request_obj:
            flash('Request cancelled successfully!')
            return redirect(url_for('auth.request_storage'))
        else:
            flash('There was an error while connecting to database!')
            return redirect(url_for('auth.request_storage'))
    except Exception as e:
        print(e)
        return redirect(url_for('auth.request_storage'))
    
@blp.route('/mark_request_read/<int:request_id>')
@login_required
def mark_request_read(request_id):
    try:
        request_obj = Requests.get_by_id(request_id)
        request_obj.marked_read = True
        request_obj.update_db()
        if request_obj:
            flash('Request marked as read successfully!')
            return redirect(url_for('auth.requests'))
        else:
            flash('There was an error while connecting to database!')
            return redirect(url_for('auth.requests'))
    except Exception as e:
        print(e)
        flash('There was an error while connecting to database!')
        return redirect(url_for('auth.requests'))

@blp.route('/requests',methods=['POST','GET'])
@login_required
def requests():
    if request.method=='POST':
        if current_user.isAdmin:
            pass
            flash("The request(s) is/are approved!!")
            return jsonify({'redirect_url': url_for('drive.index')})
        else:
            flash("Only admin can approve requests!")
            
    requests,marker = HelperClass.get_superuser_requests(current_user.id)
    
    return render_template('auth/requests.html',
                            requests = requests,
                            marker = marker,
                            flash_message = HelperClass.get_message())

@blp.route('/reset_password', methods=['POST'])
@login_required
def reset_password():
    if current_user.isAdmin: 
        if request.method=='POST':
            try:
                json_data = request.json
                user = User.query.filter_by(id=json_data['user_id']).first()
                if user and user.isActive:
                    reset_pwd = json_data['reset_password']
                    user.set_password(reset_pwd)
                    user.update_db()
                    flash('Password reset successfully! Please login with new password!')
                    return jsonify({'message' : 'Password reset successfull'}),200
                elif user is None:
                    flash('User does not exist!')
                    return jsonify({'message' : 'User does not exist!'}),200
                elif not user.isActive:
                    flash('User is not active!')
                    return jsonify({'message' : 'User is not active!'}),200
            except Exception as e:
                flash('There was an error connecting to database!')
                print(e)
                return jsonify({'message' : 'There was an error connecting to database!'}),200
                        
    else:
        flash("Only admin can reset password!")
        return jsonify({'message' : 'Only admin can reset password!'}),200
    

@blp.route('/manage_users', methods=['POST','GET'])
@login_required
def manage_users():
    if request.method =='POST':
        if current_user.isAdmin:
            json_data = request.json
            for item in json_data:
                if item['id']:
                    user_object = User.get_by_id(item['id'])
                    user_object.isActive = bool(item['isActive'])
                    user_object.update_db()
            flash("The user(s) is/are approved!!")
            return jsonify({'redirect_url': url_for('drive.index')})
        else:
            flash("Only admin can reset password!")
    if current_user.isAdmin:
        
        users,storage = HelperClass.get_users_data(current_user.id)
        superusers = User.get_superusers(current_user.id)
        storage_remaining = storage['remaining'][0]
        message = HelperClass.get_message()
        return render_template('auth/manage_users.html',
                            flash_message = message,
                            superusers=superusers,
                            users=users,
                            storage_remaining=storage_remaining,
                            storage_data=json.dumps(storage),
                            user_data=json.dumps(users))
    else: 
        flash('You must be admin to view this page!')
        return redirect(url_for('auth.login'))
    
@blp.route('/update_storage',methods=['POST'])
@login_required
def update_storage():
    if current_user.is_authenticated:
        if current_user.isAdmin:
            if request.method=='POST':
                json_data = request.json
                user_update = HelperClass.update_user_storage(json_data)
                return jsonify({'redirect_url':url_for('auth.manage_users')})
                
        flash('You must be admin to view this page!')
        return redirect(url_for('auth.login'))
    flash('You must be logged in to view this page!')
    return redirect(url_for('auth.login'))

@blp.route('/update_reporting',methods=['POST'])
@login_required
def update_reporting():
    if current_user.is_authenticated:
        if current_user.isAdmin:
            if request.method=='POST':
                json_data = request.json
                if json_data['reporting_to_id'] == json_data['user_id']:
                    flash('You cannot assign user to self!')
                    return jsonify({'redirect_url':url_for('auth.manage_users')})
                user_update = User.update_reporting(json_data['user_id'],json_data['reporting_to_id'])
                if user_update:
                    flash('Reporting user updated successfully!')
                else:
                    flash('There was an error updating reporting user!')
                return jsonify({'redirect_url':url_for('auth.manage_users')})
                
        flash('You must be admin to view this page!')
        return redirect(url_for('auth.login'))
    flash('You must be logged in to view this page!')
    return redirect(url_for('auth.login'))

@blp.route('/toggle_admin_status',methods=['POST'])
@login_required
def toggle_admin_status():
    if current_user.is_authenticated:
        if current_user.isAdmin:
            if request.method=='POST':
                json_data = request.json
                user_update = User.toggle_admin_status(json_data['user_id'])
                if user_update:
                    flash('User admin status updated successfully!')
                else:
                    flash('There was an error updating user admin status!')
                return jsonify({'redirect_url':url_for('auth.manage_users')})
                
        flash('You must be admin to view this page!')
        return redirect(url_for('auth.login'))
    flash('You must be logged in to view this page!')
    return redirect(url_for('auth.login'))

@blp.route('/toggle_user_status',methods=['POST'])
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

