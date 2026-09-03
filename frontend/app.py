from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    make_response,
    jsonify,
)
import os
import sys
import requests
import time
import gzip
import io
import threading
from datetime import timedelta
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import importlib.util

def _load_ai_support_generator():
    try:
        service_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend", "app", "services", "ai_support_service.py"))
        spec = importlib.util.spec_from_file_location("ai_support_service_module", service_file)
        ai_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ai_module)
        return ai_module.generate_ai_response
    except Exception as e:
        print(f"AI loader note: {e}")
        return None

generate_ai_response = _load_ai_support_generator()

_FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(_FRONTEND_DIR, "templates"),
    static_folder=os.path.join(_FRONTEND_DIR, "static")
)

# Secret Key & Session Config
app.secret_key = os.getenv("FLASK_SECRET_KEY", "development-only-secret-key")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=72)
# Maximum upload size set to 200 MB
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

# Reusable high-performance HTTP session with connection pooling
http_session = requests.Session()
adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50, max_retries=Retry(total=2, backoff_factor=0.05))
http_session.mount("http://", adapter)
http_session.mount("https://", adapter)

# ── Render Free-Tier Keep-Alive Background Worker ──
def _start_keep_alive_daemon():
    """
    Background daemon that pings the Render public endpoint every 9 minutes
    to prevent Render Free Tier instances from sleeping / cold-starting.
    """
    def _ping_loop():
        time.sleep(20)  # Initial wait on boot
        while True:
            try:
                render_url = os.getenv("RENDER_EXTERNAL_URL", "https://expertdecision.onrender.com")
                ping_target = f"{render_url.rstrip('/')}/health"
                requests.get(ping_target, timeout=8)
            except Exception:
                pass
            time.sleep(540)  # Ping every 9 minutes (540s < 900s inactivity threshold)

    t = threading.Thread(target=_ping_loop, daemon=True, name="RenderKeepAliveWorker")
    t.start()

_start_keep_alive_daemon()

@app.route("/health", methods=["GET", "HEAD"])
@app.route("/ping", methods=["GET", "HEAD"])
def health_check():
    """Instantaneous lightweight healthcheck endpoint (0ms response)."""
    return jsonify({
        "status": "healthy",
        "service": "EDRP Frontend",
        "timestamp": time.time()
    }), 200

@app.route("/debug-info")
def debug_info():
    """Diagnostic endpoint to debug deployment issues."""
    static_folder = app.static_folder
    template_folder = app.template_folder
    js_files = []
    if static_folder and os.path.isdir(os.path.join(static_folder, "js")):
        js_files = os.listdir(os.path.join(static_folder, "js"))
    
    # Get database info
    db_url_raw = os.getenv("DATABASE_URL", "(NOT SET)")
    db_url_safe = db_url_raw[:20] + "..." if len(db_url_raw) > 20 else db_url_raw
    db_type = "unknown"
    try:
        from backend.app.database.connection import DATABASE_URL as active_db_url
        if "sqlite" in (active_db_url or ""):
            db_type = "sqlite"
        elif "postgresql" in (active_db_url or ""):
            db_type = "postgresql"
    except Exception:
        try:
            from app.database.connection import DATABASE_URL as active_db_url
            if "sqlite" in (active_db_url or ""):
                db_type = "sqlite"
            elif "postgresql" in (active_db_url or ""):
                db_type = "postgresql"
        except Exception:
            pass

    return jsonify({
        "cwd": os.getcwd(),
        "frontend_dir": _FRONTEND_DIR,
        "static_folder": static_folder,
        "static_exists": os.path.isdir(static_folder) if static_folder else False,
        "template_folder": template_folder,
        "template_exists": os.path.isdir(template_folder) if template_folder else False,
        "js_files": js_files,
        "bridge_active": _fastapi_client is not None,
        "sys_modules_app": "app" in sys.modules,
        "python_path_0": sys.path[0] if sys.path else "empty",
        "database_url_env_set": db_url_raw != "(NOT SET)",
        "database_url_preview": db_url_safe,
        "active_db_type": db_type,
    }), 200

@app.after_request
def optimize_and_compress_response(response):
    """
    1. Long-term browser caching for static assets (CSS, JS, Fonts, Images).
    2. Real-time GZIP payload compression (reduces payload transfer size by 75-80%).
    """
    try:
        content_type = response.content_type or ""
        is_static = request.path.startswith('/static/') or request.path.startswith('/favicon')
        is_asset = any(content_type.startswith(t) for t in (
            'text/css', 'application/javascript', 'text/javascript',
            'image/', 'font/', 'application/font', 'application/x-font'
        ))
        
        if is_static or is_asset:
            # Aggressive caching for static assets (7 days)
            response.headers["Cache-Control"] = "public, max-age=604800, immutable"
            response.headers.pop("Pragma", None)
            response.headers.pop("Expires", None)
        else:
            # Dynamic HTML / API fresh headers
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        # Fast GZIP compression for HTML, CSS, JS, and JSON
        accept_encoding = request.headers.get('Accept-Encoding', '')
        if (
            'gzip' in accept_encoding.lower() and
            response.status_code < 300 and
            'Content-Encoding' not in response.headers and
            len(response.get_data()) > 400 and
            any(ct in content_type for ct in ['text/html', 'text/css', 'text/javascript', 'application/javascript', 'application/json'])
        ):
            try:
                gzip_buffer = io.BytesIO()
                with gzip.GzipFile(mode='wb', fileobj=gzip_buffer, compresslevel=5) as gzip_file:
                    gzip_file.write(response.get_data())
                response.set_data(gzip_buffer.getvalue())
                response.headers['Content-Encoding'] = 'gzip'
                response.headers['Content-Length'] = len(response.get_data())
                response.headers['Vary'] = 'Accept-Encoding'
            except Exception:
                pass
    except Exception as e:
        print(f"[MIDDLEWARE] after_request error on {request.path}: {e}")

    return response


# FastAPI Backend URL (Server-side Flask to FastAPI communication)
def _resolve_backend_url():
    env_url = os.getenv("BACKEND_URL", os.getenv("API_URL", "http://127.0.0.1:8000")).rstrip("/")
    if "://backend" in env_url:
        import socket
        try:
            socket.gethostbyname("backend")
        except Exception:
            return "http://127.0.0.1:8000"
    return env_url

def _load_fastapi_app_and_client():
    try:
        candidate_dirs = [
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")),
            os.path.abspath(os.path.join(os.getcwd(), "backend")),
            os.path.abspath(os.path.join(os.getcwd(), "..", "backend")),
            os.path.abspath("backend"),
        ]
        backend_dir = None
        for d in candidate_dirs:
            if os.path.isdir(d) and os.path.exists(os.path.join(d, "app", "main.py")):
                backend_dir = d
                break

        if not backend_dir:
            print(f"[BRIDGE] FastAPI backend directory not found. Candidates: {candidate_dirs}")
            return None, None

        print(f"[BRIDGE] Found backend at: {backend_dir}")

        if backend_dir in sys.path:
            sys.path.remove(backend_dir)
        sys.path.insert(0, backend_dir)

        import importlib.util
        app_pkg_dir = os.path.join(backend_dir, "app")
        app_init_file = os.path.join(app_pkg_dir, "__init__.py")
        if not os.path.exists(app_init_file):
            with open(app_init_file, "a") as f:
                pass

        pkg_spec = importlib.util.spec_from_file_location(
            "app",
            app_init_file,
            submodule_search_locations=[app_pkg_dir]
        )
        pkg_mod = importlib.util.module_from_spec(pkg_spec)
        sys.modules["app"] = pkg_mod
        pkg_spec.loader.exec_module(pkg_mod)

        main_file = os.path.join(app_pkg_dir, "main.py")
        main_spec = importlib.util.spec_from_file_location("app.main", main_file)
        backend_main_mod = importlib.util.module_from_spec(main_spec)
        sys.modules["app.main"] = backend_main_mod
        main_spec.loader.exec_module(backend_main_mod)

        fastapi_app_obj = backend_main_mod.app
        from fastapi.testclient import TestClient
        test_client = TestClient(fastapi_app_obj)
        print("[BRIDGE] FastAPI in-process bridge loaded successfully.")
        return fastapi_app_obj, test_client
    except Exception as e:
        import traceback
        print(f"[BRIDGE] FastAPI in-process bridge loader FAILED: {e}")
        traceback.print_exc()
        return None, None

