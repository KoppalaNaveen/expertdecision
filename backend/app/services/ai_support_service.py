import os
import json
import urllib.request
import urllib.error
import re
from typing import Dict, Any, List, Tuple

EDRP_SYSTEM_PROMPT = """You are the EDRP AI Support Assistant for the Expert Decision Replay Platform (EDRP).
EDRP is an enterprise platform for documenting, reviewing, approving, auditing, and replaying strategic business decisions.

Key Platform Knowledge:
- 4 Roles: Administrator (AD-xxx), Manager (MN-xxx), Reviewer (RW-xxx), Employee (EMP-xxx).
- Decision Workflow: Draft -> In Review -> Approved / Rejected / Revision Requested -> Archived.
- Decision Creation: Requires Title, Problem Rationale, Category, Stakeholders, Urgency, Budget/Financial Impact, and at least one Recommended Alternative.
- Alternatives: Evaluates pros, cons, estimated cost, feasibility score (1-10), risk level (Low/Med/High).
- Multi-Tier Approval Chains: Sequential review stages (Reviewer -> Manager -> Administrator). Reviewers can Approve, Reject (with reason), or Request Revision.
- Decision Replay: Point-in-time version snapshotting (v1, v2, etc.) and visual timeline playback of the full rationale and reviewer evaluations.
- Audit System: Structured append-only audit trail with field-level before/after diffs in JSON, database triggers preventing modification/deletion, and CSV export.
- User Onboarding: 6-digit email OTP verification via SMTP + Administrator verification queue.
- File Uploads: Supports PDF, DOCX, PPTX up to 200MB.

Always provide an accurate, helpful, step-by-step response directly answering the user's specific question using clean Markdown formatting.
"""

def generate_ai_response(user_message: str, user_name: str = "User", conversation_history: List[dict] = None) -> Dict[str, Any]:
    """
    Generates an intelligent AI response for the EDRP Support Center.
    First attempts live LLM APIs (Gemini / Groq / OpenAI), and seamlessly
    falls back to the built-in intelligent EDRP Knowledge Engine.
    """
    clean_msg = (user_message or "").strip()
    if not clean_msg:
        return {
            "reply": f"Hello {user_name}! How can I assist you with the Expert Decision Replay Platform today? Ask me any question about creating decisions, approval workflows, audit diffs, or account settings.",
            "suggested_actions": ["How do I create a decision?", "Explain approval workflow", "How does Decision Replay work?", "How do I reset my password?"],
            "source": "EDRP AI Assistant"
        }

    # 1. Live Google Gemini API (if key available)
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": f"{EDRP_SYSTEM_PROMPT}\n\nUser Question from {user_name}: {clean_msg}"}]}
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 700
                }
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            return {
                                "reply": parts[0]["text"].strip(),
                                "suggested_actions": _derive_custom_suggestions(clean_msg),
                                "source": "Google Gemini AI"
                            }
        except Exception as e:
            print(f"[AI SUPPORT GEMINI] Note: {e}")

    # 2. Live Groq / OpenAI API (if key available)
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": EDRP_SYSTEM_PROMPT},
                    {"role": "user", "content": clean_msg}
                ],
                "temperature": 0.2,
                "max_tokens": 700
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {groq_key}"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        return {
                            "reply": choices[0]["message"].get("content", "").strip(),
                            "suggested_actions": _derive_custom_suggestions(clean_msg),
                            "source": "Groq AI Engine"
                        }
        except Exception as e:
            print(f"[AI SUPPORT GROQ] Note: {e}")

    # 3. Comprehensive Built-in Semantic AI Engine
    return _answer_with_semantic_engine(clean_msg, user_name)


