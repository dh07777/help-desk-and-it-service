import csv
import io
import re
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, make_response, Response
from app.extensions import db
from app.models import (
    User, Role, Ticket, TicketCategory, SLAPolicy, 
    KnowledgeArticle, AuditLog, Feedback, TicketAssignment
)
from app.decorators import login_required, admin_required, get_current_user
from app.utils.sla import get_sla_metrics
from app.utils.audit import log_audit

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/')
@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    total_tickets = Ticket.query.count()
    open_tickets = Ticket.query.filter_by(status='Open').count()
    assigned_tickets = Ticket.query.filter_by(status='Assigned').count()
    inprogress_tickets = Ticket.query.filter_by(status='In Progress').count()
    resolved_tickets = Ticket.query.filter_by(status='Resolved').count()
    closed_tickets = Ticket.query.filter_by(status='Closed').count()
    escalated_tickets = Ticket.query.filter_by(is_escalated=True).count()
    
    # SLA metrics
    sla_stats = get_sla_metrics()
    
    # User counts
    total_users = User.query.count()
    agent_role = Role.query.filter_by(name='agent').first()
    agents_count = User.query.filter_by(role_id=agent_role.id).count() if agent_role else 0
    
    # Recent tickets
    recent_tickets = Ticket.query.order_by(Ticket.created_at.desc()).limit(8).all()
    
    return render_template(
        'admin/dashboard.html',
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        assigned_tickets=assigned_tickets,
        inprogress_tickets=inprogress_tickets,
        resolved_tickets=resolved_tickets,
        closed_tickets=closed_tickets,
        escalated_tickets=escalated_tickets,
        sla_stats=sla_stats,
        total_users=total_users,
        agents_count=agents_count,
        recent_tickets=recent_tickets
    )

@admin_bp.route('/users', methods=['GET', 'POST'])
@login_required
@admin_required
def users():
    roles = Role.query.all()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create':
            full_name = request.form.get('full_name', '').strip()
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            role_id = request.form.get('role_id', type=int)
            department = request.form.get('department', 'General').strip()
            phone = request.form.get('phone', '').strip()

            if not full_name or not email or not password or not role_id:
                flash('Full name, email, password, and role are required.', 'danger')
            elif User.query.filter_by(email=email).first():
                flash('A user with that email already exists.', 'warning')
            else:
                new_user = User(
                    full_name=full_name,
                    email=email,
                    role_id=role_id,
                    department=department,
                    phone=phone,
                    is_active=True
                )
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                flash(f"User '{full_name}' created successfully.", 'success')

        elif action == 'toggle_status':
            user_id = request.form.get('user_id', type=int)
            user_to_toggle = User.query.get(user_id)
            if user_to_toggle:
                # Prevent deactivating oneself
                if user_to_toggle.id == g.current_user.id:
                    flash('You cannot deactivate your own admin account.', 'danger')
                else:
                    user_to_toggle.is_active = not user_to_toggle.is_active
                    db.session.commit()
                    status_str = "activated" if user_to_toggle.is_active else "deactivated"
                    flash(f"User '{user_to_toggle.full_name}' has been {status_str}.", 'info')

        elif action == 'update_role':
            user_id = request.form.get('user_id', type=int)
            new_role_id = request.form.get('role_id', type=int)
            user_to_edit = User.query.get(user_id)
            if user_to_edit:
                user_to_edit.role_id = new_role_id
                db.session.commit()
                flash(f"Role updated for '{user_to_edit.full_name}'.", 'success')

        return redirect(url_for('admin.users'))

    role_filter = request.args.get('role')
    query = User.query
    if role_filter:
        role_obj = Role.query.filter_by(name=role_filter).first()
        if role_obj:
            query = query.filter_by(role_id=role_obj.id)

    users_list = query.order_by(User.created_at.desc()).all()

    return render_template('admin/users.html', users=users_list, roles=roles, selected_role=role_filter)

