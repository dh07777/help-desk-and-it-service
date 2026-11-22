from datetime import datetime, timedelta
from app.models import Ticket, TicketCategory, Feedback, AuditLog

def test_ticket_creation_and_numbering(client, test_users, db_session):
    client.post('/auth/login', data={'email': 'employee@test.local', 'password': 'EmployeePass123'})
    cat = TicketCategory.query.first()

    resp = client.post('/employee/create-ticket', data={
        'title': 'Test Monitor Display Issue',
        'category_id': cat.id,
        'priority': 'High',
        'description': 'The secondary monitor does not receive display signal over HDMI.'
    }, follow_redirects=True)

    assert resp.status_code == 200
    ticket = Ticket.query.filter_by(title='Test Monitor Display Issue').first()
    assert ticket is not None
    assert ticket.ticket_number.startswith('TIC-')
    assert ticket.priority == 'High'
    assert ticket.status == 'Open'
    assert ticket.creator_id == test_users['employee'].id
    assert ticket.response_due_at is not None
    assert ticket.resolution_due_at is not None

def test_ticket_filtering_and_search(client, test_users, db_session):
    client.post('/auth/login', data={'email': 'admin@test.local', 'password': 'AdminPass123'})
    cat = TicketCategory.query.first()
    emp = test_users['employee']

    t1 = Ticket(ticket_number='TIC-2001', title='First Alpha Issue', description='Desc 1', category_id=cat.id, priority='Low', status='Open', creator_id=emp.id)
    t2 = Ticket(ticket_number='TIC-2002', title='Second Beta Issue', description='Desc 2', category_id=cat.id, priority='Critical', status='Resolved', creator_id=emp.id)
    db_session.add_all([t1, t2])
    db_session.commit()

    # Search keyword
    resp_search = client.get('/tickets/?q=Alpha')
    assert b"TIC-2001" in resp_search.data
    assert b"TIC-2002" not in resp_search.data

    # Filter status
    resp_status = client.get('/tickets/?status=Resolved')
    assert b"TIC-2002" in resp_status.data
    assert b"TIC-2001" not in resp_status.data

    # Filter priority
    resp_prio = client.get('/tickets/?priority=Critical')
    assert b"TIC-2002" in resp_prio.data
    assert b"TIC-2001" not in resp_prio.data

def test_ticket_feedback_submission(client, test_users, db_session):
    cat = TicketCategory.query.first()
    emp = test_users['employee']

    ticket = Ticket(
        ticket_number='TIC-3001',
        title='Resolved Ticket Awaiting Feedback',
        description='Everything was solved.',
        category_id=cat.id,
        priority='Medium',
        status='Resolved',
        creator_id=emp.id,
        resolved_at=datetime.utcnow()
    )
    db_session.add(ticket)
    db_session.commit()

    client.post('/auth/login', data={'email': 'employee@test.local', 'password': 'EmployeePass123'})

    resp = client.post(f'/tickets/{ticket.id}/feedback', data={
        'rating': 5,
        'comment': 'Outstanding and fast support!'
    }, follow_redirects=True)

    assert resp.status_code == 200
    assert b"feedback has been recorded" in resp.data.lower()
    
    fb = Feedback.query.filter_by(ticket_id=ticket.id).first()
    assert fb is not None
    assert fb.rating == 5
    assert fb.comment == 'Outstanding and fast support!'

def test_ticket_reopen(client, test_users, db_session):
    cat = TicketCategory.query.first()
    emp = test_users['employee']

    ticket = Ticket(
        ticket_number='TIC-3002',
        title='Previously Resolved Issue',
        description='Should reopen.',
        category_id=cat.id,
        priority='Medium',
        status='Resolved',
        creator_id=emp.id,
        resolved_at=datetime.utcnow()
    )
    db_session.add(ticket)
    db_session.commit()

    client.post('/auth/login', data={'email': 'employee@test.local', 'password': 'EmployeePass123'})

    resp = client.post(f'/tickets/{ticket.id}/reopen', data={
        'reason': 'The issue started happening again this afternoon.'
    }, follow_redirects=True)

    assert resp.status_code == 200
    db_session.refresh(ticket)
    assert ticket.status == 'In Progress'
    assert ticket.resolved_at is None
