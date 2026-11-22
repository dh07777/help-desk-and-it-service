from datetime import datetime, timedelta
from app.extensions import db
from app.models import SLAPolicy, Ticket

DEFAULT_SLA_DEFAULTS = {
    'Critical': {'response_hours': 1.0, 'resolution_hours': 4.0},
    'High': {'response_hours': 2.0, 'resolution_hours': 8.0},
    'Medium': {'response_hours': 8.0, 'resolution_hours': 24.0},
    'Low': {'response_hours': 24.0, 'resolution_hours': 72.0}
}

def calculate_sla_deadlines(priority, base_time=None):
    """
    Calculates response_due_at and resolution_due_at based on SLA policies in DB
    or fallback defaults.
    """
    if base_time is None:
        base_time = datetime.utcnow()
        
    policy = SLAPolicy.query.filter_by(priority=priority).first()
    if policy:
        resp_hours = policy.response_time_hours
        res_hours = policy.resolution_time_hours
    else:
        defaults = DEFAULT_SLA_DEFAULTS.get(priority, DEFAULT_SLA_DEFAULTS['Medium'])
        resp_hours = defaults['response_hours']
        res_hours = defaults['resolution_hours']
        
    response_due = base_time + timedelta(hours=resp_hours)
    resolution_due = base_time + timedelta(hours=res_hours)
    return response_due, resolution_due

def update_ticket_sla_deadlines(ticket):
    """
    Recalculates SLA deadlines for an existing ticket (e.g. if priority changed).
    Preserves original created_at as base.
    """
    resp_due, res_due = calculate_sla_deadlines(ticket.priority, ticket.created_at)
    ticket.response_due_at = resp_due
    ticket.resolution_due_at = res_due

def get_sla_metrics():
    """
    Computes overall SLA compliance metrics and averages across all tickets.
    """
    tickets = Ticket.query.all()
    total_tickets = len(tickets)
    if total_tickets == 0:
        return {
            'total_tickets': 0,
            'compliance_rate': 100.0,
            'overdue_count': 0,
            'avg_response_time_min': 0,
            'avg_resolution_time_hr': 0,
            'breached_count': 0
        }

    response_times = []
    resolution_times = []
    breached_count = 0
    overdue_count = 0
    resolved_count = 0
    compliant_resolutions = 0

    for t in tickets:
        if t.is_overdue:
            overdue_count += 1

        # Response time metrics
        if t.first_responded_at and t.created_at:
            delta = (t.first_responded_at - t.created_at).total_seconds() / 60.0
            response_times.append(max(0, delta))

        # Resolution metrics
        if t.status in ('Resolved', 'Closed'):
            resolved_count += 1
            if t.resolved_at and t.created_at:
                delta_hr = (t.resolved_at - t.created_at).total_seconds() / 3600.0
                resolution_times.append(max(0, delta_hr))
            
            if t.resolution_due_at and t.resolved_at:
                if t.resolved_at <= t.resolution_due_at:
                    compliant_resolutions += 1
                else:
                    breached_count += 1
            else:
                compliant_resolutions += 1

    avg_response = round(sum(response_times) / len(response_times), 1) if response_times else 0.0
    avg_resolution = round(sum(resolution_times) / len(resolution_times), 1) if resolution_times else 0.0
    
    compliance_rate = round((compliant_resolutions / resolved_count) * 100, 1) if resolved_count > 0 else 100.0

    return {
        'total_tickets': total_tickets,
        'compliance_rate': compliance_rate,
        'overdue_count': overdue_count,
        'breached_count': breached_count,
        'avg_response_time_min': avg_response,
        'avg_resolution_time_hr': avg_resolution,
        'resolved_count': resolved_count
    }
