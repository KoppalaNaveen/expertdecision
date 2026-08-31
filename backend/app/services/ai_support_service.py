# -*- coding: utf-8 -*-
import os
import json
import urllib.request
import urllib.error
import re
from typing import Dict, Any, List, Optional, Tuple

try:
    from dotenv import load_dotenv
    _curr_dir = os.path.dirname(os.path.abspath(__file__))
    _backend_env = os.path.join(_curr_dir, "..", "..", ".env")
    _root_env = os.path.join(_curr_dir, "..", "..", "..", ".env")
    if os.path.exists(_backend_env):
        load_dotenv(_backend_env)
    if os.path.exists(_root_env):
        load_dotenv(_root_env)
    load_dotenv()
except Exception:
    pass

EDRP_SYSTEM_PROMPT = """You are the EDRP AI Assistant, the intelligent copilot for the Expert Decision Replay Platform (EDRP).
EDRP is an enterprise-grade platform for creating, evaluating, reviewing, approving, replaying, restoring, and auditing critical strategic business decisions.

=== Core Platform Knowledge & Workflows ===
1. User Roles & Access Hierarchy:
   - Administrator (AD-xxxx): Platform governance, user verification, system configuration, final approval sign-off, master audit logs, support ticket management.
   - Manager (MN-xxxx): Departmental team oversight, budget and resource allocation review, Stage 2 approval authority, department analytics.
   - Reviewer (RW-xxxx): Domain expert evaluation, alternative scoring (feasibility, cost, risk, pros/cons), Stage 1 approval/rejection/revision requests.
   - Employee (EMP-xxxx): Proposing new strategic decisions, drafting alternatives, participating in decision discussion threads, viewing approved records.

2. Step-by-Step Decision Creation Process (UI Navigation & Fields):
   - Step 1: Click "Create Decision" in the sidebar navigation (or navigate to /create-decision).
   - Step 2: Primary Information:
     * Title: Clear, descriptive name (e.g., "Select Cloud Infrastructure Provider for EDRP").
     * Problem Statement / Rationale: Detailed problem context, operational challenges, and business justification.
     * Category: Technology, Finance, Operations, Human Resources, Infrastructure, Legal, Security, etc.
     * Department: Target organizational department (Engineering, IT, Finance, Operations, Product, HR).
     * Priority / Urgency: Low, Medium, High, or Critical.
     * Stakeholders: Impacted teams or key individuals.
     * Financial Impact / Budget: Estimated total cost/investment in dollars ($).
   - Step 3: Alternative Evaluation Matrix (Must evaluate at least 1 alternative, recommended 2+):
     * Alternative Title & Detailed Description.
     * Pros & Cons: Itemized benefits vs operational trade-offs.
     * Estimated Cost ($): Direct and indirect implementation cost.
     * Feasibility Score (1-10): Technical readiness and practicality rating (10 = highest feasibility).
     * Risk Level: Low, Medium, High, or Critical.
     * Recommended Option: Mark one option as "Recommended".
   - Step 4: Attachments: Optional supporting documents (PDF, DOCX, PPTX, CSV, PNG up to 200MB).
   - Step 5: Save as "Draft" (with auto-save) or click "Submit Decision" to transition to "In Review" and trigger the approval chain.

3. Multi-Tier Sequential Approval Workflow:
   - Lifecycle: Draft → In Review (Stage 1: Reviewer) → In Review (Stage 2: Manager) → In Review (Stage 3: Administrator) → Approved / Rejected / Revision Requested → Archived.
   - Reviewer Actions:
     * Approve: Endorses the decision and advances it to the next tier or final approval.
     * Reject: Denies the decision with mandatory explanatory feedback.
     * Request Revision: Returns decision to Draft status with revision notes, allowing author to update and resubmit as Version v2.

4. Decision Replay, Version History & Version Restore:
   - Timeline Slider: Visual chronological reconstruction of decision lifecycle (initial draft, reviewer scores, comments, status changes).
   - Version Snapshotting: Every major event (Submission, Revision, Review, Restore) creates an immutable version snapshot (v1, v2, v3, etc.).
   - Version Restore Feature:
     * Purpose: Enables authorized users to roll back an accidental edit or restore an earlier evaluated consensus (e.g. Version 1) without losing history.
     * Lineage & Attribution: Restoring a version generates a new version state (e.g., v3 restored from v1) and records the actor's User Name, User ID, and Role (e.g., "Restored from Version 1 by Koppala Naveen (ID: 1, Administrator)").
     * Where to View: The restored version details are displayed in:
       1. Decision Overview Page (Status banner, current version tag, and restoration notice).
       2. Version History Modal (Full version timeline with user name, user ID, role, and diff comparison).
       3. Immutable Audit Logs Table (Before/after JSON diffs).

5. Knowledge Repository & RAG Intelligence:
   - Central repository of approved strategic decisions, evaluated alternatives, cost histories, and feasibility scores.
   - Cross-Department Analysis: Query decisions by department, compare alternatives and budgets, and review historical reviewer conclusions.

6. Append-Only Audit Logs & Security:
   - PostgreSQL/SQLite immutable append-only audit trail capturing every state change, field-level before/after JSON diffs, timestamps, user IDs, roles, and client IP addresses.
   - Exportable to CSV / PDF for SOC 2 and ISO 27001 compliance.

7. Communication, Email & Notifications:
   - Internal Notification Engine: Real-time top navbar bell alerts with unread badge count for review assignments, status changes, and mentions.
   - Email Service (/email): Role-based recipient filtering (@mention by name or ID), Gmail and SMTP delivery options, message editing, and resending.

8. Support Center & SLA Guarantees:
   - AI Support Assistant (Standard Helpdesk & Knowledge Repo AI modes).
   - Formal Support Tickets (SUP-xxxx) with priority SLAs (1-Hour Resolution for Urgent requests).

=== Response Guidelines ===
- Always provide accurate, clear, and professional plain-text answers.
- Do NOT use markdown decorative syntax such as asterisks (** or *), blockquotes (> ❝), backticks (`), hashtags (###), emojis, or markdown pipe tables (|---|).
- Format all replies in clean, natural, professional plain text with standard paragraphs and simple clean bullet points (-).
- When asked to create, draft, write, or generate problem statements or alternatives, generate rich, professional enterprise content ready to use.
"""

KNOWLEDGE_REPOSITORY_SYSTEM_PROMPT = """You are the EDRP Knowledge Repository AI Assistant for the Expert Decision Replay Platform.
Your mission is to answer user questions strictly grounded in the institutional knowledge repository records, approved decisions, evaluated alternatives, cost estimates, feasibility metrics, and historical reviewer conclusions provided in the [Knowledge Repository Context].

When answering:
1. Ground your response in the actual institutional decision records (e.g. DEC-45, DEC-12, etc.).
2. Detail the exact problem statements, approved budgets/costs, evaluated alternatives with Pros/Cons and feasibility scores, and reviewer conclusions.
3. Do NOT use markdown decorative syntax such as asterisks (** or *), blockquotes (> ❝), backticks, hashtags (###), emojis, or markdown pipe tables.
4. Structure your reply in clean, readable plain text with standard paragraphs and clean bullet points (-).
"""

def _clean_ai_output_text(text: str) -> str:
    """
    Cleans raw AI generated output so it looks like a normal, natural, professional human response:
    - Strips quote brackets and decorative blockquotes (> ❝, ❞, etc.)
    - Strips asterisks (**, *), underscores (__), and backticks (`)
    - Strips markdown heading hashes (###, ####, etc.)
    - Strips decorative emojis
    - Converts markdown table syntax into clean, readable text lines
    - Preserves clean paragraphs and standard bullet points (-)
    """
    if not text:
        return ""
    
    lines = text.splitlines()
    cleaned_lines = []
    
    in_table = False
    
    for line in lines:
        raw = line.strip()
        
        # Check if line is a markdown table separator (e.g. |---|:---:|)
        if re.match(r'^[\|\s\:\-]+$', raw) and raw.count('|') >= 2:
            in_table = True
            continue
            
        # Check if line is a markdown table row (e.g. | Option | Cost | ...)
        if raw.startswith('|') and raw.endswith('|'):
            cells = [c.strip() for c in raw.strip('|').split('|')]
            clean_cells = []
            for c in cells:
                c_clean = re.sub(r'[*_`#~❝❞"\'\>]+', '', c).strip()
                c_clean = re.sub(r'[\U00010000-\U0010ffff\u2600-\u27ff\u2300-\u23ff\u2b50\u2b55\ufe0f]', '', c_clean).strip()
                clean_cells.append(c_clean)
            
            if not in_table and any(h in clean_cells[0].lower() for h in ["option", "title", "metric", "item"]):
                in_table = True
                continue
            else:
                if len(clean_cells) >= 4:
                    opt_title = clean_cells[0]
                    cost = clean_cells[1] if len(clean_cells) > 1 else ""
                    score = clean_cells[2] if len(clean_cells) > 2 else ""
                    risk = clean_cells[3] if len(clean_cells) > 3 else ""
                    rec = clean_cells[4] if len(clean_cells) > 4 else ""
                    
                    row_text = f"Option {opt_title}" if not opt_title.lower().startswith("option") else opt_title
                    if rec and "rec" in rec.lower():
                        row_text += " [Recommended]"
                    row_text += f"\n- Estimated Cost: {cost} | Feasibility: {score} | Risk Level: {risk}"
                    cleaned_lines.append(row_text)
                    continue
                else:
                    cleaned_lines.append(" - ".join(c for c in clean_cells if c))
                    continue

        in_table = False
        
        # Remove blockquotes > ❝ or > or ❝ or ❞
        raw = re.sub(r'^[ \t]*>[ \t]*[❝“"\']?[ \t]*', '', raw)
        raw = raw.replace("❝", "").replace("❞", "").replace("“", "\"").replace("”", "\"")
        
        # Remove header hashes (###, ####, ##, #)
        raw = re.sub(r'^[ \t]*#{1,6}[ \t]*', '', raw)
        
        # Remove decorative emojis
        raw = re.sub(r'[\U00010000-\U0010ffff\u2600-\u27ff\u2300-\u23ff\u2b50\u2b55\ufe0f]', '', raw)
        
        # Remove bold / italics asterisks and underscores (**word**, *word*, etc.)
        raw = re.sub(r'\*\*(.*?)\*\*', r'\1', raw)
        raw = re.sub(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', r'\1', raw)
        raw = re.sub(r'\_\_(.*?)\_\_', r'\1', raw)
        
        # Remove backticks (`code`)
        raw = re.sub(r'`([^`]+)`', r'\1', raw)
        
        # Replace special dot separators '·' with '|'
        raw = raw.replace('·', '|')
        
        # Normalize bullet points (* Item -> - Item, • Item -> - Item)
        raw = re.sub(r'^[ \t]*[\*•][ \t]+', '- ', raw)
        raw = re.sub(r'^[ \t]*\*[ \t]*\*[ \t]*', '- ', raw)
        
        # Strip extra whitespace
        raw = re.sub(r'[ \t]+', ' ', raw).strip()
        
        cleaned_lines.append(raw)

    result = "\n".join(cleaned_lines)
    result = re.sub(r'\n{3,}', '\n\n', result).strip()
    return result

def generate_ai_response(
    user_message: str,
    user_name: str = "User",
    user_id: Optional[int] = None,
    conversation_history: List[dict] = None,
    page_context: Optional[str] = None,
    page_title: Optional[str] = None,
    page_url: Optional[str] = None,
    mode: Optional[str] = "standard",
    use_knowledge_repository: Optional[bool] = False
) -> Dict[str, Any]:
    res = _generate_ai_response_internal(
        user_message=user_message,
        user_name=user_name,
        user_id=user_id,
        conversation_history=conversation_history,
        page_context=page_context,
        page_title=page_title,
        page_url=page_url,
        mode=mode,
        use_knowledge_repository=use_knowledge_repository
    )
    if res and isinstance(res, dict) and "reply" in res:
        res["reply"] = _clean_ai_output_text(res["reply"])
    return res

def _generate_ai_response_internal(
    user_message: str,
    user_name: str = "User",
    user_id: Optional[int] = None,
    conversation_history: List[dict] = None,
    page_context: Optional[str] = None,
    page_title: Optional[str] = None,
    page_url: Optional[str] = None,
    mode: Optional[str] = "standard",
    use_knowledge_repository: Optional[bool] = False
) -> Dict[str, Any]:
    """
    Generates an intelligent AI response for the EDRP Support Center.
    Supports Standard Platform Helpdesk Mode and Knowledge Repository RAG Mode.
    Queries real platform database records (RAG), attempts live LLM APIs (Gemini, OpenAI, Groq, Claude, OpenRouter),
    and falls back to the high-precision EDRP Knowledge Engine.
    """
    clean_msg = (user_message or "").strip()
    is_kr_mode = use_knowledge_repository or (mode == "knowledge_repository") or any(
        k in clean_msg.lower() for k in [
            "knowledge repository", "knowledge repo", "approved decision", "approved decisions",
            "decisions were approved", "decisions that were approved", "decisions approved",
            "repository details", "from the repository", "past decisions", "previous decisions",
            "in the repository", "technology budget", "search repository", "compare past decisions",
            "what decisions was approved", "what decisions are approved"
        ]
    )

    if not clean_msg:
        if is_kr_mode:
            greeting_text = f"Hello {user_name}! I am your **EDRP Knowledge Repository AI Assistant**.\n\nI can answer questions grounded in our institutional repository of approved decisions, alternative evaluations, budgets, and historical decision replays. What would you like to search or analyze?"
            suggested = [
                "Search Technology & Cloud decisions",
                "What decisions were approved in Finance & Operations?",
                "Compare alternatives and costs across past decisions",
                "Summarize risk mitigations from Knowledge Repository"
            ]
        else:
            greeting_text = f"Hello {user_name}! I am your EDRP AI Assistant."
            if page_title:
                greeting_text += f" I see you are on **{page_title}**."
            greeting_text += " How can I assist you with this page or any platform and decision queries?"
            suggested = ["Explain this page", "How do I create a decision?", "Show my decisions", "Explain approval workflow"]

        return {
            "reply": greeting_text,
            "suggested_actions": suggested,
            "source": "EDRP Knowledge Repository AI" if is_kr_mode else "EDRP AI Assistant",
            "is_knowledge_repository": is_kr_mode
        }

    # 1. Retrieve Real Database Context (Decisions, Alternatives, Reviews)
    db_context = _retrieve_database_context(clean_msg, user_id, page_url, page_title)

    # 1b. Inject Live Page Context (Screen user is actively viewing)
    if page_context or page_title or page_url:
        page_info_lines = ["[Active Screen Context]"]
        if page_title:
            page_info_lines.append(f"Screen Title: {page_title}")
        if page_url:
            page_info_lines.append(f"Current URL: {page_url}")
        if page_context:
            page_info_lines.append(f"Visible Content on Page:\n{page_context.strip()[:3500]}")
        page_context_str = "\n".join(page_info_lines)
        if db_context.get('summary_text'):
            db_context['summary_text'] = f"{page_context_str}\n\n{db_context['summary_text']}"
        else:
            db_context['summary_text'] = page_context_str

    # 1c. If in Knowledge Repository Mode, prioritize Knowledge Repository Engine
    if is_kr_mode:
        kr_response = _answer_knowledge_repository_query(clean_msg, user_name, db_context, force_mode=True)
        if kr_response is not None:
            return kr_response

    # 2. Check if this is a direct Decision Data Query (e.g. "what problem did i add for...", "my decisions", "status of DEC-28")
    data_response = _answer_decision_data_query(clean_msg, user_name, db_context)
    if data_response is not None:
        return data_response

    # 2b. Direct Decision Component Generator for specific decision title & category
    q_lower = clean_msg.lower()
    is_generative_request = (
        any(w in q_lower for w in ["generate", "create", "draft", "suggest", "auto-generate", "write", "propose", "recommend"]) and
        any(w in q_lower for w in ["description", "problem statement", "rationale", "alternative", "options", "risk", "kpi", "metric", "decision for", "formulate", "titled", "category", "department"])
    )
    if is_generative_request:
        title_m = re.search(r"titled\s+['\"]([^'\"]+)['\"]", clean_msg, re.IGNORECASE)
        cat_m = re.search(r"category\s+['\"]([^'\"]+)['\"]", clean_msg, re.IGNORECASE)
        dept_m = re.search(r"department\s+['\"]([^'\"]+)['\"]", clean_msg, re.IGNORECASE)
        target_title = title_m.group(1).strip() if title_m else ""
        if not target_title:
            t_match = re.search(r"(?:for|titled)\s+['\"]?([^'\"\n\r,]+)['\"]?", clean_msg, re.IGNORECASE)
            if t_match and len(t_match.group(1).strip()) > 2:
                target_title = t_match.group(1).strip()
        target_cat = cat_m.group(1).strip() if cat_m else "General"
        target_dept = dept_m.group(1).strip() if dept_m else "Operations"

        if target_title:
            intent_type = "description"
            if any(w in q_lower for w in ["description", "problem statement", "rationale", "context"]):
                intent_type = "description"
            elif any(w in q_lower for w in ["alternative", "option"]):
                intent_type = "alternatives"
            elif any(w in q_lower for w in ["risk", "challenge", "friction"]):
                intent_type = "risks"
            elif any(w in q_lower for w in ["kpi", "metric", "success"]):
                intent_type = "kpis"
            elif any(w in q_lower for w in ["full proposal", "complete formulation", "all sections"]):
                intent_type = "full"

            gen_paragraph = _generate_tailored_decision_description(target_title, target_cat, target_dept, intent_type=intent_type)
            return {
                "reply": gen_paragraph,
                "suggested_actions": ["Evaluate alternatives", "Check feasibility score", "View approval workflow"],
                "source": "EDRP Decision AI"
            }

    # 2c. Check if the query is unrelated to EDRP / Decision Governance
    if not _is_edrp_related_query(clean_msg, db_context):
        return _handle_unrelated_query(clean_msg, user_name)

    # 3. Live Groq API (with RAG Context Injection)
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        resp = _call_groq_api(clean_msg, user_name, db_context, conversation_history, groq_key)
        if resp:
            return resp

    # 4. Live Google Gemini API (with RAG Context Injection)
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key:
        resp = _call_gemini_api(clean_msg, user_name, db_context, conversation_history, gemini_key)
        if resp:
            return resp

    # 5. Live OpenAI API (with RAG Context Injection)
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        resp = _call_openai_api(clean_msg, user_name, db_context, conversation_history, openai_key)
        if resp:
            return resp

    # 6. Live Official xAI Grok API
    xai_key = os.getenv("XAI_API_KEY") or (os.getenv("GROK_API_KEY") if not os.getenv("GROK_API_KEY", "").startswith("gsk_") else None)
    if xai_key:
        resp = _call_xai_grok_api(clean_msg, user_name, db_context, conversation_history, xai_key)
        if resp:
            return resp

    # 7. Free Grok API Wrapper (https://github.com/realasfngl/Grok-Api)
    grok_api_url = os.getenv("GROK_API_URL") or (os.getenv("USE_FREE_GROK", "").lower() == "true" and "http://localhost:6969/ask")
    if grok_api_url:
        resp = _call_free_grok_wrapper_api(clean_msg, user_name, db_context, conversation_history, str(grok_api_url))
        if resp:
            return resp

    # 8. Live Anthropic Claude API
    claude_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    if claude_key:
        resp = _call_anthropic_api(clean_msg, user_name, db_context, conversation_history, claude_key)
        if resp:
            return resp

    # 9. Live OpenRouter API
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if openrouter_key:
        resp = _call_openrouter_api(clean_msg, user_name, db_context, conversation_history, openrouter_key)
        if resp:
            return resp

    # 10. High-Precision EDRP Knowledge Engine fallback
    return _answer_with_knowledge_engine(clean_msg, user_name, db_context)


def _call_gemini_api(clean_msg: str, user_name: str, db_context: Dict[str, Any], conversation_history: Optional[List[dict]], api_key: str) -> Optional[Dict[str, Any]]:
    """Calls Google Gemini API with RAG context."""
    models_to_try = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-pro"]
    rag_context = db_context.get('summary_text', '').strip()
    system_ctx = f"{EDRP_SYSTEM_PROMPT}\n\n[Database Context]:\n{rag_context}" if rag_context else EDRP_SYSTEM_PROMPT
    
    contents = []
    if conversation_history:
        for turn in conversation_history[-6:]:
            role = "user" if turn.get("role") == "user" else "model"
            content = turn.get("content", "")
            if content:
                contents.append({"role": role, "parts": [{"text": content}]})
    
    user_part = f"{system_ctx}\n\nUser ({user_name}) asks: {clean_msg}"
    contents.append({"role": "user", "parts": [{"text": user_part}]})

    for model in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": contents,
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 800
                }
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "EDRP-App/1.0"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            return {
                                "reply": parts[0]["text"].strip(),
                                "suggested_actions": _derive_custom_suggestions(clean_msg, db_context),
                                "source": f"Google Gemini AI ({model})"
                            }
        except Exception as e:
            print(f"[AI SUPPORT GEMINI {model}] Note: {e}")
    return None


