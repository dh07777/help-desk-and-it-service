from datetime import datetime
from app.models import Ticket, TicketCategory, TicketAssignment, User, Role

def test_rbac_access_control(client, test_users):
    # Employee cannot access admin dashboard
    client.post('/auth/login', data={'email': 'employee@test.local', 'password': 'EmployeePass123'})
    resp_admin = client.get('/admin/dashboard', follow_redirects=False)
    assert resp_admin.status_code in (302, 403)

    # Employee cannot access agent workspace
    resp_agent = client.get('/agent/dashboard', follow_redirects=False)
    assert resp_agent.status_code in (302, 403)

    # Agent CAN access agent dashboard
    client.get('/auth/logout')
    client.post('/auth/login', data={'email': 'agent@test.local', 'password': 'AgentPass123'})
    resp_agent_ok = client.get('/agent/dashboard')
    assert resp_agent_ok.status_code == 200

    # Admin CAN access admin dashboard
    client.get('/auth/logout')
    client.post('/auth/login', data={'email': 'admin@test.local', 'password': 'AdminPass123'})
    resp_admin_ok = client.get('/admin/dashboard')
    assert resp_admin_ok.status_code == 200

def test_ticket_assignment_and_reassignment(client, test_users, db_session):
    cat = TicketCategory.query.first()
    emp = test_users['employee']
    ag = test_users['agent']

    ticket = Ticket(
        ticket_number='TIC-4001',
        title='Assignment Test Ticket',
        description='To be assigned',
        category_id=cat.id,
        priority='Medium',
        status='Open',
        creator_id=emp.id
    )
    db_session.add(ticket)
    db_session.commit()

    # Agent assigns ticket to themselves
    client.post('/auth/login', data={'email': 'agent@test.local', 'password': 'AgentPass123'})
    resp = client.post(f'/tickets/{ticket.id}/assign', data={
        'agent_id': ag.id,
        'notes': 'Claiming for resolution'
    }, follow_redirects=True)

    assert resp.status_code == 200
    db_session.refresh(ticket)
    assert ticket.assigned_agent_id == ag.id
    assert ticket.status == 'Assigned'

    # Verify assignment record in database
    ass = TicketAssignment.query.filter_by(ticket_id=ticket.id).first()
    assert ass is not None
    assert ass.agent_id == ag.id

def test_status_workflow(client, test_users, db_session):
    cat = TicketCategory.query.first()
    emp = test_users['employee']

    ticket = Ticket(
        ticket_number='TIC-4002',
        title='Status Progression Ticket',
        description='Workflow verification',
        category_id=cat.id,
        priority='High',
        status='Open',
        creator_id=emp.id
    )
    db_session.add(ticket)
    db_session.commit()

    client.post('/auth/login', data={'email': 'agent@test.local', 'password': 'AgentPass123'})

    # Transition to In Progress
    client.post(f'/tickets/{ticket.id}/status', data={'status': 'In Progress'}, follow_redirects=True)
    db_session.refresh(ticket)
    assert ticket.status == 'In Progress'

    # Transition to Resolved
    client.post(f'/tickets/{ticket.id}/status', data={'status': 'Resolved'}, follow_redirects=True)
    db_session.refresh(ticket)
    assert ticket.status == 'Resolved'
    assert ticket.resolved_at is not None

    # Transition to Closed
    client.post(f'/tickets/{ticket.id}/status', data={'status': 'Closed'}, follow_redirects=True)
    db_session.refresh(ticket)
    assert ticket.status == 'Closed'
    assert ticket.closed_at is not None

def test_ticket_escalation(client, test_users, db_session):
    cat = TicketCategory.query.first()
    emp = test_users['employee']

    ticket = Ticket(
        ticket_number='TIC-4003',
        title='Escalation Target Ticket',
        description='Needs escalation',
        category_id=cat.id,
        priority='High',
        status='Open',
        creator_id=emp.id
    )
    db_session.add(ticket)
    db_session.commit()

    client.post('/auth/login', data={'email': 'agent@test.local', 'password': 'AgentPass123'})

    resp = client.post(f'/tickets/{ticket.id}/escalate', data={
        'reason': 'Production environment blocked by unknown firewall restriction.'
    }, follow_redirects=True)

    assert resp.status_code == 200
    db_session.refresh(ticket)
    assert ticket.is_escalated is True
    assert ticket.escalation_level == 1
    assert 'Production environment blocked' in ticket.escalation_reason

def test_csv_reports_export(client, test_users, db_session):
    client.post('/auth/login', data={'email': 'admin@test.local', 'password': 'AdminPass123'})

    # Tickets CSV
    resp_tickets = client.get('/admin/reports/export/tickets')
    assert resp_tickets.status_code == 200
    assert resp_tickets.mimetype == 'text/csv'
    assert b"Ticket Number,Title,Category,Priority" in resp_tickets.data

    # Agents CSV
    resp_agents = client.get('/admin/reports/export/agents')
    assert resp_agents.status_code == 200
    assert resp_agents.mimetype == 'text/csv'
    assert b"Agent Name,Email,Department" in resp_agents.data

    # Audit CSV
    resp_audit = client.get('/admin/reports/export/audit')
    assert resp_audit.status_code == 200
    assert resp_audit.mimetype == 'text/csv'
    assert b"Timestamp,Ticket Number,User,Action" in resp_audit.data
