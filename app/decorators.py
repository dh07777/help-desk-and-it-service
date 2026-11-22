from functools import wraps
from flask import session, redirect, url_for, flash, request, abort, g
from app.extensions import db
from app.models import User

def get_current_user():
    if not hasattr(g, 'current_user') or g.current_user is None:
        user_id = session.get('user_id')
        if user_id:
            g.current_user = db.session.get(User, user_id)
        else:
            g.current_user = None
    return g.current_user

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if user is None:
            if request.is_json or request.path.startswith('/api/'):
                return {'error': 'Authentication required'}, 401
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        if not user.is_active:
            session.clear()
            flash('Your account has been deactivated. Please contact an administrator.', 'danger')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*role_names):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if user is None:
                if request.is_json or request.path.startswith('/api/'):
                    return {'error': 'Authentication required'}, 401
                return redirect(url_for('auth.login', next=request.url))
            if not user.is_active:
                session.clear()
                flash('Your account has been deactivated.', 'danger')
                return redirect(url_for('auth.login'))
            
            user_role = user.role.name if user.role else None
            if user_role not in role_names:
                if request.is_json or request.path.startswith('/api/'):
                    return {'error': 'Permission denied'}, 403
                flash('Access denied. You do not have permission to access this resource.', 'danger')
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def admin_required(f):
    return roles_required('admin')(f)

def agent_or_admin_required(f):
    return roles_required('agent', 'admin')(f)

def employee_required(f):
    return roles_required('employee')(f)
