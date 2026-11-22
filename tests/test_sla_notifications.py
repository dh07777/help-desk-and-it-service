from datetime import datetime, timedelta
from app.models import Ticket, TicketCategory, Notification, KnowledgeArticle
from app.utils.sla import calculate_sla_deadlines, update_ticket_sla_deadlines

def test_sla_deadlines_calculation(db_session):
    base = datetime(2026, 1, 1, 12, 0, 0)

    # Critical: 1h response, 4h resolution
    resp_crit, res_crit = calculate_sla_deadlines('Critical', base)
    assert resp_crit == base + timedelta(hours=1.0)
    assert res_crit == base + timedelta(hours=4.0)

    # High: 2h response, 8h resolution
    resp_high, res_high = calculate_sla_deadlines('High', base)
    assert resp_high == base + timedelta(hours=2.0)
    assert res_high == base + timedelta(hours=8.0)

    # Medium: 8h response, 24h resolution
    resp_med, res_med = calculate_sla_deadlines('Medium', base)
    assert resp_med == base + timedelta(hours=8.0)
    assert res_med == base + timedelta(hours=24.0)

    # Low: 24h response, 72h resolution
    resp_low, res_low = calculate_sla_deadlines('Low', base)
    assert resp_low == base + timedelta(hours=24.0)
    assert res_low == base + timedelta(hours=72.0)

def test_sla_breach_detection(test_users, db_session):
    cat = TicketCategory.query.first()
    emp = test_users['employee']
    now = datetime.utcnow()

    # Ticket created in the past with overdue resolution
    ticket_overdue = Ticket(
        ticket_number='TIC-6001',
        title='Breached SLA Ticket',
        description='Desc',
        category_id=cat.id,
        priority='High',
        status='In Progress',
        creator_id=emp.id,
        created_at=now - timedelta(hours=10),
        response_due_at=now - timedelta(hours=8),
        resolution_due_at=now - timedelta(hours=2) # overdue
    )
    db_session.add(ticket_overdue)
    db_session.commit()

    assert ticket_overdue.is_resolution_overdue() is True
    assert ticket_overdue.is_overdue is True
    assert ticket_overdue.sla_status == 'Overdue'

def test_notification_api(client, test_users, db_session):
    emp = test_users['employee']
    notif = Notification(
        user_id=emp.id,
        title='Test Alert',
        message='Your ticket has an update.',
        link='/tickets/1',
        is_read=False
    )
    db_session.add(notif)
    db_session.commit()

    client.post('/auth/login', data={'email': 'employee@test.local', 'password': 'EmployeePass123'})

    # Fetch notifications
    resp = client.get('/api/notifications')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['unread_count'] == 1
    assert len(data['notifications']) == 1

    # Mark as read
    resp_read = client.post(f'/api/notifications/{notif.id}/read')
    assert resp_read.status_code == 200

    db_session.refresh(notif)
    assert notif.is_read is True

def test_kb_search_and_voting_api(client, test_users, db_session):
    art = KnowledgeArticle(
        title='Configure Microsoft Outlook Sync',
        slug='configure-outlook-sync',
        content='Detailed instructions to synchronize Outlook folders.',
        author_id=test_users['admin'].id,
        is_published=True,
        helpful_count=5,
        not_helpful_count=1
    )
    db_session.add(art)
    db_session.commit()

    # Live search API
    resp_search = client.get('/api/kb/search?q=Outlook')
    assert resp_search.status_code == 200
    results = resp_search.get_json()
    assert len(results) >= 1
    assert results[0]['slug'] == 'configure-outlook-sync'

    # Vote Helpful
    resp_vote = client.post(f'/api/kb/{art.id}/vote', json={'vote': 'helpful'})
    assert resp_vote.status_code == 200
    vote_data = resp_vote.get_json()
    assert vote_data['helpful_count'] == 6
