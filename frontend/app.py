from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
import requests
from datetime import timedelta

app = Flask(__name__)

# Secret Key & Session Config
app.secret_key = "expert_decision_platform"
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=72)
# Maximum upload size set to 200 MB
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

# FastAPI Backend URL
API_URL = "http://127.0.0.1:8000"

@app.context_processor
def inject_global_stats():
    if not session.get("logged_in"):
        return {}
    
    try:
        user_id = session.get("user_id")
        token = session.get("token")
        if not user_id or not token:
            return {}
            
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{API_URL}/dashboard/{user_id}", headers=headers, timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            return {
                "unread_notifications_count": data.get("unread_notifications_count", 0),
                "pending_reviews": data.get("pending_reviews", 0)
            }
    except Exception:
        pass
    
    return {"unread_notifications_count": 0, "pending_reviews": 0}

# ===========================
# HOME
# ===========================

@app.route("/")
def index():
    if session.get("logged_in") and "token" in session:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")

@app.route("/landing")
def home():
    if session.get("logged_in") and "token" in session:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")



# ===========================
# LOGIN
# ===========================

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in") and "token" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        remember_me = request.form.get("remember_me") or request.form.get("remember")
        payload = {
            "employee_id": request.form.get("employee_id", "").strip(),
            "password": request.form.get("password", "")
        }

        try:
            response = requests.post(f"{API_URL}/users/login", json=payload, timeout=5)
            if response.status_code == 200:
                token = response.json()
                if remember_me:
                    session.permanent = True
                else:
                    session.permanent = False
                session["logged_in"] = True
                session["token"] = token["access_token"]
                session["user_id"] = token["user_id"]
                session["role_name"] = token.get("role_name", "User")
                full_name = token.get("full_name", "User")
                session["full_name"] = full_name
                
                parts = full_name.split()
                session["initials"] = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()

                try:
                    requests.post(f"{API_URL}/audit/log", json={
                        "user_id": token["user_id"],
                        "action": f"User login successful: {full_name}",
                        "details": f"Role: {session['role_name']}"
                    }, timeout=2)
                except Exception as log_err:
                    print(f"Frontend audit log note: {log_err}")

                flash("Login Successful", "success")
                return redirect(url_for("dashboard"))

            try:
                error_msg = response.json().get("detail", "Invalid Employee ID or Password.")
            except Exception:
                error_msg = "Invalid Employee ID or Password."
            flash(error_msg, "danger")
        except requests.exceptions.RequestException:
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
            response = requests.post(f"{API_URL}/users/register/step1", json=payload, timeout=15)
            if response.status_code == 200:
                session["reg_data"] = payload
                flash("Verification code sent to your email.", "info")
                return redirect(url_for("verify_email"))

            try:
                err_detail = response.json().get("detail", "Registration failed.")
            except Exception:
                err_detail = response.text
            flash(err_detail, "danger")
        except requests.exceptions.RequestException:
            flash("Backend connection error.", "danger")

    return render_template("register.html")


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
            response = requests.post(f"{API_URL}/users/check-verification-code", json=payload, timeout=15)
            if response.status_code == 200:
                session["email_verified"] = True
                flash("Email verified successfully! Now create your Employee ID.", "success")
                return redirect(url_for("create_employee_id"))

            try:
                err_msg = response.json().get("detail", "Invalid verification code.")
            except Exception:
                err_msg = "Invalid verification code."
            flash(err_msg, "danger")
        except requests.exceptions.RequestException:
            flash("Backend connection error.", "danger")

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
            response = requests.post(f"{API_URL}/users/save-employee-id", json=payload, timeout=15)
            if response.status_code == 200:
                res_json = response.json()
                session.pop("reg_data", None)
                session.pop("email_verified", None)
                return render_template("create_employee_id.html", success=True, msg=res_json.get("message"), sub_msg=res_json.get("sub_message"))

            try:
                err_msg = response.json().get("detail", "Failed to save Employee ID.")
            except Exception:
                err_msg = "Failed to save Employee ID."
            flash(err_msg, "danger")
        except requests.exceptions.RequestException as req_err:
            print(f"[API ERROR] /users/save-employee-id failed: {req_err}")
            flash(f"Backend connection error: {req_err}", "danger")

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
        response = requests.get(f"{API_URL}/users/pending", timeout=5)
        pending_users = response.json() if response.status_code == 200 else []
    except Exception:
        pending_users = []

    return render_template("pending_approvals.html", pending_users=pending_users)


@app.route("/api/check-employee-id", methods=["POST"])
def api_check_employee_id():
    data = request.json
    try:
        response = requests.post(f"{API_URL}/users/check-employee-id", json=data, timeout=5)
        return jsonify(response.json()), response.status_code
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
        response = requests.delete(f"{API_URL}/users/{user_id}", timeout=5)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"detail": f"Error deleting user: {e}"}), 500


@app.route("/api/pending-approvals/action", methods=["POST"])
def api_pending_approval_action():
    if "token" not in session:
        return jsonify({"detail": "Unauthorized"}), 401
    
    role = session.get("role_name", "User")
    if role not in ("Administrator", "Admin"):
        return jsonify({"detail": "Forbidden: Admin access required"}), 403

    data = request.json
    data["actor_name"] = session.get("full_name", "Administrator")
    endpoint = f"{API_URL}/users/{data.get('action')}"
    
    try:
        response = requests.post(endpoint, json=data, timeout=5)
        return jsonify(response.json()), response.status_code
    except Exception:
        return jsonify({"detail": "Error processing approval action"}), 500

# ===========================
# API PROXIES (Email Verification & Password Reset)
# ===========================
from flask import jsonify