def _answer_with_semantic_engine(query: str, user_name: str) -> Dict[str, Any]:
    """
    High-precision dynamic question answering system that parses the user's intent,
    keywords, question structure, and contextual entities to formulate tailored replies.
    """
    q = query.lower().strip()

    # --- Greetings & Casual Chat ---
    if q in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "greetings", "help"]:
        return {
            "reply": f"Hello **{user_name}**! I am your **EDRP AI Support Assistant**.\n\nI can help you navigate decision creation, reviewer approval chains, version replay, audit diffs, and account settings.\n\nWhat would you like assistance with today?",
            "suggested_actions": ["How do I create a new decision?", "Explain the approval workflow", "How does Decision Replay work?", "How do I reset my password?"],
            "source": "EDRP AI Assistant"
        }

    if any(k in q for k in ["thank", "thanks", "appreciate", "helpful"]):
        return {
            "reply": f"You're very welcome, **{user_name}**! Let me know if you have any other questions regarding EDRP workflows, approvals, or reports.",
            "suggested_actions": ["How do I export reports?", "How to view audit logs?", "Explain approval workflow"],
            "source": "EDRP AI Assistant"
        }

    if any(k in q for k in ["who are you", "what is your name", "what can you do", "what are you"]):
        return {
            "reply": """I am the **EDRP AI Support Assistant**, designed to provide real-time guidance on the **Expert Decision Replay Platform**.

**What I Can Do:**
- 📋 Guide you through **creating decisions** and structuring alternative matrices.
- ⚡ Explain **multi-tier approval chains** (Reviewer → Manager → Administrator).
- ⏪ Explain **Decision Replay**, version snapshotting (`v1`, `v2`), and timeline diffs.
- 🔒 Clarify **append-only audit logs**, field-level diffs, and compliance exports.
- 🔑 Assist with **password resets**, OTP verification, role permissions, and ticket creation.
""",
            "suggested_actions": ["How do I create a new decision?", "Explain the approval workflow", "How does Decision Replay work?"],
            "source": "EDRP AI Assistant"
        }

    # --- 1. Decision Creation & Problem Rationale ---
    if any(k in q for k in ["how do i create", "how to create a decision", "create new decision", "start decision", "make decision", "steps to create"]):
        return {
            "reply": """**Step-by-Step Guide to Creating a Decision in EDRP:**

1. **Open Creation Wizard**: Click **'Create Decision'** in the sidebar navigation.
2. **Step 1 — Problem Statement & Rationale**:
   - Enter a clear **Title** and detailed **Problem Rationale** (explain why this decision is needed).
   - Select the **Category** (e.g. Infrastructure, Software, Operations) and **Urgency** (Low/Med/High/Critical).
   - Enter estimated **Financial Impact ($ ROI / Budget)**.
3. **Step 2 — Alternative Evaluation**:
   - Add at least 2 evaluated alternatives.
   - For each alternative, provide estimated **Cost**, **Feasibility Score (1-10)**, **Risk Level**, and **Pros & Cons**.
   - Select one alternative as **'Recommended'**.
4. **Step 3 — Attachments & Reviewers**:
   - Upload supporting files (PDF, DOCX, PPTX up to 200MB).
   - Choose assigned Reviewers and Managers.
5. **Step 4 — Submit**:
   - Click **'Save as Draft'** (auto-saves every 30s) or click **'Submit for Approval'** to trigger the review workflow.
""",
            "suggested_actions": ["What is an Alternative Analysis?", "Explain the approval workflow", "Can I edit a decision after submission?"],
            "source": "EDRP AI Assistant"
        }

    if any(k in q for k in ["rationale", "problem statement", "justification", "why rationale"]):
        return {
            "reply": """**What is a Decision Rationale in EDRP?**

The **Decision Rationale** is the foundational justification for why a strategic choice is being made. It captures:
- **The Core Problem**: The business challenge or opportunity being addressed.
- **Expected Value / ROI**: Financial impact, cost savings, or efficiency gains.
- **Strategic Alignment**: How this decision aligns with organizational goals.
- **Urgency & Context**: Why this decision must be made now and what happens if no action is taken.

*Tip: A well-defined rationale speeds up reviewer approval and provides valuable context during future Decision Replays.*
""",
            "suggested_actions": ["How do I evaluate alternatives?", "Explain the approval workflow", "How does Decision Replay work?"],
            "source": "EDRP AI Assistant"
        }

    # --- 2. Alternative Matrix, Feasibility & Risk ---
    if any(k in q for k in ["alternative", "feasibility", "risk level", "pros and cons", "matrix", "recommended option"]):
        return {
            "reply": """**How the Alternative Evaluation Matrix Works:**

When submitting a decision, EDRP requires comparative analysis across alternatives:

1. **Feasibility Score (1–10)**:
   - Evaluates technical capability, time constraints, resource readiness, and complexity.
   - *10 = Extremely Easy / High Confidence; 1 = High Complexity / Low Feasibility.*
2. **Estimated Cost / Budget**:
   - Direct and indirect financial investment required for this option.
3. **Risk Level (Low / Medium / High)**:
   - Assessment of potential downsides, security exposure, or operational disruption.
4. **Pros & Cons**:
   - Clear bullet points outlining the competitive advantages vs trade-offs.
5. **Recommended Flag**:
   - Mark the proposed option as **'Recommended'** to guide the approval chain.
""",
            "suggested_actions": ["How do I create a new decision?", "Explain the approval workflow", "How does Decision Replay work?"],
            "source": "EDRP AI Assistant"
        }

    # --- 3. Approval Workflow, Reviewers, Rejection & Revision ---
    if any(k in q for k in ["can i edit", "edit decision", "modify decision", "update after submit", "change after submit"]):
        return {
            "reply": """**Can I Edit a Decision After It Has Been Submitted?**

- **Once Submitted**: Decisions are **locked from direct editing** while active in the review pipeline to maintain audit integrity.
- **If Changes are Needed**:
  - A Reviewer or Manager can select **'Request Revision'** (or **'Send Back'**).
  - This returns the decision to **Draft** status.
  - You can update title, rationale, alternatives, or attachments and click **'Resubmit'**.
  - Resubmission automatically generates a new version snapshot (**`v2`**) with a documented change reason.
""",
            "suggested_actions": ["Explain the approval workflow", "How does Decision Replay work?", "Where do I find my pending reviews?"],
            "source": "EDRP AI Assistant"
        }

    if any(k in q for k in ["reject", "rejected", "why rejected", "rejection reason"]):
        return {
            "reply": """**What Happens When a Decision is Rejected?**

1. **Mandatory Feedback**: When a Reviewer or Manager rejects a decision, they are required to submit an **explanatory rejection note**.
2. **Notification**: The decision creator receives an immediate in-app and email notification containing the rejection comments.
3. **Resubmission**:
   - The creator can review the feedback, adjust the rationale or alternatives, and click **'Resubmit for Review'**.
   - This moves the decision back into review as Version `v2`.
4. **Audit Trail**: Both the initial rejection and subsequent resubmission are permanently recorded in the immutable Audit Log.
""",
            "suggested_actions": ["Explain the approval workflow", "How do I create a revision?", "How to view audit logs?"],
            "source": "EDRP AI Assistant"
        }

    if any(k in q for k in ["approval", "approve", "review workflow", "sequential", "chain", "tier", "stages", "pending review"]):
        return {
            "reply": """**EDRP Multi-Tier Approval Workflow:**

Decisions progress through sequential review stages:

1. **Stage 1 — Domain Reviewer (RW)**:
   - Evaluates feasibility, technical merit, pros/cons, and risks.
   - Can choose: ✅ **Approve**, ❌ **Reject**, or 🔄 **Request Revision**.
2. **Stage 2 — Department Manager (MN)**:
   - Reviews resource allocation, team budget, and strategic priorities.
3. **Stage 3 — Administrator (AD)**:
   - Final sign-off, enterprise compliance verification, and organization-wide archiving.
4. **Automated Status Progression**:
   - `Draft` → `In Review` (Stage 1) → `In Review` (Stage 2) → `Approved` / `Rejected`.
""",
            "suggested_actions": ["Where do I find my pending reviews?", "Can I edit a submitted decision?", "How does Decision Replay work?"],
            "source": "EDRP AI Assistant"
        }

    if any(k in q for k in ["pending review", "reviewer workspace", "my reviews", "where to review", "assigned to me"]):
        return {
            "reply": """**Where to Find Your Pending Reviews:**

1. Navigate to **'Reviewer Workspace'** or **'Pending Approvals'** in the left sidebar.
2. Here you will see all decisions waiting for your evaluation.
3. Click **'Review Decision'** to inspect the rationale, financial impact, and alternatives.
4. Enter your evaluation notes and submit your decision (**Approve**, **Reject**, or **Request Revision**).
""",
            "suggested_actions": ["Explain the approval workflow", "What happens when a decision is rejected?", "How does Decision Replay work?"],
            "source": "EDRP AI Assistant"
        }

    # --- 4. Decision Replay & Versioning ---
    if any(k in q for k in ["replay", "version", "history", "snapshot", "timeline", "v1", "v2", "playback"]):
        return {
            "reply": """**How Decision Replay & Versioning Works:**

- **Automatic Snapshotting**: Every major event (Submission, Revision, Reviewer Evaluation, Approval) creates an immutable point-in-time snapshot (`v1`, `v2`, `v3`).
- **Interactive Visual Playback**:
  1. Navigate to **'Replays'** in the sidebar.
  2. Select any decision to launch the interactive replay viewer.
  3. Use the timeline slider to view the exact state of the decision at any moment in time:
     - Initial problem statement & estimated budget.
     - Alternative matrix scores.
     - Reviewer comments, votes, and timestamps.
- **Use Cases**: Ideal for onboarding new executives, post-mortem reviews, and regulatory compliance audits.
""",
            "suggested_actions": ["How do I view Audit Logs?", "How do I create a new decision?", "Explain the approval workflow"],
            "source": "EDRP AI Assistant"
        }

    # --- 5. Roles & RBAC ---
    if any(k in q for k in ["role", "roles", "permission", "permissions", "rbac", "employee id", "prefix", "administrator vs", "admin and manager", "manager and reviewer"]):
        return {
            "reply": """**EDRP Role-Based Access Control (RBAC):**

| Role | Prefix | Responsibilities & Access |
|---|:---:|---|
| **Administrator** | `AD-xxx` | Full platform control, user verification, audit log review, global settings, ticket administration. |
| **Manager** | `MN-xxx` | Team decision reviews, departmental analytics, assigning reviewers, second-tier approvals. |
| **Reviewer** | `RW-xxx` | Domain evaluations, alternative scoring, approving/rejecting assigned decisions, revision requests. |
| **Employee** | `EMP-xxx` | Creating decisions, drafting alternatives, participating in discussion threads, viewing approved records. |
""",
            "suggested_actions": ["How do I reset my password?", "How do I create a new decision?", "Explain the approval workflow"],
            "source": "EDRP AI Assistant"
        }

    # --- 6. Audit Logs, Diff Engine & Compliance ---
    if any(k in q for k in ["audit", "audit log", "audit logs", "diff engine", "diffs", "compliance", "append-only", "tamper", "export csv"]):
        return {
            "reply": """**Enterprise Audit Logging & Field-Level Diff Engine:**

- **Append-Only Immutability**: PostgreSQL database triggers physically reject any `UPDATE` or `DELETE` queries on the `audit_logs` table, ensuring an unalterable compliance record.
- **Field-Level Diff Engine**: Records exact before-and-after values for all modified fields:
  ```json
  {
    "status": {"before": "Draft", "after": "In Review"},
    "financial_impact": {"before": 50000, "after": 65000}
  }
  ```
- **Metadata Recorded**: User ID, Full Name, Role, IP Address, User-Agent, Action, and Timestamp.
- **Export**: Administrators can click **'Export CSV'** in the Audit Logs page for SOC 2 / ISO 27001 compliance reviews.
""",
            "suggested_actions": ["Who can view Audit Logs?", "How does Decision Replay work?", "Explain the approval workflow"],
            "source": "EDRP AI Assistant"
        }

    # --- 7. Password Reset, OTP, Login & Account ---
    if any(k in q for k in ["password", "reset password", "forgot password", "otp", "login issue", "change password", "profile"]):
        return {
            "reply": """**Password Reset & Account Security:**

1. **If You Are Logged In**:
   - Go to **'Profile'** or **'Settings'** in the sidebar.
   - Enter your current password and specify a new secure password.
2. **If You Forgot Your Password**:
   - On the Login screen, click **'Forgot Password?'**.
   - Enter your corporate email address to receive a **6-Digit OTP code** via email.
   - Enter the OTP code within 10 minutes and choose a new password.
3. **Remember Me**:
   - Selecting **'Remember Me'** on login preserves your authenticated session for **72 hours**.
""",
            "suggested_actions": ["How does OTP verification work?", "What are the roles in EDRP?", "How do I contact support?"],
            "source": "EDRP AI Assistant"
        }

    # --- 8. Email & Notifications ---
    if any(k in q for k in ["notification", "notifications", "email alert", "email notification", "smtp", "badge", "unread"]):
        return {
            "reply": """**How Notifications & Email Alerts Work in EDRP:**

- **Automatic Event Triggers**: Notifications are dispatched immediately for:
  - **Review Assignment**: Reviewers receive an email and in-app alert when a decision requires their evaluation.
  - **Decision Status Changes**: Submitter is notified when their decision is **Approved**, **Rejected**, or **Revision Requested**.
  - **New Comments**: Participants in a decision thread receive alerts on new discussion replies.
  - **Support Updates**: Support ticket confirmations and administrator responses are emailed via SMTP.
- **In-App Notification Bell**:
  - Located in the top-right header, displaying unread count badges in real-time.
  - Click any notification to navigate directly to the relevant decision or ticket.
""",
            "suggested_actions": ["Explain the approval workflow", "How do I create a new decision?", "How do I contact support?"],
            "source": "EDRP AI Assistant"
        }

    # --- 9. File Uploads & Documents ---
    if any(k in q for k in ["file", "upload", "attachment", "document", "pdf", "docx", "pptx", "size limit", "format"]):
        return {
            "reply": """**File Attachment Guidelines:**

- **Supported Formats**: PDF (`.pdf`), Microsoft Word (`.docx`), PowerPoint (`.pptx`), CSV (`.csv`), and Images (`.png`, `.jpg`).
- **Maximum File Size**: Up to **200 MB** per uploaded attachment.
- **Security**: Uploaded documents undergo MIME-type validation and are linked securely to the decision record with role-based access.
""",
            "suggested_actions": ["How do I create a new decision?", "Explain the approval workflow", "How to submit a ticket?"],
            "source": "EDRP AI Assistant"
        }

    # --- 10. Discussions & Collaboration ---
    if any(k in q for k in ["discuss", "comment", "discussion", "mention", "reply to comment", "stakeholder"]):
        return {
            "reply": """**Decision Discussions & Collaboration:**

- **Discussion Threads**: Every decision detail page includes a live **Discussion Thread** where creators, reviewers, and stakeholders can ask clarifying questions.
- **Mentions & Notifications**: Posting a comment sends an immediate in-app and email notification to the decision creator and assigned reviewers.
- **Audit Persistence**: All discussion comments are timestamped and preserved in the decision history and replay timeline.
""",
            "suggested_actions": ["How do I create a new decision?", "Explain the approval workflow", "How does Decision Replay work?"],
            "source": "EDRP AI Assistant"
        }

    # --- 11. Reports & Analytics ---
    if any(k in q for k in ["report", "analytics", "chart", "export report", "excel", "metrics", "dashboard"]):
        return {
            "reply": """**Reports & Decision Analytics:**

- **Dashboard Visualizations**: View monthly decision volume, approval vs rejection rates, department comparisons, and average SLA review duration.
- **Export Capabilities**: Export decision summaries, review evaluation matrices, and audit logs to **PDF** or **Excel / CSV** format.
- **Department Metrics**: Compare decision velocity across Engineering, Operations, Finance, and Product teams.
""",
            "suggested_actions": ["How do I view Audit Logs?", "How do I create a new decision?", "Explain the approval workflow"],
            "source": "EDRP AI Assistant"
        }

    # --- 12. Teams & Departments ---
    if any(k in q for k in ["team", "department", "invite", "add member", "organization"]):
        return {
            "reply": """**Team & Department Management:**

- **Departments**: Decisions are categorized by department (e.g., Engineering, Finance, Operations, Product, Legal).
- **Manager Visibility**: Managers have direct visibility into decisions submitted by members within their department or assigned team.
- **Administrator Role Assignment**: Administrators can configure user teams, designations, and role permissions from the **User Management** console.
""",
            "suggested_actions": ["What are the roles in EDRP?", "How do I create a new decision?", "Explain the approval workflow"],
            "source": "EDRP AI Assistant"
        }

    # --- 11. Support Tickets & Contact ---
    if any(k in q for k in ["ticket", "contact", "support email", "office hours", "phone", "helpdesk"]):
        return {
            "reply": """**Need Assistance or Encountered a Bug?**

- **Submit a Ticket**: Click **'Create Ticket'** or **'Report an Issue'** in the top action cards.
- **Track Status**: Monitor your requests under **'Previous Requests'** (`Open`, `In Progress`, `Resolved`).
- **Enterprise Contact Details**:
  - **Email**: `support@edrp-platform.com`
  - **Company**: `contact@edrp.org`
  - **Support Hours**: Mon - Fri, 9:00 AM - 6:00 PM EST
""",
            "suggested_actions": ["How do I reset my password?", "How do I create a new decision?", "Explain the approval workflow"],
            "source": "EDRP AI Assistant"
        }

    # --- 12. Theme & Accessibility ---
    if any(k in q for k in ["dark mode", "theme", "light mode", "accessibility", "color"]):
        return {
            "reply": """**Theme & Accessibility Options:**

- **Theme Toggle**: Navigate to **'Profile'** or use the top navbar to toggle between **Light Mode** and **Dark Mode**.
- **System Default**: Automatically matches your operating system preference.
- **High Contrast**: Enhanced contrast mode is available in Profile Settings for accessibility compliance.
""",
            "suggested_actions": ["How do I update my profile?", "How do I reset my password?", "How do I create a decision?"],
            "source": "EDRP AI Assistant"
        }

    # --- 13. Dynamic Fallback: Parse specific user keywords to build a tailored answer ---
    tailored_reply = _build_dynamic_tailored_reply(clean_msg, user_name)
    return {
        "reply": tailored_reply,
        "suggested_actions": _derive_custom_suggestions(clean_msg),
        "source": "EDRP AI Assistant"
    }


