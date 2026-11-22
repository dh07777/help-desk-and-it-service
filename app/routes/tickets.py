import os
from datetime import datetime
from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, g, abort, send_from_directory, current_app, jsonify
)
from app.extensions import db
from app.models import (
    Ticket, TicketCategory, User, Role, Comment, 
    Attachment, TicketAssignment, Feedback, AuditLog
)
from app.decorators import login_required, agent_or_admin_required, get_current_user
from app.utils.sla import update_ticket_sla_deadlines
from app.utils.audit import log_audit
from app.utils.uploads import save_uploaded_file
from app.utils.notifications import trigger_ticket_notification

tickets_bp = Blueprint('tickets', __name__)

@tickets_bp.route('/')
@login_required
def list_tickets():
    user = get_current_user()

    # Base query based on role
    query = Ticket.query
    if user.is_employee:
        query = query.filter_by(creator_id=user.id)

    # Search filter
    search_q = request.args.get('q', '').strip()
    if search_q:
        search_filter = (
            (Ticket.ticket_number.ilike(f'%{search_q}%')) |
            (Ticket.title.ilike(f'%{search_q}%')) |
            (Ticket.description.ilike(f'%{search_q}%'))
        )
        query = query.filter(search_filter)

    # Status filter
    status = request.args.get('status')
    if status and status != 'all':
        query = query.filter_by(status=status)

    # Priority filter
    priority = request.args.get('priority')
    if priority and priority != 'all':
        query = query.filter_by(priority=priority)

    # Category filter
    category_id = request.args.get('category_id', type=int)
    if category_id:
        query = query.filter_by(category_id=category_id)

    # Assignee filter (for staff)
    if not user.is_employee:
        assignee_id = request.args.get('assignee_id')
        if assignee_id == 'unassigned':
            query = query.filter(Ticket.assigned_agent_id == None)
        elif assignee_id and assignee_id != 'all':
            query = query.filter_by(assigned_agent_id=int(assignee_id))

    # Escalated filter
    if request.args.get('escalated') == '1':
        query = query.filter_by(is_escalated=True)

    # Overdue filter
    if request.args.get('overdue') == '1':
        now = datetime.utcnow()
        query = query.filter(
            Ticket.status.notin_(['Resolved', 'Closed']),
            (Ticket.resolution_due_at < now) | (Ticket.response_due_at < now)
        )

    # Sorting
    sort_by = request.args.get('sort', 'created_desc')
    if sort_by == 'created_asc':
        query = query.order_by(Ticket.created_at.asc())
    elif sort_by == 'updated_desc':
        query = query.order_by(Ticket.updated_at.desc())
    elif sort_by == 'priority_desc':
        # Custom order could be done or alphabetical
        query = query.order_by(Ticket.priority.desc(), Ticket.created_at.desc())
    elif sort_by == 'sla_due':
        query = query.order_by(Ticket.resolution_due_at.asc())
    else:
        query = query.order_by(Ticket.created_at.desc())

    # Pagination
    page = request.args.get('page', 1, type=int)
    per_page = 10
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    tickets = pagination.items

    categories = TicketCategory.query.filter_by(is_active=True).all()
    
    agent_role = Role.query.filter_by(name='agent').first()
    agents = User.query.filter_by(role_id=agent_role.id, is_active=True).all() if agent_role else []

    return render_template(
        'tickets/list.html',
        tickets=tickets,
        pagination=pagination,
        categories=categories,
        agents=agents,
        current_status=status or 'all',
        current_priority=priority or 'all',
        current_category=category_id,
        current_assignee=request.args.get('assignee_id', 'all'),
        current_search=search_q,
        current_sort=sort_by,
        user=user
    )

