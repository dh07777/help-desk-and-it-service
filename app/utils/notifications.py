import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
from app.extensions import db
from app.models import Notification, User, Role

logger = logging.getLogger(__name__)

def create_in_app_notification(user_id, title, message, link=None):
    """
    Creates an in-app notification entry for a user.
    """
    try:
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            link=link
        )
        db.session.add(notif)
        return notif
    except Exception as e:
        logger.error(f"Error creating in-app notification: {e}")
        return None

def send_smtp_email(to_email, subject, body_text, body_html=None):
    """
    Sends an email via SMTP if configured, or logs the message mock.
    """
    if not current_app.config.get('MAIL_ENABLED', False):
        logger.info(f"[Mock Email Notification] To: {to_email} | Subject: {subject} | Body: {body_text[:100]}...")
        return True

    server_host = current_app.config.get('MAIL_SERVER')
    server_port = current_app.config.get('MAIL_PORT', 587)
    use_tls = current_app.config.get('MAIL_USE_TLS', True)
    username = current_app.config.get('MAIL_USERNAME')
    password = current_app.config.get('MAIL_PASSWORD')
    sender = current_app.config.get('MAIL_DEFAULT_SENDER')

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = to_email

        part1 = MIMEText(body_text, 'plain')
        msg.attach(part1)

        if body_html:
            part2 = MIMEText(body_html, 'html')
            msg.attach(part2)

        server = smtplib.SMTP(server_host, server_port, timeout=10)
        if use_tls:
            server.starttls()
        if username and password:
            server.login(username, password)
        server.sendmail(sender, [to_email], msg.as_string())
        server.quit()
        logger.info(f"Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False

def notify_user(user, title, message, link=None):
    """
    Delivers both in-app notification and optional email to a single user.
    """
    if not user:
        return
    create_in_app_notification(user.id, title, message, link)
    if user.email:
        send_smtp_email(user.email, title, message)

def notify_roles(role_names, title, message, link=None):
    """
    Delivers notifications to all active users with the specified role(s).
    """
    roles = Role.query.filter(Role.name.in_(role_names)).all()
    role_ids = [r.id for r in roles]
    users = User.query.filter(User.role_id.in_(role_ids), User.is_active == True).all()
    for u in users:
        notify_user(u, title, message, link)

def trigger_ticket_notification(event_type, ticket, actor, extra_info=None):
    """
    Central dispatcher for ticket-related notification events:
    - 'created'
    - 'assigned'
    - 'status_changed'
    - 'comment_added'
    - 'escalated'
    - 'reopened'
    - 'resolved'
    - 'closed'
    """
    link = f"/tickets/{ticket.id}"
    
    if event_type == 'created':
        # Notify the creator confirmation
        notify_user(
            ticket.creator,
            f"Ticket Received: {ticket.ticket_number}",
            f"Your ticket '{ticket.title}' has been successfully logged with priority {ticket.priority}.",
            link
        )
        # Notify support staff / admins
        notify_roles(
            ['admin', 'agent'],
            f"New Ticket: {ticket.ticket_number} [{ticket.priority}]",
            f"New ticket '{ticket.title}' created by {ticket.creator.full_name} ({ticket.category.name if ticket.category else 'General'}).",
            link
        )

    elif event_type == 'assigned':
        if ticket.assigned_agent:
            notify_user(
                ticket.assigned_agent,
                f"Ticket Assigned: {ticket.ticket_number}",
                f"You have been assigned ticket '{ticket.title}' by {actor.full_name if actor else 'System'}.",
                link
            )
            # Notify creator that an agent was assigned
            if ticket.creator and ticket.creator.id != actor.id:
                notify_user(
                    ticket.creator,
                    f"Agent Assigned to {ticket.ticket_number}",
                    f"Support Agent {ticket.assigned_agent.full_name} has been assigned to your ticket.",
                    link
                )

    elif event_type == 'status_changed':
        # Notify creator if not the actor
        if ticket.creator and ticket.creator.id != actor.id:
            notify_user(
                ticket.creator,
                f"Status Updated: {ticket.ticket_number}",
                f"Ticket status changed to '{ticket.status}' by {actor.full_name}.",
                link
            )
        # Notify assigned agent if someone else changed it
        if ticket.assigned_agent and ticket.assigned_agent.id != actor.id:
            notify_user(
                ticket.assigned_agent,
                f"Status Updated: {ticket.ticket_number}",
                f"Ticket status changed to '{ticket.status}' by {actor.full_name}.",
                link
            )

    elif event_type == 'comment_added':
        is_internal = extra_info.get('is_internal', False) if extra_info else False
        if is_internal:
            # Internal notes are only notified to staff
            notify_roles(
                ['admin', 'agent'],
                f"Internal Note on {ticket.ticket_number}",
                f"{actor.full_name} added an internal note to '{ticket.title}'.",
                link
            )
        else:
            # Public comment: if employee commented, notify assigned agent / admins
            if actor.id == ticket.creator_id:
                if ticket.assigned_agent:
                    notify_user(
                        ticket.assigned_agent,
                        f"Customer Reply: {ticket.ticket_number}",
                        f"{actor.full_name} replied to ticket '{ticket.title}'.",
                        link
                    )
                else:
                    notify_roles(
                        ['admin', 'agent'],
                        f"Customer Reply: {ticket.ticket_number}",
                        f"{actor.full_name} added a reply to unassigned ticket '{ticket.title}'.",
                        link
                    )
            else:
                # Agent commented, notify customer
                notify_user(
                    ticket.creator,
                    f"New Reply on Ticket {ticket.ticket_number}",
                    f"{actor.full_name} replied to your ticket '{ticket.title}'.",
                    link
                )

    elif event_type == 'escalated':
        # Alert admins and agents
        reason = extra_info.get('reason', 'No reason provided') if extra_info else 'No reason provided'
        notify_roles(
            ['admin'],
            f"URGENT: Escalation Alert {ticket.ticket_number}",
            f"Ticket '{ticket.title}' has been escalated by {actor.full_name}. Reason: {reason}",
            link
        )

    elif event_type == 'reopened':
        notify_roles(
            ['admin', 'agent'],
            f"Ticket Reopened: {ticket.ticket_number}",
            f"Ticket '{ticket.title}' was reopened by {actor.full_name}.",
            link
        )
        if ticket.assigned_agent:
            notify_user(
                ticket.assigned_agent,
                f"Ticket Reopened: {ticket.ticket_number}",
                f"Customer {actor.full_name} reopened ticket '{ticket.title}'.",
                link
            )