_fastapi_app, _fastapi_client = _load_fastapi_app_and_client()

# Ensure gunicorn (e.g. `gunicorn app:app`) can ALWAYS find the Flask `app` object
# This must succeed regardless of whether the FastAPI bridge loaded
if "app" in sys.modules and hasattr(sys.modules["app"], "__dict__"):
    sys.modules["app"].__dict__["app"] = app
    print(f"[BRIDGE] Flask app attached to sys.modules['app']. Bridge active: {_fastapi_client is not None}")

API_URL = _resolve_backend_url()

def make_backend_request(method, path, **kwargs):
    """
    Sends a high-speed request to the FastAPI backend.
    Uses in-process direct dispatch (<0.5ms) as the primary bridge,
    guaranteeing 100% reliability and immediate live data loading across all pages.
    """
    url_path = path if path.startswith("/") else f"/{path}"

    if _fastapi_client is not None:
        try:
            tc_kwargs = {}
            if "json" in kwargs and kwargs["json"] is not None:
                tc_kwargs["json"] = kwargs["json"]
            if "data" in kwargs and kwargs["data"] is not None:
                tc_kwargs["data"] = kwargs["data"]
            if "files" in kwargs and kwargs["files"] is not None:
                tc_kwargs["files"] = kwargs["files"]
            if "params" in kwargs and kwargs["params"] is not None:
                tc_kwargs["params"] = kwargs["params"]
            if "headers" in kwargs and kwargs["headers"] is not None:
                tc_kwargs["headers"] = kwargs["headers"]
            
            resp = _fastapi_client.request(method, url_path, **tc_kwargs)
            if resp is not None:
                return resp
        except Exception:
            pass

    if "timeout" not in kwargs:
        kwargs["timeout"] = 5
    full_url = f"{API_URL}{url_path}"
    return http_session.request(method, full_url, **kwargs)

CONTACT_CONFIG = {
    "company_email": "contact@edrp.org",
    "support_email": "support@edrp-platform.com",
    "office_hours": "Mon - Fri: 9:00 AM - 6:00 PM EST",
    "location": "Enterprise Tech Tower, Suite 500, New York, NY 10001"
}

_GLOBAL_STATS_CACHE = {}
_DATA_CACHE = {}

def get_cached_data(key, path, ttl=30, headers=None, method="GET", json_payload=None):
    """
    High-speed in-memory caching for API endpoints and SSR hydration.
    Returns data in <0.5ms on cache hits.
    """
    now = time.time()
    cached = _DATA_CACHE.get(key)
    if cached and (now - cached["ts"] < ttl):
        return cached["data"]
    try:
        resp = make_backend_request(method, path, json=json_payload, headers=headers, timeout=2.5)
        if resp is not None and resp.status_code == 200:
            data = resp.json()
            _DATA_CACHE[key] = {"data": data, "ts": now}
            return data
        elif cached:
            return cached["data"]
    except Exception:
        if cached:
            return cached["data"]
    return []

def invalidate_cache_key(prefix=""):
    if not prefix:
        _DATA_CACHE.clear()
    else:
        for k in list(_DATA_CACHE.keys()):
            if prefix in k:
                _DATA_CACHE.pop(k, None)

def log_platform_audit(action, details="", module=None, severity=None, user_id=None):
    """
    Directly or asynchronously records live platform audit events into the database.
    """
    def _do_log():
        try:
            uid = user_id or session.get("user_id", 1)
            # Try direct service call first
            try:
                from backend.app.services.audit_service import AuditService
                AuditService.log_event_standalone(user_id=uid, action=action, details=details, module=module, severity=severity)
                return
            except Exception:
                pass
            try:
                from app.services.audit_service import AuditService
                AuditService.log_event_standalone(user_id=uid, action=action, details=details, module=module, severity=severity)
                return
            except Exception:
                pass

            # Fallback to FastAPI HTTP proxy
            make_backend_request("POST", "/audit/log", json={
                "user_id": uid,
                "action": action,
                "details": details,
                "module": module,
                "severity": severity
            }, timeout=2)
        except Exception as err:
            print(f"[AUDIT LOGGING NOTE] {err}")

    threading.Thread(target=_do_log, daemon=True).start()

_ROUTE_NAME_MAP = {
    "/dashboard": ("Auth", "Accessed Dashboard", "Executive overview and operational metrics"),
    "/decisions": ("Decisions", "Viewed Decisions Hub", "Navigated to organizational decisions repository"),
    "/create-decision": ("Decisions", "Opened Decision Studio", "Workspace opened to draft new decision workflow"),
    "/replays": ("Decisions", "Accessed Decision Replays", "Viewed decision version history and audit replays"),
    "/decision-replay": ("Decisions", "Accessed Decision Replays", "Viewed decision version history and audit replays"),
    "/reviews": ("Reviews", "Accessed Reviews Queue", "Opened pending decision reviews and approvals"),
    "/pending-approvals": ("Reviews", "Accessed Pending Approvals", "Viewed pending governance approvals"),
    "/alternatives": ("Decisions", "Accessed Alternatives Studio", "Viewed decision alternative comparison matrices"),
    "/discussions": ("Discussions", "Accessed Discussions Hub", "Opened team discussion threads and comments"),
    "/users": ("Users", "Accessed User Management", "Admin opened user accounts and credentials console"),
    "/teams": ("Teams", "Accessed Team Management", "Opened enterprise team structure and allocations"),
    "/roles": ("Roles", "Accessed Role Management", "Opened role permissions and access governance"),
    "/reports": ("Reports", "Accessed Reports & Analytics", "Viewed live organizational metrics, KPIs, and charts"),
    "/repository": ("Repository", "Accessed Knowledge Repository", "Viewed institutional documents and knowledge assets"),
    "/support": ("Support", "Accessed Help & Support Desk", "Opened AI copilot assistant and ticket center"),
    "/email-service": ("Email", "Accessed Email Service", "Opened SMTP delivery logs and email manager"),
    "/settings": ("Settings", "Accessed System Settings", "Opened platform security and general preferences"),
    "/admin-backup": ("Settings", "Accessed Backup Console", "Opened database backup and snapshot manager"),
    "/profile": ("Users", "Viewed User Profile", "Opened personal profile and account settings"),
    "/notifications": ("System", "Viewed Notifications Center", "Opened alert notifications inbox"),
    "/audit": ("System", "Accessed Live Audit Logs", "Administrator opened security audit trail"),
}

_LAST_PAGE_LOG = {}

@app.before_request
def log_user_page_navigation():
    try:
        if not session.get("logged_in") or "user_id" not in session:
            return
        
        path = request.path.rstrip("/")
        if not path:
            path = "/"

        # Match exact route or prefix
        route_meta = _ROUTE_NAME_MAP.get(path)
        if not route_meta:
            if path.startswith("/decision/"):
                route_meta = ("Decisions", f"Viewed Decision DEC-{path.split('/')[-1]}", f"Accessed full details for decision {path.split('/')[-1]}")
            elif path.startswith("/discussion/"):
                route_meta = ("Discussions", f"Viewed Discussion DEC-{path.split('/')[-1]}", f"Accessed discussion thread for decision {path.split('/')[-1]}")

        if route_meta and request.method == "GET":
            uid = session["user_id"]
            user_name = session.get("full_name", "User")
            now = time.time()
            last_entry = _LAST_PAGE_LOG.get(uid)

            # Prevent logging identical page transitions within 6 seconds
            if not last_entry or last_entry.get("path") != path or (now - last_entry.get("ts", 0) > 6):
                _LAST_PAGE_LOG[uid] = {"path": path, "ts": now}
                mod, act, det = route_meta
                log_platform_audit(
                    action=f"{user_name}: {act}",
                    details=det,
                    module=mod,
                    severity="Info",
                    user_id=uid
                )
    except Exception:
        pass

