from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.extensions import db
from app.models import Ticket, TicketCategory, User, Comment
from app.decorators import login_required, agent_or_admin_required, get_current_user
from app.utils.sla import get_sla_metrics

agent_bp = Blueprint('agent', __name__)

@agent_bp.route('/')
@agent_bp.route('/dashboard')
@login_required
@agent_or_admin_required
def dashboard():
    user = get_current_user()

    # Tickets assigned to this agent
    assigned_tickets = Ticket.query.filter_by(assigned_agent_id=user.id).order_by(Ticket.updated_at.desc()).all()
    
    # Unassigned open tickets waiting in queue
    unassigned_tickets = Ticket.query.filter(
        Ticket.assigned_agent_id == None,
        Ticket.status.in_(['Open'])
    ).order_by(Ticket.created_at.asc()).all()

    # Agent workload metrics
    active_assigned = [t for t in assigned_tickets if t.status in ('Assigned', 'In Progress')]
    resolved_assigned = [t for t in assigned_tickets if t.status in ('Resolved', 'Closed')]
    overdue_assigned = [t for t in assigned_tickets if t.is_overdue and t.status not in ('Resolved', 'Closed')]
    escalated_assigned = [t for t in assigned_tickets if t.is_escalated]

    # Today's resolutions
    today_start = datetime.combine(date.today(), datetime.min.time())
    resolved_today = [t for t in resolved_assigned if t.resolved_at and t.resolved_at >= today_start]

    # Calculate average resolution time for this agent
    res_times = []
    for t in resolved_assigned:
        if t.resolved_at and t.created_at:
            delta_hr = (t.resolved_at - t.created_at).total_seconds() / 3600.0
            res_times.append(delta_hr)
    avg_res_time = round(sum(res_times) / len(res_times), 1) if res_times else 0.0

    return render_template(
        'agent/dashboard.html',
        user=user,
        assigned_tickets=assigned_tickets,
        unassigned_tickets=unassigned_tickets,
        active_count=len(active_assigned),
        resolved_count=len(resolved_assigned),
        resolved_today_count=len(resolved_today),
        overdue_count=len(overdue_assigned),
        escalated_count=len(escalated_assigned),
        unassigned_count=len(unassigned_tickets),
        avg_res_time=avg_res_time
    )
