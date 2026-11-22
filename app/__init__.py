import os
import logging
from flask import Flask, render_template, request, jsonify, g
from app.config import Config
from app.extensions import db, csrf
from app.decorators import get_current_user
from app.models import Notification

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure upload folder exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)

    # Configure logging
    if not app.debug and not app.testing:
        logging.basicConfig(level=logging.INFO)

    # Context processors
    @app.context_processor
    def inject_global_data():
        current_user = get_current_user()
        unread_notifs_count = 0
        if current_user:
            unread_notifs_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return dict(
            current_user=current_user,
            unread_notifs_count=unread_notifs_count,
            app_name="SupportDesk"
        )

    # Custom Jinja filters
    @app.template_filter('datetimeformat')
    def datetimeformat(value, format='%b %d, %Y %I:%M %p'):
        if value is None:
            return ""
        return value.strftime(format)

    @app.template_filter('timeago')
    def timeago(dt):
        if not dt:
            return ""
        from datetime import datetime
        now = datetime.utcnow()
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 0:
            return "just now"
        if seconds < 60:
            return f"{int(seconds)}s ago"
        minutes = seconds / 60
        if minutes < 60:
            return f"{int(minutes)}m ago"
        hours = minutes / 60
        if hours < 24:
            return f"{int(hours)}h ago"
        days = hours / 24
        if days < 30:
            return f"{int(days)}d ago"
        return dt.strftime('%b %d, %Y')

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.main import main_bp
    from app.routes.employee import employee_bp
    from app.routes.agent import agent_bp
    from app.routes.admin import admin_bp
    from app.routes.tickets import tickets_bp
    from app.routes.api import api_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp)
    app.register_blueprint(employee_bp, url_prefix='/employee')
    app.register_blueprint(agent_bp, url_prefix='/agent')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(tickets_bp, url_prefix='/tickets')
    app.register_blueprint(api_bp, url_prefix='/api')

    # Error Handlers
    @app.errorhandler(403)
    def forbidden(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Forbidden', 'message': 'You lack permissions to access this resource.'}), 403
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Not Found', 'message': 'The requested resource was not found.'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'Internal Server Error', 'message': 'An unexpected error occurred.'}), 500
        return render_template('errors/500.html'), 500

    @app.errorhandler(413)
    def request_entity_too_large(error):
        if request.is_json or request.path.startswith('/api/'):
            return jsonify({'error': 'File Too Large', 'message': 'The uploaded file exceeds the maximum limit.'}), 413
        return render_template('errors/413.html'), 413

    return app
