from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request, g
from flask_wtf.csrf import generate_csrf
from sqlalchemy import func
from app.extensions import db
from app.models import (
    Notification, KnowledgeArticle, Ticket, TicketCategory, 
    User, Role, SLAPolicy
)
from app.decorators import login_required, get_current_user
from app.utils.sla import get_sla_metrics

api_bp = Blueprint('api', __name__)

@api_bp.route('/csrf-token')
def get_csrf_token():
    return jsonify({'csrf_token': generate_csrf()})

@api_bp.route('/notifications')
@login_required
def get_notifications():
    user = get_current_user()
    limit = request.args.get('limit', 15, type=int)
    notifs = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(limit).all()
    unread_count = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    
    return jsonify({
        'unread_count': unread_count,
        'notifications': [n.to_dict() for n in notifs]
    })

@api_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    user = get_current_user()
    notif = Notification.query.filter_by(id=notif_id, user_id=user.id).first_or_404()
    notif.is_read = True
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Notification marked as read'})

@api_bp.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    user = get_current_user()
    Notification.query.filter_by(user_id=user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'All notifications marked as read'})

@api_bp.route('/kb/search')
def kb_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])

    articles = KnowledgeArticle.query.filter(
        KnowledgeArticle.is_published == True,
        (KnowledgeArticle.title.ilike(f'%{q}%')) | (KnowledgeArticle.content.ilike(f'%{q}%'))
    ).limit(8).all()

    return jsonify([{
        'id': a.id,
        'title': a.title,
        'slug': a.slug,
        'category': a.category.name if a.category else 'General',
        'helpful_count': a.helpful_count,
        'views_count': a.views_count
    } for a in articles])

@api_bp.route('/kb/<int:article_id>/vote', methods=['POST'])
def kb_vote(article_id):
    article = KnowledgeArticle.query.get_or_404(article_id)
    data = request.get_json(silent=True) or request.form
    vote_type = data.get('vote') # 'helpful' or 'not_helpful'

    if vote_type == 'helpful':
        article.helpful_count += 1
    elif vote_type == 'not_helpful':
        article.not_helpful_count += 1
    else:
        return jsonify({'error': 'Invalid vote type'}), 400

    db.session.commit()
    return jsonify({
        'status': 'success',
        'helpful_count': article.helpful_count,
        'not_helpful_count': article.not_helpful_count
    })

@api_bp.route('/stats/dashboard')
@login_required
def dashboard_stats():
    # Role check: only staff/admin gets full system stats
    user = get_current_user()
    if user.is_employee:
        # Give personal summary for employee
        open_c = Ticket.query.filter_by(creator_id=user.id, status='Open').count()
        inprogress_c = Ticket.query.filter(Ticket.creator_id == user.id, Ticket.status.in_(['Assigned', 'In Progress'])).count()
        resolved_c = Ticket.query.filter(Ticket.creator_id == user.id, Ticket.status.in_(['Resolved', 'Closed'])).count()
        return jsonify({
            'status_breakdown': {'labels': ['Open', 'In Progress', 'Resolved/Closed'], 'data': [open_c, inprogress_c, resolved_c]}
        })

    # Status distribution
    status_counts = db.session.query(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status).all()
    status_dict = dict(status_counts)
    all_statuses = ['Open', 'Assigned', 'In Progress', 'Resolved', 'Closed']
    status_data = {
        'labels': all_statuses,
        'data': [status_dict.get(s, 0) for s in all_statuses]
    }

    # Priority distribution
    priority_counts = db.session.query(Ticket.priority, func.count(Ticket.id)).group_by(Ticket.priority).all()
    priority_dict = dict(priority_counts)
    all_priorities = ['Low', 'Medium', 'High', 'Critical']
    priority_data = {
        'labels': all_priorities,
        'data': [priority_dict.get(p, 0) for p in all_priorities]
    }

    # Category distribution
    categories = TicketCategory.query.all()
    cat_labels = [c.name for c in categories]
    cat_data = [len(c.tickets) for c in categories]

    # Daily ticket volume trend for last 14 days
    today = datetime.utcnow().date()
    days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    day_labels = [d.strftime('%b %d') for d in days]
    created_counts = []
    resolved_counts = []

    for d in days:
        day_start = datetime.combine(d, datetime.min.time())
        day_end = datetime.combine(d, datetime.max.time())
        c_count = Ticket.query.filter(Ticket.created_at >= day_start, Ticket.created_at <= day_end).count()
        r_count = Ticket.query.filter(Ticket.resolved_at >= day_start, Ticket.resolved_at <= day_end).count()
        created_counts.append(c_count)
        resolved_counts.append(r_count)

    # SLA metrics
    sla_metrics = get_sla_metrics()

    # Agent performance workload
    agent_role = Role.query.filter_by(name='agent').first()
    agents = User.query.filter_by(role_id=agent_role.id).all() if agent_role else []
    agent_names = [a.full_name for a in agents]
    agent_assigned = [Ticket.query.filter_by(assigned_agent_id=a.id).count() for a in agents]
    agent_resolved = [Ticket.query.filter(Ticket.assigned_agent_id == a.id, Ticket.status.in_(['Resolved', 'Closed'])).count() for a in agents]

    return jsonify({
        'status_breakdown': status_data,
        'priority_breakdown': priority_data,
        'category_breakdown': {'labels': cat_labels, 'data': cat_data},
        'volume_trends': {
            'labels': day_labels,
            'created': created_counts,
            'resolved': resolved_counts
        },
        'agent_performance': {
            'labels': agent_names,
            'assigned': agent_assigned,
            'resolved': agent_resolved
        },
        'sla_metrics': sla_metrics
    })