@tickets_bp.route('/<int:ticket_id>')
@login_required
def view_ticket(ticket_id):
    user = get_current_user()
    ticket = Ticket.query.get_or_404(ticket_id)

    # Role permission check: employee can only see their own ticket
    if user.is_employee and ticket.creator_id != user.id:
        flash('You are not authorized to view this ticket.', 'danger')
        abort(403)

    # Filter comments: employees should NOT see internal notes!
    comments_query = Comment.query.filter_by(ticket_id=ticket.id)
    if user.is_employee:
        comments_query = comments_query.filter_by(is_internal=False)
    comments = comments_query.order_by(Comment.created_at.asc()).all()

    # Agents list for assignment dropdown
    agent_role = Role.query.filter_by(name='agent').first()
    agents = User.query.filter_by(role_id=agent_role.id, is_active=True).all() if agent_role else []

    categories = TicketCategory.query.filter_by(is_active=True).all()

    return render_template(
        'tickets/view.html',
        ticket=ticket,
        comments=comments,
        agents=agents,
        categories=categories,
        user=user
    )

@tickets_bp.route('/<int:ticket_id>/comment', methods=['POST'])
@login_required
def add_comment(ticket_id):
    user = get_current_user()
    ticket = Ticket.query.get_or_404(ticket_id)

    if user.is_employee and ticket.creator_id != user.id:
        abort(403)

    content = request.form.get('content', '').strip()
    is_internal = bool(request.form.get('is_internal'))

    # Only staff can make internal comments
    if is_internal and user.is_employee:
        is_internal = False

    if not content:
        flash('Comment cannot be empty.', 'warning')
        return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

    comment = Comment(
        ticket_id=ticket.id,
        user_id=user.id,
        content=content,
        is_internal=is_internal,
        created_at=datetime.utcnow()
    )
    db.session.add(comment)
    db.session.flush()

    # Track first response time for SLA if staff responds publicly
    if not is_internal and (user.is_agent or user.is_admin) and not ticket.first_responded_at:
        ticket.first_responded_at = datetime.utcnow()

    # Handle optional file attachment with comment
    file = request.files.get('attachment')
    if file and file.filename:
        try:
            saved = save_uploaded_file(file)
            att = Attachment(
                ticket_id=ticket.id,
                comment_id=comment.id,
                uploader_id=user.id,
                filename=saved['filename'],
                original_filename=saved['original_filename'],
                file_path=saved['file_path'],
                file_size=saved['file_size'],
                mime_type=saved['mime_type']
            )
            db.session.add(att)
        except ValueError as e:
            flash(f"Attachment error: {str(e)}", 'warning')

    ticket.updated_at = datetime.utcnow()

    # Audit log
    action_type = 'INTERNAL_NOTE_ADDED' if is_internal else 'COMMENT_ADDED'
    log_audit(
        ticket_id=ticket.id,
        action=action_type,
        details=f"{'Internal note' if is_internal else 'Reply'} posted by {user.full_name}",
        user_id=user.id
    )

    db.session.commit()

    # Notify parties
    trigger_ticket_notification('comment_added', ticket, user, {'is_internal': is_internal})
    db.session.commit()

    flash('Reply posted successfully.', 'success')
    return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

@tickets_bp.route('/<int:ticket_id>/status', methods=['POST'])
@login_required
def update_status(ticket_id):
    user = get_current_user()
    ticket = Ticket.query.get_or_404(ticket_id)

    # Permission check: employees can only close or reopen
    new_status = request.form.get('status')
    valid_statuses = ['Open', 'Assigned', 'In Progress', 'Resolved', 'Closed']
    if new_status not in valid_statuses:
        flash('Invalid status provided.', 'danger')
        return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

    if user.is_employee:
        if ticket.creator_id != user.id:
            abort(403)
        if new_status not in ['Closed']:
            flash('Employees can only close their own tickets.', 'danger')
            return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

    old_status = ticket.status
    ticket.status = new_status
    ticket.updated_at = datetime.utcnow()

    if new_status == 'Resolved' and not ticket.resolved_at:
        ticket.resolved_at = datetime.utcnow()
    elif new_status == 'Closed':
        if not ticket.resolved_at:
            ticket.resolved_at = datetime.utcnow()
        ticket.closed_at = datetime.utcnow()
    elif new_status in ['Open', 'In Progress', 'Assigned']:
        # If moving back to in progress, clear resolved
        if old_status in ['Resolved', 'Closed']:
            ticket.resolved_at = None
            ticket.closed_at = None

    log_audit(
        ticket_id=ticket.id,
        action='STATUS_CHANGED',
        old_value=old_status,
        new_value=new_status,
        details=f"Status changed from {old_status} to {new_status} by {user.full_name}",
        user_id=user.id
    )

    db.session.commit()

    trigger_ticket_notification('status_changed', ticket, user)
    db.session.commit()

    flash(f"Ticket status updated to '{new_status}'.", 'success')
    return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

