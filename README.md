# Expert Decision Replay Platform (EDRP) — Milestone 3

> **Group 5** | Academic Year 2025–26  
> **Milestone 3: Enterprise Approvals, Append-Only Audit Engine, Security Hardening & Decision Replay**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1+-000000?style=flat&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Milestone](https://img.shields.io/badge/Milestone-3%20Completed-brightgreen?style=flat&logo=target)](https://github.com/KoppalaNaveen/EDRP)
[![Security](https://img.shields.io/badge/Security-Append--Only%20Audit-orange?style=flat&logo=auth0&logoColor=white)](https://github.com/KoppalaNaveen/EDRP)

---

## 🎯 Milestone 3 Executive Summary

Milestone 3 completes the core enterprise requirements of the **Expert Decision Replay Platform (EDRP)**, focusing on:
1. **Append-Only Structured Audit Logging** with field-level before/after diff tracking and database-level immutability triggers.
2. **Configurable Multi-Tier Approval Chains** supporting dynamic routing, sequential reviewer evaluations, and SLA notifications.
3. **Interactive Decision Replay & Versioning Engine** providing point-in-time snapshotting and visual historical playback.
4. **Reviewer Workspace & Role-Tailored Dashboards** for Administrators, Managers, Reviewers, and Employees.
5. **Security Hardening & Access Control** with PostgreSQL Row-Level Security (RLS), least-privilege database roles, 6-digit SMTP OTP onboarding, and 72-hour persistent sessions.
6. **Enterprise Settings & Support Ticketing System** for platform configuration, SMTP controls, and user issue resolution.

---

## 🚀 Key Modules Implemented in Milestone 3

### 1. Structured & Append-Only Audit Logging System

An enterprise-grade audit trail designed for regulatory compliance (SOC 2, ISO 27001) that tracks every state change across the platform:

- **Structured Log Model (`AuditLog`)**:
  - Captures `actor_id`, `action`, `entity_type`, `entity_id`, `diff` (JSON), `ip_address`, `user_agent`, and timestamp.
- **Field-Level Diff Engine (`diff.py`)**:
  - Computes granular property diffs between previous and new states:
    ```json
    {
      "status": { "before": "draft", "after": "in_review" },
      "financial_impact": { "before": 25000.0, "after": 35000.0 }
    }
    ```
- **Database Immutability Triggers**:
  - PostgreSQL trigger prevents any `UPDATE` or `DELETE` operations on the `audit_logs` table:
    ```sql
    CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
    RETURNS TRIGGER AS $$
    BEGIN
        RAISE EXCEPTION 'Audit logs are append-only. Modifying or deleting records is prohibited.';
    END;
    $$ LANGUAGE plpgsql;

    CREATE TRIGGER trg_audit_logs_immutable
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
    ```
- **Decision Audit Trail Timeline API (`/audit-logs/decision/{id}`)**:
  - Aggregates decision versions, reviewer assessments, comments, uploads, and audit records into a single unified timeline.
- **Live Polling Audit Viewer (`audit.html`, `audit.js`)**:
  - Real-time 5-second polling interface with multi-criteria filtering (Entity, Actor, Action, Date Range) and one-click **CSV export**.

---

### 2. Configurable Multi-Tier Approval Chains

A dynamic workflow engine for routing and approving strategic decisions:

- **Dynamic Approval Chain Configs (`approval_chain_api.py`, `approval_chain.py`)**:
  - Admin-configurable multi-step approval workflows based on decision category and budget threshold rules.
- **Reviewer Evaluation States**:
  - **Approve**: Advances decision to next approval stage or finalizes to `Approved`.
  - **Reject**: Terminated with mandatory justification comment; alerts creator.
  - **Request Revision**: Reverts decision status to `Draft`; creator updates and resubmits, creating version `v2`.
- **Reviewer Assignment & Notifications**:
  - Reviewers assigned directly via UI; automated alerts dispatched via in-app notifications and background SMTP emails.

---

### 3. Interactive Decision Replay & Versioning Engine

Preserves the complete evolution of organizational decisions:

- **Automated Version Snapshots (`decision_versions`)**:
  - Stores complete JSON state snapshots whenever a decision is submitted, reviewed, or modified.
- **Visual Replay Viewer (`replays.html`, `replay.js`)**:
  - Step-by-step playback interface allowing stakeholders to inspect who contributed, what alternatives were evaluated, what meeting notes were captured, and why final consensus was reached.

---

### 4. Reviewer Workspace & Role-Tailored Dashboards

Specialized interfaces for all 4 user roles:

| Dashboard | File | Key Capabilities & Metrics |
|---|---|---|
| **Reviewer Dashboard** | `reviewer_dashboard.html` | Pending review queue, side-by-side alternative comparison, fast-action approval/rejection modal. |
| **Admin Dashboard** | `admin_dashboard_raw.html` | Org-wide decision analytics, pending user approval queue, user directory, system settings, global audit log. |
| **Manager Dashboard** | `manager_dashboard.html` | Team decisions, financial impact totals, member activity overview, escalation handling. |
| **Employee Dashboard** | `employee_dashboard.html` | Personal decision tracker, draft resume panel, assigned reviews, notification feed. |

---

### 5. Enterprise Security & Hardened Onboarding

- **Multi-Step OTP Registration**:
  - Cryptographic 6-digit OTP dispatched via SMTP email (`email_service.py`, `verify_email.html`) before setting passwords.
- **Auto-Generated Role-Prefixed IDs**:
  - Automatic identifier assignment: `AD-xxx` (Admin), `MN-xxx` (Manager), `RW-xxx` (Reviewer), `EMP-xxx` (Employee).
- **Admin Verification Queue**:
  - Newly registered accounts remain in `Pending Approval` until verified by an Administrator (`pending_approvals.html`).
- **Row-Level Security (RLS)**:
  - PostgreSQL RLS policies restrict audit log access to authorized roles.
- **Least-Privilege Database Role**:
  - Application connections utilize `edrp_app` restricted to `SELECT` and `INSERT` on audit tables.
- **Persistent Sessions**:
  - 72-hour persistent login with JWT tokens and Flask session security.
- **Telemetry Capture**:
  - Client IP addresses and browser `User-Agent` strings stored in every audit log entry.

---

### 6. Enterprise Collaboration, Settings & Support Ticketing

- **Discussion Threads & Comments (`discussion_api.py`, `discussion.html`)**:
  - Threaded commenting and collaboration tied directly to decisions.
- **Meeting Notes (`meeting_note.py`)**:
  - Capture offline meeting minutes, attendee lists, and trade-off summaries.
- **System Settings Console (`settings_api.py`, `settings.html`)**:
  - Administrative control over SMTP credentials, maintenance mode, and session policies.
- **Support Ticketing System (`support_api.py`, `support.html`)**:
  - In-app support request submission with real-time status tracking (Open, In Progress, Resolved).

---

## 📊 Milestone 3 Deliverables Summary

| Component | Quantity | Details |
|---|:---:|---|
| **Database Tables** | **18** | PostgreSQL 15 schema with RLS, triggers, JSONB, and foreign keys |
| **API Routers** | **20** | FastAPI endpoints on Port 8000 with OpenAPI / Swagger documentation |
| **UI Templates** | **36** | Jinja2 templates styled with Glassmorphism dark theme |
| **ORM Models** | **19** | SQLAlchemy models with cascade rules and relationships |
| **Business Services** | **17** | Decoupled business logic services and repositories |
| **Frontend JS Modules** | **14** | Asynchronous ES6+ modules with Fetch API |

---

## 🔌 Milestone 3 API Endpoints

The FastAPI backend exposes the following primary endpoints for Milestone 3 features:

| Endpoint | Method | Description |
|---|:---:|---|
| `/audit-logs` | `GET` | List audit logs with pagination and filters (entity, actor, action, date) |
| `/audit-logs/decision/{id}` | `GET` | Retrieve complete decision audit timeline with snapshots and reviews |
| `/audit-logs/export` | `GET` | Export filtered audit logs as a downloadable CSV file |
| `/approval-chains` | `GET` / `POST` | Manage and configure dynamic multi-tier approval chains |
| `/replays/{decision_id}` | `GET` | Fetch chronological replay steps and point-in-time snapshots |
| `/reviews/{decision_id}` | `POST` | Submit review verdict (`approve`, `reject`, `revision_requested`) |
| `/dashboard/{user_id}` | `GET` | Fetch role-tailored dashboard metrics and pending review counts |
| `/settings` | `GET` / `PUT` | Read and update system settings (SMTP, maintenance, policies) |
| `/support` | `GET` / `POST` | Create and manage support tickets |
| `/email/send-otp` | `POST` | Dispatch 6-digit verification code via SMTP email |
| `/email/verify-otp` | `POST` | Validate submitted OTP code |
| `/users/pending-approvals` | `GET` | Retrieve list of unapproved user registrations for Admin review |
| `/users/{id}/approve` | `POST` | Administrator approval for pending user account |

*Interactive Swagger UI documentation is available at `http://localhost:8000/docs`.*

---

## 🛠️ Verification & Setup Guide

### 1. Backend Setup (FastAPI)

```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

# Seed default roles and test users
python seed_db.py

# Start FastAPI backend
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup (Flask)

```bash
# In a separate terminal:
cd frontend
pip install -r requirements.txt

# Start Flask frontend server
python app.py
```

### 3. Test User Credentials

| Role | Employee ID | Email | Password | Access Scope |
|---|:---:|---|:---:|---|
| **Administrator** | `AD3341` | `admin@corp.com` | `password123` | Full system access, audit logs, user approvals, settings |
| **Manager** | `MN1297` | `manager@corp.com` | `password123` | Team decisions, approvals, team analytics |
| **Reviewer** | `RW1300` | `reviewer@corp.com` | `password123` | Decision reviews, approvals, alternative evaluation |
| **Employee** | `EMP8749` | `koppala.naveen@corp.com` | `password123` | Create decisions, edit drafts, replay history |

---

## 👥 Contributors

**Expert Decision Replay Platform (EDRP) — Group 5**  
Academic Year 2025–26

- **Koppala Naveen** — *Full Stack Development, Decision Engine, Audit Trail & DevOps*
- **Vaibhav Ingle** — *Backend Architecture, Database Design & Security*