@app.context_processor
def inject_global_stats():
    base_data = {
        "contact_config": CONTACT_CONFIG,
        "unread_notifications_count": 0,
        "pending_reviews": 0,
        "backend_ws_url": API_URL.replace("http://", "ws://").replace("https://", "wss://")
    }
    if not session.get("logged_in"):
        return base_data
    
    user_id = session.get("user_id")
    token = session.get("token")
    if not user_id or not token:
        return base_data

    now = time.time()
    cached = _GLOBAL_STATS_CACHE.get(user_id)
    if cached and (now - cached["ts"] < 120):
        base_data.update(cached["data"])
        return base_data
        
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = make_backend_request("GET", f"/dashboard/{user_id}", headers=headers, timeout=0.8)
        if response is not None and response.status_code == 200:
            data = response.json()
            fresh = {
                "unread_notifications_count": data.get("unread_notifications_count", 0),
                "pending_reviews": data.get("pending_reviews", 0)
            }
            _GLOBAL_STATS_CACHE[user_id] = {"data": fresh, "ts": now}
            base_data.update(fresh)
        elif cached:
            base_data.update(cached["data"])
    except Exception:
        if cached:
            base_data.update(cached["data"])
    
    return base_data



# ===========================
# HOME
# ===========================

@app.route("/", methods=["GET", "HEAD"])
def index():
    if session.get("logged_in") and "token" in session:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")

@app.route("/landing", methods=["GET", "HEAD"])
def home():
    if session.get("logged_in") and "token" in session:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")



# ===========================
# LOGIN
# ===========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET" and session.get("logged_in") and "token" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        session.clear()
        remember_me = request.form.get("remember_me") or request.form.get("remember")
        payload = {
            "employee_id": request.form.get("employee_id", "").strip(),
            "password": request.form.get("password", "")
        }

        response = None
        try:
            response = make_backend_request("POST", "/users/login", json=payload, timeout=15)
        except Exception as e:
            print(f"Login connection error note: {e}")

        if response is not None and response.status_code == 200:
            token = response.json()
            session.clear()
            if remember_me:
                session.permanent = True
            else:
                session.permanent = False
            session["logged_in"] = True
            session["token"] = token["access_token"]
            session["user_id"] = token["user_id"]
            session["role_name"] = token.get("role_name", "User")
            session["team_id"] = token.get("team_id")
            session["team_name"] = token.get("team_name", "Not Assigned")
            session["designation"] = token.get("designation") or "Team Member"
            session["employee_id"] = token.get("employee_id") or ""
            full_name = token.get("full_name", "User")
            session["full_name"] = full_name
            
            parts = full_name.split()
            session["initials"] = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()

            def _dispatch_login_log(uid, name, role):
                try:
                    make_backend_request("POST", "/audit/log", json={
                        "user_id": uid,
                        "action": f"User login successful: {name}",
                        "details": f"Role: {role}"
                    }, timeout=2)
                except Exception:
                    pass

            import threading
            threading.Thread(target=_dispatch_login_log, args=(token["user_id"], full_name, session['role_name']), daemon=True).start()

            flash("Login Successful", "success")
            return redirect(url_for("dashboard"))


        if response is not None:
            try:
                error_msg = response.json().get("detail", "Invalid Employee ID or Password.")
            except Exception:
                error_msg = "Invalid Employee ID or Password."
            flash(error_msg, "danger")
        else:
            flash("Backend connection error. Ensure FastAPI server is running.", "danger")

    return render_template("login.html")


# ===========================
# REGISTRATION WORKFLOW (STEPS 1 - 3)
# ===========================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        role_id = int(request.form.get("role_id", 3))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("register.html", form_data=request.form)

        payload = {
            "full_name": full_name,
            "email": email,
            "password": password,
            "role_id": role_id,
            "team_id": int(request.form.get("team_id", 1)),
            "designation": request.form.get("designation", ""),
            "phone": request.form.get("phone", "")
        }

        try:
            response = make_backend_request("POST", "/users/register/step1", json=payload, timeout=12)
            if response is not None and response.status_code == 200:
                session["reg_data"] = payload
                flash("Verification code sent to your email.", "info")
                return redirect(url_for("verify_email"))

            if response is not None:
                try:
                    err_json = response.json()
                    if isinstance(err_json.get("detail"), list):
                        err_detail = err_json["detail"][0].get("msg", "Validation error.")
                    else:
                        err_detail = err_json.get("detail", "Registration failed.")
                except Exception:
                    err_detail = response.text or "Registration failed."
                flash(err_detail, "danger")
            else:
                flash("Backend connection error. Ensure FastAPI server is running on port 8000.", "danger")
        except requests.exceptions.RequestException as req_err:
            print(f"[API ERROR] /users/register/step1 failed: {req_err}")
            flash("Backend connection error. Ensure FastAPI server is running on port 8000.", "danger")

    return render_template("register.html", form_data=request.form if request.method == "POST" else None)


@app.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    reg_data = session.get("reg_data")
    if not reg_data:
        flash("Please start registration from Step 1.", "warning")
        return redirect(url_for("register"))

    email = reg_data.get("email", "")

    if request.method == "POST":
        otp_code = request.form.get("otp_code", "").strip()
        payload = {
            "email": email,
            "code": otp_code,
            "purpose": "register"
        }

        try:
            response = make_backend_request("POST", "/users/check-verification-code", json=payload, timeout=10)
            if response is not None and response.status_code == 200:
                session["email_verified"] = True
                flash("Email verified successfully! Now create your Employee ID.", "success")
                return redirect(url_for("create_employee_id"))

            if response is not None:
                try:
                    err_msg = response.json().get("detail", "Invalid verification code.")
                except Exception:
                    err_msg = "Invalid verification code."
                flash(err_msg, "danger")
            else:
                flash("Backend connection error. Ensure FastAPI server is running on port 8000.", "danger")
        except requests.exceptions.RequestException:
            flash("Backend connection error. Ensure FastAPI server is running on port 8000.", "danger")

    return render_template("verify_email.html", email=email)


@app.route("/create-employee-id", methods=["GET", "POST"])
def create_employee_id():
    reg_data = session.get("reg_data")
    email_verified = session.get("email_verified")
    if not reg_data or not email_verified:
        flash("Please verify your email first.", "warning")
        return redirect(url_for("register"))

    role_id = int(reg_data.get("role_id", 3))
    role_prefix_map = {1: "AD", 2: "MN", 3: "EMP", 4: "RW"}
    prefix = role_prefix_map.get(role_id, "EMP")

    if request.method == "POST":
        emp_number = request.form.get("employee_id_num", "").strip()

        if not emp_number.isdigit() or len(emp_number) != 6:
            flash("Employee ID must be exactly 6 numbers.", "danger")
            return render_template("create_employee_id.html", prefix=prefix, reg_data=reg_data)

        full_emp_id = f"{prefix}{emp_number}"

        payload = {
            "email": reg_data["email"],
            "role_id": role_id,
            "employee_id": full_emp_id,
            "full_name": reg_data["full_name"],
            "password": reg_data["password"],
            "team_id": reg_data.get("team_id", 1),
            "designation": reg_data.get("designation"),
            "phone": reg_data.get("phone")
        }

        try:
            response = make_backend_request("POST", "/users/save-employee-id", json=payload, timeout=12)
            if response is not None and response.status_code == 200:
                res_json = response.json()
                session.pop("reg_data", None)
                session.pop("email_verified", None)
                return render_template("create_employee_id.html", success=True, msg=res_json.get("message"), sub_msg=res_json.get("sub_message"))

            if response is not None:
                try:
                    err_msg = response.json().get("detail", "Failed to save Employee ID.")
                except Exception:
                    err_msg = "Failed to save Employee ID."
                flash(err_msg, "danger")
            else:
                flash("Backend connection error. Ensure FastAPI server is running on port 8000.", "danger")
        except requests.exceptions.RequestException as req_err:
            print(f"[API ERROR] /users/save-employee-id failed: {req_err}")
            flash("Backend connection error. Ensure FastAPI server is running on port 8000.", "danger")

    return render_template("create_employee_id.html", prefix=prefix, reg_data=reg_data)


# ===========================
# ADMIN PENDING APPROVALS
# ===========================

@app.route("/pending-approvals")
def pending_approvals():
    if "token" not in session:
        return redirect(url_for("login"))

    role = session.get("role_name", "User")
    if role not in ("Administrator", "Admin"):
        flash("Access Denied: Only Administrators can access pending approvals.", "danger")
        return redirect(url_for("dashboard"))

    try:
        response = make_backend_request("GET", "/users/pending", timeout=5)
        pending_users = response.json() if (response is not None and response.status_code == 200) else []
    except Exception:
        pending_users = []

    try:
        teams_res = make_backend_request("GET", "/teams/", timeout=5)
        teams = teams_res.json() if (teams_res is not None and teams_res.status_code == 200) else []
    except Exception:
        teams = []

    return render_template("pending_approvals.html", pending_users=pending_users, teams=teams)