@tickets_bp.route('/<int:ticket_id>/priority', methods=['POST'])
@login_required
@agent_or_admin_required
def update_priority(ticket_id):
    user = get_current_user()
    ticket = Ticket.query.get_or_404(ticket_id)

    new_priority = request.form.get('priority')
    if new_priority not in ('Low', 'Medium', 'High', 'Critical'):
        flash('Invalid priority provided.', 'danger')
        return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

    old_priority = ticket.priority
    ticket.priority = new_priority
    update_ticket_sla_deadlines(ticket)
    ticket.updated_at = datetime.utcnow()

    log_audit(
        ticket_id=ticket.id,
        action='PRIORITY_CHANGED',
        old_value=old_priority,
        new_value=new_priority,
        details=f"Priority adjusted from {old_priority} to {new_priority} by {user.full_name}. SLA deadlines recalculated.",
        user_id=user.id
    )

    db.session.commit()
    flash(f"Priority changed to {new_priority} and SLA deadlines updated.", 'success')
    return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

@tickets_bp.route('/<int:ticket_id>/assign', methods=['POST'])
@login_required
@agent_or_admin_required
def assign_ticket(ticket_id):
    user = get_current_user()
    ticket = Ticket.query.get_or_404(ticket_id)

    agent_id = request.form.get('agent_id', type=int)
    notes = request.form.get('notes', '').strip()

    if agent_id:
        agent = User.query.get(agent_id)
        if not agent or not (agent.is_agent or agent.is_admin):
            flash('Selected user is not an active support agent.', 'danger')
            return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))
        
        old_agent_name = ticket.assigned_agent.full_name if ticket.assigned_agent else "Unassigned"
        ticket.assigned_agent_id = agent.id
        if ticket.status == 'Open':
            ticket.status = 'Assigned'
        ticket.updated_at = datetime.utcnow()

        # Create assignment record
        assignment = TicketAssignment(
            ticket_id=ticket.id,
            assigned_by_id=user.id,
            agent_id=agent.id,
            notes=notes or None
        )
        db.session.add(assignment)

        log_audit(
            ticket_id=ticket.id,
            action='TICKET_ASSIGNED',
            old_value=old_agent_name,
            new_value=agent.full_name,
            details=f"Assigned to {agent.full_name} by {user.full_name}. {f'Notes: {notes}' if notes else ''}",
            user_id=user.id
        )

        db.session.commit()
        trigger_ticket_notification('assigned', ticket, user)
        db.session.commit()

        flash(f"Ticket assigned to {agent.full_name}.", 'success')
    else:
        # Unassign
        old_agent_name = ticket.assigned_agent.full_name if ticket.assigned_agent else "Unassigned"
        ticket.assigned_agent_id = None
        if ticket.status == 'Assigned':
            ticket.status = 'Open'
        ticket.updated_at = datetime.utcnow()

        log_audit(
            ticket_id=ticket.id,
            action='TICKET_UNASSIGNED',
            old_value=old_agent_name,
            new_value='Unassigned',
            details=f"Unassigned by {user.full_name}",
            user_id=user.id
        )
        db.session.commit()
        flash('Ticket has been unassigned.', 'info')

    return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

