# Expert Decision Replay Platform (EDRP) — Milestone 3 Complete

> **Group 5** | A centralized platform for documenting, managing, replaying, and reviewing strategic organizational decisions.

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?style=flat&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?style=flat&logo=postgresql&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1+-000000?style=flat&logo=flask&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-ORM-D71F00?style=flat&logo=python&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat&logo=docker&logoColor=white)

---

## Overview

The **Expert Decision Replay Platform (EDRP)** is a full-stack web application designed to help organizations preserve institutional knowledge by capturing the complete lifecycle of strategic decisions. From initial draft through expert review to final archival, every step is documented, versioned, and audit-logged.

The platform serves four user roles — **Administrator**, **Manager**, **Reviewer**, and **Employee** — each with role-based access controls. Administrators can monitor all activity through real-time dashboards and comprehensive audit trails, while decision creators can replay the full history of any decision to understand how and why it was made.

---

## System Architecture

```mermaid
graph TB
    subgraph "Frontend Layer"
        Browser["Web Browser"]
        FlaskApp["Flask Proxy Server<br/>Port 5000"]
    end

    subgraph "Backend Layer"
        FastAPIApp["FastAPI Backend<br/>Port 8000"]
        AuthModule["Authentication<br/>JWT + OTP + RBAC"]
        AuditEngine["Audit Engine<br/>Structured Logging"]
        EmailService["Email Service<br/>SMTP Threaded"]
    end

    subgraph "Data Layer"
        PostgreSQL[("PostgreSQL<br/>Database")]
        SQLAlchemy["SQLAlchemy ORM"]
        Alembic["Alembic<br/>Migrations"]
    end

    subgraph "External Services"
        SMTPServer["SMTP Server<br/>Email Delivery"]
    end

    Browser -->|"HTTP"| FlaskApp
    FlaskApp -->|"REST API"| FastAPIApp
    FastAPIApp --> AuthModule
    FastAPIApp --> AuditEngine
    FastAPIApp --> EmailService
    FastAPIApp --> SQLAlchemy
    SQLAlchemy --> PostgreSQL
    Alembic --> PostgreSQL
    EmailService -->|"Email"| SMTPServer

    style Browser fill:#e3f2fd,stroke:#1565c0
    style FlaskApp fill:#fff3e0,stroke:#e65100
    style FastAPIApp fill:#e8f5e9,stroke:#2e7d32
    style PostgreSQL fill:#fce4ec,stroke:#c62828
    style SMTPServer fill:#f3e5f5,stroke:#6a1b9a
```

---

