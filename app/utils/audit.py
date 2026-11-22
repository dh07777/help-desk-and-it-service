from datetime import datetime
from flask import g
from app.extensions import db
from app.models import AuditLog

def log_audit(ticket_id, action, old_value=None, new_value=None, details=None, user_id=None):
    """
    Creates an audit log entry for tracking ticket activities and history.
    """
    if user_id is None:
        if hasattr(g, 'current_user') and g.current_user:
            user_id = g.current_user.id
            
    audit_entry = AuditLog(
        ticket_id=ticket_id,
        user_id=user_id,
        action=action,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        details=details,
        timestamp=datetime.utcnow()
    )
    db.session.add(audit_entry)
    return audit_entry