@admin_bp.route('/categories', methods=['GET', 'POST'])
@login_required
@admin_required
def categories():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create':
            name = request.form.get('name', '').strip()
            description = request.form.get('description', '').strip()
            default_priority = request.form.get('default_priority', 'Medium')

            if not name:
                flash('Category name is required.', 'danger')
            elif TicketCategory.query.filter_by(name=name).first():
                flash('A category with that name already exists.', 'warning')
            else:
                cat = TicketCategory(
                    name=name,
                    description=description,
                    default_priority=default_priority,
                    is_active=True
                )
                db.session.add(cat)
                db.session.commit()
                flash(f"Category '{name}' created successfully.", 'success')

        elif action == 'edit':
            category_id = request.form.get('category_id', type=int)
            category = TicketCategory.query.get(category_id)
            if category:
                category.name = request.form.get('name', category.name).strip()
                category.description = request.form.get('description', category.description).strip()
                category.default_priority = request.form.get('default_priority', category.default_priority)
                category.is_active = bool(request.form.get('is_active'))
                db.session.commit()
                flash(f"Category '{category.name}' updated successfully.", 'success')

        return redirect(url_for('admin.categories'))

    categories_list = TicketCategory.query.all()
    return render_template('admin/categories.html', categories=categories_list)

@admin_bp.route('/sla', methods=['GET', 'POST'])
@login_required
@admin_required
def sla_policies():
    if request.method == 'POST':
        policy_id = request.form.get('policy_id', type=int)
        policy = SLAPolicy.query.get(policy_id)
        if policy:
            resp_hours = request.form.get('response_time_hours', type=float)
            res_hours = request.form.get('resolution_time_hours', type=float)
            description = request.form.get('description', '').strip()

            if resp_hours is not None and res_hours is not None:
                policy.response_time_hours = max(0.1, resp_hours)
                policy.resolution_time_hours = max(0.1, res_hours)
                policy.description = description
                db.session.commit()
                flash(f"SLA Policy for '{policy.priority}' priority updated successfully.", 'success')

        return redirect(url_for('admin.sla_policies'))

    policies = SLAPolicy.query.order_by(SLAPolicy.response_time_hours.asc()).all()
    sla_metrics = get_sla_metrics()
    return render_template('admin/sla_policies.html', policies=policies, sla_metrics=sla_metrics)

@admin_bp.route('/kb', methods=['GET', 'POST'])
@login_required
@admin_required
def kb_manage():
    categories = TicketCategory.query.filter_by(is_active=True).all()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'create':
            title = request.form.get('title', '').strip()
            content = request.form.get('content', '').strip()
            category_id = request.form.get('category_id', type=int)
            is_published = bool(request.form.get('is_published'))

            if not title or not content:
                flash('Title and content are required.', 'danger')
            else:
                # Generate clean slug
                base_slug = re.sub(r'[^a-zA-Z0-9]+', '-', title.lower()).strip('-')
                slug = base_slug
                counter = 1
                while KnowledgeArticle.query.filter_by(slug=slug).first():
                    slug = f"{base_slug}-{counter}"
                    counter += 1

                article = KnowledgeArticle(
                    title=title,
                    slug=slug,
                    content=content,
                    category_id=category_id if category_id else None,
                    author_id=g.current_user.id,
                    is_published=is_published
                )
                db.session.add(article)
                db.session.commit()
                flash(f"Article '{title}' created successfully.", 'success')

        elif action == 'edit':
            article_id = request.form.get('article_id', type=int)
            article = KnowledgeArticle.query.get(article_id)
            if article:
                article.title = request.form.get('title', article.title).strip()
                article.content = request.form.get('content', article.content).strip()
                article.category_id = request.form.get('category_id', type=int)
                article.is_published = bool(request.form.get('is_published'))
                db.session.commit()
                flash(f"Article '{article.title}' updated successfully.", 'success')

        elif action == 'delete':
            article_id = request.form.get('article_id', type=int)
            article = KnowledgeArticle.query.get(article_id)
            if article:
                db.session.delete(article)
                db.session.commit()
                flash('Knowledge Base article deleted.', 'info')

        return redirect(url_for('admin.kb_manage'))

    articles = KnowledgeArticle.query.order_by(KnowledgeArticle.created_at.desc()).all()
    return render_template('admin/kb_manage.html', articles=articles, categories=categories)

