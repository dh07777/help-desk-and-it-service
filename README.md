# SupportDesk – IT Help Desk & Support Ticket Management System

An enterprise-grade IT Help Desk and Support Ticket Management System engineered with **Python Flask**, **SQLite**, **SQLAlchemy ORM**, **Chart.js**, and vanilla HTML/CSS/JavaScript. Built with role-based workflows for Employees, Support Agents, and Administrators, with strict Service Level Agreement (SLA) policy enforcement, conversation history with private internal notes, searchable Knowledge Base, and real-time operational analytics.

---

## 🚀 Key Features & Highlights

### 1. Multi-Role Authorization & Access Control
- **Employee / Customer**: Submit support tickets, attach documents/screenshots, track SLA countdowns, converse with assigned technicians, reopen resolved tickets, and provide 1–5 star satisfaction feedback.
- **Support Agent**: Access focused assigned queues, unassigned ticket pools, quick status updates (`Open` &rarr; `In Progress` &rarr; `Resolved`), private internal staff notes, escalation triggers, and customer details.
- **Administrator**: Complete governance over users and roles, ticket category management with default priorities, SLA policy thresholds (Critical, High, Medium, Low), interactive analytics dashboards (Chart.js), and CSV report exports.

### 2. Service Level Agreement (SLA) Engine
- **Target Tracking**: Response and resolution deadlines dynamically computed upon ticket creation based on priority policies:
  - **Critical**: 1.0 hr First Response | 4.0 hr Resolution
  - **High**: 2.0 hr First Response | 8.0 hr Resolution
  - **Medium**: 8.0 hr First Response | 24.0 hr Resolution
  - **Low**: 24.0 hr First Response | 72.0 hr Resolution
- **Breach Detection & Overdue Highlighting**: Automatic identification of response or resolution breaches with visual warning badges and countdown alerts.
- **Dynamic SLA Recalculation**: Adjusting ticket priority automatically updates deadlines from the ticket's creation timestamp.

### 3. Ticket Management & Audit Trail
- **Unique Ticket Numbering**: Standardized formatted identifiers (e.g. `TIC-1001`, `TIC-1002`).
- **Multi-Factor Filtering & Search**: Instant keyword search across title, description, and ticket number; filters for status, priority, category, and assigned agent; flexible sorting; pagination.
- **Confidential Internal Notes**: Support agents and administrators can record private diagnosis notes that are strictly stripped and hidden from customer views.
- **Comprehensive Audit History**: Every state transition, agent assignment, escalation, priority change, and comment is permanently recorded in the `audit_logs` table.

### 4. Searchable Knowledge Base (KB)
- Categorized self-service troubleshooting articles.
- Live keyword matching suggestions displayed while an employee types a ticket subject.
- View counter telemetry and interactive helpfulness rating votes (`👍 Helpful` / `👎 Needs Improvement`).

### 5. Multi-Channel Notifications
- **In-App Notification Center**: Real-time unread badge counter, notification dropdown drawer, and mark-as-read controls.
- **Configurable SMTP Email**: Automated dispatch upon ticket receipt, assignment, status change, reply, or escalation (falls back safely to structured logging when SMTP is disabled).

### 6. Analytics & CSV Reporting
- **Chart.js Visualizations**: 14-day ticket inflow vs. resolution trends, status breakdown doughnut, priority distribution bar chart, category pie chart, and agent workload comparison.
- **CSV Data Exports**: One-click streaming exports for tickets, agent productivity metrics, and system audit logs.

---

## 🗄️ Normalized Database Schema (12 Tables)

The SQLite database is normalized using SQLAlchemy ORM:

| Table | Description | Key Columns |
|---|---|---|
| `roles` | Role definitions | `id`, `name` (`admin`, `agent`, `employee`), `description` |
| `users` | Accounts & authentication | `id`, `role_id`, `email`, `password_hash`, `full_name`, `department`, `phone`, `is_active`, `reset_token`, `reset_token_expiry` |
| `ticket_categories` | Service taxonomy | `id`, `name`, `description`, `default_priority`, `is_active`, `created_at` |
| `sla_policies` | Response & resolution targets | `id`, `priority`, `response_time_hours`, `resolution_time_hours`, `description` |
| `tickets` | Core support tickets | `id`, `ticket_number`, `title`, `description`, `category_id`, `priority`, `status`, `creator_id`, `assigned_agent_id`, `is_escalated`, `escalation_reason`, `response_due_at`, `resolution_due_at`, `first_responded_at`, `resolved_at`, `closed_at` |
| `ticket_assignments` | Technician assignment history | `id`, `ticket_id`, `assigned_by_id`, `agent_id`, `assigned_at`, `notes` |
| `comments` | Conversation & internal notes | `id`, `ticket_id`, `user_id`, `content`, `is_internal`, `created_at` |
| `attachments` | Uploaded screenshots & documents | `id`, `ticket_id`, `comment_id`, `uploader_id`, `filename`, `original_filename`, `file_path`, `file_size`, `mime_type` |
| `notifications` | In-app user notifications | `id`, `user_id`, `title`, `message`, `link`, `is_read`, `created_at` |
| `knowledge_articles` | Self-help runbooks | `id`, `category_id`, `author_id`, `title`, `slug`, `content`, `is_published`, `views_count`, `helpful_count`, `not_helpful_count` |
| `feedback` | Post-resolution ratings | `id`, `ticket_id`, `user_id`, `rating` (1–5 stars), `comment`, `created_at` |
| `audit_logs` | Immutable audit trail | `id`, `ticket_id`, `user_id`, `action`, `old_value`, `new_value`, `details`, `timestamp` |

---

## 🔑 Pre-Seeded Demonstration Accounts

The database comes pre-seeded with realistic enterprise users:

| Role | Email Address | Password | Name | Department |
|---|---|---|---|---|
| **Administrator** | `admin@supportdesk.local` | `Admin@123` | System Administrator | IT Infrastructure |
| **Support Agent** | `agent.john@supportdesk.local` | `Agent@123` | John Miller | Desktop & Cloud Support |
| **Support Agent** | `agent.sarah@supportdesk.local` | `Agent@123` | Sarah Jenkins | Network & Security Ops |
| **Employee** | `alice@company.local` | `User@123` | Alice Morgan | Product & Design |
| **Employee** | `bob@company.local` | `User@123` | Bob Vance | Sales & Accounts |

> **Tip**: The login page includes quick **1-Click Role Login Fill** buttons to switch between Administrator, Agent, and Employee roles.

---

## 📡 REST API Documentation

| Endpoint | Method | Role | Description |
|---|---|---|---|
| `/api/csrf-token` | `GET` | Public | Retrieves current CSRF token for Fetch/XHR requests |
| `/api/notifications` | `GET` | Authenticated | Retrieves current user's in-app notifications and unread counter |
| `/api/notifications/<id>/read` | `POST` | Authenticated | Marks a specific notification as read |
| `/api/notifications/mark-all-read` | `POST` | Authenticated | Marks all notifications for current user as read |
| `/api/kb/search?q=<query>` | `GET` | Public | Live search for KB articles (used by instant suggestion widget) |
| `/api/kb/<id>/vote` | `POST` | Public | Submit helpful (`vote: "helpful"`) or unhelpful vote |
| `/api/stats/dashboard` | `GET` | Authenticated | Inflow trends, status/priority/category breakdowns, and agent workloads for Chart.js |
| `/admin/reports/export/tickets` | `GET` | Admin | Downloads filtered tickets in standard CSV format |
| `/admin/reports/export/agents` | `GET` | Admin | Downloads agent productivity & SLA compliance KPIs in CSV |
| `/admin/reports/export/audit` | `GET` | Admin | Downloads system audit log history in CSV |

---

## 💻 Windows Setup & Execution Guide

### Prerequisites
- **Python 3.10+** (Tested and verified on Python 3.13)
- **PowerShell** or **Command Prompt**

### Step 1: Clone or Navigate to the Project Directory
```powershell
cd c:\Users\ELCOT\Downloads\SupportDesk
```

### Step 2: (Optional) Create & Activate Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Step 3: Install Required Dependencies
```powershell
pip install -r requirements.txt
```

### Step 4: Environment Configuration
Copy the sample environment file:
```powershell
Copy-Item .env.example .env
```

### Step 5: Seed the Database
Initialize tables, default SLA policies, sample categories, KB guides, and tickets:
```powershell
python seed_data.py
```

### Step 6: Run the Application Server
```powershell
python run.py
```

Open your browser and navigate to:
**`http://localhost:5000`**

---

## 🧪 Running Pytest Tests

A comprehensive automated test suite validates authentication, role permissions (RBAC), ticket lifecycles, assignments, internal note isolation, secure file uploads, SLA calculations, and CSV reports:

```powershell
python -m pytest -v
```

All 23 test cases run against a dedicated isolated test database without modifying production data.