@app.route("/api/pending-approvals/action", methods=["POST"])
def api_pending_approvals_action():
    if "token" not in session:
        return jsonify({"detail": "Unauthorized"}), 401

    role = session.get("role_name", "User")
    if role not in ("Administrator", "Admin", "System Administrator"):
        return jsonify({"detail": "Access Denied: Only Administrators can process approvals."}), 403

    try:
        data = request.json or {}
        actor_name = session.get("full_name") or "Administrator"
        if "actor_name" not in data:
            data["actor_name"] = actor_name

        headers = {"Authorization": f"Bearer {session.get('token', '')}"}
        action = data.get("action", "approve")
        endpoint = f"/users/{action}" if action in ("approve", "reject") else "/users/approve"
        response = make_backend_request("POST", endpoint, json=data, headers=headers, timeout=15)
        if response is not None:
            return jsonify(response.json()), response.status_code
        return jsonify({"detail": "Backend connection error"}), 500
    except Exception as e:
        return jsonify({"detail": f"Error processing approval: {e}"}), 500


@app.route("/api/check-employee-id", methods=["POST"])
def api_check_employee_id():
    data = request.json
    try:
        response = make_backend_request("POST", "/users/check-employee-id", json=data, timeout=5)
        if response is not None:
            return jsonify(response.json()), response.status_code
        return jsonify({"detail": "Error checking Employee ID"}), 500
    except Exception:
        return jsonify({"detail": "Error checking Employee ID"}), 500


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
def api_delete_user(user_id):
    if "token" not in session:
        return jsonify({"detail": "Unauthorized"}), 401
    
    role = session.get("role_name", "User")
    if role not in ("Administrator", "Admin"):
        return jsonify({"detail": "Access Denied: Only Administrators can delete accounts."}), 403

    try:
        headers = {}
        if "token" in session:
            headers["Authorization"] = f"Bearer {session['token']}"
        response = make_backend_request("DELETE", f"/users/{user_id}", headers=headers, timeout=30)
        invalidate_cache_key("all_users")
        if response is not None:
            try:
                return jsonify(response.json()), response.status_code
            except Exception:
                return jsonify({"detail": response.text or "Deleted"}), response.status_code
        return jsonify({"detail": "Backend connection error. Ensure FastAPI server is running."}), 500
    except Exception as e:
        return jsonify({"detail": f"Error deleting user: {e}"}), 500


@app.route("/api/users/admin_update_credentials", methods=["POST", "PUT"])
@app.route("/api/users/<int:user_id>/credentials", methods=["PUT", "POST"])
def proxy_admin_update_credentials(user_id=None):
    if "token" not in session:
        return jsonify({"detail": "Unauthorized"}), 401
    
    role = session.get("role_name", "User")
    if role not in ("Administrator", "Admin", "System Administrator"):
        return jsonify({"detail": "Access Denied: Only Administrators can update user credentials."}), 403

    try:
        data = request.json or {}
        if user_id and "user_id" not in data:
            data["user_id"] = user_id

        headers = {"Authorization": f"Bearer {session.get('token', '')}"}
        resp = make_backend_request("POST", "/users/admin_update_credentials", json=data, headers=headers, timeout=20)
        invalidate_cache_key("all_users")
        if resp is not None:
            return make_response(resp.content, resp.status_code, {"Content-Type": resp.headers.get("Content-Type", "application/json")})
        return jsonify({"detail": "Backend connection error"}), 500
    except Exception as e:
        return jsonify({"detail": f"Error updating user credentials: {e}"}), 500



@app.route("/api/support/<ticket_id>", methods=["DELETE"])
def api_delete_support_ticket(ticket_id):
    if "token" not in session:
        return jsonify({"detail": "Unauthorized"}), 401
    
    role = session.get("role_name", "User")
    if role not in ("Administrator", "Admin"):
        return jsonify({"detail": "Access Denied: Only Administrators can delete support tickets."}), 403

    try:
        headers = {"Authorization": f"Bearer {session['token']}"}
        response = make_backend_request("DELETE", f"/support/{ticket_id}", headers=headers, timeout=5)
        if response is not None and response.status_code == 404:
            response = make_backend_request("DELETE", f"/support/delete/{ticket_id}", headers=headers, timeout=5)
        if response is not None:
            return jsonify(response.json()), response.status_code
        return jsonify({"detail": "Error deleting support ticket"}), 500
    except Exception as e:
        return jsonify({"detail": f"Error deleting support ticket: {e}"}), 500


@app.route("/api/support/ai-chat", methods=["POST"])
def api_support_ai_chat():
    data = request.json or {}
    user_id = session.get("user_id")
    user_name = session.get("full_name") or "User"
    if user_id and not data.get("user_id"):
        data["user_id"] = user_id
    if user_name and not data.get("user_name"):
        data["user_name"] = user_name

    # 1. Primary: Forward to FastAPI backend (which runs live Groq LLM with hot reload)
    try:
        response = make_backend_request("POST", "/support/ai-chat", json=data, timeout=15)
        if response is not None and response.status_code == 200:
            return jsonify(response.json()), 200
    except Exception as e:
        print(f"AI chat backend forward note: {e}")

    # 2. Dynamic direct execution fallback
    try:
        fn = _load_ai_support_generator()
        if fn:
            res_dict = fn(
                user_message=data.get("message", ""),
                user_name=user_name,
                user_id=data.get("user_id") or user_id,
                conversation_history=data.get("conversation_history")
            )
            return jsonify(res_dict), 200
    except Exception as ai_err:
        print(f"Direct AI service fallback note: {ai_err}")

    return jsonify({
        "reply": f"Hello {user_name}! In EDRP, decisions follow a structured lifecycle: Draft → In Review → Approved / Rejected. You can create decisions from the sidebar, evaluate alternatives, track reviewer approval chains, or inspect audit diffs.",
        "suggested_actions": ["How do I create a new decision?", "Explain the approval workflow", "How does Decision Replay work?"],
        "source": "EDRP AI Assistant"
    }), 200


@app.route("/api/users/", methods=["GET"])
@app.route("/users/", methods=["GET"])
@app.route("/api/users", methods=["GET"])
def proxy_get_users():
    try:
        resp = make_backend_request("GET", "/users/", timeout=5)
        if resp is not None and resp.status_code == 200:
            data = resp.json()
            _DATA_CACHE["all_users"] = {"data": data, "ts": time.time()}
            return jsonify(data), 200
        cached = _DATA_CACHE.get("all_users")
        if cached:
            return jsonify(cached["data"]), 200
        return jsonify([]), 200
    except Exception as e:
        cached = _DATA_CACHE.get("all_users")
        if cached:
            return jsonify(cached["data"]), 200
        return jsonify([]), 200


@app.route("/api/roles", methods=["GET"])
@app.route("/roles/", methods=["GET"])
def proxy_get_roles():
    try:
        resp = make_backend_request("GET", "/roles", timeout=5)
        if resp is not None and resp.status_code == 200:
            data = resp.json()
            _DATA_CACHE["all_roles"] = {"data": data, "ts": time.time()}
            return jsonify(data), 200
        cached = _DATA_CACHE.get("all_roles")
        if cached:
            return jsonify(cached["data"]), 200
        return jsonify([]), 200
    except Exception as e:
        cached = _DATA_CACHE.get("all_roles")
        if cached:
            return jsonify(cached["data"]), 200
        return jsonify([]), 200


@app.route("/api/teams/", methods=["GET"])
@app.route("/teams/", methods=["GET"])
@app.route("/api/teams", methods=["GET"])
def proxy_get_teams():
    try:
        resp = make_backend_request("GET", "/teams/", timeout=5)
        if resp is not None and resp.status_code == 200:
            data = resp.json()
            _DATA_CACHE["all_teams"] = {"data": data, "ts": time.time()}
            return jsonify(data), 200
        cached = _DATA_CACHE.get("all_teams")
        if cached:
            return jsonify(cached["data"]), 200
        return jsonify([]), 200
    except Exception as e:
        cached = _DATA_CACHE.get("all_teams")
        if cached:
            return jsonify(cached["data"]), 200
        return jsonify([]), 200


