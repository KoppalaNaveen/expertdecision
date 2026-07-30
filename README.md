# Expert Decision Replay Platform - Group 5

## Milestone 2 – Decision Lifecycle, Real-Time Audit Trail & Enhanced User Management

## Overview

The **Expert Decision Replay Platform (EDRP)** is a centralized web application that enables organizations to document, manage, replay, and review strategic decisions. The platform preserves organizational memory by recording structured decision details, evaluated alternatives, discussion threads, reviewer approvals, and historical audit trails.

This repository contains the implementation of **Milestone 2**, which expands upon Milestone 1 by delivering complete decision workflow management, multi-step email OTP registration, role-based employee ID auto-generation, administrator approval workflows, 72-hour persistent sessions, real-time activity audit logging, and dynamic administrator monitoring dashboards.

---

## Objectives

- Implement end-to-end Decision Creation, Evaluation, and Approval workflows.
- Expand secure user onboarding with Email OTP verification and automated Employee ID generation.
- Build Administrator Approval controls with automated email notifications upon account verification.
- Establish a 72-Hour Persistent Session ("Remember Me") authentication mechanism.
- Develop a real-time Audit Logging system to track all platform events dynamically.
- Build interactive Administrator and Employee Dashboards connected directly to PostgreSQL live data.
- Refine user management layouts with single-screen view user profile modals and permanent deletion cascades.

---

## Features Implemented

### Decision Workflow & Replay Engine

- **Decision Creation & Tracking**: Comprehensive recording of Title, Category, Urgency, Rationale, Alternatives Evaluated, Financial Impact, and Risk Level.
- **Workflow Lifecycle**: Decision transition through states (`Draft` ➔ `In Review` ➔ `Approved` / `Rejected` ➔ `Archived`).
- **Decision Replay**: Step-by-step audit playback of decision history and reviewer contributions.
- **Reviewer Assignment**: Assigning strategic reviewers to evaluate submitted proposals.

### Enhanced User Management & Security

- **Multi-Step OTP Registration**: 6-digit Email OTP generation and verification via SMTP before account creation.
- **Auto-Generated Employee IDs**: Unique role-prefixed IDs (`AD` for Admin, `MN` for Manager, `RW` for Reviewer, `EMP` for Employee).
- **Administrator Account Approval**: Newly registered users remain in a "Pending Approval" state until verified by an Administrator.
- **Automated Approval Notifications**: Instant email notification dispatched to users once approved by the Admin.
- **72-Hour Persistent Session ("Remember Me")**: Extended JWT session lifetime (72 hours) allowing seamless direct dashboard access upon returning.
- **Single-Screen User Directory**: Compact user table layout (12 rows/page) with centered stat cards, profile details modal, and cascade-safe permanent deletion.

### Real-Time Audit Trail & Analytics

- **Live Activity Logging**: Automatic capture of all platform events (Logins, Registration, Admin Approvals/Rejections, Account Deletions, Decision Updates).
- **Module Classification**: Automatic categorisation into `Auth`, `Decisions`, `Reports`, `Reviews`, and `System`.
- **Live Auto-Refresh**: 5-second dynamic polling on the Audit Logs dashboard displaying real-time updates.
- **Accurate Timestamps**: Dual timestamp rendering displaying both relative time (`Just now`, `5 mins ago`) and exact date/time (`Jul 28, 2026 07:54 PM`).
- **Admin Dashboard Integration**: Real-time synchronization of stat cards, recent activity feeds, and compliance widgets with live PostgreSQL database records.

---

## Technology Stack

### Frontend

- HTML5
- Vanilla CSS (Glassmorphism, Vibrant Dark/Light Themes, CSS Grid/Flexbox)
- JavaScript (ES6+, Async/Await, Fetch API, Lucide Icons)
- Flask Proxy Server (Jinja2 Templating, Session Management)

### Backend

- Python 3.10+
- FastAPI
- Uvicorn (ASGI Web Server)

### Database

- PostgreSQL
- SQLAlchemy (ORM)
- Alembic (Database Migrations)

### Authentication & Email Services

- JWT (JSON Web Tokens)
- Passlib & Bcrypt (Password Hashing)
- SMTP (Background Threaded Email Dispatch for OTP & Approvals)

### Development & API Testing

- Git & GitHub
- Postman
- Visual Studio Code

---

## Database Schema (Milestone 2)

The application utilizes **PostgreSQL** to store relational enterprise data:

### Core Tables

1. **Users**: User ID, Full Name, Email (Plaintext & Hashed), Hashed Password, Employee ID, Role ID, Team ID, Status (`Pending Approval`, `Approved`, `Rejected`), Email Verified, Created At.
2. **Roles**: Role ID, Role Name (`Administrator`, `Manager`, `Employee`, `Reviewer`), Description.
3. **Decisions**: Decision ID, Title, Category, Urgency, Status (`Draft`, `In Review`, `Approved`, `Rejected`, `Archived`), Creator ID, Rationale, Alternatives, Financial Impact, Risk Level, Created At.
4. **Activity Logs**: Log ID, User ID (Foreign Key), Action, Module, Details, Created At.
5. **Verification Codes**: Code ID, Email, Code, Purpose (`register`, `reset_password`), Expiration Time, Is Verified.
6. **Notifications**: Notification ID, User ID, Message, Notification Type, Is Read, Created At.

---

## Authentication & User Onboarding Flow

1. **Email OTP Verification**: User enters full name and email; a 6-digit OTP is sent via SMTP.
2. **Employee ID Assignment**: System automatically generates a unique role-prefixed Employee ID (e.g. `EMP4821` / `AD1002`).
3. **Account Creation (Pending State)**: Credentials are stored with hashed password; account is marked `Pending Approval`.
4. **Administrator Verification**: Admin receives a notification and reviews the pending account on the User Management dashboard.
5. **Approval & Email Notification**: Admin approves the user; system dispatches an automated verification email (`Your account has been verified`).
6. **Persistent Login ("Remember Me")**: User logs in with Employee ID & Password. Checking "Remember Me" grants a 72-hour active session with auto-redirect to `/dashboard`.

---

## Milestone 2 Deliverables

- End-to-end Decision Lifecycle & Workflow implemented
- Decision Replay engine established
- Multi-step Email OTP Registration completed
- Role-based Employee ID Auto-Generation implemented
- Administrator Approval & Rejection Workflow completed
- Automated SMTP Account Approval Email Notification integrated
- 72-Hour Persistent Session ("Remember Me") implemented
- Single-Screen User Management Dashboard & User Details Modal deployed
- Real-Time Audit Log Engine & Module Categorization deployed
- Live 5-Second Auto-Refreshing Audit Logs Interface completed
- PostgreSQL Foreign Key cascade handling for user deletions implemented
- Postman API collection updated and verified