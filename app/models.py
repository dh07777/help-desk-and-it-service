import secrets
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

class Role(db.Model):
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)  # 'employee', 'agent', 'admin'
    description = db.Column(db.String(200))
    
    users = db.relationship('User', back_populates='role', lazy=True)

    def __repr__(self):
        return f"<Role {self.name}>"

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    department = db.Column(db.String(100), default='General')
    phone = db.Column(db.String(30), nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    reset_token = db.Column(db.String(100), nullable=True, index=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    role = db.relationship('Role', back_populates='users')
    created_tickets = db.relationship('Ticket', foreign_keys='Ticket.creator_id', back_populates='creator', lazy=True)
    assigned_tickets = db.relationship('Ticket', foreign_keys='Ticket.assigned_agent_id', back_populates='assigned_agent', lazy=True)
    comments = db.relationship('Comment', back_populates='user', lazy=True)
    notifications = db.relationship('Notification', back_populates='user', lazy=True, order_by='desc(Notification.created_at)')
    feedbacks = db.relationship('Feedback', back_populates='user', lazy=True)
    audit_logs = db.relationship('AuditLog', back_populates='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    def generate_reset_token(self, expires_in_hours=2):
        self.reset_token = secrets.token_urlsafe(32)
        self.reset_token_expiry = datetime.utcnow() + timedelta(hours=expires_in_hours)
        return self.reset_token

    def verify_reset_token(self, token):
        if not self.reset_token or self.reset_token != token:
            return False
        if not self.reset_token_expiry or datetime.utcnow() > self.reset_token_expiry:
            return False
        return True

    @property
    def is_admin(self):
        return self.role and self.role.name == 'admin'

    @property
    def is_agent(self):
        return self.role and self.role.name == 'agent'

    @property
    def is_employee(self):
        return self.role and self.role.name == 'employee'
        
    @property
    def initials(self):
        parts = self.full_name.strip().split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        elif parts:
            return parts[0][:2].upper()
        return "U"

    def to_dict(self):
        return {
            'id': self.id,
            'role': self.role.name if self.role else None,
            'email': self.email,
            'full_name': self.full_name,
            'department': self.department,
            'phone': self.phone,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<User {self.email} ({self.role.name if self.role else 'no-role'})>"

class TicketCategory(db.Model):
    __tablename__ = 'ticket_categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    default_priority = db.Column(db.String(20), default='Medium', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    tickets = db.relationship('Ticket', back_populates='category', lazy=True)
    articles = db.relationship('KnowledgeArticle', back_populates='category', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'default_priority': self.default_priority,
            'is_active': self.is_active,
            'tickets_count': len(self.tickets)
        }

    def __repr__(self):
        return f"<TicketCategory {self.name}>"

class SLAPolicy(db.Model):
    __tablename__ = 'sla_policies'
    
    id = db.Column(db.Integer, primary_key=True)
    priority = db.Column(db.String(20), unique=True, nullable=False)  # 'Low', 'Medium', 'High', 'Critical'
    response_time_hours = db.Column(db.Float, nullable=False)
    resolution_time_hours = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(255), nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'priority': self.priority,
            'response_time_hours': self.response_time_hours,
            'resolution_time_hours': self.resolution_time_hours,
            'description': self.description
        }

    def __repr__(self):
        return f"<SLAPolicy {self.priority}: {self.response_time_hours}h resp / {self.resolution_time_hours}h res>"

class Ticket(db.Model):
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), unique=True, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('ticket_categories.id'), nullable=False)
    priority = db.Column(db.String(20), default='Medium', nullable=False)  # Low, Medium, High, Critical
    status = db.Column(db.String(30), default='Open', nullable=False)      # Open, Assigned, In Progress, Resolved, Closed
    
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_agent_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    is_escalated = db.Column(db.Boolean, default=False, nullable=False)
    escalation_reason = db.Column(db.Text, nullable=True)
    escalation_level = db.Column(db.Integer, default=0, nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    response_due_at = db.Column(db.DateTime, nullable=True)
    resolution_due_at = db.Column(db.DateTime, nullable=True)
    first_responded_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    category = db.relationship('TicketCategory', back_populates='tickets')
    creator = db.relationship('User', foreign_keys=[creator_id], back_populates='created_tickets')
    assigned_agent = db.relationship('User', foreign_keys=[assigned_agent_id], back_populates='assigned_tickets')
    comments = db.relationship('Comment', back_populates='ticket', cascade='all, delete-orphan', lazy=True, order_by='Comment.created_at')
    attachments = db.relationship('Attachment', back_populates='ticket', cascade='all, delete-orphan', lazy=True)
    assignments = db.relationship('TicketAssignment', back_populates='ticket', cascade='all, delete-orphan', lazy=True, order_by='TicketAssignment.assigned_at.desc()')
    feedback = db.relationship('Feedback', back_populates='ticket', uselist=False, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', back_populates='ticket', cascade='all, delete-orphan', lazy=True, order_by='AuditLog.timestamp.desc()')

    def is_response_overdue(self):
        if not self.response_due_at:
            return False
        # Overdue if not yet responded and now > response_due_at
        if not self.first_responded_at:
            return datetime.utcnow() > self.response_due_at
        # Or responded after deadline
        return self.first_responded_at > self.response_due_at

    def is_resolution_overdue(self):
        if not self.resolution_due_at:
            return False
        # Overdue if not resolved/closed and now > resolution_due_at
        if self.status not in ('Resolved', 'Closed'):
            return datetime.utcnow() > self.resolution_due_at
        # Or if resolved, was it resolved after deadline?
        if self.resolved_at:
            return self.resolved_at > self.resolution_due_at
        return False

    @property
    def is_overdue(self):
        return self.is_response_overdue() or self.is_resolution_overdue()

    @property
    def sla_status(self):
        if self.status in ('Resolved', 'Closed'):
            if self.is_resolution_overdue():
                return 'Breached'
            return 'Compliant'
        if self.is_resolution_overdue() or self.is_response_overdue():
            return 'Overdue'
        return 'On Track'

    @property
    def priority_badge_class(self):
        mapping = {
            'Low': 'badge-low',
            'Medium': 'badge-medium',
            'High': 'badge-high',
            'Critical': 'badge-critical'
        }
        return mapping.get(self.priority, 'badge-secondary')

    @property
    def status_badge_class(self):
        mapping = {
            'Open': 'badge-open',
            'Assigned': 'badge-assigned',
            'In Progress': 'badge-inprogress',
            'Resolved': 'badge-resolved',
            'Closed': 'badge-closed'
        }
        return mapping.get(self.status, 'badge-secondary')

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_number': self.ticket_number,
            'title': self.title,
            'description': self.description,
            'category': self.category.name if self.category else None,
            'category_id': self.category_id,
            'priority': self.priority,
            'status': self.status,
            'creator': {
                'id': self.creator.id,
                'name': self.creator.full_name,
                'email': self.creator.email,
                'department': self.creator.department
            } if self.creator else None,
            'assigned_agent': {
                'id': self.assigned_agent.id,
                'name': self.assigned_agent.full_name,
                'email': self.assigned_agent.email
            } if self.assigned_agent else None,
            'is_escalated': self.is_escalated,
            'escalation_reason': self.escalation_reason,
            'escalation_level': self.escalation_level,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'response_due_at': self.response_due_at.isoformat() if self.response_due_at else None,
            'resolution_due_at': self.resolution_due_at.isoformat() if self.resolution_due_at else None,
            'first_responded_at': self.first_responded_at.isoformat() if self.first_responded_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None,
            'closed_at': self.closed_at.isoformat() if self.closed_at else None,
            'is_overdue': self.is_overdue,
            'sla_status': self.sla_status,
            'comments_count': len(self.comments),
            'attachments_count': len(self.attachments),
            'has_feedback': self.feedback is not None
        }

    def __repr__(self):
        return f"<Ticket {self.ticket_number} - {self.title[:30]}>"

class TicketAssignment(db.Model):
    __tablename__ = 'ticket_assignments'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    agent_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text, nullable=True)
    
    ticket = db.relationship('Ticket', back_populates='assignments')
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_id])
    agent = db.relationship('User', foreign_keys=[agent_id])

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'assigned_by': self.assigned_by.full_name if self.assigned_by else None,
            'agent': self.agent.full_name if self.agent else None,
            'assigned_at': self.assigned_at.isoformat(),
            'notes': self.notes
        }