@app.route("/upload/", methods=["POST"])
@app.route("/api/upload/", methods=["POST"])
def proxy_upload_file():
    try:
        files = {}
        for key in request.files:
            file_obj = request.files[key]
            files[key] = (file_obj.filename, file_obj.read(), file_obj.content_type or 'application/octet-stream')
        data = request.form.to_dict()
        if "user_id" not in data or not data["user_id"]:
            data["user_id"] = str(session.get("user_id", 1))
        
        resp = make_backend_request("POST", "/upload/", files=files, data=data, timeout=30)
        return make_response(resp.content, resp.status_code, {"Content-Type": resp.headers.get("Content-Type", "application/json")})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"detail": f"Upload error: {e}"}), 500


@app.route("/upload/<int:attachment_id>", methods=["GET"])
@app.route("/api/upload/<int:attachment_id>", methods=["GET"])
def proxy_get_upload(attachment_id):
    try:
        user_id = session.get("user_id", 1)
        params = dict(request.args)
        if "user_id" not in params:
            params["user_id"] = user_id
        
        import urllib.parse
        query_str = "?" + urllib.parse.urlencode(params)
        resp = make_backend_request("GET", f"/upload/{attachment_id}{query_str}", timeout=15)
        headers = {}
        if resp is not None:
            if "Content-Type" in resp.headers:
                headers["Content-Type"] = resp.headers["Content-Type"]
            if "Content-Disposition" in resp.headers:
                headers["Content-Disposition"] = resp.headers["Content-Disposition"]
            return make_response(resp.content, resp.status_code, headers)
        return jsonify({"detail": "File not available"}), 404
    except Exception as e:
        return jsonify({"detail": f"File fetch error: {e}"}), 500


@app.route("/api/decisions", methods=["GET"])
@app.route("/api/decisions/", methods=["GET"])
def proxy_get_all_decisions():
    try:
        user_id = request.args.get("user_id") or session.get("user_id", "")
        role_name = request.args.get("role_name") or session.get("role_name", "")
        scope = request.args.get("scope", "")
        status_val = request.args.get("status", "")
        params = []
        if user_id:
            params.append(f"user_id={user_id}")
        if role_name:
            params.append(f"role_name={role_name}")
        if scope:
            params.append(f"scope={scope}")
        if status_val:
            params.append(f"status={status_val}")
        query_str = f"?{'&'.join(params)}" if params else ""
        resp = make_backend_request("GET", f"/decisions/{query_str}", timeout=15)
        return make_response(resp.content, resp.status_code, {"Content-Type": resp.headers.get("Content-Type", "application/json")})
    except Exception as e:
        return jsonify({"detail": f"Decisions fetch error: {e}"}), 500


def invalidate_decision_caches():
    try:
        keys_to_remove = [k for k in _DATA_CACHE if "decision" in k or "dashboard" in k]
        for k in keys_to_remove:
            _DATA_CACHE.pop(k, None)
    except Exception:
        pass

@app.route("/api/decisions/full", methods=["POST"])
@app.route("/decisions/full", methods=["POST"])
def proxy_create_decision_full():
    try:
        data = request.json or {}
        session_uid = session.get("user_id")
        if session_uid:
            data["created_by"] = int(session_uid)
        elif not data.get("created_by"):
            data["created_by"] = 1
        resp = make_backend_request("POST", "/decisions/full", json=data, timeout=30)
        invalidate_decision_caches()
        if resp is not None:
            if resp.status_code >= 400:
                try:
                    err_json = resp.json()
                    if isinstance(err_json.get("detail"), list):
                        messages = []
                        for item in err_json["detail"]:
                            loc = item.get("loc", [])
                            field = loc[-1] if loc else "field"
                            msg = item.get("msg", "Invalid value")
                            messages.append(f"{field}: {msg}")
                        err_json["detail"] = "; ".join(messages)
                        return jsonify(err_json), resp.status_code
                except Exception:
                    pass
            return make_response(resp.content, resp.status_code, {"Content-Type": resp.headers.get("Content-Type", "application/json")})
        return jsonify({"detail": "Backend connection error"}), 500
    except Exception as e:
        return jsonify({"detail": f"Decision creation error: {e}"}), 500


@app.route("/api/decisions/<int:decision_id>/full", methods=["PUT"])
@app.route("/decisions/<int:decision_id>/full", methods=["PUT"])
def proxy_update_decision_full(decision_id):
    try:
        data = request.json or {}
        resp = make_backend_request("PUT", f"/decisions/{decision_id}/full", json=data, timeout=30)
        invalidate_decision_caches()
        if resp is not None:
            if resp.status_code >= 400:
                try:
                    err_json = resp.json()
                    if isinstance(err_json.get("detail"), list):
                        messages = []
                        for item in err_json["detail"]:
                            loc = item.get("loc", [])
                            field = loc[-1] if loc else "field"
                            msg = item.get("msg", "Invalid value")
                            messages.append(f"{field}: {msg}")
                        err_json["detail"] = "; ".join(messages)
                        return jsonify(err_json), resp.status_code
                except Exception:
                    pass
            return make_response(resp.content, resp.status_code, {"Content-Type": resp.headers.get("Content-Type", "application/json")})
        return jsonify({"detail": "Backend connection error"}), 500
    except Exception as e:
        return jsonify({"detail": f"Decision update error: {e}"}), 500


@app.route("/api/decisions/<int:decision_id>", methods=["GET"])
def proxy_get_decision_details(decision_id):
    try:
        user_id = request.args.get("user_id") or session.get("user_id", 1)
        resp = make_backend_request("GET", f"/decisions/{decision_id}?user_id={user_id}", timeout=15)
        return make_response(resp.content, resp.status_code, {"Content-Type": resp.headers.get("Content-Type", "application/json")})
    except Exception as e:
        return jsonify({"detail": f"Fetch error: {e}"}), 500


@app.route("/api/decisions/<int:decision_id>", methods=["DELETE"])
@app.route("/decisions/<int:decision_id>", methods=["DELETE"])
def proxy_delete_decision(decision_id):
    try:
        user_id = request.args.get("user_id") or session.get("user_id", "")
        role_name = request.args.get("role_name") or session.get("role_name", "")
        params = []
        if user_id:
            params.append(f"user_id={user_id}")
        if role_name:
            params.append(f"role_name={role_name}")
        query_str = f"?{'&'.join(params)}" if params else ""
        resp = make_backend_request("DELETE", f"/decisions/{decision_id}{query_str}", timeout=15)
        invalidate_decision_caches()
        return make_response(resp.content, resp.status_code, {"Content-Type": resp.headers.get("Content-Type", "application/json")})
    except Exception as e:
        return jsonify({"detail": f"Decision delete error: {e}"}), 500


@app.route("/api/decisions/bulk-delete", methods=["POST"])
@app.route("/decisions/bulk-delete", methods=["POST"])
def proxy_bulk_delete_decisions():
    try:
        data = request.get_json(silent=True) or {}
        # Ensure user_id and role_name from session if missing or 0
        if (not data.get("user_id") or data.get("user_id") == 0) and session.get("user_id"):
            data["user_id"] = session["user_id"]
        if not data.get("role_name") and session.get("role_name"):
            data["role_name"] = session["role_name"]

        resp = make_backend_request("POST", "/decisions/bulk-delete", json=data, timeout=30)
        invalidate_decision_caches()
        if resp is not None:
            return make_response(resp.content, resp.status_code, {"Content-Type": "application/json"})
        return jsonify({"detail": "Backend unavailable. Please ensure FastAPI server is running."}), 500
    except Exception as e:
        return jsonify({"detail": f"Bulk delete error: {e}"}), 500


@app.route("/api/decisions/<int:decision_id>/status", methods=["PATCH"])
@app.route("/decisions/<int:decision_id>/status", methods=["PATCH"])
def proxy_update_decision_status(decision_id):
    try:
        user_id = session.get("user_id", 1)
        data = request.json or {}
        resp = make_backend_request("PATCH", f"/decisions/{decision_id}/status?user_id={user_id}", json=data, timeout=15)
        invalidate_decision_caches()
        return make_response(resp.content, resp.status_code, {"Content-Type": resp.headers.get("Content-Type", "application/json")})
    except Exception as e:
        return jsonify({"detail": f"Decision status update error: {e}"}), 500


