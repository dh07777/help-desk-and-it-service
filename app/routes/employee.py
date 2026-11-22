import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, current_app
from app.extensions import db
from app.models import Ticket, TicketCategory, Attachment, User
from app.decorators import login_required, employee_required, get_current_user
from app.utils.sla import calculate_sla_deadlines
from app.utils.audit import log_audit
from app.utils.uploads import save_uploaded_file
from app.utils.notifications import trigger_ticket_notification

employee_bp = Blueprint('employee', __name__)

@employee_bp.route('/')
@employee_bp.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    
    # Filter tickets created by this employee
    tickets = Ticket.query.filter_by(creator_id=user.id).order_by(Ticket.created_at.desc()).all()
    
    open_count = sum(1 for t in tickets if t.status in ('Open', 'Assigned', 'In Progress'))
    resolved_count = sum(1 for t in tickets if t.status == 'Resolved')
    closed_count = sum(1 for t in tickets if t.status == 'Closed')
    
    recent_tickets = tickets[:5]
    categories = TicketCategory.query.filter_by(is_active=True).all()
    
    return render_template(
        'employee/dashboard.html',
        user=user,
        tickets=recent_tickets,
        total_tickets=len(tickets),
        open_count=open_count,
        resolved_count=resolved_count,
        closed_count=closed_count,
        categories=categories
    )

@employee_bp.route('/create-ticket', methods=['GET', 'POST'])
@login_required
def create_ticket():
    user = get_current_user()
    categories = TicketCategory.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        category_id = request.form.get('category_id', type=int)
        priority = request.form.get('priority', 'Medium')
        description = request.form.get('description', '').strip()

        if not title or not category_id or not description:
            flash('Title, category, and description are required.', 'danger')
            return render_template('employee/create_ticket.html', categories=categories, form_data=request.form)

        category = TicketCategory.query.get(category_id)
        if not category:
            flash('Selected category is invalid.', 'danger')
            return render_template('employee/create_ticket.html', categories=categories, form_data=request.form)

        if priority not in ('Low', 'Medium', 'High', 'Critical'):
            priority = category.default_priority or 'Medium'

        # Generate unique ticket number: TIC-1001, etc.
        last_ticket = Ticket.query.order_by(Ticket.id.desc()).first()
        next_id = (last_ticket.id + 1) if last_ticket else 1001
        ticket_number = f"TIC-{next_id:04d}"

        # Calculate SLA deadlines
        resp_due, res_due = calculate_sla_deadlines(priority)

        ticket = Ticket(
            ticket_number=ticket_number,
            title=title,
            description=description,
            category_id=category_id,
            priority=priority,
            status='Open',
            creator_id=user.id,
            response_due_at=resp_due,
            resolution_due_at=res_due,
            created_at=datetime.utcnow()
        )
        db.session.add(ticket)
        db.session.flush() # get ticket.id

        # Handle attachment if uploaded
        file = request.files.get('attachment')
        if file and file.filename:
            try:
                saved = save_uploaded_file(file)
                attachment = Attachment(
                    ticket_id=ticket.id,
                    uploader_id=user.id,
                    filename=saved['filename'],
                    original_filename=saved['original_filename'],
                    file_path=saved['file_path'],
                    file_size=saved['file_size'],
                    mime_type=saved['mime_type']
                )
                db.session.add(attachment)
            except ValueError as e:
                flash(f"Attachment warning: {str(e)}", "warning")

        # Audit log
        log_audit(
            ticket_id=ticket.id,
            action='TICKET_CREATED',
            old_value=None,
            new_value='Open',
            details=f"Ticket created with priority {priority} in category '{category.name}'",
            user_id=user.id
        )

        db.session.commit()

        # Notification
        trigger_ticket_notification('created', ticket, user)
        db.session.commit()

        flash(f'Ticket #{ticket.ticket_number} created successfully!', 'success')
        return redirect(url_for('tickets.view_ticket', ticket_id=ticket.id))

    return render_template('employee/create_ticket.html', categories=categories, form_data={})
