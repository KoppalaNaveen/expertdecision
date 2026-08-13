# Expert Decision Replay Platform (EDRP) — Milestone 3

## Milestone 3 Executive Summary


Milestone 3 completes the core enterprise requirements of the **Expert Decision Replay Platform (EDRP)**, delivering:
1. **Append-Only Structured Audit Logging** with field-level before/after diff tracking and database-level immutability triggers.
2. **Configurable Multi-Tier Approval Chains** supporting dynamic routing, sequential reviewer evaluations, and SLA notifications.
3. **Interactive Decision Replay & Versioning Engine** providing point-in-time snapshotting and visual historical playback.
4. **Reviewer Workspace & Role-Tailored Dashboards** for Administrators, Managers, Reviewers, and Employees.
5. **Security Hardening & Access Control** with PostgreSQL Row-Level Security (RLS), least-privilege database roles, 6-digit SMTP OTP onboarding, and 72-hour persistent sessions.
6. **Enterprise Settings & Support Ticketing System** for platform configuration, SMTP controls, and user issue resolution.

---

## Key Modules Implemented in Milestone 3

### 1. Structured & Append-Only Audit Logging System
An enterprise-grade audit trail designed for regulatory compliance (SOC 2, ISO 27001) that tracks every state change across the platform:
- **Structured Log Model (`AuditLog`)**: Captures actor ID, action type, entity type, entity ID, JSON diffs, client IP address, User-Agent, and timestamps.
- **Field-Level Diff Engine (`diff.py`)**: Computes granular per-field differences between previous and updated states (`before`/`after`).
- **Database Immutability Triggers**: PostgreSQL triggers block any `UPDATE` or `DELETE` operations on the `audit_logs` table to guarantee an append-only, tamper-proof record.
- **Decision Audit Trail Timeline API**: Aggregates decision versions, reviewer assessments, comments, uploads, and audit records into a single unified timeline.
- **Live Polling Audit Viewer**: Real-time 5-second polling interface with multi-criteria filtering (Entity, Actor, Action, Date Range) and one-click CSV export.

---

### 2. Configurable Multi-Tier Approval Chains
A dynamic workflow engine for routing and approving strategic decisions:
- **Dynamic Approval Chain Configs**: Admin-configurable multi-step approval workflows based on decision category and budget threshold rules.
- **Reviewer Evaluation States**:
  - **Approve**: Advances decision to next approval stage or finalizes to `Approved`.
  - **Reject**: Terminated with mandatory justification comment; alerts creator.
  - **Request Revision**: Reverts decision status to `Draft`; creator updates and resubmits, creating version `v2`.
- **Reviewer Assignment & Notifications**: Reviewers assigned directly via UI; automated alerts dispatched via in-app notifications and background SMTP emails.

---

### 3. Interactive Decision Replay & Versioning Engine
Preserves the complete evolution of organizational decisions:
- **Automated Version Snapshots**: Stores complete JSON state snapshots whenever a decision is submitted, reviewed, or modified.
- **Visual Replay Viewer**: Step-by-step playback interface allowing stakeholders to inspect who contributed, what alternatives were evaluated, what meeting notes were captured, and why final consensus was reached.

---

### 4. Reviewer Workspace & Role-Tailored Dashboards
Specialized interfaces for all 4 user roles:
- **Reviewer Dashboard**: Pending review queue, side-by-side alternative comparison, and fast-action approval/rejection modal.
- **Admin Dashboard**: Org-wide decision analytics, pending user approval queue, user directory, system settings, and global audit log.
- **Manager Dashboard**: Team decisions, financial impact totals, member activity overview, and escalation handling.
- **Employee Dashboard**: Personal decision tracker, draft resume panel, assigned reviews, and notification feed.

---

### 5. Enterprise Security & Hardened Onboarding
- **Multi-Step OTP Registration**: Cryptographic 6-digit OTP dispatched via SMTP email before password setup.
- **Auto-Generated Role-Prefixed IDs**: Automatic identifier assignment (`AD-xxx`, `MN-xxx`, `RW-xxx`, `EMP-xxx`).
- **Admin Verification Queue**: Newly registered accounts remain in `Pending Approval` until verified by an Administrator.
- **Row-Level Security (RLS)**: PostgreSQL RLS policies restrict audit log access to authorized roles.
- **Least-Privilege Database Role**: Application connections utilize `edrp_app` restricted to `SELECT` and `INSERT` on audit tables.
- **Persistent Sessions**: 72-hour persistent login with JWT tokens and Flask session security.
- **Telemetry Capture**: Client IP addresses and browser User-Agent strings stored in every audit log entry.

---

### 6. Enterprise Collaboration, Settings & Support Ticketing
- **Discussion Threads & Comments**: Threaded commenting and collaboration tied directly to decisions.
- **Meeting Notes**: Capture offline meeting minutes, attendee lists, and trade-off summaries.
- **System Settings Console**: Administrative control over SMTP credentials, maintenance mode, and session policies.
- **Support Ticketing System**: In-app support request submission with real-time status tracking (Open, In Progress, Resolved).

---

## Milestone 3 Deliverables Summary

| Component | Quantity | Details |
|---|:---:|---|
| **Database Tables** | **18** | PostgreSQL 15 schema with RLS, triggers, JSONB, and foreign keys |
| **API Routers** | **20** | FastAPI endpoints on Port 8000 with OpenAPI / Swagger documentation |
| **UI Templates** | **36** | Jinja2 templates styled with Glassmorphism dark theme |
| **ORM Models** | **19** | SQLAlchemy models with cascade rules and relationships |
| **Business Services** | **17** | Decoupled business logic services and repositories |
| **Frontend JS Modules** | **14** | Asynchronous ES6+ modules with Fetch API |