@app.route("/api/send-code", methods=["POST"])
def send_code():
    data = request.json
    try:
        response = requests.post(
            f"{API_URL}/users/send-verification-code",
            json=data
        )
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"detail": "Backend connection error. Ensure the FastAPI backend is running."}), 500
    except ValueError:
        return jsonify({"detail": "Received an invalid response from the backend server."}), 500

@app.route("/api/verify-code", methods=["POST"])
def verify_code():
    data = request.json
    try:
        response = requests.post(
            f"{API_URL}/users/check-verification-code",
            json=data
        )
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"detail": "Backend connection error. Ensure the FastAPI backend is running."}), 500
    except ValueError:
        return jsonify({"detail": "Received an invalid response from the backend server."}), 500

@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.json
    try:
        response = requests.post(
            f"{API_URL}/users/reset-password",
            json=data
        )
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify(response.json()), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"detail": "Backend connection error. Ensure the FastAPI backend is running."}), 500
    except ValueError:
        return jsonify({"detail": "Received an invalid response from the backend server."}), 500

@app.route("/api/admin-create-user", methods=["POST"])
def admin_create_user_proxy():
    if not session.get("logged_in"):
        return jsonify({"detail": "Unauthorized. Please log in as Admin."}), 401
    data = request.json
    try:
        response = requests.post(
            f"{API_URL}/users/admin_create",
            json=data,
            timeout=10
        )
        try:
            return jsonify(response.json()), response.status_code
        except Exception:
            return jsonify({"detail": response.text or "Error creating user"}), response.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"detail": "Backend connection error. Ensure the FastAPI backend is running."}), 500
    except ValueError:
        return jsonify({"detail": "Received an invalid response from the backend server."}), 500

# ===========================
# NOTIFICATIONS PROXIES
# ===========================

@app.route("/notifications/<int:user_id>")
def get_notifications(user_id):
    if "token" not in session:
        return jsonify({"detail": "Unauthorized"}), 401
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        response = requests.get(f"{API_URL}/notifications/{user_id}", headers=headers, timeout=5)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify([]), 200

@app.route("/notifications/<int:user_id>/mark-all-read", methods=["PUT"])
def mark_all_read(user_id):
    if "token" not in session:
        return jsonify({"detail": "Unauthorized"}), 401
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        response = requests.put(f"{API_URL}/notifications/{user_id}/mark-all-read", headers=headers, timeout=5)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"detail": "Error"}), 500

@app.route("/notifications/<int:user_id>/clear-all", methods=["DELETE"])
def clear_all_notifications(user_id):
    if "token" not in session:
        return jsonify({"detail": "Unauthorized"}), 401
    headers = {"Authorization": f"Bearer {session['token']}"}
    try:
        response = requests.delete(f"{API_URL}/notifications/{user_id}/clear-all", headers=headers, timeout=5)
        return jsonify(response.json()), response.status_code
    except Exception as e:
        return jsonify({"detail": "Error"}), 500

@app.route("/api/decisions")
def api_get_decisions():
    if "token" not in session:
        return jsonify([]), 401
    try:
        response = requests.get(f"{API_URL}/decisions/", timeout=5)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify([]), response.status_code
    except Exception:
        return jsonify([]), 500

@app.route("/api/dashboard")
def api_get_dashboard():
    if "token" not in session or "user_id" not in session:
        return jsonify({}), 401
    headers = {"Authorization": f"Bearer {session['token']}"}
    user_id = session["user_id"]
    try:
        response = requests.get(f"{API_URL}/dashboard/{user_id}", headers=headers, timeout=5)
        if response.status_code == 200:
            return jsonify(response.json()), 200
        return jsonify({}), response.status_code
    except Exception:
        return jsonify({}), 500

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

    user_id = session.get("user_id", 2)

    response = requests.get(
        f"{API_URL}/dashboard/{user_id}",
        headers=headers
    )

    dashboard = {}

    if response.status_code == 200:
        dashboard = response.json()

    role = session.get("role_name", "User")
    if role == "Manager":
        template = "manager_dashboard.html"
    elif role == "Administrator" or role == "Admin":
        template = "dashboard.html"
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

    return render_template("users.html")


# ===========================
# ROLES
# ===========================

@app.route("/roles")
def roles():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    return render_template("roles.html")


# ===========================
# TEAMS
# ===========================

@app.route("/teams")
def teams():

    if not session.get("logged_in"):
        return redirect(url_for("login"))

    return render_template("teams.html")


# ===========================
# CREATE DECISION WIZARD
# ===========================

@app.route("/create_decision")
def create_decision():
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("create_decision.html")

# ===========================
# DECISIONS
# ===========================

@app.route("/decisions")
def decisions():

    if "token" not in session:
        return redirect(url_for("login"))

    return render_template("decisions.html")


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

    return render_template("reviews.html")


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

    return render_template("repository.html")


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

    return render_template("audit.html")


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

    response = requests.get(
        f"{API_URL}/profile/{session['user_id']}"
    )

    if response.status_code != 200:

        flash("Unable to load profile.", "danger")

        return redirect(url_for("dashboard"))

    profile = response.json()

    return render_template(
        "profile.html",
        profile=profile
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

    response = requests.put(

        f"{API_URL}/profile/{session['user_id']}",

        json=payload

    )

    if response.status_code == 200:

        flash("Profile Updated Successfully", "success")

    else:

        flash("Unable to update profile", "danger")

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

@app.route("/support")
def support():
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("support.html")

@app.route("/email-service")
def email_service():
    if "token" not in session:
        return redirect(url_for("login"))
    return render_template("support.html")


# ===========================
# LOGOUT
# ===========================

@app.route("/logout")
def logout():

    session.clear()

    flash("Logged Out Successfully", "info")

    return redirect(url_for("login"))


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
    app.run(debug=True)