@tickets_bp.route('/<int:ticket_id>/escalate', methods=['POST'])
@login_required
@agent_or_admin_required
def escalate_ticket(ticket_id):
    user = get_current_user()
    ticket = Ticket.query.get_or_404(ticket_id)

    reason = request.form.get('reason', '').strip()
    if not reason:
        flash('Escalation reason is required.', 'warning')
        return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

    ticket.is_escalated = True
    ticket.escalation_reason = reason
    ticket.escalation_level += 1
    ticket.updated_at = datetime.utcnow()

    log_audit(
        ticket_id=ticket.id,
        action='TICKET_ESCALATED',
        old_value='Standard',
        new_value=f'Tier {ticket.escalation_level}',
        details=f"Escalated by {user.full_name}. Reason: {reason}",
        user_id=user.id
    )

    db.session.commit()

    trigger_ticket_notification('escalated', ticket, user, {'reason': reason})
    db.session.commit()

    flash(f"Ticket #{ticket.ticket_number} has been escalated to Tier {ticket.escalation_level}!", 'warning')
    return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

@tickets_bp.route('/<int:ticket_id>/reopen', methods=['POST'])
@login_required
def reopen_ticket(ticket_id):
    user = get_current_user()
    ticket = Ticket.query.get_or_404(ticket_id)

    if user.is_employee and ticket.creator_id != user.id:
        abort(403)

    if ticket.status not in ('Resolved', 'Closed'):
        flash('Only resolved or closed tickets can be reopened.', 'warning')
        return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

    reason = request.form.get('reason', '').strip()
    old_status = ticket.status
    ticket.status = 'In Progress'
    ticket.resolved_at = None
    ticket.closed_at = None
    ticket.updated_at = datetime.utcnow()

    # Add a comment recording the reopen reason
    reopen_comment = Comment(
        ticket_id=ticket.id,
        user_id=user.id,
        content=f"Ticket reopened: {reason or 'Issue persists or further assistance required.'}",
        is_internal=False
    )
    db.session.add(reopen_comment)

    log_audit(
        ticket_id=ticket.id,
        action='TICKET_REOPENED',
        old_value=old_status,
        new_value='In Progress',
        details=f"Ticket reopened by {user.full_name}. Reason: {reason}",
        user_id=user.id
    )

    db.session.commit()

    trigger_ticket_notification('reopened', ticket, user)
    db.session.commit()

    flash('Ticket has been successfully reopened.', 'info')
    return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

@tickets_bp.route('/<int:ticket_id>/feedback', methods=['POST'])
@login_required
def submit_feedback(ticket_id):
    user = get_current_user()
    ticket = Ticket.query.get_or_404(ticket_id)

    # Only ticket creator can leave feedback
    if ticket.creator_id != user.id:
        abort(403)

    if ticket.status not in ('Resolved', 'Closed'):
        flash('Feedback can only be provided after ticket resolution.', 'warning')
        return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

    if ticket.feedback:
        flash('You have already submitted feedback for this ticket.', 'info')
        return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()

    if not rating or rating < 1 or rating > 5:
        flash('Please select a star rating between 1 and 5.', 'warning')
        return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

    feedback = Feedback(
        ticket_id=ticket.id,
        user_id=user.id,
        rating=rating,
        comment=comment or None
    )
    db.session.add(feedback)

    log_audit(
        ticket_id=ticket.id,
        action='FEEDBACK_SUBMITTED',
        details=f"Customer gave a {rating}-star rating.",
        user_id=user.id
    )

    db.session.commit()
    flash('Thank you! Your feedback has been recorded.', 'success')
    return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

@tickets_bp.route('/<int:ticket_id>/attachments/<int:attachment_id>/download')
@login_required
def download_attachment(ticket_id, attachment_id):
    user = get_current_user()
    ticket = Ticket.query.get_or_404(ticket_id)
    att = Attachment.query.get_or_404(attachment_id)

    if att.ticket_id != ticket.id:
        abort(404)

    # Permission check: employee can only download from their own tickets
    if user.is_employee and ticket.creator_id != user.id:
        abort(403)

    upload_folder = current_app.config['UPLOAD_FOLDER']
    return send_from_directory(
        upload_folder,
        att.filename,
        as_attachment=True,
        download_name=att.original_filename
    )
