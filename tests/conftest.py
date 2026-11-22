import pytest
import os
import shutil
from pathlib import Path
from app import create_app
from app.config import TestConfig, BASE_DIR
from app.extensions import db
from app.models import Role, User, TicketCategory, SLAPolicy

TEST_DB_PATH = BASE_DIR / 'tests' / 'test_supportdesk.db'

@pytest.fixture(scope='session')
def app():
    # Setup test uploads directory
    test_upload_dir = TestConfig.UPLOAD_FOLDER
    os.makedirs(test_upload_dir, exist_ok=True)

    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

    app = create_app(TestConfig)

    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

    if os.path.exists(test_upload_dir):
        shutil.rmtree(test_upload_dir, ignore_errors=True)
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass

@pytest.fixture(scope='function')
def client(app):
    return app.test_client()

@pytest.fixture(scope='function')
def db_session(app):
    with app.app_context():
        meta = db.metadata
        for table in reversed(meta.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()

        # Seed standard roles
        admin_role = Role(name='admin', description='Administrator')
        agent_role = Role(name='agent', description='Support Agent')
        employee_role = Role(name='employee', description='Employee')
        db.session.add_all([admin_role, agent_role, employee_role])
        db.session.commit()

        # Seed SLA policies
        sla_policies = [
            SLAPolicy(priority='Critical', response_time_hours=1.0, resolution_time_hours=4.0),
            SLAPolicy(priority='High', response_time_hours=2.0, resolution_time_hours=8.0),
            SLAPolicy(priority='Medium', response_time_hours=8.0, resolution_time_hours=24.0),
            SLAPolicy(priority='Low', response_time_hours=24.0, resolution_time_hours=72.0),
        ]
        db.session.add_all(sla_policies)
        db.session.commit()

        # Seed standard category
        cat = TicketCategory(name='IT Hardware', description='Hardware issues', default_priority='Medium')
        db.session.add(cat)
        db.session.commit()

        yield db.session

@pytest.fixture
def test_users(db_session):
    admin_role = Role.query.filter_by(name='admin').first()
    agent_role = Role.query.filter_by(name='agent').first()
    employee_role = Role.query.filter_by(name='employee').first()

    admin = User(full_name='Test Admin', email='admin@test.local', role_id=admin_role.id, department='IT')
    admin.set_password('AdminPass123')

    agent = User(full_name='Test Agent', email='agent@test.local', role_id=agent_role.id, department='Support')
    agent.set_password('AgentPass123')

    employee = User(full_name='Test Employee', email='employee@test.local', role_id=employee_role.id, department='Sales')
    employee.set_password('EmployeePass123')

    other_employee = User(full_name='Other Employee', email='other@test.local', role_id=employee_role.id, department='HR')
    other_employee.set_password('OtherPass123')

    db_session.add_all([admin, agent, employee, other_employee])
    db_session.commit()

    return {
        'admin': admin,
        'agent': agent,
        'employee': employee,
        'other_employee': other_employee
    }
