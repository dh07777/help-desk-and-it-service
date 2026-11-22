from app.models import User

def test_user_registration(client, db_session):
    resp = client.post('/auth/register', data={
        'full_name': 'New Tester',
        'email': 'newtester@company.local',
        'department': 'Operations',
        'phone': '1234567890',
        'password': 'SecurePassword123',
        'confirm_password': 'SecurePassword123'
    }, follow_redirects=True)

    assert resp.status_code == 200
    user = User.query.filter_by(email='newtester@company.local').first()
    assert user is not None
    assert user.full_name == 'New Tester'
    assert user.role.name == 'employee'
    assert user.check_password('SecurePassword123')

def test_login_success_and_logout(client, test_users):
    resp = client.post('/auth/login', data={
        'email': 'employee@test.local',
        'password': 'EmployeePass123'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"My Support Portal" in resp.data

    # Logout
    resp_logout = client.get('/auth/logout', follow_redirects=True)
    assert resp_logout.status_code == 200
    assert b"logged out" in resp_logout.data.lower()

def test_login_invalid_credentials(client, test_users):
    resp = client.post('/auth/login', data={
        'email': 'employee@test.local',
        'password': 'WrongPassword'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Invalid email or password" in resp.data

def test_login_deactivated_account(client, test_users, db_session):
    employee = test_users['employee']
    employee.is_active = False
    db_session.commit()

    resp = client.post('/auth/login', data={
        'email': 'employee@test.local',
        'password': 'EmployeePass123'
    }, follow_redirects=True)
    assert resp.status_code == 200
    assert b"deactivated" in resp.data.lower()

def test_password_reset_flow(client, test_users, db_session):
    user = test_users['employee']
    token = user.generate_reset_token()
    db_session.commit()

    # Verify reset page loads with valid token
    resp_get = client.get(f'/auth/reset-password/{token}')
    assert resp_get.status_code == 200
    assert b"Set New Password" in resp_get.data

    # Post new password
    resp_post = client.post(f'/auth/reset-password/{token}', data={
        'password': 'BrandNewPassword123',
        'confirm_password': 'BrandNewPassword123'
    }, follow_redirects=True)
    assert resp_post.status_code == 200
    assert b"password has been successfully reset" in resp_post.data.lower()

    # Verify new password works
    db_session.refresh(user)
    assert user.check_password('BrandNewPassword123')
    assert user.reset_token is None

def test_profile_update(client, test_users, db_session):
    # Log in as employee
    client.post('/auth/login', data={'email': 'employee@test.local', 'password': 'EmployeePass123'})
    
    resp = client.post('/auth/profile', data={
        'action': 'update_info',
        'full_name': 'Updated Employee Name',
        'department': 'New Department',
        'phone': '999-888-7777'
    }, follow_redirects=True)
    
    assert resp.status_code == 200
    user = test_users['employee']
    db_session.refresh(user)
    assert user.full_name == 'Updated Employee Name'
    assert user.department == 'New Department'