class Comment(db.Model):
    __tablename__ = 'comments'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_internal = db.Column(db.Boolean, default=False, nullable=False)  # Private agent/admin note
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ticket = db.relationship('Ticket', back_populates='comments')
    user = db.relationship('User', back_populates='comments')
    attachments = db.relationship('Attachment', back_populates='comment', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'author': {
                'id': self.user.id,
                'name': self.user.full_name,
                'role': self.user.role.name if self.user.role else 'user',
                'initials': self.user.initials
            } if self.user else None,
            'content': self.content,
            'is_internal': self.is_internal,
            'created_at': self.created_at.isoformat(),
            'attachments': [a.to_dict() for a in self.attachments]
        }

class Attachment(db.Model):
    __tablename__ = 'attachments'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'), nullable=True)
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # bytes
    mime_type = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ticket = db.relationship('Ticket', back_populates='attachments')
    comment = db.relationship('Comment', back_populates='attachments')
    uploader = db.relationship('User')

    @property
    def file_size_display(self):
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.1f} KB"
        return f"{self.file_size / (1024 * 1024):.2f} MB"

    @property
    def is_image(self):
        if self.mime_type and self.mime_type.startswith('image/'):
            return True
        ext = self.original_filename.rsplit('.', 1)[-1].lower() if '.' in self.original_filename else ''
        return ext in {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'file_size_display': self.file_size_display,
            'mime_type': self.mime_type,
            'is_image': self.is_image,
            'uploader_name': self.uploader.full_name if self.uploader else 'Unknown',
            'created_at': self.created_at.isoformat()
        }

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', back_populates='notifications')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'message': self.message,
            'link': self.link,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat()
        }

class KnowledgeArticle(db.Model):
    __tablename__ = 'knowledge_articles'
    
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey('ticket_categories.id'), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    is_published = db.Column(db.Boolean, default=True, nullable=False)
    views_count = db.Column(db.Integer, default=0, nullable=False)
    helpful_count = db.Column(db.Integer, default=0, nullable=False)
    not_helpful_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    category = db.relationship('TicketCategory', back_populates='articles')
    author = db.relationship('User')

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'slug': self.slug,
            'content': self.content,
            'category': self.category.name if self.category else 'General',
            'category_id': self.category_id,
            'author': self.author.full_name if self.author else 'Support Team',
            'is_published': self.is_published,
            'views_count': self.views_count,
            'helpful_count': self.helpful_count,
            'not_helpful_count': self.not_helpful_count,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class Feedback(db.Model):
    __tablename__ = 'feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1 to 5
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    ticket = db.relationship('Ticket', back_populates='feedback')
    user = db.relationship('User', back_populates='feedbacks')

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'user': self.user.full_name if self.user else 'Anonymous',
            'rating': self.rating,
            'comment': self.comment,
            'created_at': self.created_at.isoformat()
        }

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    ticket = db.relationship('Ticket', back_populates='audit_logs')
    user = db.relationship('User', back_populates='audit_logs')

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'actor': self.user.full_name if self.user else 'System',
            'action': self.action,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }
