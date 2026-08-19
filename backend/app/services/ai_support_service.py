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

EDRP_SYSTEM_PROMPT = """You are the EDRP AI Assistant for the Expert Decision Replay Platform (EDRP).
EDRP is an enterprise platform for creating, evaluating, reviewing, approving, replaying, and auditing critical strategic business decisions.

=== Core Platform Knowledge ===
1. User Roles:
   - Administrator (AD-xxxx): Platform governance, user verification, system settings, final approval stage, master audit logs.
   - Manager (MN-xxxx): Team oversight, budget review, Stage 2 approval authority, department analytics.
   - Reviewer (RW-xxxx): Domain expert review, evaluating alternatives, Stage 1 approval/rejection/revision requests.
   - Employee (EMP-xxxx): Creating decisions, proposing alternatives, tracking status, participating in decision discussions.

2. Step-by-Step Decision Creation Process (UI Navigation & Fields):
   - Step 1: Open the Sidebar and click "Create Decision" (or go to /create-decision).
   - Step 2: Fill in the Primary Information:
     * Title: Descriptive decision name (e.g. "Select Cloud Provider for EDRP").
     * Problem Statement / Rationale: Detailed problem description and business necessity.
     * Category: Technology, Finance, Operations, Legal, HR, Infrastructure, etc.
     * Department: Target department (Engineering, Sales, IT, etc.).
     * Priority / Urgency: Low, Medium, High, or Critical.
     * Stakeholders: Key persons/groups impacted.
     * Financial Impact / Budget: Estimated total cost/investment.
   - Step 3: Define Alternatives (Must evaluate at least 1 alternative, recommended 2+):
     * Alternative Title & Description.
     * Pros & Cons: Key benefits and trade-offs.
     * Estimated Cost ($): Projected implementation cost.
     * Feasibility Score (1-10): Implementation practicality rating.
     * Risk Level: Low, Medium, or High.
   - Step 4: Attach Files: Optional supporting documents (PDF, DOCX, PPTX up to 200MB).
   - Step 5: Save as "Draft" or click "Submit Decision" to transition status to "In Review" and trigger the approval chain.

3. Approval & Review Workflow:
   - Lifecycle: Draft → In Review → Approved / Rejected / Revision Requested → Archived.
   - Sequential Approval Chain: Reviewer (RW) → Manager (MN) → Administrator (AD).
   - Reviewer Actions:
     * Approve: Endorses the decision and advances it to the next tier or final approval.
     * Reject: Denies the decision with mandatory rejection justification.
     * Request Revision: Sends the decision back to the author with required modifications and feedback.

4. Decision Replay & Versioning:
   - Navigate to any decision detail page and click "Decision Replay" (or Replay tab).
   - Step-by-step visual timeline reconstruction of the decision's entire history: initial draft, reviewer comments, alternative comparisons, and version diffs (v1, v2, etc.).

5. Audit Logs & Compliance:
   - Append-only immutable audit trail capturing every change, field-level before/after JSON diffs, timestamps, user IDs, and IP addresses.
   - Exportable to CSV or PDF for compliance audits.

6. Support Center & Tickets:
   - Use the AI Support Assistant for instant answers or click "Create Ticket" to generate a formal support ticket (SUP-xxxx) for helpdesk assistance.

=== Response Instructions ===
- When the user asks "how to create a decision", "explain the steps", or questions about platform features, provide clear, step-by-step instructions with exact UI buttons, fields, and workflow stages.
- When the user asks to "create", "generate", "write", "draft", or "suggest" a Problem Statement or Alternatives for a decision title (e.g. "create and generate a new problem statement for the decision title Cloud mitigation"):
  * Generate a comprehensive, professional, enterprise-grade problem statement and rationale tailored to that topic.
  * Structure the response with:
    1. **Executive Problem Statement / Rationale** (A crisp, impactful rationale paragraph ready to paste into EDRP).
    2. **Background & Technical / Business Friction** (Current challenges and root causes).
    3. **Key Risks & Business Impact** (Security, downtime, compliance, financial impact).
    4. **Success Criteria & Objectives** (Measurable goals like 99.99% availability, SLA compliance).
    5. **Recommended Alternatives to Evaluate in EDRP** (2-3 structured alternatives with Pros, Cons, Estimated Cost, Feasibility Score, and Risk Level).
- Format all responses using clean Markdown with bold headings, numbered lists, bullet points, and code spans.
- If real platform decisions, alternatives, or reviews are provided in the [Database Context], seamlessly reference them as concrete examples.
"""