def _build_dynamic_tailored_reply(query: str, user_name: str) -> str:
    """
    Constructs a customized, direct answer analyzing the user's specific question phrasing.
    """
    clean = query.strip()
    words = re.findall(r'\b\w+\b', clean.lower())
    
    # Extract question subject
    subject_snippet = clean
    if len(clean) > 80:
        subject_snippet = clean[:80] + "..."

    response_parts = [
        f"Regarding your query about **\"{subject_snippet}\"**:\n"
    ]

    # Provide targeted guidance based on recognized entities
    if "decision" in words:
        response_parts.append("• **Decisions**: All strategic decisions in EDRP follow a structured lifecycle: `Draft` → `In Review` → `Approved` / `Rejected`. You can create decisions from the sidebar wizard, attach alternative matrices, and submit them for multi-stage review.")
    
    if any(w in words for w in ["review", "reviewer", "approval", "approve"]):
        response_parts.append("• **Reviews & Approvals**: Assigned reviewers evaluate feasibility scores, budget impact, and risk levels. They can Approve, Reject with mandatory notes, or Request Revision back to draft.")

    if any(w in words for w in ["replay", "history", "version"]):
        response_parts.append("• **Replay & History**: Point-in-time snapshots (`v1`, `v2`) allow complete visual playback of the decision timeline, reviewer scores, and discussions.")

    if any(w in words for w in ["audit", "log", "security", "diff"]):
        response_parts.append("• **Audit Logs**: Append-only database triggers ensure immutable logging of all state changes, capturing before/after JSON diffs, actor details, and client IP addresses.")

    if any(w in words for w in ["user", "account", "password", "login", "otp", "role"]):
        response_parts.append("• **User Accounts & Security**: Roles (Admin, Manager, Reviewer, Employee) control access. Password resets use 6-digit email OTP verification, and 'Remember Me' maintains sessions for 72 hours.")

    if len(response_parts) == 1:
        # General response if no specific keyword triggered
        response_parts.append(f"In the **Expert Decision Replay Platform**, you can manage decisions, coordinate multi-stage approvals, track append-only audit diffs, and inspect version replays.\n\nTo help you with this, you can:\n1. Check the relevant section in the **Sidebar Navigation**.\n2. Click **'Create Ticket'** above to submit a specific support request to our engineering team.\n3. Or ask me a more specific question about decision creation, workflows, or account settings!")

    return "\n\n".join(response_parts)


def _derive_custom_suggestions(query: str) -> List[str]:
    q = query.lower()
    if any(k in q for k in ["create", "draft", "new", "rationale"]):
        return ["What is an Alternative Analysis?", "Explain the approval workflow", "Can I edit a submitted decision?"]
    if any(k in q for k in ["approve", "reject", "review", "workflow", "revision"]):
        return ["Where do I find my pending reviews?", "What happens when a decision is rejected?", "How does Decision Replay work?"]
    if any(k in q for k in ["replay", "version", "history", "v1", "v2"]):
        return ["How do I view Audit Logs?", "How do I create a new decision?", "Explain the approval workflow"]
    if any(k in q for k in ["audit", "diff", "compliance", "security"]):
        return ["How do I export audit logs?", "Who can view Audit Logs?", "Explain the approval workflow"]
    if any(k in q for k in ["password", "otp", "login", "account", "role"]):
        return ["How does OTP verification work?", "What are the roles in EDRP?", "How do I create a support ticket?"]
    return ["How do I create a new decision?", "Explain the approval workflow", "How does Decision Replay work?", "How do I reset my password?"]