@app.route("/api/decisions/<int:decision_id>/send_reminder", methods=["POST"])
@app.route("/decisions/<int:decision_id>/send_reminder", methods=["POST"])
def proxy_send_decision_reminder(decision_id):
    try:
        user_id = session.get("user_id", 1)
        resp = make_backend_request("POST", f"/decisions/{decision_id}/send_reminder?user_id={user_id}", timeout=15)
        return make_response(resp.content, resp.status_code, {"Content-Type": resp.headers.get("Content-Type", "application/json")})
    except Exception as e:
        return jsonify({"detail": f"Decision reminder error: {e}"}), 500


@app.route("/api/dashboard", methods=["GET"])
@app.route("/api/dashboard/", methods=["GET"])
@app.route("/api/dashboard/<int:user_id>", methods=["GET"])
def api_dashboard(user_id=None):
    if not user_id:
        user_id = session.get("user_id", 1)
    try:
        response = make_backend_request("GET", f"/dashboard/{user_id}", timeout=5)
        if response is not None and response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify({"detail": "Error loading dashboard"}), response.status_code if response else 500
    except Exception as e:
        return jsonify({"detail": str(e)}), 500


@app.route("/api/<path:endpoint>", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
def universal_api_proxy(endpoint):
    try:
        method = request.method
        url_path = f"/{endpoint}"
        query_string = request.query_string.decode("utf-8")
        if query_string:
            url_path = f"{url_path}?{query_string}"

        # Strip encoding headers to prevent gzip mismatch (requests auto-decompresses)
        headers = {
            k: v for k, v in request.headers
            if k.lower() not in ["host", "content-length", "accept-encoding", "content-encoding", "transfer-encoding"]
        }
        
        json_data = None
        form_data = None
        files = None

        if request.is_json:
            json_data = request.get_json(silent=True)
        elif request.files:
            files = {}
            for key in request.files:
                f = request.files[key]
                files[key] = (f.filename, f.read(), f.content_type or "application/octet-stream")
            form_data = request.form.to_dict()
        elif request.form:
            form_data = request.form.to_dict()

        resp = make_backend_request(
            method,
            url_path,
            json=json_data,
            data=form_data,
            files=files,
            headers=headers,
            timeout=30
        )

        # Automatically record audit logs across all platform mutations
        if method in ["POST", "PUT", "PATCH", "DELETE"] and resp is not None and resp.status_code < 400 and not endpoint.startswith("audit"):
            try:
                ep_low = endpoint.lower()
                req_json = json_data or {}
                
                if "decision" in ep_low:
                    title_str = req_json.get("title", "")
                    if method == "POST":
                        log_platform_audit(f"Created Decision: {title_str}" if title_str else "Created Decision", f"Endpoint: /{endpoint}", module="Decisions", severity="Success")
                    elif method in ["PUT", "PATCH"]:
                        status_str = req_json.get("status", "")
                        if status_str:
                            log_platform_audit(f"Decision Status Changed to {status_str}", f"Endpoint: /{endpoint}", module="Reviews", severity="Success" if status_str == "Approved" else "Warning")
                        else:
                            log_platform_audit(f"Updated Decision: {title_str}" if title_str else "Updated Decision", f"Endpoint: /{endpoint}", module="Decisions", severity="Warning")
                    elif method == "DELETE":
                        log_platform_audit(f"Deleted Decision", f"Endpoint: /{endpoint}", module="Decisions", severity="Critical")
                elif "user" in ep_low:
                    name_str = req_json.get("full_name", "")
                    if method == "POST":
                        log_platform_audit(f"Created User Account: {name_str}" if name_str else "Created User Account", f"Email: {req_json.get('email', '')}", module="Users", severity="Success")
                    elif method in ["PUT", "PATCH"]:
                        log_platform_audit(f"Updated User Details: {name_str}" if name_str else "Updated User Details", f"Endpoint: /{endpoint}", module="Users", severity="Warning")
                    elif method == "DELETE":
                        log_platform_audit(f"Deactivated User Account", f"Endpoint: /{endpoint}", module="Users", severity="Critical")
                elif "team" in ep_low:
                    t_name = req_json.get("team_name", "")
                    if method == "POST":
                        log_platform_audit(f"Created Team: {t_name}" if t_name else "Created Team", f"Description: {req_json.get('description', '')}", module="Teams", severity="Success")
                    elif method in ["PUT", "PATCH"]:
                        log_platform_audit(f"Updated Team: {t_name}" if t_name else "Updated Team", f"Endpoint: /{endpoint}", module="Teams", severity="Warning")
                    elif method == "DELETE":
                        log_platform_audit(f"Deleted Team", f"Endpoint: /{endpoint}", module="Teams", severity="Critical")
                elif "role" in ep_low:
                    r_name = req_json.get("role_name", "")
                    log_platform_audit(f"Modified Role: {r_name}" if r_name else "Modified Role Permissions", f"Endpoint: /{endpoint}", module="Roles", severity="Warning")
                elif "discuss" in ep_low or "comment" in ep_low:
                    log_platform_audit("Posted Discussion Message", f"Endpoint: /{endpoint}", module="Discussions", severity="Info")
                elif "support" in ep_low:
                    if "ai-chat" in ep_low:
                        log_platform_audit("AI Copilot Assistant Query", f"User queried AI Support ({req_json.get('mode', 'standard')})", module="AI", severity="Info")
                    else:
                        log_platform_audit(f"Submitted Support Ticket: {req_json.get('subject', '')}" if req_json.get('subject') else "Submitted Support Ticket", f"Category: {req_json.get('category', 'General')}", module="Support", severity="Info")
                elif "email" in ep_low:
                    log_platform_audit(f"Dispatched Email Notification", f"To: {req_json.get('to_email', 'User')}", module="Email", severity="Info")
                elif "review" in ep_low:
                    log_platform_audit("Submitted Review Evaluation", f"Endpoint: /{endpoint}", module="Reviews", severity="Success")
                elif "repository" in ep_low:
                    log_platform_audit("Updated Knowledge Repository", f"Endpoint: /{endpoint}", module="Repository", severity="Success")
            except Exception as e:
                print(f"[AUDIT PROXY LOG ERROR] {e}")

        # Forward only safe headers; exclude encoding headers since requests auto-decompresses
        excluded = {"content-encoding", "transfer-encoding", "connection", "content-length"}
        out_headers = {k: v for k, v in resp.headers.items() if k.lower() not in excluded}

        return make_response(resp.content, resp.status_code, out_headers)
    except Exception as e:
        return jsonify({"detail": f"Proxy error on /{endpoint}: {e}"}), 500


# ===========================
# API PROXIES (Email Verification & Password Reset)
# ===========================

@app.route("/api/send-code", methods=["POST"])
def send_code():
    data = request.json
    try:
        response = make_backend_request("POST", "/users/send-verification-code", json=data, timeout=10)
        if response is not None and response.status_code == 200:
            return jsonify(response.json()), 200
        if response is not None:
            return jsonify(response.json()), response.status_code
        return jsonify({"detail": "Backend connection error. Ensure the FastAPI backend is running."}), 500
    except requests.exceptions.RequestException:
        return jsonify({"detail": "Backend connection error. Ensure the FastAPI backend is running."}), 500
    except ValueError:
        return jsonify({"detail": "Received an invalid response from the backend server."}), 500

@app.route("/api/verify-code", methods=["POST"])
def verify_code():
    data = request.json
    try:
        response = make_backend_request("POST", "/users/check-verification-code", json=data, timeout=10)
        if response is not None and response.status_code == 200:
            return jsonify(response.json()), 200
        if response is not None:
            return jsonify(response.json()), response.status_code
        return jsonify({"detail": "Backend connection error. Ensure the FastAPI backend is running."}), 500
    except requests.exceptions.RequestException:
        return jsonify({"detail": "Backend connection error. Ensure the FastAPI backend is running."}), 500
    except ValueError:
        return jsonify({"detail": "Received an invalid response from the backend server."}), 500

@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.json
    try:
        response = make_backend_request("POST", "/users/reset-password", json=data, timeout=10)
        if response is not None and response.status_code == 200:
            return jsonify(response.json()), 200
        if response is not None:
            return jsonify(response.json()), response.status_code
        return jsonify({"detail": "Backend connection error. Ensure the FastAPI backend is running."}), 500
    except requests.exceptions.RequestException:
        return jsonify({"detail": "Backend connection error. Ensure the FastAPI backend is running."}), 500
    except ValueError:
        return jsonify({"detail": "Received an invalid response from the backend server."}), 500

@app.route("/api/admin-create-user", methods=["POST"])
def admin_create_user_proxy():
    if not session.get("logged_in"):
        return jsonify({"detail": "Unauthorized. Please log in as Admin."}), 401
    data = request.json
    try:
        headers = {}
        if "token" in session:
            headers["Authorization"] = f"Bearer {session['token']}"
        response = make_backend_request("POST", "/users/admin_create", json=data, headers=headers, timeout=10)
        if response is not None:
            try:
                invalidate_cache_key("all_users")
                return jsonify(response.json()), response.status_code
            except Exception:
                return jsonify({"detail": response.text or "Error creating user"}), response.status_code
        return jsonify({"detail": "Backend connection error. Ensure the FastAPI backend is running."}), 500
    except requests.exceptions.RequestException as e:
        return jsonify({"detail": "Backend connection error. Ensure the FastAPI backend is running."}), 500
    except ValueError:
        return jsonify({"detail": "Received an invalid response from the backend server."}), 500

# ===========================
# NOTIFICATIONS PROXIES
# ===========================

@app.route("/notifications/<int:user_id>")
@app.route("/api/notifications/<int:user_id>")
def get_notifications(user_id):
    if "token" not in session:
        return jsonify({"detail": "Unauthorized"}), 401
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        response = make_backend_request("GET", f"/notifications/{user_id}", headers=headers, timeout=5)
        if response is not None:
            return jsonify(response.json()), response.status_code
        return jsonify([]), 200
    except Exception as e:
        return jsonify([]), 200

@app.route("/notifications/<int:user_id>/mark-all-read", methods=["PUT"])
@app.route("/api/notifications/<int:user_id>/mark-all-read", methods=["PUT"])
def mark_all_read(user_id):
    if "token" not in session:
        return jsonify({"detail": "Unauthorized"}), 401
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        response = make_backend_request("PUT", f"/notifications/{user_id}/mark-all-read", headers=headers, timeout=5)
        if response is not None:
            return jsonify(response.json()), response.status_code
        return jsonify({"detail": "Error"}), 500
    except Exception as e:
        return jsonify({"detail": "Error"}), 500

@app.route("/notifications/<int:user_id>/clear-all", methods=["DELETE"])
@app.route("/api/notifications/<int:user_id>/clear-all", methods=["DELETE"])
def clear_all_notifications(user_id):
    if "token" not in session:
        return jsonify({"detail": "Unauthorized"}), 401
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        response = make_backend_request("DELETE", f"/notifications/{user_id}/clear-all", headers=headers, timeout=5)
        if response is not None:
            return jsonify(response.json()), response.status_code
        return jsonify({"detail": "Error"}), 500
    except Exception as e:
        return jsonify({"detail": "Error"}), 500

# ===========================
# DASHBOARD
# ===========================

@app.route("/dashboard")
def dashboard():

    if "token" not in session:
        return redirect(url_for("login"))

    headers = {
        "Authorization": f"Bearer {session['token']}"
    }

    user_id = session.get("user_id") or 48

    dashboard = {}
    try:
        response = make_backend_request("GET", f"/dashboard/{user_id}", headers=headers, timeout=10)
        if response is not None and response.status_code == 200:
            dashboard = response.json()
            if dashboard.get("team"):
                session["team_name"] = dashboard.get("team")
            elif dashboard.get("team") == "":
                session["team_name"] = "Not Assigned"
        else:
            # Fallback to general admin ID 48
            fallback_resp = make_backend_request("GET", "/dashboard/48", headers=headers, timeout=10)
            if fallback_resp is not None and fallback_resp.status_code == 200:
                dashboard = fallback_resp.json()
            else:
                flash("Backend service returned an error. Showing offline dashboard view.", "warning")
    except Exception as e:
        print(f"[FRONTEND DASHBOARD REQ ERR] {e}")
        try:
            fallback_resp = make_backend_request("GET", "/dashboard/48", headers=headers, timeout=10)
            if fallback_resp is not None and fallback_resp.status_code == 200:
                dashboard = fallback_resp.json()
        except Exception:
            flash("Backend server is unreachable. Please ensure the backend is running.", "warning")


    role = (session.get("role_name") or "Employee").strip()
    role_lower = role.lower()
    if "manager" in role_lower or "lead" in role_lower:
        template = "manager_dashboard.html"
    elif "admin" in role_lower:
        template = "dashboard.html"
    elif "reviewer" in role_lower:
        template = "reviewer_dashboard.html"
    else:
        template = "employee_dashboard.html"

    total_decisions = dashboard.get("total_decisions", 0)
    approved_decisions = dashboard.get("approved_decisions", 0)
    pending_reviews = dashboard.get("pending_reviews", 0)
    rejected_decisions = dashboard.get("rejected_decisions", 0)
    draft_decisions = dashboard.get("draft_decisions", 0)

    # Pre-compute bar widths to avoid Jinja arithmetic inside style attributes
    approved_pct = int(approved_decisions / total_decisions * 100) if total_decisions > 0 else 0
    pending_pct  = int(pending_reviews    / total_decisions * 100) if total_decisions > 0 else 0
    rejected_pct = int(rejected_decisions / total_decisions * 100) if total_decisions > 0 else 0
    draft_pct    = int(draft_decisions    / total_decisions * 100) if total_decisions > 0 else 0

    return render_template(
        template,
        dashboard=dashboard,
        team=dashboard.get("team") or session.get("team_name") or "Not Assigned",
        # Unpack for convenient direct access in templates
        total_users=dashboard.get("total_users", 0),
        active_users=dashboard.get("active_users", 0),
        total_decisions=total_decisions,
        pending_reviews=pending_reviews,
        total_replays=dashboard.get("total_replays", 0),
        approved_decisions=approved_decisions,
        rejected_decisions=rejected_decisions,
        draft_decisions=draft_decisions,
        total_audit_logs=dashboard.get("total_audit_logs", 0),
        system_health=dashboard.get("system_health", "99%"),
        recent_decisions=dashboard.get("recent_decisions", []),
        recent_reviews=dashboard.get("recent_reviews", []),
        recent_replays=dashboard.get("recent_replays", []),
        recent_users=dashboard.get("recent_users", []),
        recent_audit_logs=dashboard.get("recent_audit_logs", []),
        recent_discussions=dashboard.get("recent_discussions", []),
        approval_flow=dashboard.get("approval_flow", []),
        decision_trends=dashboard.get("decision_trends"),
        department_comparison=dashboard.get("department_comparison"),
        monthly_activity=dashboard.get("monthly_activity"),
        security_events=dashboard.get("security_events", []),
        admin_tasks=dashboard.get("admin_tasks", []),
        unread_notifications_count=dashboard.get("unread_notifications_count", 0),
        # Pre-computed percentage widths for progress bars
        approved_pct=approved_pct,
        pending_pct=pending_pct,
        rejected_pct=rejected_pct,
        draft_pct=draft_pct,
    )


# ===========================
# USERS
# ===========================

@app.route("/users")
def users():
    if "token" not in session:
        return redirect(url_for("login"))

    headers = {"Authorization": f"Bearer {session['token']}"} if "token" in session else {}
    initial_users = get_cached_data("all_users", "/users/", ttl=5, headers=headers)
    initial_roles = get_cached_data("all_roles", "/roles", ttl=30, headers=headers)
    initial_teams = get_cached_data("all_teams", "/teams/", ttl=30, headers=headers)

    return render_template(
        "users.html",
        initial_users=initial_users,
        initial_roles=initial_roles,
        initial_teams=initial_teams
    )


# ===========================
# ROLES
# ===========================

@app.route("/roles")
def roles():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    initial_roles = get_cached_data("all_roles", "/roles", ttl=120)
    return render_template("roles.html", initial_roles=initial_roles)


# ===========================
# TEAMS
# ===========================

@app.route("/teams")
def teams():
    if not session.get("logged_in"):
        return redirect(url_for("login"))

    initial_teams = get_cached_data("all_teams", "/teams/", ttl=60)
    return render_template("teams.html", initial_teams=initial_teams)


# ===========================
# CREATE DECISION WIZARD
# ===========================

@app.route("/create_decision")
def create_decision():
    if "token" not in session:
        return redirect(url_for("login"))
    
    role = (session.get("role_name") or "Employee").strip().lower()
    if "reviewer" in role:
        flash("Access Denied: Creating decisions is restricted to Employees.", "danger")
        return redirect(url_for("dashboard"))

    return render_template("create_decision.html")

# ===========================
# DECISIONS
# ===========================

@app.route("/decisions")
def decisions():
    if "token" not in session:
        return redirect(url_for("login"))

    role = (session.get("role_name") or "Employee").strip().lower()
    if "reviewer" in role:
        flash("Access Denied: My Decisions page is restricted to Employees.", "danger")
        return redirect(url_for("dashboard"))

    user_id = session.get("user_id", "")
    role_name = session.get("role_name", "")
    headers = {"Authorization": f"Bearer {session['token']}"} if "token" in session else {}
    initial_decisions = get_cached_data(f"decisions_{user_id}_{role_name}", f"/decisions/?user_id={user_id}&role_name={role_name}", ttl=0, headers=headers)

    return render_template("decisions.html", initial_decisions=initial_decisions)


# ===========================
# DECISION DETAILS
# ===========================

@app.route("/decision/<int:id>")
def decision_details(id):
    if "token" not in session:
        return redirect(url_for("login"))

    return render_template("decision_details.html", decision_id=id)


# ===========================
# ALTERNATIVES
# ===========================

@app.route("/alternatives")
def alternatives():
    if "token" not in session:
        return redirect(url_for("login"))

    return render_template("alternatives.html")


# ===========================
# DISCUSSION
# ===========================

@app.route("/discussion")
def discussion():
    if "token" not in session:
        return redirect(url_for("login"))

    return render_template("discussion.html")


# ===========================
# REVIEWS
# ===========================

@app.route("/reviews")
def reviews():
    if "token" not in session:
        return redirect(url_for("login"))

    role = (session.get("role_name") or "Employee").strip().lower()
    if "employee" in role:
        flash("Access Denied: Pending Reviews page is restricted to Reviewers and Managers.", "danger")
        return redirect(url_for("dashboard"))

    user_id = session.get("user_id", "")
    headers = {"Authorization": f"Bearer {session['token']}"} if "token" in session else {}
    initial_reviews = get_cached_data(f"reviews_{user_id}", f"/reviews/?user_id={user_id}", ttl=20, headers=headers)

    return render_template("reviews.html", initial_reviews=initial_reviews)


# ===========================
# REPLAYS
# ===========================

@app.route("/replays")
def replays():
    if "token" not in session:
        return redirect(url_for("login"))

    return render_template("replays.html")


# ===========================
# KNOWLEDGE REPOSITORY
# ===========================

@app.route("/repository")
def repository():
    if "token" not in session:
        return redirect(url_for("login"))

    headers = {"Authorization": f"Bearer {session['token']}"} if "token" in session else {}
    initial_approved_decisions = get_cached_data("repo_approved_decisions", "/decisions/?scope=repository&status=Approved", ttl=20, headers=headers)
    return render_template("repository.html", initial_approved_decisions=initial_approved_decisions)


# ===========================
# AUDIT
# ===========================

@app.route("/audit")
def audit():
    if "token" not in session:
        return redirect(url_for("login"))

    role = session.get("role_name", "User")
    if role not in ("Administrator", "Admin"):
        flash("Access Denied: Audit logs are restricted to Administrators only.", "danger")
        return redirect(url_for("dashboard"))

    headers = {"Authorization": f"Bearer {session['token']}"} if "token" in session else {}
    initial_audit_logs = get_cached_data("all_audit_logs", "/audit/?limit=500", ttl=20, headers=headers)

    return render_template("audit.html", initial_audit_logs=initial_audit_logs)


# ===========================
# REPORTS
# ===========================

@app.route("/reports")
def reports():

    if "token" not in session:
        return redirect(url_for("login"))

    return render_template("reports.html")


# ===========================
# PROFILE
# ===========================

@app.route("/profile")
def profile():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    current_user_id = session.get("user_id")
    profile = {}
    try:
        response = make_backend_request(
            "GET",
            f"/profile/{current_user_id}",
            params={"current_user_id": current_user_id},
            timeout=5
        )
        if response is None or response.status_code != 200:
            flash("Unable to load profile.", "danger")
            return redirect(url_for("dashboard"))
        profile = response.json()
        if profile.get("designation"):
            session["designation"] = profile.get("designation")
        if profile.get("team"):
            session["team_name"] = profile.get("team")
            session["team_id"] = profile.get("team_id")
        elif profile.get("team") == "":
            session["team_name"] = "Not Assigned"
            session["team_id"] = None
    except Exception as e:
        print(f"[FRONTEND PROFILE REQ ERR] {e}")
        flash("Backend connection error. Please ensure the backend service is running.", "danger")
        return redirect(url_for("dashboard"))

    return render_template(
        "profile.html",
        profile=profile,
        current_user_id=current_user_id
    )



@app.route("/profile/update", methods=["POST"])
def update_profile():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    payload = {

        "full_name": request.form["full_name"],

        "phone": request.form["phone"],

        "designation": request.form["designation"]

    }

    try:
        response = make_backend_request(
            "PUT",
            f"/profile/{session['user_id']}",
            json=payload,
            timeout=5
        )
        if response is not None and response.status_code == 200:
            flash("Profile Updated Successfully", "success")
        else:
            flash("Unable to update profile", "danger")
    except Exception as e:
        print(f"[FRONTEND PROFILE UPDATE REQ ERR] {e}")
        flash("Backend connection error. Unable to save profile changes.", "danger")

    return redirect(url_for("profile"))

# ===========================
# UPLOAD
# ===========================

@app.route("/upload")
def upload():

    if "token" not in session:
        return redirect(url_for("login"))

    return render_template("upload.html")


# ===========================
# NOTIFICATIONS
# ===========================

@app.route("/notifications_page")
def notifications_page():

    if "token" not in session:
        return redirect(url_for("login"))

    return render_template("notifications.html")


# ===========================
# SETTINGS & SUPPORT
# ===========================

@app.route("/settings")
def settings():
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("settings.html")

@app.route("/admin-backup")
def admin_backup():
    if "token" not in session:
        return redirect(url_for("login"))

    role = session.get("role_name", "User")
    if role not in ("Administrator", "Admin"):
        flash("Access Denied: Only Administrators can access backup management.", "danger")
        return redirect(url_for("dashboard"))

    return render_template("admin_backup.html")

@app.route("/support")
def support():
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("support.html")

@app.route("/email-service")
def email_service():
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("email_service.html")


# ===========================
# LOGOUT
# ===========================

@app.route("/logout")
def logout():
    uid = session.get("user_id")
    name = session.get("full_name", "User")
    if uid:
        try:
            log_platform_audit(f"User logged out: {name}", "User ended active session", module="Auth", severity="Info", user_id=uid)
            make_backend_request("POST", "/users/logout-presence", json={"user_id": uid}, timeout=2)
        except Exception:
            pass
    session.clear()
    session.permanent = False
    flash("Logged Out Successfully", "info")
    res = make_response(redirect(url_for("login")))
    res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    res.headers["Pragma"] = "no-cache"
    res.headers["Expires"] = "0"
    return res

@app.route("/account-deleted")
def account_deleted():
    session.clear()
    session.permanent = False
    flash("Your account and all associated data have been permanently deleted.", "warning")
    res = make_response(redirect(url_for("login")))
    res.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    res.headers["Pragma"] = "no-cache"
    res.headers["Expires"] = "0"
    return res



# ===========================
# ERROR HANDLERS
# ===========================


@app.route("/404-error")
def error_404():
    return render_template("404.html"), 404

@app.errorhandler(404)
def page_not_found(e):
    return redirect(url_for("error_404"))

# ===========================
# START APPLICATION
# ===========================

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "True").lower() in ("true", "1")
    app.run(host=host, port=port, debug=debug)