import psycopg2
import sqlite3
import hashlib
from datetime import datetime

# 1. Connect to both DBs
conn_pg = psycopg2.connect(dbname='expert_decision_db', user='postgres', password='ShabhanaaNaveen0320', host='localhost', port=5432)
cur_pg = conn_pg.cursor()

conn_sq = sqlite3.connect('edrp.db')
cur_sq = conn_sq.cursor()

print("--- Step 1: Analyze Postgres Users ---")
cur_pg.execute("SELECT id, full_name, email, password, role_id, team_id, designation, phone, is_active, employee_id FROM users ORDER BY id;")
pg_users = cur_pg.fetchall()

print("--- Step 2: Analyze SQLite Users ---")
cur_sq.execute("SELECT id, employee_id, full_name, email, email_original, password, role_id, team_id, designation, phone, status, is_active, email_verified, approved FROM users ORDER BY id;")
sq_users = cur_sq.fetchall()

# Map roles
# Role 1: Administrator (AD)
# Role 2: Manager (MN)
# Role 3: Employee (EMP)
# Role 4: Reviewer (RW)

# Standardize role IDs from postgres (where 1=Admin/Student, 3=Admin, 4=Manager, 5=Employee, 6=Reviewer)
def normalize_role(role_id, full_name="", email=""):
    name_low = (full_name or "").lower()
    email_low = (email or "").lower()
    if "admin" in name_low or "admin" in email_low or role_id in (1, 3):
        return 1 # Admin
    if "manager" in name_low or "manager" in email_low or role_id in (2, 4):
        return 2 # Manager
    if "reviewer" in name_low or "reviewer" in email_low or role_id == 6:
        return 4 # Reviewer
    return 3 # Employee

# Build consolidated unique user map by email
# Key: normalized email
users_by_email = {}

# Process Postgres users first (original primary accounts)
for u in pg_users:
    pg_id, name, email, pwd, role_id, team_id, desig, phone, is_act, emp_id = u
    norm_email = (email or "").strip().lower()
    norm_role = normalize_role(role_id, name, email)
    users_by_email[norm_email] = {
        "pg_id": pg_id,
        "full_name": name,
        "email": norm_email,
        "password": pwd,
        "role_id": norm_role,
        "team_id": team_id or 1,
        "designation": desig or "",
        "phone": phone or "",
        "employee_id": emp_id
    }

# Process SQLite users (merge, avoid duplicates)
for u in sq_users:
    sq_id, emp_id, name, e_hash, e_orig, pwd, role_id, team_id, desig, phone, status, is_act, ev, app = u
    norm_email = (e_orig or "").strip().lower()
    if not norm_email and e_hash:
        norm_email = f"user{sq_id}@corp.com"
    
    if norm_email in users_by_email:
        # Update existing if better info
        if emp_id and not users_by_email[norm_email]["employee_id"]:
            users_by_email[norm_email]["employee_id"] = emp_id
        if pwd and not users_by_email[norm_email]["password"]:
            users_by_email[norm_email]["password"] = pwd
    else:
        users_by_email[norm_email] = {
            "pg_id": None,
            "full_name": name,
            "email": norm_email,
            "password": pwd or hashlib.sha256("password123".encode()).hexdigest(),
            "role_id": role_id or 3,
            "team_id": team_id or 1,
            "designation": desig or "",
            "phone": phone or "",
            "employee_id": emp_id
        }

print(f"Total Unique Users identified: {len(users_by_email)}")

# Ensure unique, clean Employee IDs for everyone without conflicts
used_emp_ids = set()
# Fixed mappings for key accounts if known:
fixed_emp_ids = {
    "admin.naveen@corp.com": "AD3341",
    "manager.naveen@corp.com": "MN1297",
    "reviewer.naveen@corp.com": "RW1300",
    "koppala.naveen@corp.com": "EMP8749",
    "naveen.k@corp.com": "AD030120",
    "koppalanaveen20@gmail.com": "AD123456",
    "koppalanaveen0320@gmail.com": "EMP2362",
    "manager@gmail.com": "MN6424",
    "sheik@corp.com": "EMP33333",
}

for email, u in users_by_email.items():
    if email in fixed_emp_ids:
        u["employee_id"] = fixed_emp_ids[email]
        used_emp_ids.add(u["employee_id"])

# Assign IDs to remaining users
import random
prefix_map = {1: "AD", 2: "MN", 3: "EMP", 4: "RW"}

for email, u in users_by_email.items():
    if not u["employee_id"] or u["employee_id"] in used_emp_ids:
        # Check if existing employee_id can be kept
        if u["employee_id"] and u["employee_id"] not in used_emp_ids:
            used_emp_ids.add(u["employee_id"])
        else:
            pfx = prefix_map.get(u["role_id"], "EMP")
            # Generate deterministic or random ID
            candidate = f"{pfx}{random.randint(1000, 9999)}"
            while candidate in used_emp_ids:
                candidate = f"{pfx}{random.randint(10000, 99999)}"
            u["employee_id"] = candidate
            used_emp_ids.add(candidate)
    else:
        used_emp_ids.add(u["employee_id"])

print("\n--- Consolidated Clean Unique User List ---")
for email, u in sorted(users_by_email.items(), key=lambda x: x[1]["role_id"]):
    print(f"Role={u['role_id']} | EmpID={u['employee_id']:<10} | Name={u['full_name']:<20} | Email={email}")

conn_pg.close()
conn_sq.close()