def _call_free_grok_wrapper_api(clean_msg: str, user_name: str, db_context: Dict[str, Any], conversation_history: Optional[List[dict]], endpoint_url: str) -> Optional[Dict[str, Any]]:
    """
    Calls the local or remote Free Grok API server wrapper (https://github.com/realasfngl/Grok-Api).
    Default endpoint: http://localhost:6969/ask
    """
    rag_context = db_context.get('summary_text', '').strip()
    system_ctx = f"{EDRP_SYSTEM_PROMPT}\n\n[Database Context]:\n{rag_context}" if rag_context else EDRP_SYSTEM_PROMPT
    model = os.getenv("GROK_MODEL", "grok-3-fast")
    proxy = os.getenv("GROK_PROXY", None)

    # Format full context into message for Grok wrapper
    history_lines = []
    if conversation_history:
        for turn in conversation_history[-4:]:
            role = "User" if turn.get("role") == "user" else "AI Assistant"
            c = turn.get("content", "")
            if c:
                history_lines.append(f"{role}: {c}")
    
    history_block = f"\n\n[Recent Conversation History]:\n" + "\n".join(history_lines) if history_lines else ""
    full_message = f"{system_ctx}{history_block}\n\nUser Question ({user_name}): {clean_msg}"

    try:
        payload = {
            "message": full_message,
            "model": model,
            "proxy": proxy,
            "extra_data": None
        }
        req = urllib.request.Request(
            endpoint_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "EDRP-App/1.0"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                reply_text = data.get("response") or data.get("reply")
                if reply_text:
                    return {
                        "reply": str(reply_text).strip(),
                        "suggested_actions": _derive_custom_suggestions(clean_msg, db_context),
                        "source": f"Free Grok AI ({model})"
                    }
    except Exception as e:
        print(f"[AI SUPPORT FREE GROK WRAPPER] Note: {e}")
    return None


def _call_xai_grok_api(clean_msg: str, user_name: str, db_context: Dict[str, Any], conversation_history: Optional[List[dict]], api_key: str) -> Optional[Dict[str, Any]]:
    """Calls official xAI Grok API (https://api.x.ai/v1/chat/completions)."""
    rag_context = db_context.get('summary_text', '').strip()
    system_ctx = f"{EDRP_SYSTEM_PROMPT}\n\n[Database Context]:\n{rag_context}" if rag_context else EDRP_SYSTEM_PROMPT

    messages = [{"role": "system", "content": system_ctx}]
    if conversation_history:
        for turn in conversation_history[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if content and role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": f"{user_name}: {clean_msg}"})

    models = ["grok-2-latest", "grok-beta", "grok-2-vision-1212"]
    for model in models:
        try:
            url = "https://api.x.ai/v1/chat/completions"
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 800
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "EDRP-App/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        return {
                            "reply": choices[0]["message"].get("content", "").strip(),
                            "suggested_actions": _derive_custom_suggestions(clean_msg, db_context),
                            "source": f"xAI Grok ({model})"
                        }
        except Exception as e:
            print(f"[AI SUPPORT XAI GROK {model}] Note: {e}")
    return None


def _call_openai_api(clean_msg: str, user_name: str, db_context: Dict[str, Any], conversation_history: Optional[List[dict]], api_key: str) -> Optional[Dict[str, Any]]:
    """Calls OpenAI API with RAG context."""
    rag_context = db_context.get('summary_text', '').strip()
    system_ctx = f"{EDRP_SYSTEM_PROMPT}\n\n[Database Context]:\n{rag_context}" if rag_context else EDRP_SYSTEM_PROMPT

    messages = [{"role": "system", "content": system_ctx}]
    if conversation_history:
        for turn in conversation_history[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if content and role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": f"{user_name}: {clean_msg}"})

    models = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
    for model in models:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 800
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "EDRP-App/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        return {
                            "reply": choices[0]["message"].get("content", "").strip(),
                            "suggested_actions": _derive_custom_suggestions(clean_msg, db_context),
                            "source": f"OpenAI ({model})"
                        }
        except Exception as e:
            print(f"[AI SUPPORT OPENAI {model}] Note: {e}")
    return None


def _call_groq_api(clean_msg: str, user_name: str, db_context: Dict[str, Any], conversation_history: Optional[List[dict]], api_key: str) -> Optional[Dict[str, Any]]:
    """Calls Groq Cloud API with RAG context."""
    rag_context = db_context.get('summary_text', '').strip()
    system_ctx = f"{EDRP_SYSTEM_PROMPT}\n\n[Database Context]:\n{rag_context}" if rag_context else EDRP_SYSTEM_PROMPT

    messages = [{"role": "system", "content": system_ctx}]
    if conversation_history:
        for turn in conversation_history[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if content and role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": f"{user_name}: {clean_msg}"})

    models = ["qwen/qwen3.8-27b", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "qwen/qwen3.6-27b", "groq/compound-mini"]
    for model in models:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            payload = {
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 1200
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key.strip()}",
                    "User-Agent": "EDRP-App/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    choices = data.get("choices", [])
                    if choices and "message" in choices[0]:
                        raw_content = choices[0]["message"].get("content", "").strip()
                        if "<think>" in raw_content and "</think>" in raw_content:
                            raw_content = re.sub(r"<think>.*?</think>", "", raw_content, flags=re.DOTALL).strip()
                        elif "</think>" in raw_content:
                            raw_content = raw_content.split("</think>")[-1].strip()
                        
                        if raw_content:
                            return {
                                "reply": raw_content,
                                "suggested_actions": _derive_custom_suggestions(clean_msg, db_context),
                                "source": f"Groq ({model.split('/')[-1]})"
                            }
        except Exception as e:
            print(f"[AI SUPPORT GROQ {model}] Note: {e}")
    return None


def _call_anthropic_api(clean_msg: str, user_name: str, db_context: Dict[str, Any], conversation_history: Optional[List[dict]], api_key: str) -> Optional[Dict[str, Any]]:
    """Calls Anthropic Claude API."""
    rag_context = db_context.get('summary_text', '').strip()
    system_ctx = f"{EDRP_SYSTEM_PROMPT}\n\n[Database Context]:\n{rag_context}" if rag_context else EDRP_SYSTEM_PROMPT

    messages = []
    if conversation_history:
        for turn in conversation_history[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if content and role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": f"{user_name}: {clean_msg}"})

    models = ["claude-3-5-haiku-20241022", "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"]
    for model in models:
        try:
            url = "https://api.anthropic.com/v1/messages"
            payload = {
                "model": model,
                "system": system_ctx,
                "messages": messages,
                "max_tokens": 800
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "User-Agent": "EDRP-App/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    content_parts = data.get("content", [])
                    if content_parts and "text" in content_parts[0]:
                        return {
                            "reply": content_parts[0]["text"].strip(),
                            "suggested_actions": _derive_custom_suggestions(clean_msg, db_context),
                            "source": f"Anthropic Claude ({model})"
                        }
        except Exception as e:
            print(f"[AI SUPPORT CLAUDE {model}] Note: {e}")
    return None


def _call_openrouter_api(clean_msg: str, user_name: str, db_context: Dict[str, Any], conversation_history: Optional[List[dict]], api_key: str) -> Optional[Dict[str, Any]]:
    """Calls OpenRouter API."""
    rag_context = db_context.get('summary_text', '').strip()
    system_ctx = f"{EDRP_SYSTEM_PROMPT}\n\n[Database Context]:\n{rag_context}" if rag_context else EDRP_SYSTEM_PROMPT

    messages = [{"role": "system", "content": system_ctx}]
    if conversation_history:
        for turn in conversation_history[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if content and role in ["user", "assistant"]:
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": f"{user_name}: {clean_msg}"})

    try:
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": "meta-llama/llama-3.3-70b-instruct:free",
            "messages": messages,
            "max_tokens": 800
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "User-Agent": "EDRP-App/1.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices and "message" in choices[0]:
                    return {
                        "reply": choices[0]["message"].get("content", "").strip(),
                        "suggested_actions": _derive_custom_suggestions(clean_msg, db_context),
                        "source": "OpenRouter AI"
                    }
    except Exception as e:
        print(f"[AI SUPPORT OPENROUTER] Note: {e}")
    return None


def _retrieve_database_context(query: str, user_id: Optional[int] = None, page_url: Optional[str] = None, page_title: Optional[str] = None) -> Dict[str, Any]:
    # Queries the database for decisions, alternatives, and reviews matching the query, active URL, or user.
    context = {
        "matched_decisions": [],
        "user_decisions": [],
        "summary_text": "",
        "current_decision": None
    }

    try:
        from app.database.connection import SessionLocal
        from app.models.decision import Decision
        from app.models.alternative import Alternative
        from app.models.review import Review
        from app.models.user import User

        db = SessionLocal()
        all_decisions = db.query(Decision).all()

        # Stop words to filter out during tokenization
        stop_words = {
            'what', 'problem', 'did', 'i', 'add', 'for', 'this', 'title', 'is', 'the',
            'a', 'an', 'in', 'of', 'to', 'my', 'decision', 'about', 'show', 'me', 'details',
            'tell', 'give', 'how', 'when', 'why', 'who', 'where', 'which', 'we', 'are', 'was',
            'summarize', 'summary', 'page', 'current', 'explain'
        }

        search_blob = f"{query} {page_url or ''} {page_title or ''}"
        q_clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', query.lower())
        q_tokens = [w for w in q_clean.split() if w not in stop_words and len(w) > 1]

        # Check explicit ID match (e.g. DEC-28, #28, 28, /decision/27)
        id_match = re.search(r'\b(?:dec[-_ /]?|/decision/)?(\d+)\b', search_blob, re.IGNORECASE)
        explicit_id = int(id_match.group(1)) if id_match else None

        scored_decisions = []
        for d in all_decisions:
            alts = db.query(Alternative).filter(Alternative.decision_id == d.id).all()
            reviews = db.query(Review).filter(Review.decision_id == d.id).all()
            creator = db.query(User).filter(User.id == d.created_by).first()

            alts_titles = [a.title for a in alts]
            alts_text = " ".join([f"{a.title} {a.description or ''} {a.pros or ''} {a.cons or ''}" for a in alts]).lower()
            d_text = f"{d.title} {d.description} {d.department or ''} {d.tags or ''} {alts_text}".lower()

            score = 0
            if explicit_id and d.id == explicit_id:
                score += 100

            for t in q_tokens:
                if t in d.title.lower():
                    score += 8
                elif t in d.description.lower():
                    score += 4
                elif t in alts_text:
                    score += 4
                elif t in d_text:
                    score += 2

            d_info = {
                "id": d.id,
                "title": d.title,
                "description": d.description,
                "status": d.status or "Pending",
                "department": d.department or "General",
                "priority_level": d.priority_level or "Medium",
                "created_by": d.created_by,
                "creator_name": creator.full_name if creator else "Enterprise User",
                "created_at": d.created_at.strftime("%b %d, %Y") if d.created_at else "Recently",
                "alternatives": [
                    {
                        "title": a.title,
                        "description": a.description or "",
                        "cost": float(a.cost) if a.cost is not None else 0.0,
                        "feasibility_score": a.feasibility_score or 0,
                        "risk_level": a.risk_level or "Low",
                        "pros": a.pros or "",
                        "cons": a.cons or ""
                    }
                    for a in alts
                ],
                "reviews": [
                    {
                        "reviewer_id": r.reviewer_id,
                        "status": r.status,
                        "comments": r.comments or "No comments provided"
                    }
                    for r in reviews
                ]
            }

            if user_id and d.created_by == user_id:
                context["user_decisions"].append(d_info)

            if explicit_id and d.id == explicit_id:
                context["current_decision"] = d_info

            if score > 0:
                scored_decisions.append((score, d_info))

        scored_decisions.sort(key=lambda x: x[0], reverse=True)
        context["matched_decisions"] = [x[1] for x in scored_decisions]
        context["all_repository_decisions"] = [
            {
                "id": d.id,
                "title": d.title,
                "description": d.description,
                "status": d.status or "Pending",
                "department": d.department or "General",
                "priority_level": d.priority_level or "Medium",
                "created_by": d.created_by,
                "creator_name": "Enterprise User",
                "created_at": d.created_at.strftime("%b %d, %Y") if d.created_at else "Recently",
                "alternatives": [
                    {
                        "title": a.title,
                        "description": a.description or "",
                        "cost": float(a.cost) if a.cost is not None else 0.0,
                        "feasibility_score": a.feasibility_score or 0,
                        "risk_level": a.risk_level or "Low",
                        "pros": a.pros or "",
                        "cons": a.cons or ""
                    }
                    for a in db.query(Alternative).filter(Alternative.decision_id == d.id).all()
                ]
            }
            for d in all_decisions
        ]

        # Ensure current decision is at the very top of matched_decisions
        if context.get("current_decision") and (not context["matched_decisions"] or context["matched_decisions"][0]["id"] != context["current_decision"]["id"]):
            context["matched_decisions"].insert(0, context["current_decision"])

        # Build concise summary text for LLM RAG
        lines = []
        for d in context["matched_decisions"][:4]:
            alts_str = ", ".join([f"{a['title']} (${a['cost']}, Feasibility: {a['feasibility_score']}/10, Risk: {a['risk_level']})" for a in d['alternatives']])
            lines.append(f"- Decision DEC-{d['id']} ('{d['title']}'): Status={d['status']}, Creator={d['creator_name']}, Problem/Rationale=\"{d['description']}\", Alternatives=[{alts_str}]")
        context["summary_text"] = "\n".join(lines)

        db.close()
    except Exception as e:
        print(f"[AI RAG RETRIEVAL] Note: {e}")

    return context


def _answer_knowledge_repository_query(query: str, user_name: str, db_context: Dict[str, Any], force_mode: bool = False) -> Optional[Dict[str, Any]]:
    # Synthesizes and answers queries grounded exclusively in Knowledge Repository records
    # (Approved & institutional strategic decisions, alternatives, feasibility scores, and cost data).
    q = query.lower().strip()
    all_decisions = db_context.get("all_repository_decisions", []) or db_context.get("matched_decisions", [])
    matched = db_context.get("matched_decisions", [])

    targets = matched if matched else all_decisions

    if not targets:
        return {
            "reply": "### 📚 Knowledge Repository Overview\n\nNo decision records are currently found in the Knowledge Repository. Once strategic decisions are reviewed and approved through the platform's multi-stage review workflow (Reviewer -> Manager -> Administrator), they are automatically indexed into the repository for historical lookup, cross-department comparison, and AI-assisted analytics.",
            "suggested_actions": ["How to create a decision", "Explain approval workflow", "View Knowledge Repository"],
            "source": "EDRP Knowledge Repository AI",
            "is_knowledge_repository": True
        }

    # Detect specific question intents
    is_cost_inquiry = any(w in q for w in ["cost", "budget", "cheapest", "expensive", "investment", "price", "how much", "$"])
    is_risk_inquiry = any(w in q for w in ["risk", "mitigation", "safety", "hazard", "threat", "downside"])
    is_general_list = any(w in q for w in ["what is in", "show all", "list all", "all decisions", "what decisions", "browse", "available in", "what do we have", "index", "overview"]) or len(q.split()) <= 2

    reply_lines = []
    reply_lines.append("### 📚 Knowledge Repository Verified Intelligence\n")

    # If asking for a specific decision or top matching decision
    if not is_general_list and matched:
        top_d = matched[0]
        status_tag = f"**[{top_d['status']}]**" if top_d['status'] == "Approved" else f"*({top_d['status']})*"
        
        reply_lines.append(f"#### 📌 **DEC-{top_d['id']}: {top_d['title']}** {status_tag}")
        reply_lines.append(f"- **Department**: `{top_d.get('department', 'General')}` · **Priority Level**: `{top_d.get('priority_level', 'Medium')}`")
        reply_lines.append(f"- **Problem Statement / Rationale**:\n> ❝ *{top_d.get('description', 'No rationale documented.')}* ❞\n")
        
        alts = top_d.get('alternatives', [])
        if alts:
            reply_lines.append(f"**Comparative Alternatives Matrix ({len(alts)} Evaluated Options):**\n")
            reply_lines.append("| Alternative Title | Estimated Cost | Feasibility | Risk Level |")
            reply_lines.append("|---|:---:|:---:|:---:|")
            for a in alts:
                cost_str = f"${a['cost']:,.2f}" if a.get('cost') is not None and a.get('cost') > 0 else "N/A"
                feas_str = f"{a['feasibility_score']}/10" if a.get('feasibility_score') else "N/A"
                risk_str = a.get('risk_level', 'Low')
                reply_lines.append(f"| **{a['title']}** | `{cost_str}` | `{feas_str}` | `{risk_str}` |")
            
            reply_lines.append("\n**Detailed Pros & Cons Breakdown:**")
            for idx, a in enumerate(alts, 1):
                p_text = a.get('pros', '').strip() or 'None documented'
                c_text = a.get('cons', '').strip() or 'None documented'
                reply_lines.append(f"- **Option {idx} ({a['title']})**:")
                reply_lines.append(f"  * **Pros**: {p_text}")
                reply_lines.append(f"  * **Cons**: {c_text}")

        reply_lines.append(f"\n👉 **[Open Complete Record & Replay for DEC-{top_d['id']}](/decisions/{top_d['id']})**\n")

        # If there are additional related decisions in the repository, list them concisely
        if len(matched) > 1:
            reply_lines.append("##### 📁 Other Related Decisions in Repository:")
            for d in matched[1:4]:
                s_tag = f"[{d['status']}]" if d['status'] == "Approved" else f"({d['status']})"
                reply_lines.append(f"- **DEC-{d['id']}: {d['title']}** {s_tag} &mdash; Department: {d.get('department', 'General')} · [View](/decisions/{d['id']})")
    else:
        # General list / department overview
        reply_lines.append(f"Here is the summary of strategic decision records indexed across organizational departments:\n")
        reply_lines.append("| Decision ID | Title | Department | Status | Alternatives |")
        reply_lines.append("|:---:|---|---|:---:|:---:|")
        for d in targets[:6]:
            s_tag = f"**{d['status']}**" if d['status'] == "Approved" else d['status']
            alt_cnt = f"{len(d.get('alternatives', []))} options"
            reply_lines.append(f"| `DEC-{d['id']}` | **[{d['title']}](/decisions/{d['id']})** | {d.get('department', 'General')} | {s_tag} | {alt_cnt} |")
        
        reply_lines.append("\n💡 *Tip: Click any decision link or ask specific questions like 'What are the alternatives for DEC-45?' for full metrics and cost diffs.*")

    top_id = targets[0]['id'] if targets else 1
    suggested = [
        f"What are the alternatives for DEC-{top_id}?",
        "What decisions were approved for Technology Budget?",
        "Compare past decision costs",
        "Open Knowledge Repository"
    ]

    return {
        "reply": "\n".join(reply_lines),
        "suggested_actions": suggested,
        "source": "EDRP Knowledge Repository AI",
        "is_knowledge_repository": True
    }


def _answer_decision_data_query(query: str, user_name: str, db_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # Detects if the user is asking about specific decisions, problem statements,
    # alternatives, statuses, or their own decision list, and generates direct data-driven replies.
    q = query.lower().strip()
    matched = db_context.get("matched_decisions", [])
    user_decisions = db_context.get("user_decisions", [])

    # If the user is asking the AI to generate, create, draft, or suggest something new, bypass lookup
    is_generative_intent = any(g in q for g in [
        "create and generate", "generate a", "generate new", "create a new", "create new",
        "write a", "write new", "draft a", "draft new", "suggest a", "suggest new",
        "help me write", "help me create", "help me draft", "brainstorm", "formulate",
        "give me a problem", "generate problem", "write problem", "create problem",
        "suggest problem", "generate alternative", "suggest alternative", "create alternative",
        "write alternative", "propose a", "propose new", "compose a", "compose new",
        "how should i write", "how should i formulate", "recommend alternatives", "generate for the decision",
        "create for the decision", "make a problem statement", "give a problem statement"
    ])
    if is_generative_intent:
        return None

    # 1. Problem Statement / Description Inquiry (Look up existing database records)
    is_problem_inquiry = any(k in q for k in [
        "what problem did i add", "what problem is added", "problem did i add",
        "description did i add", "what did i add for", "what rationale did i",
        "why did i create", "what did i write for", "tell me the problem i wrote",
        "show problem statement for dec", "problem statement of dec-", "problem statement for dec-"
    ]) or (any(k in q for k in ["what problem", "what description", "what rationale"]) and any(w in q for w in ["i add", "added", "existing", "dec-", "my decision"]))

    if is_problem_inquiry and matched:
        top_d = matched[0]
        alts_str = ", ".join([f"`{a['title']}`" for a in top_d['alternatives']]) if top_d['alternatives'] else "None specified"
        
        reply_lines = [
            f"Here is the **Problem Statement / Description** added for **\"{top_d['title']}\"** (DEC-{top_d['id']}):\n",
            f"> ❝ **{top_d['description']}** ❞\n",
            f"**Decision Overview:**",
            f"- **Decision ID**: `DEC-{top_d['id']}`",
            f"- **Status**: **{top_d['status']}**",
            f"- **Department**: {top_d['department']} · **Priority**: {top_d['priority_level']}",
            f"- **Created By**: {top_d['creator_name']} on {top_d['created_at']}",
            f"- **Alternatives Evaluated**: {alts_str}"
        ]

        # If there were multiple close matches (e.g. "cloud" and "mitigation" matching 2 different decisions)
        if len(matched) > 1 and matched[1]['id'] != top_d['id']:
            other_d = matched[1]
            reply_lines.append(f"\n*Related Match — **\"{other_d['title']}\"** (DEC-{other_d['id']}):*")
            reply_lines.append(f"> ❝ {other_d['description']} ❞")

        return {
            "reply": "\n".join(reply_lines),
            "suggested_actions": [
                f"What are the alternatives for DEC-{top_d['id']}?",
                f"What is the status of DEC-{top_d['id']}?",
                "How does Decision Replay work?",
                "Show my decisions"
            ],
            "source": "EDRP Decision Engine"
        }

    # 2. Alternatives Inquiry (e.g. "what are the alternatives for Cloud Provider", "alternatives of DEC-36")
    is_alts_inquiry = any(k in q for k in [
        "what are the alternatives", "alternatives for", "alternatives of", "options for",
        "what alternatives", "cost of", "feasibility of", "risk of"
    ])

    if is_alts_inquiry and matched:
        top_d = matched[0]
        reply_lines = [
            f"**Evaluated Alternatives for \"{top_d['title']}\" (DEC-{top_d['id']}):**\n"
        ]

        if top_d['alternatives']:
            for idx, a in enumerate(top_d['alternatives'], 1):
                reply_lines.append(f"**{idx}. {a['title']}**")
                if a['cost']:
                    reply_lines.append(f"   - **Estimated Cost**: ${a['cost']:,.2f}" if isinstance(a['cost'], (int, float)) else f"   - **Estimated Cost**: {a['cost']}")
                if a['feasibility_score']:
                    reply_lines.append(f"   - **Feasibility Score**: {a['feasibility_score']} / 10")
                if a['risk_level']:
                    reply_lines.append(f"   - **Risk Level**: {a['risk_level']}")
                if a['pros']:
                    reply_lines.append(f"   - **Pros**: {a['pros']}")
                if a['cons']:
                    reply_lines.append(f"   - **Cons**: {a['cons']}")
                reply_lines.append("")
        else:
            reply_lines.append("No alternatives have been documented for this decision yet.")

        return {
            "reply": "\n".join(reply_lines),
            "suggested_actions": [
                f"What is the problem statement for DEC-{top_d['id']}?",
                f"What is the status of DEC-{top_d['id']}?",
                "How does Decision Replay work?"
            ],
            "source": "EDRP Decision Engine"
        }

    # 3. Status / Review Inquiry (e.g. "what is the status of DEC-28", "is cloud decision approved")
    is_status_inquiry = any(k in q for k in [
        "status of", "is it approved", "is my decision approved", "who reviewed", "review status",
        "is it rejected", "pending approval"
    ])

    if is_status_inquiry and matched:
        top_d = matched[0]
        status_badge = "✅ Approved" if top_d['status'].lower() == "approved" else ("⏳ " + top_d['status'])
        reply_lines = [
            f"**Status Information for \"{top_d['title']}\" (DEC-{top_d['id']}):**\n",
            f"- **Current Status**: **{status_badge}**",
            f"- **Department**: {top_d['department']}",
            f"- **Priority**: {top_d['priority_level']}",
            f"- **Submitted by**: {top_d['creator_name']} ({top_d['created_at']})\n"
        ]

        if top_d['reviews']:
            reply_lines.append("**Reviewer Evaluations:**")
            for r in top_d['reviews']:
                reply_lines.append(f"- Status: **{r['status']}** · Feedback: *\"{r['comments']}\"*")

        return {
            "reply": "\n".join(reply_lines),
            "suggested_actions": [
                f"What is the problem statement for DEC-{top_d['id']}?",
                f"What are the alternatives for DEC-{top_d['id']}?",
                "How does Decision Replay work?"
            ],
            "source": "EDRP Decision Engine"
        }

    # 4. User Decisions List (e.g. "what decisions did i create", "show my decisions", "list my decisions")
    is_my_decisions = any(k in q for k in [
        "what decisions did i create", "my decisions", "show my decisions", "list my decisions",
        "decisions i made", "what did i submit"
    ])

    if is_my_decisions:
        target_list = user_decisions if user_decisions else matched
        if target_list:
            reply_lines = [f"**Decisions Found in Your Organization:**\n"]
            for d in target_list[:6]:
                st_icon = "✅" if d['status'].lower() == "approved" else "⏳"
                reply_lines.append(f"- **DEC-{d['id']} — {d['title']}**")
                reply_lines.append(f"  - Status: {st_icon} **{d['status']}** · Dept: {d['department']} · Created: {d['created_at']}")
                reply_lines.append(f"  - *Problem*: \"{d['description'][:80]}...\"" if len(d['description']) > 80 else f"  - *Problem*: \"{d['description']}\"")
                reply_lines.append("")
            
            return {
                "reply": "\n".join(reply_lines),
                "suggested_actions": [
                    "How do I create a new decision?",
                    "Explain the approval workflow",
                    "How does Decision Replay work?"
                ],
                "source": "EDRP Decision Engine"
            }
        else:
            return {
                "reply": "No decisions were found for your user account yet. You can create your first decision by clicking **'Create Decision'** in the sidebar navigation.",
                "suggested_actions": ["How do I create a new decision?", "Explain the approval workflow"],
                "source": "EDRP Decision Engine"
            }

    return None


def _generate_tailored_decision_description(title: str, category: str = "General", department: str = "Operations", intent_type: str = "description") -> str:
    t_clean = (title or "Strategic Business Initiative").strip()
    c_clean = (category or "General").strip()
    d_clean = (department or "Operations").strip()
    t_lower = t_clean.lower()

    if any(w in t_lower for w in ["database", "migration", "postgres", "sql", "data warehouse", "mongodb"]):
        exec_summary = f"This strategic initiative addresses critical scalability, data throughput, and schema integrity constraints in our core database infrastructure for {d_clean}. Migrating to a modern distributed database architecture will eliminate legacy query bottlenecks, implement multi-region automated failover, and ensure 99.99% system availability to support projected enterprise transaction volume growth over the next 24 months."
        friction = "Legacy on-premises database instances are operating at 85%+ CPU utilization during peak hours, causing query latency spikes (>1,200ms) and limiting developer velocity for new microservice deployments."
        risks = "Unscheduled downtime risks during peak traffic periods, data synchronization latency across regions, and compliance exposure if backup snapshots fail recovery SLAs."
        kpis = "Reduce average query latency to <150ms, achieve zero data loss (RPO = 0, RTO < 5 min), and support 3x annual transaction scaling."
        alts = [
            {"title": "Managed PostgreSQL on Cloud (RDS/AlloyDB)", "cost": 42000, "score": 9, "risk": "Low", "pros": "Fully automated backups, seamless vertical/horizontal scaling, native IAM integration.", "cons": "Ongoing cloud compute subscription costs."},
            {"title": "Self-Hosted Distributed Cluster (CockroachDB/Kubernetes)", "cost": 65000, "score": 7, "risk": "Medium", "pros": "Multi-cloud portability, zero vendor lock-in, customizable shard controls.", "cons": "Requires dedicated in-house DevOps maintenance and operational complexity."},
            {"title": "In-Place Vertical Hardware & Schema Optimization", "cost": 15000, "score": 4, "risk": "High", "pros": "Lowest upfront implementation capital.", "cons": "Short-term temporary fix; fails to resolve underlying architectural scalability limits."}
        ]
    elif any(w in t_lower for w in ["cloud", "aws", "azure", "gcp", "hosting", "kubernetes", "infra"]):
        exec_summary = f"This strategic decision establishes the adoption and migration roadmap for {t_clean} within {d_clean}. Transitioning from high-maintenance on-premises infrastructure to a resilient, secure, and auto-scaling cloud environment optimizes compute resource utilization, enhances multi-zone disaster recovery, and reduces total cost of ownership (TCO) by an estimated 28% over 3 years."
        friction = "Aging physical servers require frequent emergency maintenance, have rigid capacity limits that delay application launches by 4-6 weeks, and lack automated disaster recovery failover."
        risks = "Cloud migration egress costs, temporary service cutover friction, and security policy misalignment during initial configuration."
        kpis = "Achieve 99.99% infrastructure uptime, reduce provisioning time from weeks to minutes, and maintain SOC2 Type II compliance."
        alts = [
            {"title": "Multi-Cloud Native Architecture (AWS + GCP)", "cost": 85000, "score": 8, "risk": "Low", "pros": "High redundancy, best-of-breed services, zero vendor lock-in.", "cons": "Higher cross-cloud orchestration complexity."},
            {"title": "Single Cloud Provider Tier-1 Partner (AWS / Azure)", "cost": 55000, "score": 9, "risk": "Low", "pros": "Consolidated enterprise discounts, unified IAM and billing, faster implementation timeline.", "cons": "Moderate vendor lock-in over 3-year term."},
            {"title": "Hybrid Cloud Extension with On-Premises Core", "cost": 40000, "score": 6, "risk": "Medium", "pros": "Preserves existing hardware depreciation assets.", "cons": "Dual operational overhead for maintenance and security patching."}
        ]
    elif any(w in t_lower for w in ["ai", "chatbot", "machine learning", "llm", "automation", "assistant", "copilot"]):
        exec_summary = f"This proposal approves the implementation of {t_clean} to automate repetitive workflows, accelerate decision evaluation turnaround, and enhance stakeholder communication across {d_clean}. Deploying this AI copilot solution is projected to reduce decision cycle duration by 45%, deliver 24/7 grounded guidance, and empower teams to focus on high-leverage strategic initiatives while adhering to enterprise governance."
        friction = "Manual review triage and repetitive query answering consume 15+ hours per week per reviewer, slowing strategic decision turnaround and delaying cross-department projects."
        risks = "Hallucination risks if models are not strictly grounded with RAG, API rate limits, and sensitive data exposure without proper RBAC masking."
        kpis = "Resolve 75% of helpdesk queries instantly, cut approval turnaround time from 7 days to 48 hours, and achieve 95%+ user satisfaction rating."
        alts = [
            {"title": "Enterprise Grounded RAG + Local LLM Fallback", "cost": 25000, "score": 9, "risk": "Low", "pros": "100% database-grounded, zero data leakage, automatic fallback ensures 100% uptime.", "cons": "Requires periodic vector index optimization."},
            {"title": "Third-Party SaaS AI Integration", "cost": 38000, "score": 7, "risk": "Medium", "pros": "Turnkey deployment with minimal setup.", "cons": "External data transit, recurring per-seat licensing, limited custom RBAC controls."},
            {"title": "Rule-Based FAQ Engine", "cost": 5000, "score": 4, "risk": "High", "pros": "Lowest cost.", "cons": "Inflexible, cannot synthesize alternatives or understand natural language queries."}
        ]
    elif any(w in t_lower for w in ["security", "cyber", "firewall", "iam", "zero trust", "vulnerability", "audit"]):
        exec_summary = f"This cybersecurity initiative establishes the deployment framework for {t_clean} to enforce zero-trust security principles, protect sensitive corporate assets, and guarantee regulatory compliance across all {d_clean} endpoints and microservices. Executing this decision hardens platform defenses, eliminates single-point authentication vulnerabilities, and fulfills SOC2 and GDPR mandate requirements."
        friction = "Fragmented legacy access controls and disparate credential stores increase risk of unauthorized lateral movement and complicate compliance auditing."
        risks = "User friction during MFA/SSO rollout, potential temporary service disruption during firewall rule tightening."
        kpis = "100% enforcement of Multi-Factor Authentication, zero unpatched critical CVEs, and automated audit logging with zero tamper tolerance."
        alts = [
            {"title": "Enterprise Zero-Trust IAM & SSO Gateway", "cost": 35000, "score": 9, "risk": "Low", "pros": "Centralized policy enforcement, automated offboarding, seamless SAML/OAuth integration.", "cons": "Initial end-user migration training required."},
            {"title": "Perimeter-Based Firewall & VPN Upgrade", "cost": 22000, "score": 6, "risk": "Medium", "pros": "Familiar architecture for legacy systems.", "cons": "Does not protect against internal lateral threats in modern remote/hybrid environments."},
            {"title": "Manual Periodic Security Audits & Pentesting", "cost": 12000, "score": 4, "risk": "High", "pros": "Low upfront tooling spend.", "cons": "Reactive approach that fails continuous real-time compliance requirements."}
        ]
    elif any(w in t_lower for w in ["budget", "finance", "q4", "q1", "q2", "q3", "capex", "opex", "allocation", "pricing", "cost"]):
        exec_summary = f"This financial governance decision outlines the capital allocation and expenditure framework for {t_clean} within {d_clean}. The strategic objective is to prioritize high-ROI operational requirements, establish clear accountability thresholds, and mitigate fiscal risk while guaranteeing funding for all critical milestones."
        friction = "Uncoordinated departmental spending and variable software licenses lead to 15-20% budget variance and delayed quarterly reconciliation."
        risks = "Cost overruns due to scope creep, currency/inflation fluctuations, and delayed vendor deliverables."
        kpis = "Maintain budget variance within ±3%, achieve 15% procurement cost reduction, and automate monthly audit reconciliations."
        alts = [
            {"title": "Tiered Milestone-Based Budget Allocation", "cost": 50000, "score": 9, "risk": "Low", "pros": "Funds released only upon verified milestone delivery; maximum accountability.", "cons": "Requires active manager sign-offs at each phase."},
            {"title": "Consolidated Upfront Annual CapEx Allocation", "cost": 75000, "score": 7, "risk": "Medium", "pros": "Secures maximum volume vendor discounts.", "cons": "Less flexibility if quarterly priorities shift."},
            {"title": "Ad-Hoc Expense Approval Model", "cost": 60000, "score": 4, "risk": "High", "pros": "Minimal upfront planning.", "cons": "High risk of duplicate spending and poor fiscal governance."}
        ]
    else:
        exec_summary = f"This strategic decision outlines the operational execution plan and business rationale for {t_clean} under the {c_clean} category for {d_clean}. The primary objective is to address operational bottlenecks, establish standardized governance, and align cross-functional workflows with organizational priorities to ensure high-quality delivery, measurable ROI, and minimal business disruption."
        friction = "Current unstructured workflows create operational delays, inconsistent quality standards, and lack clear accountability metrics across cross-functional teams."
        risks = "Resource contention during rollout, resistance to new operational workflows, and initial adjustment curve."
        kpis = "Achieve 99% SLA adherence, decrease project delivery turnaround time by 30%, and establish 100% audit traceability."
        alts = [
            {"title": "Phased Implementation with Automated Tooling", "cost": 30000, "score": 9, "risk": "Low", "pros": "Controlled rollout, minimal operational downtime, rapid user adoption.", "cons": "Requires 2-week transition phase."},
            {"title": "Comprehensive All-at-Once Overhaul", "cost": 45000, "score": 6, "risk": "Medium", "pros": "Instantly eliminates legacy technical debt.", "cons": "Higher initial change management friction."},
            {"title": "Minimal Policy-Only Update", "cost": 8000, "score": 4, "risk": "High", "pros": "Lowest direct expense.", "cons": "Fails to provide automated tooling needed for long-term scalability."}
        ]

    # Return ONLY what was requested
    if intent_type == "description":
        return f"{exec_summary}\n\n{friction}"

    if intent_type == "alternatives":
        lines = [f"Recommended Alternatives for \"{t_clean}\":\n"]
        for idx, alt in enumerate(alts, 1):
            rec_tag = " [Recommended]" if idx == 1 else ""
            lines.append(f"Option {idx}: {alt['title']}{rec_tag}")
            lines.append(f"- Estimated Cost: ${alt['cost']:,} | Feasibility: {alt['score']}/10 | Risk Level: {alt['risk']}")
            lines.append(f"- Pros: {alt['pros']}")
            lines.append(f"- Cons: {alt['cons']}\n")
        return "\n".join(lines).strip()

    if intent_type == "risks":
        return f"Operational Challenges:\n- {friction}\n\nStrategic Risks:\n- {risks}"

    if intent_type == "kpis":
        return f"Target KPIs & Success Criteria:\n- {kpis}"

    # Full formulation
    output_lines = [
        f"Tailored Decision Formulation: \"{t_clean}\"\n",
        f"- Category: {c_clean} | Department: {d_clean} | Target Priority: High\n",
        "1. Executive Problem Statement & Rationale (Ready to paste into EDRP):",
        f"{exec_summary}\n",
        "2. Root Operational Challenges & Friction:",
        f"- {friction}\n",
        "3. Strategic Risks & Business Exposure:",
        f"- {risks}\n",
        "4. Measurable Success Criteria & Target KPIs:",
        f"- {kpis}\n",
        "5. Recommended Alternative Evaluation Options:"
    ]

    for idx, alt in enumerate(alts, 1):
        rec_tag = " [Recommended]" if idx == 1 else ""
        output_lines.append(f"Option {idx}: {alt['title']}{rec_tag}")
        output_lines.append(f"- Estimated Cost: ${alt['cost']:,} | Feasibility: {alt['score']}/10 | Risk Level: {alt['risk']}")
        output_lines.append(f"- Pros: {alt['pros']}")
        output_lines.append(f"- Cons: {alt['cons']}\n")

    output_lines.extend([
        "Next Steps in EDRP:",
        "1. Click 'Create Decision' in the sidebar navigation.",
        "2. Copy and paste the Executive Problem Statement above into the Problem Statement field.",
        "3. Add the 3 evaluated alternatives into the Alternative Evaluation Matrix and click 'Submit Decision' to start the approval review chain."
    ])

    return "\n".join(output_lines)


def _answer_with_knowledge_engine(query: str, user_name: str, db_context: Dict[str, Any]) -> Dict[str, Any]:
    # Built-in EDRP Knowledge Engine that understands all workflows,
    # lifecycle states, approval tiers, audit trails, and troubleshooting steps.
    q = query.lower().strip()

    # --- Direct Decision Component Generation for specific title ---
    is_generative_req = (
        any(w in q for w in ["generate", "create", "draft", "write", "suggest", "auto-generate", "propose", "recommend"]) and
        any(w in q for w in ["description", "problem statement", "rationale", "alternative", "options", "risk", "kpi", "metric", "decision titled", "for decision", "formulate"])
    )
    if is_generative_req:
        title_m = re.search(r"titled\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
        cat_m = re.search(r"category\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
        dept_m = re.search(r"department\s+['\"]([^'\"]+)['\"]", query, re.IGNORECASE)
        
        target_title = title_m.group(1).strip() if title_m else ""
        if not target_title:
            t_match = re.search(r"(?:for|titled)\s+['\"]?([^'\"\n\r,]+)['\"]?", query, re.IGNORECASE)
            if t_match and len(t_match.group(1).strip()) > 2:
                target_title = t_match.group(1).strip()

        target_cat = cat_m.group(1).strip() if cat_m else "General"
        target_dept = dept_m.group(1).strip() if dept_m else "Operations"

        if target_title:
            intent_type = "description"
            if any(w in q for w in ["description", "problem statement", "rationale", "context"]):
                intent_type = "description"
            elif any(w in q for w in ["alternative", "option"]):
                intent_type = "alternatives"
            elif any(w in q for w in ["risk", "challenge", "friction"]):
                intent_type = "risks"
            elif any(w in q for w in ["kpi", "metric", "success"]):
                intent_type = "kpis"
            elif any(w in q for w in ["full proposal", "complete formulation", "all sections"]):
                intent_type = "full"

            gen_paragraph = _generate_tailored_decision_description(target_title, target_cat, target_dept, intent_type=intent_type)
            return {
                "reply": gen_paragraph,
                "suggested_actions": ["Evaluate alternatives", "Check feasibility score", "View approval workflow"],
                "source": "EDRP Decision AI"
            }

    # --- Greetings & Casual Chat ---
    if q in ["hi", "hello", "hey", "good morning", "good afternoon", "good evening", "greetings", "help"]:
        return {
            "reply": f"Hello **{user_name}**! I am your **EDRP AI Support Assistant**.\n\nI can help you look up decisions, problem statements, alternatives, reviewer approval chains, version replay, and audit diffs.\n\nWhat would you like assistance with today?",
            "suggested_actions": ["How do I create a new decision?", "Explain the approval workflow", "Show my decisions", "How do I reset my password?"],
            "source": "EDRP AI Assistant"
        }

    if any(k in q for k in ["thank", "thanks", "appreciate", "helpful"]):
        return {
            "reply": f"You're very welcome, **{user_name}**! Let me know if you need anything else regarding decision tracking, approvals, or reports.",
            "suggested_actions": ["How do I export reports?", "How to view audit logs?", "Explain approval workflow"],
            "source": "EDRP AI Assistant"
        }

    if any(k in q for k in ["who are you", "what is your name", "what can you do", "what are you"]):
        return {
            "reply": (
                "I am the **EDRP AI Support Assistant**, designed to provide real-time guidance and data lookups on the **Expert Decision Replay Platform**.\n\n"
                "**What I Can Do:**\n"
                "- Look up your **actual decisions, problem statements, and alternative matrices**.\n"
                "- Query approved strategic decisions and alternatives in the **Knowledge Repository**.\n"
                "- Guide you through **creating decisions** and structuring evaluations.\n"
                "- Explain **multi-tier approval chains** (Reviewer -> Manager -> Administrator).\n"
                "- Explain **Decision Replay**, version snapshotting (`v1`, `v2`), and timeline diffs.\n"
                "- Clarify **append-only audit logs**, field-level diffs, and compliance exports."
            ),
            "suggested_actions": ["How do I create a new decision?", "Explain the approval workflow", "Show my decisions"],
            "source": "EDRP AI Assistant"
        }

    # --- Page Guide & Summarize Current Page ---
    is_page_inquiry = any(k in q for k in [
        "explain this page", "summarize the current page", "summarize this page",
        "summarize the present page", "summarize page", "summarize",
        "what can i do here", "page guide", "what is this page", "what actions can i perform",
        "give full detailed", "full details of this page"
    ])
    if is_page_inquiry:
        summary_raw = db_context.get('summary_text', '')
        screen_title = "EDRP Platform"
        current_url = ""
        visible_text = ""

        if "[Active Screen Context]" in summary_raw:
            for line in summary_raw.splitlines():
                if line.startswith("Screen Title:"):
                    screen_title = line.replace("Screen Title:", "").strip()
                elif line.startswith("Current URL:"):
                    current_url = line.replace("Current URL:", "").strip()
            
            if "Visible Content on Page:" in summary_raw:
                visible_text = summary_raw.split("Visible Content on Page:")[-1].strip()

        # Check if we have an active Decision loaded from DB or URL
        current_dec = db_context.get("current_decision")
        
        is_dashboard = (
            "dashboard" in screen_title.lower() or 
            "dashboard" in current_url.lower() or 
            current_url in ["/", "/index", "/dashboard", "/admin-dashboard", "/manager-dashboard", "/reviewer-dashboard"] or
            "administrator dashboard" in screen_title.lower() or
            "manager dashboard" in screen_title.lower() or
            "reviewer dashboard" in screen_title.lower() or
            "employee dashboard" in screen_title.lower()
        )

        is_decision_details = (
            not is_dashboard and
            (
                "/decision/" in current_url.lower() or
                bool(re.search(r'\bdec-\d+\b', screen_title.lower())) or
                (current_dec and not any(p in current_url.lower() for p in ["/dashboard", "/teams", "/users", "/audit", "/reviews", "/repository", "/roles", "/email", "/replays", "/alternatives", "/support"]))
            )
        )

        # ── Case A: Dashboard (Administrator, Manager, Reviewer, Employee) ──
        if is_dashboard:
            reply_lines = [
                f"### 📊 Executive Overview: **{screen_title}**\n",
                f"The **{screen_title}** serves as your centralized command center in the Expert Decision Replay Platform (EDRP) for real-time decision governance, organizational analytics, and system monitoring.\n",
                "#### 📈 Key Visible Components & Operational Metrics:"
            ]
            if visible_text:
                # Clean and append visible metrics
                clean_visible = visible_text.replace("Executive Decision Summary:", "").strip()
                reply_lines.append(f"{clean_visible[:900]}\n")
            else:
                reply_lines.extend([
                    "- **Total Users & Active Sessions**: Real-time count of registered members and active platform sessions.",
                    "- **Decision Volume & Approvals**: Total platform decisions, categorized by Approved, In Review, and Rejected.",
                    "- **Organization Analytics**: Visual decision submission velocity, approval flow rates, and SLA turnaround.",
                    "- **System Health & Audit Activity**: System uptime and immutable audit log activity counters.\n"
                ])

            reply_lines.extend([
                "#### ⚡ Key Actions You Can Perform Here:",
                "1. **Propose Strategic Decisions**: Click **'Create Decision'** in the sidebar to start formulating a new decision with alternative matrices.",
                "2. **Monitor Approval Flows**: Review real-time approval rates and identify bottlenecks across Reviewer, Manager, and Admin tiers.",
                "3. **Inspect Governance & Audit Logs**: Navigate to **Audit Logs** to view immutable before/after diffs and event timestamps.",
                "4. **User & Team Management**: Access **User Management** and **Teams** to configure role permissions and department assignments.",
                "5. **Decision Replay & Knowledge Base**: Open **Replays** or **Knowledge Repository** to examine decision timelines and past consensus records."
            ])

            return {
                "reply": "\n".join(reply_lines),
                "suggested_actions": [
                    "How do I create a new decision?",
                    "Explain the 3-tier approval workflow",
                    "How do I view Audit Logs?",
                    "Search Knowledge Repository"
                ],
                "source": "EDRP AI Assistant"
            }

        # ── Case B: Decision Details Page Full Breakdown ──
        if is_decision_details:
            d = current_dec if current_dec else (db_context["matched_decisions"][0] if db_context.get("matched_decisions") else None)
            if not d:
                # Parse structured fields from live screen context
                dec_id_match = re.search(r'(?:dec[-_ ]?|/decision/)(\d+)', f"{current_url} {screen_title}", re.IGNORECASE)
                dec_id_str = dec_id_match.group(1) if dec_id_match else "Current"
                
                status_m = re.search(r'Status:\s*([^\n\r]+)', visible_text, re.IGNORECASE)
                status_val = status_m.group(1).strip() if status_m else "Under Review"

                desc_m = re.search(r'(?:Problem Context[^\n]*|Problem Context|Rationale):\s*\n*"?([^"\n\r]+(?:\n(?!(?:Owner|Category|Evaluated Alternatives|Approval Governance Chain):)[^\n\r]+)*)"?', visible_text, re.IGNORECASE)
                desc_val = desc_m.group(1).strip() if desc_m else "Strategic organizational decision."

                owner_m = re.search(r'Owner:\s*([^\n\r\|]+)', visible_text)
                owner_val = owner_m.group(1).strip() if owner_m else user_name

                cat_m = re.search(r'Category:\s*([^\n\r\|]+)', visible_text)
                cat_val = cat_m.group(1).strip() if cat_m else "General"

                impact_m = re.search(r'Impact Level:\s*([^\n\r\|]+)', visible_text)
                impact_val = impact_m.group(1).strip() if impact_m else "High Impact"

                # Parse alternatives from visible text
                parsed_alts = []
                for line in visible_text.splitlines():
                    if line.strip().startswith("- Alternative") or "Evaluated Alternatives:" in line or ("Alignment:" in line and "Cost:" in line):
                        parsed_alts.append({
                            "title": line.replace("-", "").strip(),
                            "cost": 0,
                            "feasibility_score": 0,
                            "risk_level": "Evaluated",
                            "pros": "",
                            "cons": ""
                        })

                d = {
                    "id": dec_id_str,
                    "title": screen_title.replace("Decision:", "").strip() or f"DEC-{dec_id_str}",
                    "status": status_val,
                    "description": desc_val,
                    "department": cat_val,
                    "priority_level": impact_val,
                    "creator_name": owner_val,
                    "created_at": "Active",
                    "alternatives": parsed_alts,
                    "reviews": []
                }

            if d:
                status_raw = d.get('status', 'Pending')
                status_icon = "✅" if status_raw.lower() == "approved" else ("⏳" if status_raw.lower() in ["pending", "under review"] else "⚠️")
                
                reply_lines = [
                    f"### 📑 Executive Decision Summary: **{d['title']}** (`DEC-{d['id']}`)\n",
                    f"- **Current Status**: {status_icon} **{status_raw}**",
                    f"- **Category & Department**: {d.get('department', 'General')} · Priority: **{d.get('priority_level', 'Medium')}**",
                    f"- **Owner & Timeline**: Submitted by **{d.get('creator_name', 'User')}** ({d.get('created_at', 'Recently')})\n",
                    "#### 🎯 Problem Statement & Strategic Context:",
                    f"> \"{d.get('description', 'No detailed description specified.')}\"\n"
                ]

                # Alternatives evaluation breakdown
                alts = d.get('alternatives', [])
                if alts:
                    reply_lines.append(f"#### ⚖️ Evaluated Alternatives ({len(alts)} Considered):")
                    for idx, a in enumerate(alts, 1):
                        cost_str = f"${a['cost']:,.2f}" if isinstance(a['cost'], (int, float)) and a['cost'] > 0 else "Budget TBD"
                        score_str = f"{a['feasibility_score']}/10" if a.get('feasibility_score') else "N/A"
                        risk_str = a.get('risk_level', 'Medium')
                        pros_str = f" · *Pros*: {a['pros']}" if a.get('pros') else ""
                        cons_str = f" · *Cons*: {a['cons']}" if a.get('cons') else ""
                        rec_tag = " ⭐ **[Recommended Option]**" if idx == 1 else ""
                        
                        reply_lines.append(f"{idx}. **{a['title']}**{rec_tag}")
                        reply_lines.append(f"   - **Estimated Cost**: `{cost_str}` | **Feasibility Score**: `{score_str}` | **Risk Level**: `{risk_str}`")
                        if a.get('description'):
                            reply_lines.append(f"   - *Details*: {a['description']}")
                        if pros_str or cons_str:
                            reply_lines.append(f"   - {pros_str}{cons_str}")
                    reply_lines.append("")

                # Approval Chain breakdown
                reviews = d.get('reviews', [])
                reply_lines.append("#### 🛡️ Approval Governance & Review Stages:")
                if reviews:
                    for r in reviews:
                        r_status = r.get('status', 'Pending')
                        r_icon = "✅" if r_status.lower() == "approved" else ("❌" if r_status.lower() == "rejected" else "⏳")
                        r_comm = r.get('comments', 'No comments provided')
                        reply_lines.append(f"- {r_icon} Review Stage: **{r_status}** · Reviewer Feedback: *\"{r_comm}\"*")
                else:
                    reply_lines.append("- ⏳ **Review Stage**: Currently under multi-stage review. Awaiting evaluations from assigned Reviewers and Managers.")
                reply_lines.append("")

                # Actionable Next Steps
                reply_lines.extend([
                    "#### ⚡ Key Actions You Can Take on this Page:",
                    "- **Evaluate & Vote**: If you are an assigned Reviewer/Manager, click **Accept** or **Reject** to log your formal decision record.",
                    "- **Edit & Refine**: Click **Edit** to modify the problem rationale, adjust financial budgets, or upload attachments.",
                    "- **Add Options**: Click **Add Option** to include new evaluated alternative technologies or vendors.",
                    "- **Send Reminder**: Click **Send Reminder** to ping pending reviewers with in-app email notifications.",
                    "- **Decision Replay**: Open **Version History** to inspect chronological snapshot diffs and audit logs."
                ])

                return {
                    "reply": "\n".join(reply_lines),
                    "suggested_actions": [
                        f"What is the status of DEC-{d['id']}?",
                        f"What are the alternatives for DEC-{d['id']}?",
                        "How does Decision Replay work?"
                    ],
                    "source": "EDRP Decision Engine"
                }

        # ── Case C: Internal Email Service Full Breakdown ──
        if "email" in screen_title.lower() or "/email" in current_url.lower():
            reply_lines = [
                f"### 📍 Executive Guide: **Internal Email & Communication Center** (`/email`)\n",
                "This workspace enables secure role-governed email dispatches, audit tracking, and direct notifications across all organizational members.\n",
                "#### ✉️ Core Email Workflows & Capabilities:",
                "1. **Compose & Send Internal Emails**:",
                "   - Filter recipients quickly by role (**Employee**, **Reviewer**, **Manager**, **Administrator**) or type `@` to search team members by name or Employee ID.",
                "   - Set Subject, Urgency Priority (Low/Medium/High/Urgent), and Rich Message Body.",
                "2. **Delivery Providers**:",
                "   - Choose between **Original Gmail Integration** or the **Project SMTP Gateway** for delivery.",
                "3. **Edit & Resend Sent Messages**:",
                "   - Click **Edit** on any sent email card to load the message back into the composer, refine the content, and resend it with updated notifications.",
                "4. **Email Deletion & Cleanup**:",
                "   - Click **Delete** on any card to purge unnecessary correspondence with real-time stats counter updates.",
                "5. **Real-time Live Metrics**:",
                "   - Live telemetry monitors total **Sent**, **Delivered**, and **Read** messages in the summary cards."
            ]
            if visible_text:
                reply_lines.append(f"\n**Visible Activity Snapshot:**\n*{visible_text[:300]}...*")

            return {
                "reply": "\n".join(reply_lines),
                "suggested_actions": [
                    "How do I filter recipients by role?",
                    "How to edit and resend an email?",
                    "How to check delivery status?"
                ],
                "source": "EDRP Email Service"
            }

        # ── Case D: User Management Full Breakdown ──
        if "user" in screen_title.lower() or "/users" in current_url.lower():
            reply_lines = [
                f"### 📍 Executive Guide: **Enterprise User & Role Management** (`/users`)\n",
                "This administrative workspace manages all member accounts, role access levels, and security states.\n",
                "#### 👥 Key Capabilities & Operations:",
                "1. **Role Filtering & Inspection**: Filter user directory by **Employees**, **Reviewers**, **Managers**, or **Administrators**.",
                "2. **Promotion & Demotion**: Adjust user privileges to match organizational hierarchy and approval authority.",
                "3. **Account Activation**: Toggle active/inactive status to instantly grant or revoke platform access.",
                "4. **Direct Communication**: Jump directly into internal email to message any employee."
            ]
            if visible_text:
                reply_lines.append(f"\n**Visible User Data:**\n*{visible_text[:300]}...*")

            return {
                "reply": "\n".join(reply_lines),
                "suggested_actions": [
                    "How do approval tiers work?",
                    "What permissions does a Manager have?",
                    "How to promote an employee to Reviewer?"
                ],
                "source": "EDRP User Directory"
            }

        # ── Case E: Audit Logs Full Breakdown ──
        if "audit" in screen_title.lower() or "/audit" in current_url.lower():
            reply_lines = [
                f"### 🔒 Executive Guide: **Immutable Audit Logs & Compliance** (`/audit`)\n",
                "This security workspace provides an immutable, append-only chronological log of every action, state change, and vote across the platform.\n",
                "#### 🛡️ Key Capabilities & Features:",
                "1. **Append-Only Logging**: Every decision creation, status change, review evaluation, and version restore is permanently logged.",
                "2. **Field-Level JSON Diffs**: Inspect precise before/after field changes for complete transparency.",
                "3. **Security Auditing**: Track user identity, role, timestamp, and IP address for compliance (SOC 2, ISO 27001).",
                "4. **Search & Filter**: Search logs by user, action type, severity, or module."
            ]
            if visible_text:
                reply_lines.append(f"\n**Visible Audit Records:**\n*{visible_text[:300]}...*")

            return {
                "reply": "\n".join(reply_lines),
                "suggested_actions": [
                    "Who can view Audit Logs?",
                    "How does Decision Replay use audit diffs?",
                    "Explain the approval workflow"
                ],
                "source": "EDRP Audit Engine"
            }

        # ── Case F: Team Management Full Breakdown ──
        if "team" in screen_title.lower() or "/teams" in current_url.lower():
            reply_lines = [
                f"### 👥 Executive Guide: **Team & Department Management** (`/teams`)\n",
                "This workspace allows administrators and managers to organize employees into functional departments and project teams.\n",
                "#### 🏢 Key Capabilities & Operations:",
                "1. **Create Teams**: Set up department teams (e.g. Engineering, Finance, Operations, Product, Legal).",
                "2. **Assign Members**: Allocate employees and assign team leads with specific decision authority.",
                "3. **Department Analytics**: Track decision volume and review turnaround per team."
            ]
            if visible_text:
                reply_lines.append(f"\n**Visible Teams:**\n*{visible_text[:300]}...*")

            return {
                "reply": "\n".join(reply_lines),
                "suggested_actions": [
                    "How do I assign users to a team?",
                    "What permissions does a Manager have?",
                    "How to create a new decision?"
                ],
                "source": "EDRP Team Management"
            }

        # ── Case D: General Structured Page Summary ──
        reply_lines = [
            f"### 📍 Executive Summary: **{screen_title}** (`{current_url or 'Active View'}`)\n",
            f"You are currently viewing the **{screen_title}** screen in the Expert Decision Replay Platform.\n",
            "#### 🎯 Workspace Overview & Capabilities:",
            "- **Strategic Decision Tracking**: View, structure, and monitor multi-tier organizational decisions.",
            "- **Audit Trail & Governance**: Inspect field-level diffs, reviewer votes, and version replays.",
            "- **Communication & Collaboration**: Exchange context with teammates using `@` mentions and internal emails."
        ]
        if visible_text:
            reply_lines.append(f"\n#### 📊 Page Context & Visible Data:\n{visible_text[:800]}\n")

        reply_lines.extend([
            "#### 💡 Recommended Next Actions:",
            "- You can ask me to draft problem statements, compare alternatives, or audit risks.",
            "- Use the **Quick Actions** above for one-click analysis of this page."
        ])

        return {
            "reply": "\n".join(reply_lines),
            "suggested_actions": [
                "How do I create a new decision?",
                "Explain the approval workflow",
                "Show my decisions"
            ],
            "source": "EDRP AI Assistant"
        }

    # --- 1. Decision Creation & Problem Rationale ---
    if any(k in q for k in ["how do i create", "how to create a decision", "create new decision", "start decision", "make decision", "steps to create"]):
        return {
            "reply": (
                "**Step-by-Step Guide to Creating a Decision in EDRP:**\n\n"
                "1. **Open Creation Wizard**: Click **'Create Decision'** in the sidebar navigation.\n"
                "2. **Step 1 - Problem Statement & Rationale**:\n"
                "   - Enter a clear **Title** and detailed **Problem Rationale** (explain why this decision is needed).\n"
                "   - Select the **Category** (e.g. Infrastructure, Software, Operations) and **Urgency** (Low/Med/High/Critical).\n"
                "   - Enter estimated **Financial Impact ($ ROI / Budget)**.\n"
                "3. **Step 2 - Alternative Evaluation**:\n"
                "   - Add at least 2 evaluated alternatives.\n"
                "   - For each alternative, provide estimated **Cost**, **Feasibility Score (1-10)**, **Risk Level**, and **Pros & Cons**.\n"
                "   - Select one alternative as **'Recommended'**.\n"
                "4. **Step 3 - Attachments & Reviewers**:\n"
                "   - Upload supporting files (PDF, DOCX, PPTX up to 200MB).\n"
                "   - Choose assigned Reviewers and Managers.\n"
                "5. **Step 4 - Submit**:\n"
                "   - Click **'Save as Draft'** (auto-saves every 30s) or click **'Submit for Approval'** to trigger the review workflow."
            ),
            "suggested_actions": ["What is an Alternative Analysis?", "Explain the approval workflow", "Can I edit a decision after submission?"],
            "source": "EDRP AI Assistant"
        }

    if any(k in q for k in ["rationale", "problem statement", "justification", "why rationale"]):
        return {
            "reply": (
                "**What is a Decision Rationale in EDRP?**\n\n"
                "The **Decision Rationale** is the foundational justification for why a strategic choice is being made. It captures:\n"
                "- **The Core Problem**: The business challenge or opportunity being addressed.\n"
                "- **Expected Value / ROI**: Financial impact, cost savings, or efficiency gains.\n"
                "- **Strategic Alignment**: How this decision aligns with organizational goals.\n"
                "- **Urgency & Context**: Why this decision must be made now and what happens if no action is taken.\n\n"
                "*Tip: A well-defined rationale speeds up reviewer approval and provides valuable context during future Decision Replays.*"
            ),
            "suggested_actions": ["How do I evaluate alternatives?", "Explain the approval workflow", "How does Decision Replay work?"],
            "source": "EDRP AI Assistant"
        }

    # --- 2. Alternative Matrix, Feasibility & Risk ---
    if any(k in q for k in ["alternative", "feasibility", "risk level", "pros and cons", "matrix", "recommended option"]):
        return {
            "reply": (
                "**How the Alternative Evaluation Matrix Works:**\n\n"
                "When submitting a decision, EDRP requires comparative analysis across alternatives:\n\n"
                "1. **Feasibility Score (1-10)**:\n"
                "   - Evaluates technical capability, time constraints, resource readiness, and complexity.\n"
                "   - *10 = Extremely Easy / High Confidence; 1 = High Complexity / Low Feasibility.*\n"
                "2. **Estimated Cost / Budget**:\n"
                "   - Direct and indirect financial investment required for this option.\n"
                "3. **Risk Level (Low / Medium / High)**:\n"
                "   - Assessment of potential downsides, security exposure, or operational disruption.\n"
                "4. **Pros & Cons**:\n"
                "   - Clear bullet points outlining the competitive advantages vs trade-offs.\n"
                "5. **Recommended Flag**:\n"
                "   - Mark the proposed option as **'Recommended'** to guide the approval chain."
            ),
            "suggested_actions": ["How do I create a new decision?", "Explain the approval workflow", "How does Decision Replay work?"],
            "source": "EDRP AI Assistant"
        }

    # --- 3. Approval Workflow, Reviewers, Rejection & Revision ---
    if any(k in q for k in ["can i edit", "edit decision", "modify decision", "update after submit", "change after submit"]):
        return {
            "reply": (
                "**Can I Edit a Decision After It Has Been Submitted?**\n\n"
                "- **Once Submitted**: Decisions are **locked from direct editing** while active in the review pipeline to maintain audit integrity.\n"
                "- **If Changes are Needed**:\n"
                "  - A Reviewer or Manager can select **'Request Revision'** (or **'Send Back'**).\n"
                "  - This returns the decision to **Draft** status.\n"
                "  - You can update title, rationale, alternatives, or attachments and click **'Resubmit'**.\n"
                "  - Resubmission automatically generates a new version snapshot (**`v2`**) with a documented change reason."
            ),
            "suggested_actions": ["Explain the approval workflow", "How does Decision Replay work?", "Where do I find my pending reviews?"],
            "source": "EDRP AI Assistant"
        }

    if any(k in q for k in ["reject", "rejected", "why rejected", "rejection reason"]):
        return {
            "reply": (
                "**What Happens When a Decision is Rejected?**\n\n"
                "1. **Mandatory Feedback**: When a Reviewer or Manager rejects a decision, they are required to submit an **explanatory rejection note**.\n"
                "2. **Notification**: The decision creator receives an immediate in-app and email notification containing the rejection comments.\n"
                "3. **Resubmission**:\n"
                "   - The creator can review the feedback, adjust the rationale or alternatives, and click **'Resubmit for Review'**.\n"
                "   - This moves the decision back into review as Version `v2`.\n"
                "4. **Audit Trail**: Both the initial rejection and subsequent resubmission are permanently recorded in the immutable Audit Log."
            ),
            "suggested_actions": ["Explain the approval workflow", "How do I create a revision?", "How to view audit logs?"],
            "source": "EDRP AI Assistant"
        }

    if any(k in q for k in ["approval workflow", "how does approval", "explain approval", "review workflow", "sequential review", "approval chain", "approval tier", "approval stages", "how to approve", "stages of approval"]) or (("approval" in q or "approve" in q) and ("how" in q or "explain" in q or "process" in q or "steps" in q or "chain" in q or "tier" in q)):
        return {
            "reply": (
                "**EDRP Multi-Tier Approval Workflow:**\n\n"
                "Decisions progress through sequential review stages:\n\n"
                "1. **Stage 1 - Domain Reviewer (RW)**:\n"
                "   - Evaluates feasibility, technical merit, pros/cons, and risks.\n"
                "   - Can choose: **Approve**, **Reject**, or **Request Revision**.\n"
                "2. **Stage 2 - Department Manager (MN)**:\n"
                "   - Reviews resource allocation, team budget, and strategic priorities.\n"
                "3. **Stage 3 - Administrator (AD)**:\n"
                "   - Final sign-off, enterprise compliance verification, and organization-wide archiving.\n"
                "4. **Automated Status Progression**:\n"
                "   - `Draft` -> `In Review (Stage 1)` -> `In Review (Stage 2)` -> `Approved` / `Rejected`."
            ),
            "suggested_actions": ["Where do I find my pending reviews?", "Can I edit a submitted decision?", "How does Decision Replay work?"],
            "source": "EDRP AI Assistant"
        }

    if any(k in q for k in ["pending review", "reviewer workspace", "my reviews", "where to review", "assigned to me"]):
        return {
            "reply": (
                "**Where to Find Your Pending Reviews:**\n\n"
                "1. Navigate to **'Reviewer Workspace'** or **'Pending Approvals'** in the left sidebar.\n"
                "2. Here you will see all decisions waiting for your evaluation.\n"
                "3. Click **'Review Decision'** to inspect the rationale, financial impact, and alternatives.\n"
                "4. Enter your evaluation notes and submit your decision (**Approve**, **Reject**, or **Request Revision**)."
            ),
            "suggested_actions": ["Explain the approval workflow", "What happens when a decision is rejected?", "How does Decision Replay work?"],
            "source": "EDRP AI Assistant"
        }

    # --- 4. Decision Replay, Versioning & Version Restore ---
    if any(k in q for k in [
        "restore version", "use of restore", "why restore", "restored version", "how to restore",
        "where can the restored", "where to see restored", "restored details", "restored version details",
        "who restored", "restore v1", "restore version 1"
    ]):
        return {
            "reply": (
                "### 🔄 Version Restore & Historical Snapshot Engine in EDRP\n\n"
                "#### 1. What is the Purpose of 'Restore Version'?\n"
                "- **Revert to Approved Baseline**: Enables authorized Managers and Administrators to roll back unintended modifications or reinstate an earlier consensus state (e.g. `Version 1`) without breaking compliance.\n"
                "- **Audit Preservation**: Instead of overwriting history, restoring generates a **new version snapshot** (e.g. `v3` restored from `v1`), preserving every intermediate draft, revision comment, and approval stage.\n\n"
                "#### 2. Where Can You Find Restored Version Details?\n"
                "1. **Decision Overview Page** (`/decisions/xx`):\n"
                "   - Displays the active version tag and an alert banner indicating: *\"Restored from Version X by [User Name, User ID, Role]\"*.\n"
                "2. **Version History Modal**:\n"
                "   - Click **'Version History'** on the decision page to view all version records, timestamps, change summaries, and actor attributions (User Name, User ID, Role: Reviewer/Manager/Administrator).\n"
                "   - Provides side-by-side field-level comparison diffs.\n"
                "3. **Immutable Audit Logs** (`/audit-logs`):\n"
                "   - Full append-only log entry capturing action `DECISION_RESTORE` with before/after JSON diffs, actor ID, and IP address."
            ),
            "suggested_actions": ["How does Decision Replay work?", "How do I view Audit Logs?", "Explain the approval workflow"],
            "source": "EDRP Decision Engine"
        }

    if any(k in q for k in ["replay", "version", "history", "snapshot", "timeline", "v1", "v2", "playback", "diff engine"]):
        return {
            "reply": (
                "**How Decision Replay & Versioning Works in EDRP:**\n\n"
                "- **Automatic Snapshotting**: Every major event (Submission, Revision, Reviewer Evaluation, Approval, Restore) creates an immutable point-in-time snapshot (`v1`, `v2`, `v3`).\n"
                "- **Interactive Visual Playback**:\n"
                "  1. Navigate to **'Replays'** in the sidebar (or click 'Decision Replay' on any decision page).\n"
                "  2. Select any decision to launch the interactive timeline player.\n"
                "  3. Use the playback slider to view the exact state of the decision at each step:\n"
                "     - Initial problem statement & estimated budget.\n"
                "     - Alternative matrix scores and feasibility rankings.\n"
                "     - Reviewer evaluations, votes, comments, and timestamps.\n"
                "     - Restored version checkpoints and diff comparisons.\n"
                "- **Use Cases**: Ideal for onboarding new team members, executive reviews, and regulatory compliance audits."
            ),
            "suggested_actions": ["Where can I see restored version details?", "How do I view Audit Logs?", "Explain the approval workflow"],
            "source": "EDRP Decision Engine"
        }

    # --- 5. Roles & RBAC ---
    if any(k in q for k in ["role", "roles", "permission", "permissions", "rbac", "employee id", "prefix", "administrator vs", "admin and manager", "manager and reviewer"]):
        return {
            "reply": (
                "**EDRP Role-Based Access Control (RBAC):**\n\n"
                "| Role | Prefix | Responsibilities & Access |\n"
                "|---|:---:|---|\n"
                "| **Administrator** | `AD-xxx` | Full platform control, user verification, audit log review, global settings, ticket administration. |\n"
                "| **Manager** | `MN-xxx` | Team decision reviews, departmental analytics, assigning reviewers, second-tier approvals. |\n"
                "| **Reviewer** | `RW-xxx` | Domain evaluations, alternative scoring, approving/rejecting assigned decisions, revision requests. |\n"
                "| **Employee** | `EMP-xxx` | Creating decisions, drafting alternatives, participating in discussion threads, viewing approved records. |"
            ),
            "suggested_actions": ["How do I reset my password?", "How do I create a new decision?", "Explain the approval workflow"],
            "source": "EDRP AI Assistant"
        }

    # --- 6. Audit Logs, Diff Engine & Compliance ---
    if any(k in q for k in ["audit", "audit log", "audit logs", "diff engine", "diffs", "compliance", "append-only", "tamper", "export csv"]):
        return {
            "reply": (
                "**Enterprise Audit Logging & Field-Level Diff Engine:**\n\n"
                "- **Append-Only Immutability**: PostgreSQL database triggers physically reject any `UPDATE` or `DELETE` queries on the `audit_logs` table, ensuring an unalterable compliance record.\n"
                "- **Field-Level Diff Engine**: Records exact before-and-after values for all modified fields:\n"
                "  ```json\n"
                "  {\n"
                "    \"status\": {\"before\": \"Draft\", \"after\": \"In Review\"},\n"
                "    \"financial_impact\": {\"before\": 50000, \"after\": 65000}\n"
                "  }\n"
                "  ```\n"
                "- **Metadata Recorded**: User ID, Full Name, Role, IP Address, User-Agent, Action, and Timestamp.\n"
                "- **Export**: Administrators can click **'Export CSV'** in the Audit Logs page for SOC 2 / ISO 27001 compliance reviews."
            ),
            "suggested_actions": ["Who can view Audit Logs?", "How does Decision Replay work?", "Explain the approval workflow"],
            "source": "EDRP AI Assistant"
        }

    # --- 7. Password Reset, OTP, Login & Account ---
    if any(k in q for k in ["password", "reset password", "forgot password", "otp", "login issue", "change password", "profile"]):
        return {
            "reply": (
                "**Password Reset & Account Security:**\n\n"
                "1. **If You Are Logged In**:\n"
                "   - Go to **'Profile'** or **'Settings'** in the sidebar.\n"
                "   - Enter your current password and specify a new secure password.\n"
                "2. **If You Forgot Your Password**:\n"
                "   - On the Login screen, click **'Forgot Password?'**.\n"
                "   - Enter your corporate email address to receive a **6-Digit OTP code** via email.\n"
                "   - Enter the OTP code within 10 minutes and choose a new password.\n"
                "3. **Remember Me**:\n"
                "   - Selecting **'Remember Me'** on login preserves your authenticated session for **72 hours**."
            ),
            "suggested_actions": ["How does OTP verification work?", "What are the roles in EDRP?", "How do I contact support?"],
            "source": "EDRP AI Assistant"
        }

    # --- 8. Email & Notifications ---
    if any(k in q for k in ["notification", "notifications", "email alert", "email notification", "smtp", "badge", "unread"]):
        return {
            "reply": (
                "**How Notifications & Email Alerts Work in EDRP:**\n\n"
                "- **Automatic Event Triggers**: Notifications are dispatched immediately for:\n"
                "  - **Review Assignment**: Reviewers receive an email and in-app alert when a decision requires their evaluation.\n"
                "  - **Decision Status Changes**: Submitter is notified when their decision is **Approved**, **Rejected**, or **Revision Requested**.\n"
                "  - **New Comments**: Participants in a decision thread receive alerts on new discussion replies.\n"
                "  - **Support Updates**: Support ticket confirmations and administrator responses are emailed via SMTP.\n"
                "- **In-App Notification Bell**:\n"
                "  - Located in the top-right header, displaying unread count badges in real-time.\n"
                "  - Click any notification to navigate directly to the relevant decision or ticket."
            ),
            "suggested_actions": ["Explain the approval workflow", "How do I create a new decision?", "How do I contact support?"],
            "source": "EDRP AI Assistant"
        }

    # --- 9. File Uploads & Documents ---
    if any(k in q for k in ["file", "upload", "attachment", "document", "pdf", "docx", "pptx", "size limit", "format"]):
        return {
            "reply": (
                "**File Attachment Guidelines:**\n\n"
                "- **Supported Formats**: PDF (`.pdf`), Microsoft Word (`.docx`), PowerPoint (`.pptx`), CSV (`.csv`), and Images (`.png`, `.jpg`).\n"
                "- **Maximum File Size**: Up to **200 MB** per uploaded attachment.\n"
                "- **Security**: Uploaded documents undergo MIME-type validation and are linked securely to the decision record with role-based access."
            ),
            "suggested_actions": ["How do I create a new decision?", "Explain the approval workflow", "How to submit a ticket?"],
            "source": "EDRP AI Assistant"
        }

    # --- 10. Discussions & Collaboration ---
    if any(k in q for k in ["discuss", "comment", "discussion", "mention", "reply to comment", "stakeholder"]):
        return {
            "reply": (
                "**Decision Discussions & Collaboration:**\n\n"
                "- **Discussion Threads**: Every decision detail page includes a live **Discussion Thread** where creators, reviewers, and stakeholders can ask clarifying questions.\n"
                "- **Mentions & Notifications**: Posting a comment sends an immediate in-app and email notification to the decision creator and assigned reviewers.\n"
                "- **Audit Persistence**: All discussion comments are timestamped and preserved in the decision history and replay timeline."
            ),
            "suggested_actions": ["How do I create a new decision?", "Explain the approval workflow", "How does Decision Replay work?"],
            "source": "EDRP AI Assistant"
        }

    # --- 11. Reports & Analytics ---
    if any(k in q for k in ["report", "analytics", "chart", "export report", "excel", "metrics", "dashboard"]):
        return {
            "reply": (
                "**Reports & Decision Analytics:**\n\n"
                "- **Dashboard Visualizations**: View monthly decision volume, approval vs rejection rates, department comparisons, and average SLA review duration.\n"
                "- **Export Capabilities**: Export decision summaries, review evaluation matrices, and audit logs to **PDF** or **Excel / CSV** format.\n"
                "- **Department Metrics**: Compare decision velocity across Engineering, Operations, Finance, and Product teams."
            ),
            "suggested_actions": ["How do I view Audit Logs?", "How do I create a new decision?", "Explain the approval workflow"],
            "source": "EDRP AI Assistant"
        }

    # --- 12. Teams & Departments ---
    if any(k in q for k in ["team", "department", "invite", "add member", "organization"]):
        return {
            "reply": (
                "**Team & Department Management:**\n\n"
                "- **Departments**: Decisions are categorized by department (e.g., Engineering, Finance, Operations, Product, Legal).\n"
                "- **Manager Visibility**: Managers have direct visibility into decisions submitted by members within their department or assigned team.\n"
                "- **Administrator Role Assignment**: Administrators can configure user teams, designations, and role permissions from the **User Management** console."
            ),
            "suggested_actions": ["What are the roles in EDRP?", "How do I create a new decision?", "Explain the approval workflow"],
            "source": "EDRP AI Assistant"
        }

    # --- 13. Support Tickets & Contact ---
    if any(k in q for k in ["ticket", "contact", "support email", "office hours", "phone", "helpdesk"]):
        return {
            "reply": (
                "**Need Assistance or Encountered a Bug?**\n\n"
                "- **Submit a Ticket**: Click **'Create Ticket'** or **'Report an Issue'** in the top action cards.\n"
                "- **Track Status**: Monitor your requests under **'Previous Requests'** (`Open`, `In Progress`, `Resolved`).\n"
                "- **Enterprise Contact Details**:\n"
                "  - **Email**: `support@edrp-platform.com`\n"
                "  - **Company**: `contact@edrp.org`\n"
                "  - **Support Hours**: Mon - Fri, 9:00 AM - 6:00 PM EST"
            ),
            "suggested_actions": ["How do I reset my password?", "How do I create a new decision?", "Explain the approval workflow"],
            "source": "EDRP AI Assistant"
        }

    # --- 14. Theme & Accessibility ---
    if any(k in q for k in ["dark mode", "theme", "light mode", "accessibility", "color"]):
        return {
            "reply": (
                "**Theme & Accessibility Options:**\n\n"
                "- **Theme Toggle**: Navigate to **'Profile'** or use the top navbar to toggle between **Light Mode** and **Dark Mode**.\n"
                "- **System Default**: Automatically matches your operating system preference.\n"
                "- **High Contrast**: Enhanced contrast mode is available in Profile Settings for accessibility compliance."
            ),
            "suggested_actions": ["How do I update my profile?", "How do I reset my password?", "How do I create a decision?"],
            "source": "EDRP AI Assistant"
        }

    # --- 15. Dynamic Fallback: Parse specific user keywords to build a tailored answer ---
    tailored_reply = _build_dynamic_tailored_reply(query, user_name)
    return {
        "reply": tailored_reply,
        "suggested_actions": _derive_custom_suggestions(query, db_context),
        "source": "EDRP AI Assistant"
    }


def _build_dynamic_tailored_reply(query: str, user_name: str) -> str:
    clean = query.strip()
    words = re.findall(r'\b\w+\b', clean.lower())
    
    subject_snippet = clean
    if len(clean) > 80:
        subject_snippet = clean[:80] + "..."

    response_parts = [
        f"Regarding your query about **\"{subject_snippet}\"**:\n"
    ]

    if "decision" in words:
        response_parts.append("- **Decisions**: All strategic decisions in EDRP follow a structured lifecycle: `Draft` -> `In Review` -> `Approved` / `Rejected`. You can create decisions from the sidebar wizard, attach alternative matrices, and submit them for multi-stage review.")
    
    if any(w in words for w in ["review", "reviewer", "approval", "approve"]):
        response_parts.append("- **Reviews & Approvals**: Assigned reviewers evaluate feasibility scores, budget impact, and risk levels. They can Approve, Reject with mandatory notes, or Request Revision back to draft.")

    if any(w in words for w in ["replay", "history", "version"]):
        response_parts.append("- **Replay & History**: Point-in-time snapshots (`v1`, `v2`) allow complete visual playback of the decision timeline, reviewer scores, and discussions.")

    if any(w in words for w in ["audit", "log", "security", "diff"]):
        response_parts.append("- **Audit Logs**: Append-only database triggers ensure immutable logging of all state changes, capturing before/after JSON diffs, actor details, and client IP addresses.")

    if any(w in words for w in ["user", "account", "password", "login", "otp", "role"]):
        response_parts.append("- **User Accounts & Security**: Roles (Admin, Manager, Reviewer, Employee) control access. Password resets use 6-digit email OTP verification, and 'Remember Me' maintains sessions for 72 hours.")

    if len(response_parts) == 1:
        response_parts.append(f"In the **Expert Decision Replay Platform**, you can manage decisions, coordinate multi-stage approvals, track append-only audit diffs, and inspect version replays.\n\nTo help you with this, you can:\n1. Check the relevant section in the **Sidebar Navigation**.\n2. Click **'Create Ticket'** above to submit a specific support request to our engineering team.\n3. Or ask me a more specific question about decision creation, workflows, or account settings!")

    return "\n\n".join(response_parts)


def _is_edrp_related_query(query: str, db_context: Dict[str, Any]) -> bool:
    """
    Determines if a query is relevant to EDRP, enterprise decision governance, or platform workflows.
    Returns False for off-topic questions (e.g. general programming tutorials, recipes, weather, general trivia).
    """
    q = query.lower().strip()
    words = set(re.findall(r'\b[a-zA-Z0-9_-]+\b', q))

    # Common greetings and identity queries are always valid
    if q in ["hi", "hello", "hey", "greetings", "good morning", "good afternoon", "good evening", "help", "who are you", "what can you do", "what is your name", "thank you", "thanks"]:
        return True

    # Core EDRP and Decision Management Keywords
    edrp_keywords = {
        "edrp", "decision", "decisions", "dec", "alternative", "alternatives", "rationale", "problem",
        "statement", "approval", "approve", "approvals", "approving", "reject", "rejected", "rejection",
        "revision", "resubmit", "reviewer", "reviewers", "review", "reviews", "manager", "managers",
        "admin", "administrator", "administrators", "employee", "employees", "role", "roles", "rbac",
        "replay", "replays", "history", "version", "versions", "snapshot", "restore", "restored",
        "restoration", "timeline", "playback", "diff", "diffs", "audit", "logs", "log", "compliance",
        "tamper", "immutable", "ticket", "tickets", "support", "helpdesk", "sla", "email", "emails",
        "smtp", "notification", "notifications", "unread", "bell", "team", "teams", "department",
        "departments", "budget", "budgets", "cost", "costs", "feasibility", "risk", "risks",
        "pros", "cons", "matrix", "priority", "urgency", "stakeholder", "stakeholders", "attachment",
        "attachments", "upload", "uploads", "export", "report", "reports", "analytics", "repository",
        "knowledge", "password", "otp", "login", "profile", "settings", "draft", "drafts", "overview",
        "summary", "page", "guide", "workflow", "stage", "stages", "tier", "tiers", "governance"
    }

    if words.intersection(edrp_keywords):
        return True

    # Check for decision ID pattern (e.g., DEC-1, DEC-28, #12, /decision/5)
    if re.search(r'\b(?:dec[-_ /]?|/decision/)?\d+\b', q):
        return True

    # Check for decision creation/formulation intents (e.g. "generate problem statement for...", "suggest alternatives for...")
    is_decision_generative = any(g in q for g in ["problem statement", "rationale", "alternative", "decision for", "titled", "category", "department", "evaluate", "formulate"]) and any(a in q for a in ["create", "generate", "draft", "suggest", "write", "propose", "recommend"])
    if is_decision_generative:
        return True

    # Check if query matches existing database decisions or active page
    matched_decisions = db_context.get("matched_decisions", [])
    if matched_decisions:
        top_d = matched_decisions[0]
        d_words = set(re.findall(r'\b[a-zA-Z0-9_-]+\b', (top_d.get("title", "") + " " + top_d.get("description", "")).lower()))
        if len(words.intersection(d_words)) >= 2:
            return True

    return False


def _handle_unrelated_query(clean_msg: str, user_name: str) -> Dict[str, Any]:
    """
    Returns a polite refusal explaining that this assistant is dedicated to EDRP,
    and guides the user to ask questions related to the Expert Decision Replay Platform.
    """
    reply_text = (
        f"I am the specialized AI Assistant for the **Expert Decision Replay Platform (EDRP)**.\n\n"
        f"I can only assist you with questions related to **EDRP**, strategic organizational decisions, and decision governance. I cannot provide answers for unrelated topics (such as general programming tutorials, recipes, weather, or general trivia).\n\n"
        f"**Please ask questions regarding EDRP, such as:**\n"
        f"- 🎯 **Decision Management**: *\"How do I create and structure a new strategic decision?\"*\n"
        f"- 🛡️ **Approval Workflows**: *\"Explain the 3-tier review chain (Reviewer → Manager → Administrator)\"*\n"
        f"- ⚖️ **Alternative Matrices**: *\"How to evaluate alternatives, feasibility scores, and cost estimates?\"*\n"
        f"- 🔄 **Decision Replay & Restore**: *\"What is the use of restore version and where can I view it?\"*\n"
        f"- 📚 **Knowledge Repository**: *\"What decisions were approved for Technology Budget?\"*\n"
        f"- 🔒 **Audit & Security**: *\"How does the immutable audit log and diff engine work?\"*"
    )
    return {
        "reply": reply_text,
        "suggested_actions": [
            "How do I create a new decision?",
            "Explain the approval workflow",
            "What is the use of restore version?",
            "Search Knowledge Repository"
        ],
        "source": "EDRP AI Assistant",
        "is_knowledge_repository": False
    }


def _derive_custom_suggestions(query: str, db_context: Optional[Dict[str, Any]] = None) -> List[str]:
    q = query.lower()
    if any(k in q for k in ["problem", "what did i add", "rationale"]):
        return ["What are the alternatives for this decision?", "What is the status of this decision?", "Show my decisions", "Explain approval workflow"]
    if any(k in q for k in ["alternative", "feasibility", "cost"]):
        return ["What is the problem statement for this decision?", "What is the status of this decision?", "How does Decision Replay work?"]
    if any(k in q for k in ["create", "draft", "new"]):
        return ["What is an Alternative Analysis?", "Explain the approval workflow", "Can I edit a submitted decision?"]
    if any(k in q for k in ["approve", "reject", "review", "workflow", "revision", "status"]):
        return ["Where do I find my pending reviews?", "What happens when a decision is rejected?", "How does Decision Replay work?"]
    if any(k in q for k in ["replay", "version", "history", "v1", "v2"]):
        return ["How do I view Audit Logs?", "How do I create a new decision?", "Explain the approval workflow"]
    if any(k in q for k in ["audit", "diff", "compliance", "security"]):
        return ["How do I export audit logs?", "Who can view Audit Logs?", "Explain the approval workflow"]
    if any(k in q for k in ["password", "otp", "login", "account", "role"]):
        return ["How does OTP verification work?", "What are the roles in EDRP?", "How do I create a support ticket?"]
    return ["How do I create a new decision?", "Explain the approval workflow", "Show my decisions", "How does Decision Replay work?"]