@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    sla_stats = get_sla_metrics()
    
    # Calculate agent performance table
    agent_role = Role.query.filter_by(name='agent').first()
    agents = User.query.filter_by(role_id=agent_role.id).all() if agent_role else []
    
    agent_stats = []
    for agent in agents:
        assigned = Ticket.query.filter_by(assigned_agent_id=agent.id).all()
        resolved = [t for t in assigned if t.status in ('Resolved', 'Closed')]
        
        # Avg resolution time
        res_times = []
        compliant_count = 0
        for t in resolved:
            if t.resolved_at and t.created_at:
                res_times.append((t.resolved_at - t.created_at).total_seconds() / 3600.0)
            if t.resolution_due_at and t.resolved_at:
                if t.resolved_at <= t.resolution_due_at:
                    compliant_count += 1
            else:
                compliant_count += 1
                
        avg_res = round(sum(res_times) / len(res_times), 1) if res_times else 0.0
        sla_comp = round((compliant_count / len(resolved)) * 100, 1) if resolved else 100.0
        
        agent_stats.append({
            'agent': agent,
            'assigned_count': len(assigned),
            'resolved_count': len(resolved),
            'avg_res_time': avg_res,
            'sla_compliance': sla_comp
        })

    return render_template('admin/reports.html', sla_stats=sla_stats, agent_stats=agent_stats)

@admin_bp.route('/reports/export/<export_type>')
@login_required
@admin_required
def export_csv(export_type):
    output = io.StringIO()
    writer = csv.writer(output)

    if export_type == 'tickets':
        writer.writerow([
            'Ticket Number', 'Title', 'Category', 'Priority', 'Status', 
            'Creator Name', 'Creator Email', 'Assigned Agent', 
            'Escalated', 'Created At', 'Resolved At', 'SLA Status'
        ])
        tickets = Ticket.query.order_by(Ticket.id.desc()).all()
        for t in tickets:
            writer.writerow([
                t.ticket_number,
                t.title,
                t.category.name if t.category else 'N/A',
                t.priority,
                t.status,
                t.creator.full_name if t.creator else 'N/A',
                t.creator.email if t.creator else 'N/A',
                t.assigned_agent.full_name if t.assigned_agent else 'Unassigned',
                'Yes' if t.is_escalated else 'No',
                t.created_at.strftime('%Y-%m-%d %H:%M:%S') if t.created_at else '',
                t.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if t.resolved_at else '',
                t.sla_status
            ])
        filename = f"supportdesk_tickets_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    elif export_type == 'agents':
        writer.writerow([
            'Agent Name', 'Email', 'Department', 'Tickets Assigned', 
            'Tickets Resolved', 'Avg Resolution Time (hrs)', 'SLA Compliance (%)'
        ])
        agent_role = Role.query.filter_by(name='agent').first()
        agents = User.query.filter_by(role_id=agent_role.id).all() if agent_role else []
        for agent in agents:
            assigned = Ticket.query.filter_by(assigned_agent_id=agent.id).all()
            resolved = [t for t in assigned if t.status in ('Resolved', 'Closed')]
            res_times = [(t.resolved_at - t.created_at).total_seconds() / 3600.0 for t in resolved if t.resolved_at and t.created_at]
            compliant = sum(1 for t in resolved if not t.is_resolution_overdue())
            avg_res = round(sum(res_times) / len(res_times), 1) if res_times else 0.0
            sla_comp = round((compliant / len(resolved)) * 100, 1) if resolved else 100.0

            writer.writerow([
                agent.full_name,
                agent.email,
                agent.department,
                len(assigned),
                len(resolved),
                avg_res,
                f"{sla_comp}%"
            ])
        filename = f"supportdesk_agents_performance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    elif export_type == 'audit':
        writer.writerow(['Timestamp', 'Ticket Number', 'User', 'Action', 'Old Value', 'New Value', 'Details'])
        logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(1000).all()
        for log in logs:
            writer.writerow([
                log.timestamp.strftime('%Y-%m-%d %H:%M:%S') if log.timestamp else '',
                log.ticket.ticket_number if log.ticket else 'N/A',
                log.user.full_name if log.user else 'System',
                log.action,
                log.old_value or '',
                log.new_value or '',
                log.details or ''
            ])
        filename = f"supportdesk_audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    else:
        return "Invalid export type", 400

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )
