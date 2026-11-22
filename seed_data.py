import os
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import (
    Role, User, TicketCategory, SLAPolicy, 
    Ticket, TicketAssignment, Comment, KnowledgeArticle, 
    Feedback, AuditLog, Notification
)

def seed():
    app = create_app()
    with app.app_context():
        print("Initializing database tables...")
        db.create_all()

        # Check if already seeded
        if User.query.filter_by(email='admin@supportdesk.local').first():
            print("Database already contains seed data. Skipping.")
            return

        print("Seeding Roles...")
        roles = {
            'admin': Role(name='admin', description='System Administrator with full governance and configuration access'),
            'agent': Role(name='agent', description='Support Desk Agent resolving tickets and diagnosing issues'),
            'employee': Role(name='employee', description='Customer/Employee creating and tracking personal support requests')
        }
        for r in roles.values():
            db.session.add(r)
        db.session.commit()

        print("Seeding Users...")
        # Admin
        admin = User(
            role_id=roles['admin'].id,
            email='admin@supportdesk.local',
            full_name='System Administrator',
            department='IT Infrastructure',
            phone='+1 (555) 900-0001'
        )
        admin.set_password('Admin@123')
        db.session.add(admin)

        # Support Agents
        agent_john = User(
            role_id=roles['agent'].id,
            email='agent.john@supportdesk.local',
            full_name='John Miller',
            department='Desktop & Cloud Support',
            phone='+1 (555) 900-0010'
        )
        agent_john.set_password('Agent@123')
        db.session.add(agent_john)

        agent_sarah = User(
            role_id=roles['agent'].id,
            email='agent.sarah@supportdesk.local',
            full_name='Sarah Jenkins',
            department='Network & Security Operations',
            phone='+1 (555) 900-0011'
        )
        agent_sarah.set_password('Agent@123')
        db.session.add(agent_sarah)

        # Employees / Customers
        alice = User(
            role_id=roles['employee'].id,
            email='alice@company.local',
            full_name='Alice Morgan',
            department='Product & Design',
            phone='+1 (555) 100-0101'
        )
        alice.set_password('User@123')
        db.session.add(alice)

        bob = User(
            role_id=roles['employee'].id,
            email='bob@company.local',
            full_name='Bob Vance',
            department='Sales & Accounts',
            phone='+1 (555) 100-0102'
        )
        bob.set_password('User@123')
        db.session.add(bob)

        db.session.commit()

        print("Seeding SLA Policies...")
        sla_policies = [
            SLAPolicy(priority='Critical', response_time_hours=1.0, resolution_time_hours=4.0, description='High business impact outage, complete system blockage'),
            SLAPolicy(priority='High', response_time_hours=2.0, resolution_time_hours=8.0, description='Major function impaired, high urgency workflow blocked'),
            SLAPolicy(priority='Medium', response_time_hours=8.0, resolution_time_hours=24.0, description='Standard business issues, workaround available'),
            SLAPolicy(priority='Low', response_time_hours=24.0, resolution_time_hours=72.0, description='Minor questions, general requests, cosmetics')
        ]
        for p in sla_policies:
            db.session.add(p)
        db.session.commit()

        print("Seeding Ticket Categories...")
        categories = {
            'hardware': TicketCategory(name='Hardware & Workstations', description='Laptops, monitors, peripherals, docking stations, physical repairs', default_priority='Medium'),
            'software': TicketCategory(name='Software & Applications', description='Operating systems, productivity tools, Slack, Zoom, IDEs, licenses', default_priority='Medium'),
            'network': TicketCategory(name='Network, WiFi & VPN', description='Corporate WiFi, remote VPN access, firewall, DNS, bandwidth', default_priority='High'),
            'access': TicketCategory(name='Access, SSO & Accounts', description='Password resets, Okta/Azure SSO, 2FA, group permissions', default_priority='High'),
            'email': TicketCategory(name='Email & Collaboration', description='Outlook, Exchange, distribution lists, shared mailboxes, calendar', default_priority='Medium'),
            'security': TicketCategory(name='Security & Compliance', description='Phishing reports, suspicious activity, device encryption, audits', default_priority='Critical')
        }
        for c in categories.values():
            db.session.add(c)
        db.session.commit()

        print("Seeding Knowledge Base Articles...")
        kb_articles = [
            KnowledgeArticle(
                title='How to Connect to Corporate GlobalProtect VPN on Windows 11',
                slug='connect-globalprotect-vpn-windows-11',
                category_id=categories['network'].id,
                author_id=agent_sarah.id,
                content="""### Overview
All remote employees must connect to the corporate VPN before accessing internal Git repositories, staging servers, and ERP portals.

### Step-by-Step Instructions:
1. Open the Windows System Tray (bottom right near clock).
2. Click the **GlobalProtect** shield icon.
3. In the Portal address field, enter: `vpn.company.local`
4. Click **Connect**.
5. When prompted by Microsoft Authenticator, approve the 2FA push notification on your mobile phone.
6. Once connected, the shield icon will display a green checkmark.

### Troubleshooting
- **Error 403 / Authentication Denied**: Ensure your system clock is synchronized with internet time.
- **Connection Timed Out**: Verify you are not behind an aggressive hotel firewall blocking UDP port 4500.""",
                views_count=142,
                helpful_count=38,
                not_helpful_count=2,
                is_published=True
            ),
            KnowledgeArticle(
                title='Troubleshooting Outlook Search Indexing and Calendar Sync',
                slug='troubleshoot-outlook-search-calendar-sync',
                category_id=categories['email'].id,
                author_id=agent_john.id,
                content="""### Problem
Outlook displays "Something went wrong and your search couldn't be completed" or calendar meeting changes do not reflect in real time.

### Resolution Steps:
1. Close Microsoft Outlook completely.
2. Open Windows Start menu and type `Indexing Options`.
3. Click **Advanced**, then select **Rebuild** under Troubleshooting.
4. Allow 15-30 minutes for the index to rebuild in background.
5. In Outlook, go to **File > Account Settings > Account Settings**.
6. Double click your email, ensure **Use Cached Exchange Mode** is enabled with slider set to 1 year.
7. Restart Outlook.""",
                views_count=89,
                helpful_count=24,
                not_helpful_count=1,
                is_published=True
            ),
            KnowledgeArticle(
                title='Self-Service Password Reset (SSPR) and 2FA Authenticator Setup',
                slug='self-service-password-reset-2fa-setup',
                category_id=categories['access'].id,
                author_id=admin.id,
                content="""### Setting Up Your Security Methods
All employees must register at least two authentication methods:
- Microsoft Authenticator app (Recommended)
- SMS verification mobile number

Visit `https://myaccount.company.local` to manage your security keys, phone numbers, and emergency recovery codes. Passwords must be at least 12 characters with upper, lower, numbers, and symbols.""",
                views_count=210,
                helpful_count=65,
                not_helpful_count=3,
                is_published=True
            ),
            KnowledgeArticle(
                title='Setting Up Dual 4K Monitors and USB-C Docking Stations',
                slug='dual-monitors-usbc-docking-setup',
                category_id=categories['hardware'].id,
                author_id=agent_john.id,
                content="""### Hardware Connection Guide
1. Connect the 100W USB-C power adapter directly to the dock.
2. Plug the upstream Thunderbolt cable from the dock into your laptop's Thunderbolt port (marked with a lightning bolt).
3. Connect Monitor 1 using DisplayPort.
4. Connect Monitor 2 using HDMI.
5. In Windows Settings > Display, click **Extend these displays** and select 60Hz refresh rate.""",
                views_count=77,
                helpful_count=19,
                not_helpful_count=0,
                is_published=True
            )
        ]
        for a in kb_articles:
            db.session.add(a)
        db.session.commit()

        print("Seeding Tickets across various lifecycle states...")
        now = datetime.utcnow()

        # Ticket 1: Open, Unassigned, Low priority
        t1_created = now - timedelta(hours=3)
        t1 = Ticket(
            ticket_number='TIC-1001',
            title='Request for secondary 27-inch 4K monitor for design workstation',
            description='I need a second monitor to compare Figma designs against mobile test viewports simultaneously. Workstation desk mount already in place.',
            category_id=categories['hardware'].id,
            priority='Low',
            status='Open',
            creator_id=alice.id,
            created_at=t1_created,
            response_due_at=t1_created + timedelta(hours=24),
            resolution_due_at=t1_created + timedelta(hours=72)
        )
        db.session.add(t1)
        db.session.flush()

        db.session.add(AuditLog(
            ticket_id=t1.id,
            user_id=alice.id,
            action='TICKET_CREATED',
            old_value=None,
            new_value='Open',
            details='Ticket created with priority Low',
            timestamp=t1_created
        ))

        # Ticket 2: Assigned, Medium priority
        t2_created = now - timedelta(hours=5)
        t2 = Ticket(
            ticket_number='TIC-1002',
            title='Slack desktop application crashes on launch after Windows update',
            description='Every time I boot my machine and click Slack, it displays a blank gray screen and quits with error code STATUS_ACCESS_VIOLATION. Web Slack works fine.',
            category_id=categories['software'].id,
            priority='Medium',
            status='Assigned',
            creator_id=bob.id,
            assigned_agent_id=agent_sarah.id,
            created_at=t2_created,
            response_due_at=t2_created + timedelta(hours=8),
            resolution_due_at=t2_created + timedelta(hours=24)
        )
        db.session.add(t2)
        db.session.flush()

        db.session.add(TicketAssignment(
            ticket_id=t2.id,
            assigned_by_id=admin.id,
            agent_id=agent_sarah.id,
            assigned_at=t2_created + timedelta(minutes=20),
            notes='Assigned to Sarah for desktop app cache clearance'
        ))
        db.session.add(AuditLog(
            ticket_id=t2.id,
            user_id=admin.id,
            action='TICKET_ASSIGNED',
            old_value='Unassigned',
            new_value=agent_sarah.full_name,
            details='Assigned to Sarah Jenkins',
            timestamp=t2_created + timedelta(minutes=20)
        ))

        # Ticket 3: In Progress, High priority, with discussion & internal note
        t3_created = now - timedelta(hours=4)
        t3 = Ticket(
            ticket_number='TIC-1003',
            title='Cannot authenticate to AWS Production VPN - Error 403',
            description='I am unable to connect to the production AWS gateway from home. It was working yesterday afternoon.',
            category_id=categories['network'].id,
            priority='High',
            status='In Progress',
            creator_id=alice.id,
            assigned_agent_id=agent_john.id,
            created_at=t3_created,
            first_responded_at=t3_created + timedelta(minutes=35),
            response_due_at=t3_created + timedelta(hours=2),
            resolution_due_at=t3_created + timedelta(hours=8)
        )
        db.session.add(t3)
        db.session.flush()

        db.session.add(Comment(
            ticket_id=t3.id,
            user_id=agent_john.id,
            content='Hi Alice, I am checking the RADIUS authentication logs for your user profile right now.',
            is_internal=False,
            created_at=t3_created + timedelta(minutes=35)
        ))
        db.session.add(Comment(
            ticket_id=t3.id,
            user_id=agent_john.id,
            content='Internal Note: Her Okta group membership expired at midnight. Need to renew AWS-Engineers-Group in IdP.',
            is_internal=True,
            created_at=t3_created + timedelta(minutes=45)
        ))
        db.session.add(Comment(
            ticket_id=t3.id,
            user_id=alice.id,
            content='Thanks John! Let me know as soon as I can test again.',
            is_internal=False,
            created_at=t3_created + timedelta(minutes=50)
        ))

        # Ticket 4: Escalated, Critical priority
        t4_created = now - timedelta(hours=2)
        t4 = Ticket(
            ticket_number='TIC-1004',
            title='Company-wide email gateway bouncing external incoming mail',
            description='Clients and partners are reporting NDR bounce codes (550 Mailbox unavailable). Inbound MX queue is stopped.',
            category_id=categories['security'].id,
            priority='Critical',
            status='In Progress',
            creator_id=bob.id,
            assigned_agent_id=agent_sarah.id,
            is_escalated=True,
            escalation_reason='Critical executive and sales pipeline emails blocked. High revenue impact.',
            escalation_level=2,
            created_at=t4_created,
            first_responded_at=t4_created + timedelta(minutes=15),
            response_due_at=t4_created + timedelta(hours=1),
            resolution_due_at=t4_created + timedelta(hours=4)
        )
        db.session.add(t4)
        db.session.flush()

        db.session.add(AuditLog(
            ticket_id=t4.id,
            user_id=agent_sarah.id,
            action='TICKET_ESCALATED',
            old_value='Standard',
            new_value='Tier 2',
            details='Escalated to Tier 2 due to business outage impact',
            timestamp=t4_created + timedelta(minutes=20)
        ))

        # Ticket 5: Resolved, with Customer Feedback (5 Stars)
        t5_created = now - timedelta(days=2)
        t5_resolved = t5_created + timedelta(hours=3)
        t5 = Ticket(
            ticket_number='TIC-1005',
            title='Need Git repository access permissions for Project Helios',
            description='Please grant read/write access to github.com/company/helios-core for development onboarding.',
            category_id=categories['access'].id,
            priority='Medium',
            status='Resolved',
            creator_id=alice.id,
            assigned_agent_id=agent_john.id,
            created_at=t5_created,
            first_responded_at=t5_created + timedelta(minutes=45),
            response_due_at=t5_created + timedelta(hours=8),
            resolution_due_at=t5_created + timedelta(hours=24),
            resolved_at=t5_resolved
        )
        db.session.add(t5)
        db.session.flush()

        db.session.add(Comment(
            ticket_id=t5.id,
            user_id=agent_john.id,
            content='Permissions provisioned via GitHub Enterprise team sync. You should now see the repository on your dashboard.',
            is_internal=False,
            created_at=t5_resolved
        ))
        db.session.add(Feedback(
            ticket_id=t5.id,
            user_id=alice.id,
            rating=5,
            comment='Super prompt resolution! Access was granted within the hour. Thank you John!',
            created_at=t5_resolved + timedelta(minutes=30)
        ))

        # Ticket 6: Closed
        t6_created = now - timedelta(days=4)
        t6_resolved = t6_created + timedelta(hours=5)
        t6 = Ticket(
            ticket_number='TIC-1006',
            title='New employee laptop onboarding and BitLocker encryption setup',
            description='Standard issue ThinkPad P14s preparation for new hire starting Monday.',
            category_id=categories['hardware'].id,
            priority='Medium',
            status='Closed',
            creator_id=bob.id,
            assigned_agent_id=agent_john.id,
            created_at=t6_created,
            first_responded_at=t6_created + timedelta(hours=1),
            response_due_at=t6_created + timedelta(hours=8),
            resolution_due_at=t6_created + timedelta(hours=24),
            resolved_at=t6_resolved,
            closed_at=t6_resolved + timedelta(days=1)
        )
        db.session.add(t6)
        db.session.flush()

        # Ticket 7: Overdue ticket demonstrating SLA breach highlighting
        t7_created = now - timedelta(hours=36)
        t7 = Ticket(
            ticket_number='TIC-1007',
            title='License renewal error in JetBrains IntelliJ IDEA Ultimate',
            description='Activation server returns HTTP 500 when attempting to fetch the organizational license key.',
            category_id=categories['software'].id,
            priority='High',
            status='In Progress',
            creator_id=alice.id,
            assigned_agent_id=agent_sarah.id,
            created_at=t7_created,
            first_responded_at=t7_created + timedelta(hours=1),
            response_due_at=t7_created + timedelta(hours=2),
            resolution_due_at=t7_created + timedelta(hours=8) # Overdue!
        )
        db.session.add(t7)

        # In-app notifications
        db.session.add(Notification(
            user_id=alice.id,
            title='Ticket Resolved: TIC-1005',
            message='Your ticket "Need Git repository access permissions for Project Helios" has been marked as Resolved.',
            link='/tickets/5',
            is_read=True,
            created_at=t5_resolved
        ))
        db.session.add(Notification(
            user_id=agent_sarah.id,
            title='URGENT: Escalation Alert TIC-1004',
            message='Ticket TIC-1004 has been escalated to Tier 2 due to company-wide email gateway bouncing mail.',
            link='/tickets/4',
            is_read=False,
            created_at=t4_created + timedelta(minutes=20)
        ))
        db.session.add(Notification(
            user_id=admin.id,
            title='New Critical Ticket Logged: TIC-1004',
            message='Company-wide email gateway bouncing external incoming mail was created with Critical priority.',
            link='/tickets/4',
            is_read=False,
            created_at=t4_created
        ))

        db.session.commit()
        print("Database successfully seeded with realistic enterprise support data!")

if __name__ == '__main__':
    seed()
