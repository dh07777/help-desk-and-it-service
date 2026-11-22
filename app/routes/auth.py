from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from app.extensions import db
from app.models import User, Role
from app.decorators import login_required, get_current_user

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # Only redirect authenticated users on GET requests
    if request.method == 'GET' and get_current_user():
        user = g.current_user
        if user.is_admin:
            return redirect(url_for('admin.dashboard'))
        elif user.is_agent:
            return redirect(url_for('agent.dashboard'))
        else:
            return redirect(url_for('employee.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        if not email or not password:
            flash('Please provide both email and password.', 'warning')
            return render_template('auth/login.html')

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact an administrator.', 'danger')
                return render_template('auth/login.html')

            session.clear()
            session.permanent = remember
            session['user_id'] = user.id
            g.current_user = user
            flash(f'Welcome back, {user.full_name}!', 'success')

            next_url = request.args.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)

            if user.is_admin:
                return redirect(url_for('admin.dashboard'))
            elif user.is_agent:
                return redirect(url_for('agent.dashboard'))
            else:
                return redirect(url_for('employee.dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET' and get_current_user():
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        department = request.form.get('department', 'General').strip()
        phone = request.form.get('phone', '').strip()

        if not full_name or not email or not password:
            flash('All required fields must be filled.', 'warning')
            return render_template('auth/register.html')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'warning')
            return render_template('auth/register.html')

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with this email already exists.', 'warning')
            return render_template('auth/register.html')

        # Get or create 'employee' role
        employee_role = Role.query.filter_by(name='employee').first()
        if not employee_role:
            employee_role = Role(name='employee', description='Standard Customer/Employee user')
            db.session.add(employee_role)
            db.session.commit()

        new_user = User(
            full_name=full_name,
            email=email,
            role_id=employee_role.id,
            department=department or 'General',
            phone=phone
        )
        new_user.set_password(password)

        db.session.add(new_user)
        db.session.commit()

        session.clear()
        session['user_id'] = new_user.id
        g.current_user = new_user
        flash('Account created successfully! Welcome to SupportDesk.', 'success')
        return redirect(url_for('employee.dashboard'))

    return render_template('auth/register.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    if hasattr(g, 'current_user'):
        g.current_user = None
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    reset_link = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            token = user.generate_reset_token()
            db.session.commit()
            reset_link = url_for('auth.reset_password', token=token, _external=True)
            flash('Password reset token generated. In a production environment with SMTP, this link is emailed directly.', 'info')
        else:
            flash('If an account exists with that email, a password reset link has been prepared.', 'info')

    return render_template('auth/forgot_password.html', reset_link=reset_link)

@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.verify_reset_token(token):
        flash('The password reset link is invalid or has expired. Please request a new one.', 'danger')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'warning')
            return render_template('auth/reset_password.html', token=token)

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/reset_password.html', token=token)

        user.set_password(password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()

        flash('Your password has been successfully reset! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = get_current_user()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_info':
            full_name = request.form.get('full_name', '').strip()
            department = request.form.get('department', '').strip()
            phone = request.form.get('phone', '').strip()

            if not full_name:
                flash('Full Name is required.', 'warning')
            else:
                user.full_name = full_name
                user.department = department
                user.phone = phone
                user.updated_at = datetime.utcnow()
                db.session.commit()
                flash('Profile information updated successfully.', 'success')

        elif action == 'change_password':
            current_password = request.form.get('current_password', '')
            new_password = request.form.get('new_password', '')
            confirm_password = request.form.get('confirm_password', '')

            if not user.check_password(current_password):
                flash('Current password is incorrect.', 'danger')
            elif len(new_password) < 6:
                flash('New password must be at least 6 characters long.', 'warning')
            elif new_password != confirm_password:
                flash('New passwords do not match.', 'danger')
            else:
                user.set_password(new_password)
                db.session.commit()
                flash('Password changed successfully!', 'success')

        return redirect(url_for('auth.profile'))

    return render_template('auth/profile.html', user=user)