def generate_ai_response(
    user_message: str,
    user_name: str = "User",
    user_id: Optional[int] = None,
    conversation_history: List[dict] = None,
    page_context: Optional[str] = None,
    page_title: Optional[str] = None,
    page_url: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generates an intelligent AI response for the EDRP Support Center.
    Queries real platform database records (RAG), attempts live LLM APIs (Gemini, OpenAI, Groq, Claude, OpenRouter),
    and falls back to the high-precision EDRP Knowledge Engine.
    """
    clean_msg = (user_message or "").strip()
    if not clean_msg:
        greeting_text = f"Hello {user_name}! I am your EDRP AI Assistant."
        if page_title:
            greeting_text += f" I see you are on **{page_title}**."
        greeting_text += " How can I assist you with this page or any platform and decision queries?"
        return {
            "reply": greeting_text,
            "suggested_actions": ["Explain this page", "How do I create a decision?", "Show my decisions", "Explain approval workflow"],
            "source": "EDRP AI Assistant"
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

    # 2. Check if this is a direct Decision Data Query (e.g. "what problem did i add for...", "my decisions", "status of DEC-28")
    data_response = _answer_decision_data_query(clean_msg, user_name, db_context)
    if data_response is not None:
        return data_response

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

    models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"]
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
    """
    Queries the database for decisions, alternatives, and reviews matching the query, active URL, or user.
    """
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


def _answer_decision_data_query(query: str, user_name: str, db_context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Detects if the user is asking about specific decisions, problem statements,
    alternatives, statuses, or their own decision list, and generates direct data-driven replies.
    If the user is asking to CREATE / GENERATE / DRAFT new content, returns None to allow LLM generation.
    """
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


def _answer_with_knowledge_engine(query: str, user_name: str, db_context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Intelligent built-in EDRP Knowledge Engine that understands all workflows,
    lifecycle states, approval tiers, audit trails, and troubleshooting steps.
    """
    q = query.lower().strip()

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
            "reply": """I am the **EDRP AI Support Assistant**, designed to provide real-time guidance and data lookups on the **Expert Decision Replay Platform**.

**What I Can Do:**
- 🔍 Look up your **actual decisions, problem statements, and alternative matrices**.
- 📋 Guide you through **creating decisions** and structuring evaluations.
- ⚡ Explain **multi-tier approval chains** (Reviewer → Manager → Administrator).
- ⏪ Explain **Decision Replay**, version snapshotting (`v1`, `v2`), and timeline diffs.
- 🔒 Clarify **append-only audit logs**, field-level diffs, and compliance exports.
""",
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
        if not current_dec and db_context.get("matched_decisions"):
            # If on a decision page or title mentions decision
            if "/decision/" in current_url.lower() or "dec-" in screen_title.lower() or "dec-" in current_url.lower():
                current_dec = db_context["matched_decisions"][0]

        # ── Case A: Decision Details Page Full Breakdown ──
        if current_dec or "/decision/" in current_url.lower() or "dec-" in screen_title.lower() or "decision:" in visible_text.lower():
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

        # ── Case B: Internal Email Service Full Breakdown ──
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

        # ── Case C: User Management Full Breakdown ──
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

    # --- 13. Support Tickets & Contact ---
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

    # --- 14. Theme & Accessibility ---
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

    # --- 15. Dynamic Fallback: Parse specific user keywords to build a tailored answer ---
    tailored_reply = _build_dynamic_tailored_reply(query, user_name)
    return {
        "reply": tailored_reply,
        "suggested_actions": _derive_custom_suggestions(query, db_context),
        "source": "EDRP AI Assistant"
    }


def _build_dynamic_tailored_reply(query: str, user_name: str) -> str:
    """
    Constructs a customized, direct answer analyzing the user's specific question phrasing.
    """
    clean = query.strip()
    words = re.findall(r'\b\w+\b', clean.lower())
    
    subject_snippet = clean
    if len(clean) > 80:
        subject_snippet = clean[:80] + "..."

    response_parts = [
        f"Regarding your query about **\"{subject_snippet}\"**:\n"
    ]

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
        response_parts.append(f"In the **Expert Decision Replay Platform**, you can manage decisions, coordinate multi-stage approvals, track append-only audit diffs, and inspect version replays.\n\nTo help you with this, you can:\n1. Check the relevant section in the **Sidebar Navigation**.\n2. Click **'Create Ticket'** above to submit a specific support request to our engineering team.\n3. Or ask me a more specific question about decision creation, workflows, or account settings!")

    return "\n\n".join(response_parts)


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
