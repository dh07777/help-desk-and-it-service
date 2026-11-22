import io
from app.models import Ticket, TicketCategory, Comment, Attachment

def test_comment_and_sla_first_response(client, test_users, db_session):
    cat = TicketCategory.query.first()
    emp = test_users['employee']
    ag = test_users['agent']

    ticket = Ticket(
        ticket_number='TIC-5001',
        title='First Response Test',
        description='Awaiting agent answer',
        category_id=cat.id,
        priority='High',
        status='Open',
        creator_id=emp.id
    )
    db_session.add(ticket)
    db_session.commit()
    assert ticket.first_responded_at is None

    # Agent posts public reply
    client.post('/auth/login', data={'email': 'agent@test.local', 'password': 'AgentPass123'})
    client.post(f'/tickets/{ticket.id}/comment', data={
        'content': 'Hello Alice, I am investigating this now.',
        'is_internal': ''
    }, follow_redirects=True)

    db_session.refresh(ticket)
    assert ticket.first_responded_at is not None
    assert len(ticket.comments) == 1

def test_internal_note_isolation(client, test_users, db_session):
    cat = TicketCategory.query.first()
    emp = test_users['employee']
    ag = test_users['agent']

    ticket = Ticket(
        ticket_number='TIC-5002',
        title='Internal Note Confidentiality Test',
        description='Testing isolation of staff notes',
        category_id=cat.id,
        priority='Medium',
        status='In Progress',
        creator_id=emp.id
    )
    db_session.add(ticket)
    db_session.commit()

    # Agent creates internal note
    client.post('/auth/login', data={'email': 'agent@test.local', 'password': 'AgentPass123'})
    client.post(f'/tickets/{ticket.id}/comment', data={
        'content': 'INTERNAL CONFIDENTIAL: Root cause is bad database credential.',
        'is_internal': '1'
    }, follow_redirects=True)

    # Agent viewing ticket: internal note MUST be visible
    resp_agent = client.get(f'/tickets/{ticket.id}')
    assert b"INTERNAL CONFIDENTIAL" in resp_agent.data
    assert b"Private Internal Note" in resp_agent.data

    # Log in as the Employee: internal note MUST NOT be present in HTML!
    client.get('/auth/logout')
    client.post('/auth/login', data={'email': 'employee@test.local', 'password': 'EmployeePass123'})
    resp_emp = client.get(f'/tickets/{ticket.id}')
    assert b"INTERNAL CONFIDENTIAL" not in resp_emp.data
    assert b"Private Internal Note" not in resp_emp.data

def test_file_upload_validation(client, test_users, db_session):
    cat = TicketCategory.query.first()
    emp = test_users['employee']

    client.post('/auth/login', data={'email': 'employee@test.local', 'password': 'EmployeePass123'})

    # 1. Valid file upload (PNG screenshot)
    fake_png = (io.BytesIO(b"\x89PNG\r\n\x1a\nTest image content"), "screenshot.png")
    resp_valid = client.post('/employee/create-ticket', data={
        'title': 'Ticket with valid PNG',
        'category_id': cat.id,
        'priority': 'Medium',
        'description': 'See attached screenshot of error.',
        'attachment': fake_png
    }, follow_redirects=True)

    assert resp_valid.status_code == 200
    ticket = Ticket.query.filter_by(title='Ticket with valid PNG').first()
    assert ticket is not None
    assert len(ticket.attachments) == 1
    assert ticket.attachments[0].original_filename == 'screenshot.png'

    # 2. Disallowed extension (.exe executable)
    fake_exe = (io.BytesIO(b"MZExecutableContent"), "malicious.exe")
    resp_invalid = client.post('/employee/create-ticket', data={
        'title': 'Ticket with bad file',
        'category_id': cat.id,
        'priority': 'Medium',
        'description': 'Malicious file attempt.',
        'attachment': fake_exe
    }, follow_redirects=True)

    assert resp_invalid.status_code == 200
    # Should warning and NOT create attachment
    ticket_bad = Ticket.query.filter_by(title='Ticket with bad file').first()
    if ticket_bad:
        assert len(ticket_bad.attachments) == 0

def test_unauthorized_attachment_download(client, test_users, db_session):
    cat = TicketCategory.query.first()
    emp = test_users['employee']
    other_emp = test_users['other_employee']

    ticket = Ticket(
        ticket_number='TIC-5003',
        title='Private Ticket with Document',
        description='Secret info',
        category_id=cat.id,
        priority='Low',
        status='Open',
        creator_id=emp.id
    )
    db_session.add(ticket)
    db_session.flush()

    att = Attachment(
        ticket_id=ticket.id,
        uploader_id=emp.id,
        filename='test_secret.txt',
        original_filename='secret.txt',
        file_path='/tmp/fake.txt',
        file_size=100,
        mime_type='text/plain'
    )
    db_session.add(att)
    db_session.commit()

    # Other employee tries to download attachment
    client.post('/auth/login', data={'email': 'other@test.local', 'password': 'OtherPass123'})
    resp = client.get(f'/tickets/{ticket.id}/attachments/{att.id}/download')
    assert resp.status_code == 403