## Entity Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ ROLES : has
    USERS ||--o{ TEAMS : belongs_to
    USERS ||--o{ DECISIONS : creates
    USERS ||--o{ REVIEWS : performs
    USERS ||--o{ ACTIVITY_LOGS : generates
    USERS ||--o{ AUDIT_LOGS : actor
    USERS ||--o{ NOTIFICATIONS : receives
    USERS ||--o{ EMAIL_VERIFICATIONS : has
    USERS ||--o{ DISCUSSION_THREADS : creates
    USERS ||--o{ COMMENTS : writes
    USERS ||--o{ MEETING_NOTES : creates
    USERS ||--o{ ATTACHMENTS : uploads
    USERS ||--o{ SUPPORT_TICKETS : submits
    USERS ||--o{ APPROVAL_CHAIN_CONFIGS : configures

    DECISIONS ||--o{ ALTERNATIVES : evaluates
    DECISIONS ||--o{ REVIEWS : receives
    DECISIONS ||--o{ DECISION_VERSIONS : versioned_by
    DECISIONS ||--o{ REPLAYS : has
    DECISIONS ||--o{ DISCUSSION_THREADS : discussed_in
    DECISIONS ||--o{ MEETING_NOTES : documented_in
    DECISIONS ||--o{ ATTACHMENTS : has

    DISCUSSION_THREADS ||--o{ COMMENTS : contains

    ROLES {
        int id PK
        string name
        string description
    }

    TEAMS {
        int id PK
        string name
        string description
    }

    USERS {
        int id PK
        string full_name
        string email
        string email_hashed
        string password_hashed
        string employee_id UK
        int role_id FK
        int team_id FK
        string status
        boolean email_verified
        datetime created_at
    }

    DECISIONS {
        int id PK
        string title
        string category
        string urgency
        string status
        int creator_id FK
        text rationale
        text alternatives
        decimal financial_impact
        string risk_level
        datetime created_at
    }

    ALTERNATIVES {
        int id PK
        int decision_id FK
        string title
        text description
        decimal estimated_cost
        string feasibility
        string recommendation
    }

    REVIEWS {
        int id PK
        int decision_id FK
        int reviewer_id FK
        string status
        text comments
        datetime reviewed_at
    }

    DECISION_VERSIONS {
        int id PK
        int decision_id FK
        int version_number
        json snapshot
        string change_reason
        int changed_by FK
        datetime created_at
    }

    AUDIT_LOGS {
        int id PK
        int company_id
        int actor_id FK
        string action
        string entity_type
        int entity_id
        json diff
        text details
        string ip_address
        string user_agent
        datetime created_at
    }

    ACTIVITY_LOGS {
        int id PK
        int user_id FK
        string action
        string module
        string details
        datetime created_at
    }

    APPROVAL_CHAIN_CONFIGS {
        int id PK
        int company_id
        string name
        text description
        json steps
        boolean is_active
        int created_by FK
        datetime created_at
    }

    NOTIFICATIONS {
        int id PK
        int user_id FK
        string message
        string notification_type
        boolean is_read
        datetime created_at
    }

    DISCUSSION_THREADS {
        int id PK
        int decision_id FK
        int created_by FK
        string topic
        datetime created_at
    }

    COMMENTS {
        int id PK
        int thread_id FK
        int user_id FK
        text content
        datetime created_at
    }

    ATTACHMENTS {
        int id PK
        int decision_id FK
        int uploaded_by FK
        string filename
        bigint file_size
        datetime uploaded_at
    }

    MEETING_NOTES {
        int id PK
        int decision_id FK
        int created_by FK
        string title
        text notes
        datetime created_at
    }

    EMAIL_VERIFICATIONS {
        int id PK
        string email
        string code
        string purpose
        datetime expires_at
        boolean is_verified
    }

    SUPPORT_TICKETS {
        int id PK
        int user_id FK
        string subject
        text message
        string status
        datetime created_at
    }

    SYSTEM_SETTINGS {
        int id PK
        string key_name
        text value
        string description
    }
```

---

## Decision Workflow

```mermaid
stateDiagram-v2
    [*] --> Draft: Create Decision

    Draft --> InReview: Submit for Review
    Draft --> Archived: Discard

    InReview --> Approved: All Reviewers Approve
    InReview --> Rejected: Any Reviewer Rejects
    InReview --> Draft: Send Back for Revision

    Approved --> Archived: Archive Decision
    Rejected --> Draft: Revise & Resubmit

    Archived --> [*]

    note right of Draft
        Decision creator can edit
        all fields freely
    end note

    note right of InReview
        Reviewers assigned by admin
        can approve or reject
    end note

    note right of Approved
        Decision is finalized and
        versioned for replay
    end note
```

---

## User Onboarding Flow

```mermaid
flowchart TD
    Start([New User Visits /register]) --> EnterInfo[Enter Full Name & Email]
    EnterInfo --> SendOTP[System Sends 6-Digit OTP via SMTP]
    SendOTP --> VerifyOTP{OTP Verified?}
    VerifyOTP -->|No| RetryOTP[Resend OTP]
    RetryOTP --> VerifyOTP
    VerifyOTP -->|Yes| SetCreds[Set Employee ID & Password]
    SetCreds --> AutoGenID[Auto-Generate Role-Prefixed ID]
    AutoGenID --> Pending[Account Status: Pending Approval]
    Pending --> AdminNotif[Admin Receives Notification]
    AdminNotif --> AdminReview{Admin Decision}
    AdminReview -->|Approve| Approved[Status: Approved]
    AdminReview -->|Reject| Rejected[Status: Rejected]
    Approved --> EmailNotif[User Receives Approval Email]
    EmailNotif --> Login[User Can Now Login]
    Rejected --> RejectedNotif[User Receives Rejection Email]
    RejectedNotif --> End([Account Cannot Login])
    Login --> Dashboard[Redirect to Dashboard]

    style Start fill:#e8f5e9,stroke:#2e7d32
    style Dashboard fill:#e3f2fd,stroke:#1565c0
    style End fill:#ffebee,stroke:#c62828
    style Pending fill:#fff3e0,stroke:#e65100
    style Approved fill:#e8f5e9,stroke:#2e7d32
    style Rejected fill:#ffebee,stroke:#c62828
```

---

## Features by Milestone

### Milestone 1 — Foundation

| Feature | Description |
|---------|-------------|
| User Registration & Login | Email/password authentication with JWT tokens |
| Role-Based Access Control | Four roles: Administrator, Manager, Reviewer, Employee |
| Team Management | Create, assign, and manage organizational teams |
| Decision CRUD | Create, read, update, and delete decisions |
| Alternative Evaluation | Evaluate multiple alternatives per decision with cost analysis |
| Basic Dashboard | Role-based dashboard views for each user type |
| File Uploads | Attach documents (PDF, DOCX, PPTX) to decisions |

### Milestone 2 — Decision Lifecycle & Audit

| Feature | Description |
|---------|-------------|
| Decision Workflow Lifecycle | State machine: Draft → In Review → Approved/Rejected → Archived |
| Multi-Step OTP Registration | 6-digit Email OTP verification via SMTP before account creation |
| Auto-Generated Employee IDs | Role-prefixed unique IDs (`AD`, `MN`, `RW`, `EMP`) |
| Admin Approval Workflow | Pending accounts verified by administrators with email notifications |
| 72-Hour Persistent Sessions | "Remember Me" extended JWT session lifetime |
| Real-Time Audit Logging | Automatic capture of all platform events with module classification |
| 5-Second Auto-Refresh Audit | Live polling audit logs dashboard with relative timestamps |
| Decision Replay Engine | Step-by-step playback of decision history and reviewer contributions |
| Reviewer Assignment | Assign strategic reviewers to evaluate submitted decisions |
| Discussion Threads | Threaded discussions on decisions with comment support |
| Meeting Notes | Document meeting notes linked to specific decisions |
| Single-Screen User Directory | Compact user table with profile modals and cascade deletion |
| Admin/Manager/Employee Dashboards | Role-specific dashboards with live PostgreSQL data |

### Latest — Enhanced Audit & Approval Chains

| Feature | Description |
|---------|-------------|
| Structured Audit Logging | New `AuditLog` model with JSON field-level diffs (`before`/`after`) |
| Append-Only Audit Table | PostgreSQL triggers prevent UPDATE/DELETE on audit_logs |
| Decision Audit Trail API | Full timeline of versions, reviews, comments, uploads, and audit events per decision |
| Field-Level Diff Engine | `diff_dicts()` utility captures per-field changes between snapshots |
| Approval Chain Configuration | Admin-configurable multi-step approval chains with role-based steps |
| Decision Versioning | Automatic version snapshots on every decision state change |
| Row-Level Security | PostgreSQL RLS policies on audit_logs for restricted access |
| Least-Privilege DB Roles | Separate `edrp_app` role with SELECT/INSERT only on audit tables |
| IP & User-Agent Tracking | Audit logs capture client IP and browser user-agent strings |

---

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | HTML5, CSS3 (Glassmorphism), JavaScript ES6+ | UI with Lucide icons, Fetch API, async/await |
| **Frontend Server** | Flask 3.1 | Jinja2 templating, session management, reverse proxy |
| **Backend** | FastAPI, Python 3.10+ | REST API, dependency injection, async support |
| **ASGI Server** | Uvicorn 0.49 | Production-grade async web server |
| **Database** | PostgreSQL 15 | Relational data store with JSON support |
| **ORM** | SQLAlchemy | Database abstraction and model relationships |
| **Migrations** | Alembic | Version-controlled database schema changes |
| **Authentication** | JWT (python-jose) | Stateless token-based authentication |
| **Password Hashing** | Passlib + Bcrypt | Secure password storage |
| **Email** | SMTP (threaded) | Background OTP and notification emails |
| **Session** | Flask sessions | 72-hour persistent login with "Remember Me" |
| **DevOps** | Docker, Docker Compose | Containerized deployment |
| **Version Control** | Git, GitHub | Source code management |

---

## Project Structure

```
EDRP/
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI route handlers (20 routers)
│   │   │   ├── user_api.py         # User CRUD & management
│   │   │   ├── role_api.py         # Role management
│   │   │   ├── team_api.py         # Team management
│   │   │   ├── decision_api.py     # Decision lifecycle
│   │   │   ├── alternative_api.py  # Alternative evaluation
│   │   │   ├── review_api.py       # Reviewer assignments & reviews
│   │   │   ├── replay_api.py       # Decision replay engine
│   │   │   ├── audit_api.py        # Structured audit logs + decision trail
│   │   │   ├── approval_chain_api.py # Configurable approval chains
│   │   │   ├── dashboard_api.py    # Dashboard data endpoints
│   │   │   ├── profile_api.py      # User profile management
│   │   │   ├── notification_api.py # In-app notifications
│   │   │   ├── discussion_api.py   # Discussion threads & comments
│   │   │   ├── upload_api.py       # File upload handling
│   │   │   ├── report_api.py       # Report generation
│   │   │   ├── repository_api.py   # Decision repository
│   │   │   ├── settings_api.py     # System settings
│   │   │   └── support_api.py      # Support tickets
│   │   ├── models/                 # SQLAlchemy ORM models (19 models)
│   │   │   ├── user.py             # User accounts
│   │   │   ├── role.py             # User roles
│   │   │   ├── team.py             # Organizational teams
│   │   │   ├── decision.py         # Decision records
│   │   │   ├── decision_version.py # Decision version snapshots
│   │   │   ├── alternative.py      # Evaluated alternatives
│   │   │   ├── review.py           # Reviewer assessments
│   │   │   ├── replay.py           # Decision replay data
│   │   │   ├── audit_log.py        # Structured audit trail (append-only)
│   │   │   ├── activity_log.py     # Legacy activity logs
│   │   │   ├── approval_chain.py   # Approval chain configs
│   │   │   ├── notification.py     # User notifications
│   │   │   ├── comment.py          # Discussion threads & comments
│   │   │   ├── meeting_note.py     # Meeting notes
│   │   │   ├── attachment.py       # File attachments
│   │   │   ├── email_verification.py # OTP verification codes
│   │   │   ├── support_ticket.py   # Support tickets
│   │   │   └── system_setting.py   # System configuration
│   │   ├── services/               # Business logic layer (17 services)
│   │   ├── repositories/           # Data access layer
│   │   ├── schemas/                # Pydantic request/response models
│   │   ├── dependencies/           # FastAPI dependency injection
│   │   │   └── auth.py             # JWT auth & role requirements
│   │   ├── utils/                  # Utility functions
│   │   │   └── diff.py             # Field-level diff engine
│   │   ├── config/                 # Application configuration
│   │   ├── database/               # DB connection & base model
│   │   └── main.py                 # FastAPI app entry point
│   ├── uploads/                    # Uploaded files storage
│   ├── requirements.txt            # Python backend dependencies
│   └── database.db                 # SQLite (development fallback)
├── frontend/
│   ├── app.py                      # Flask application (851 lines)
│   ├── templates/                  # Jinja2 HTML templates (36 pages)
│   │   ├── base.html               # Base layout with navigation
│   │   ├── landing.html            # Public landing page
│   │   ├── login.html              # Login with Remember Me
│   │   ├── register.html           # Multi-step OTP registration
│   │   ├── dashboard.html          # Main dashboard
│   │   ├── admin_dashboard_raw.html # Admin dashboard
│   │   ├── manager_dashboard.html  # Manager dashboard
│   │   ├── employee_dashboard.html # Employee dashboard
│   │   ├── decisions.html          # Decision listing
│   │   ├── create_decision.html    # Decision creation form
│   │   ├── decision_details.html   # Decision detail view
│   │   ├── audit.html              # Audit logs viewer
│   │   ├── replays.html            # Decision replay viewer
│   │   ├── reviews.html            # Reviewer assignments
│   │   ├── users.html              # User management
│   │   ├── roles.html              # Role management
│   │   ├── teams.html              # Team management
│   │   ├── discussion.html         # Discussion threads
│   │   ├── upload.html             # File uploads
│   │   ├── notifications.html      # User notifications
│   │   ├── profile.html            # User profile
│   │   ├── settings.html           # System settings
│   │   ├── support.html            # Support tickets
│   │   └── reports.html            # Report generation
│   ├── static/
│   │   ├── js/                     # JavaScript modules (14 files)
│   │   ├── css/                    # Custom stylesheets
│   │   └── images/                 # Static assets
│   └── requirements.txt            # Python frontend dependencies
├── database/
│   ├── schema.sql                  # Database schema definition
│   ├── seed.sql                    # Sample data seeding
│   └── migrations/
│       └── 001_audit_logs.sql      # Audit log indexes, triggers, RLS
├── docker/
│   ├── Dockerfile.backend          # Backend container image
│   ├── Dockerfile.frontend         # Frontend container image
│   └── docker-compose.yml          # Multi-service orchestration
├── docs/
│   ├── Architecture.pdf            # System architecture document
│   ├── ERDiagram.pdf               # Entity relationship diagram
│   ├── API_Documentation.pdf       # REST API reference
│   └── User_Manual.pdf             # End-user guide
├── EDRP UI/                        # UI mockups and captures
│   ├── index.html                  # Dashboard UI prototype
│   └── *.png / *.pdf               # Dashboard screenshots
└── .gitignore                      # Git ignore rules (includes venv/)
```

---

## API Endpoints

| Prefix | Module | Description |
|--------|--------|-------------|
| `/users` | `user_api` | User CRUD, registration, admin approval |
| `/roles` | `role_api` | Role management and assignment |
| `/teams` | `team_api` | Team creation and management |
| `/decisions` | `decision_api` | Decision lifecycle operations |
| `/alternatives` | `alternative_api` | Alternative evaluation CRUD |
| `/reviews` | `review_api` | Reviewer assignments and assessments |
| `/replays` | `replay_api` | Decision replay engine |
| `/audit-logs` | `audit_api` | Structured audit logs + decision trail |
| `/approval-chains` | `approval_chain_api` | Configurable approval chain management |
| `/dashboard` | `dashboard_api` | Dashboard data aggregation |
| `/profile` | `profile_api` | User profile operations |
| `/notifications` | `notification_api` | In-app notification system |
| `/discussions` | `discussion_api` | Discussion threads and comments |
| `/upload` | `upload_api` | File upload handling |
| `/reports` | `report_api` | Report generation |
| `/repository` | `repository_api` | Decision repository browser |
| `/settings` | `settings_api` | System configuration |
| `/support` | `support_api` | Support ticket system |

---

## Database Schema Summary

| Table | Purpose | Key Relationships |
|-------|---------|-------------------|
| `users` | User accounts with roles and teams | FK to roles, teams |
| `roles` | Role definitions (Admin, Manager, Reviewer, Employee) | Referenced by users |
| `teams` | Organizational teams | Referenced by users |
| `decisions` | Decision records with full metadata | FK to users (creator) |
| `decision_versions` | Version snapshots of decisions | FK to decisions, users |
| `alternatives` | Evaluated alternatives per decision | FK to decisions |
| `reviews` | Reviewer assessments of decisions | FK to decisions, users |
| `audit_logs` | Append-only structured audit trail | FK to users (actor) |
| `activity_logs` | Legacy activity event logging | FK to users |
| `approval_chain_configs` | Multi-step approval chain definitions | FK to users (creator) |
| `notifications` | In-app user notifications | FK to users |
| `discussion_threads` | Discussion topics per decision | FK to decisions, users |
| `comments` | Threaded comments | FK to threads, users |
| `meeting_notes` | Meeting notes per decision | FK to decisions, users |
| `attachments` | File uploads per decision | FK to decisions, users |
| `email_verifications` | OTP verification codes | Standalone |
| `support_tickets` | User support requests | FK to users |
| `system_settings` | Application configuration | Standalone |

---

## Installation & Setup

### Prerequisites

- Python 3.10+
- PostgreSQL 15+
- pip (Python package manager)
- Git

### Backend Setup

```bash
# Clone the repository
git clone https://github.com/KoppalaNaveen/EDRP.git
cd EDRP

# Create and activate virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

# Install backend dependencies
cd backend
pip install -r requirements.txt

# Set up environment variables
# Create backend/.env with:
#   DATABASE_URL=postgresql://user:password@localhost:5432/edrp
#   SECRET_KEY=your-secret-key
#   SMTP_HOST=smtp.gmail.com
#   SMTP_PORT=587
#   SMTP_USER=your-email@gmail.com
#   SMTP_PASS=your-app-password

# Run database migrations
alembic upgrade head

# Start the backend server
uvicorn app.main:app --reload --port 8000
```

### Frontend Setup

```bash
# In a new terminal, navigate to frontend
cd frontend

# Install frontend dependencies
pip install -r requirements.txt

# Start the Flask server
python app.py
```

### Access the Application

| Service | URL |
|---------|-----|
| Frontend (Flask) | http://localhost:5000 |
| Backend API (FastAPI) | http://localhost:8000 |
| API Documentation | http://localhost:8000/docs |

### Docker Setup

```bash
# Build and start all services
cd docker
docker-compose up --build

# Access the application
# Frontend: http://localhost:5000
# Backend: http://localhost:8000
```

---

## Security Features

| Feature | Implementation |
|---------|---------------|
| **Password Hashing** | Bcrypt via Passlib — passwords never stored in plaintext |
| **JWT Authentication** | Stateless tokens with configurable expiry (72-hour "Remember Me") |
| **Role-Based Access Control** | Four roles with endpoint-level permission checks |
| **Email OTP Verification** | 6-digit codes with expiration before account activation |
| **Admin Approval Workflow** | Accounts remain pending until administrator verification |
| **Append-Only Audit Logs** | PostgreSQL triggers block UPDATE/DELETE on audit_logs |
| **Row-Level Security** | PostgreSQL RLS policies restrict audit log access |
| **Least-Privilege DB Roles** | Separate `edrp_app` role with SELECT/INSERT only |
| **IP & User-Agent Tracking** | Client metadata captured in audit trail |
| **Field-Level Diff Logging** | Every change recorded with before/after values |

---

## Audit Logging System

The audit system provides enterprise-grade compliance tracking:

- **Structured Logs**: Each entry captures actor, action, entity, field-level diffs, IP, and user-agent
- **Append-Only Enforcement**: Database triggers prevent any modification or deletion of audit records
- **Decision Audit Trail**: Full timeline API aggregating versions, reviews, comments, uploads, and audit events
- **Real-Time Dashboard**: 5-second auto-refresh with filtering by entity, actor, action, and date range
- **CSV Export**: One-click export of filtered audit logs for compliance reporting
- **Legacy Backfill**: Migration script carries historical events from activity_logs into audit_logs

---

## Contributors

*

---




