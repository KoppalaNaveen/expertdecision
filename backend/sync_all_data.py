import sqlite3
import hashlib
from datetime import datetime

def make_email_hash(email):
    return hashlib.sha256(email.strip().lower().encode('utf-8')).hexdigest()

def make_pass_hash(pwd="password123"):
    return hashlib.sha256(pwd.encode('utf-8')).hexdigest()

def generate_hash(*args):
    h = hashlib.sha256()
    for a in args:
        if a is not None:
            h.update(str(a).encode('utf-8'))
    return h.hexdigest()

def sync_data():
    conn = sqlite3.connect('edrp.db')
    cur = conn.cursor()

    # 1. Setup Roles
    cur.execute("DELETE FROM roles;")
    roles = [
        (1, "Administrator", "Full platform access and management"),
        (2, "Manager", "Team management and decision approvals"),
        (3, "Employee", "Create and submit decisions"),
        (4, "Reviewer", "Review and audit assigned decisions")
    ]
    cur.executemany("INSERT INTO roles (id, role_name, description) VALUES (?, ?, ?);", roles)

    # 2. Setup Teams
    cur.execute("DELETE FROM teams;")
    teams = [
        (1, "AI Team", "Artificial Intelligence and Machine Learning Research"),
        (2, "Engineering", "Core platform and application engineering"),
        (3, "Product", "Product strategy, UI/UX, and feature roadmap"),
        (4, "Operations", "Cloud operations, DevOps, and infrastructure")
    ]
    cur.executemany("INSERT INTO teams (id, team_name, description) VALUES (?, ?, ?);", teams)

    # 3. Setup Categories
    cur.execute("DELETE FROM categories;")
    categories = [
        (1, "Technical", "Architecture, systems, software and infrastructure decisions"),
        (2, "Operational", "Workflow, processes, and delivery operations"),
        (3, "Strategic", "Long-term organizational strategy and milestones"),
        (4, "Financial", "Budget, licensing, and resource allocations"),
        (5, "Academic & Research", "Research projects, thesis topics, and publications")
    ]
    cur.executemany("INSERT INTO categories (id, name, description) VALUES (?, ?, ?);", categories)

    # 4. Clean Unique Users (Exact 1-to-1 mapping, NO DUPLICATE EMPLOYEE IDS)
    # Password default: password123 (sha256: ef92b778bafe771e89245b89ecbc08a44a4e166c06659911881f383d4473e94f)
    default_pass = make_pass_hash("password123")

    users_list = [
        # Admin accounts
        {"emp_id": "AD030120", "name": "Naveen K",        "email": "naveen.k@corp.com",           "role_id": 1, "team_id": 1, "desig": "Lead Administrator", "phone": "9876543210"},
        {"emp_id": "AD123456", "name": "Koppala Naveen", "email": "koppalanaveen20@gmail.com",   "role_id": 1, "team_id": 1, "desig": "Cyber Security",     "phone": "7894561230"},
        {"emp_id": "AD3341",   "name": "Admin Naveen",   "email": "admin.naveen@corp.com",       "role_id": 1, "team_id": 1, "desig": "System Admin",       "phone": "9874562310"},
        {"emp_id": "AD1793",   "name": "Naveen",         "email": "naveen@gmail.com",            "role_id": 1, "team_id": 1, "desig": "Student / Researcher","phone": "9876543210"},
        {"emp_id": "AD4594",   "name": "Koppala Naveen", "email": "koppalanaveen82@gmail.com",   "role_id": 1, "team_id": 2, "desig": "Cyber Security Eng", "phone": "6281198993"},
        {"emp_id": "AD5125",   "name": "K Naveen",       "email": "koppalanaveen@gmail.com",     "role_id": 1, "team_id": 2, "desig": "Software Architect", "phone": "7894561230"},
        {"emp_id": "AD4672",   "name": "Admin",          "email": "admin@gmail.com",             "role_id": 1, "team_id": 1, "desig": "Super Admin",        "phone": "9874562310"},
        {"emp_id": "AD01019",  "name": "Vaibhav Ingle",  "email": "vaibhav.ingle@corp.com",      "role_id": 1, "team_id": 2, "desig": "Security Specialist", "phone": ""},
        {"emp_id": "AD06116",  "name": "Naveen K",       "email": "naveenk@corp.com",            "role_id": 1, "team_id": 1, "desig": "Admin Lead",         "phone": ""},

        # Manager accounts
        {"emp_id": "MN1297",   "name": "Manager Naveen", "email": "manager.naveen@corp.com",     "role_id": 2, "team_id": 1, "desig": "Engineering Manager","phone": "9876543211"},
        {"emp_id": "MN6424",   "name": "Manager",        "email": "manager@gmail.com",           "role_id": 2, "team_id": 2, "desig": "Team Manager",       "phone": ""},
        {"emp_id": "MN1001",   "name": "user1",          "email": "user1@replay.com",            "role_id": 2, "team_id": 1, "desig": "Project Manager",    "phone": "0000000000"},
        {"emp_id": "MN06116",  "name": "Naveen",         "email": "naveen.classic@corp.com",     "role_id": 2, "team_id": 2, "desig": "Operations Manager", "phone": ""},
        {"emp_id": "MN8BP1",   "name": "user3",          "email": "user3@replay.com",            "role_id": 2, "team_id": 3, "desig": "Product Manager",    "phone": "0000000000"},
        {"emp_id": "MN1800",   "name": "User2",          "email": "user2@replay.com",            "role_id": 2, "team_id": 4, "desig": "Operations Lead",    "phone": "0000000000"},
        {"emp_id": "MN8727",   "name": "Manager User",   "email": "manager@edrp.com",            "role_id": 2, "team_id": 1, "desig": "Technical Manager",  "phone": ""},

        # Employee accounts
        {"emp_id": "EMP8749",  "name": "Koppala Naveen", "email": "koppala.naveen@corp.com",     "role_id": 3, "team_id": 1, "desig": "Software Engineer",  "phone": ""},
        {"emp_id": "EMP33333", "name": "Employee Sheik", "email": "sheik@corp.com",             "role_id": 3, "team_id": 2, "desig": "Senior Developer",   "phone": ""},
        {"emp_id": "EP2362",   "name": "Koppala Naveen", "email": "koppalanaveen0320@gmail.com", "role_id": 3, "team_id": 1, "desig": "Software",          "phone": ""},
        {"emp_id": "EMP589",   "name": "E2E Test User",  "email": "e2e.test@corp.com",          "role_id": 3, "team_id": 2, "desig": "QA Automation Lead", "phone": "9000000000"},
        {"emp_id": "EMP2452",  "name": "Admin User",     "email": "admin@edrp.com",              "role_id": 3, "team_id": 1, "desig": "Staff Engineer",     "phone": ""},

        # Reviewer accounts
        {"emp_id": "RW1300",   "name": "Reviewer Naveen","email": "reviewer.naveen@corp.com",    "role_id": 4, "team_id": 1, "desig": "Senior Reviewer",    "phone": ""},
    ]

    # Delete existing users and insert clean unique users
    cur.execute("DELETE FROM users;")
    
    user_id_map = {} # email -> inserted id
    
    for u in users_list:
        e_orig = u["email"].strip().lower()
        e_hash = make_email_hash(e_orig)
        cur.execute("""
            INSERT INTO users (
                full_name, email, email_hash, email_original, password, employee_id,
                role_id, team_id, designation, phone, is_active, email_verified, approved, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 1, 'Active', datetime('now'));
        """, (
            u["name"], e_hash, e_hash, e_orig, default_pass, u["emp_id"],
            u["role_id"], u["team_id"], u["desig"], u["phone"]
        ))
        inserted_id = cur.lastrowid
        user_id_map[e_orig] = inserted_id
        user_id_map[u["emp_id"]] = inserted_id

    print(f"Clean Unique Users inserted: {len(users_list)}")

    # 5. Clean Decisions
    cur.execute("DELETE FROM decisions;")
    
    creator_1 = user_id_map.get("naveen@gmail.com", 1)
    creator_2 = user_id_map.get("koppalanaveen20@gmail.com", 2)
    creator_3 = user_id_map.get("naveen.k@corp.com", 1)
    creator_4 = user_id_map.get("koppala.naveen@corp.com", 3)

    decisions_data = [
        (
            1,
            "Final Year Project Selection",
            "Select Alzheimer's Disease Detection as final year project using multimodal deep learning and neuroimaging data.",
            "High",
            "Engineering & Research",
            "2026-07-02 18:32:07",
            "AI, Deep Learning, Healthcare, Research",
            5, # Academic & Research
            "Approved",
            creator_1,
            "2026-07-02 18:32:07",
            generate_hash("Final Year Project Selection", "Select Alzheimer's Disease Detection as final year project.", creator_1),
            "To develop an automated early-stage cognitive impairment detection system using 3D MRI scans.",
            "High societal impact, clinically validated dataset access (ADNI), strong baseline benchmark scores.",
            "Automates diagnostic biomarker detection, accelerates clinical screening, publishable research artifact.",
            "Handling multi-center scanner variance, domain shift, and patient privacy compliance (HIPAA/GDPR).",
            "Standardized ADNI preprocessing pipeline and availability of GPU compute resources.",
            "2026-07-02 18:35:00",
            creator_1
        ),
        (
            2,
            "Quarterly Architecture Review",
            "Evaluate microservices vs modular monolithic architecture scaling, fault tolerance, and security.",
            "Medium",
            "Architecture & DevOps",
            "2026-08-06 13:59:24",
            "Architecture, Microservices, Security, Scaling",
            1, # Technical
            "Approved",
            creator_2,
            "2026-08-06 13:59:24",
            generate_hash("Quarterly Architecture Review", "Evaluate microservices vs modular monolithic architecture.", creator_2),
            "To optimize platform scalability and support enterprise high-availability deployment.",
            "Modular architecture enables isolated failure domains and independent service scaling.",
            "99.9% service availability, isolated blast radius, faster CI/CD release cycles.",
            "Distributed tracing complexity and multi-database data consistency management.",
            "Kubernetes orchestration and containerized runtime environment.",
            "2026-08-06 14:00:00",
            creator_2
        ),
        (
            3,
            "Enterprise Security & Audit Trail Governance",
            "Implement SHA-256 integrity hashing, immutable audit logging, and role-based access control across all modules.",
            "Critical",
            "Cyber Security",
            "2026-08-10 10:15:00",
            "Security, Audit, RBAC, Integrity, Compliance",
            1, # Technical
            "Approved",
            creator_3,
            "2026-08-10 10:15:00",
            generate_hash("Enterprise Security & Audit Trail Governance", "Implement SHA-256 integrity hashing and RBAC.", creator_3),
            "Establish end-to-end security compliance and tamper-proof decision replay capabilities.",
            "Guarantees data integrity for all decision versions and reviewer comments.",
            "Zero data tampering, verifiable decision history, role segregation.",
            "Slight hashing overhead on large batch submissions.",
            "SHA-256 cryptographic standard meets enterprise security requirements.",
            "2026-08-10 10:20:00",
            creator_3
        ),
        (
            4,
            "Real-Time Collaborative Decision Review Workflow",
            "Deploy WebSocket and asynchronous notification pipelines for instantaneous reviewer assignment alerts.",
            "High",
            "Platform Engineering",
            "2026-08-15 09:30:00",
            "Collaboration, Workflow, Real-Time, Review",
            2, # Operational
            "Approved",
            creator_4,
            "2026-08-15 09:30:00",
            generate_hash("Real-Time Collaborative Decision Review Workflow", "Deploy real-time collaborative review workflow.", creator_4),
            "Reduce turnaround latency for decision approvals across cross-functional teams.",
            "Immediate alert dispatch eliminates email lag and improves reviewer responsiveness.",
            "50% reduction in approval cycle time, immediate stakeholder feedback.",
            "Handling transient network disconnections during live reviews.",
            "Fallback email dispatch ensures 100% notification delivery.",
            "2026-08-15 09:45:00",
            creator_4
        )
    ]

    cur.executemany("""
        INSERT INTO decisions (
            id, title, description, priority_level, department, decision_date, tags,
            category_id, status, created_by, created_at, content_hash,
            rationale_why, rationale_justification, rationale_benefits, rationale_risks, rationale_assumptions,
            rationale_updated_at, rationale_updated_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, decisions_data)

    print(f"Decisions retrieved and inserted: {len(decisions_data)}")

    # 6. Reviews
    cur.execute("DELETE FROM reviews;")
    reviewer_id = user_id_map.get("reviewer.naveen@corp.com", 11)
    reviews_data = [
        (1, 1, reviewer_id, "Approved", "Project methodology, clinical dataset access, and ethics compliance verified and approved.", "2026-07-02 18:39:30"),
        (2, 2, reviewer_id, "Approved", "Architecture plan conforms to enterprise scaling and security guidelines.", "2026-08-06 14:05:00"),
        (3, 3, reviewer_id, "Approved", "Cryptographic integrity hashing and RBAC matrix verified.", "2026-08-10 10:30:00"),
        (4, 4, reviewer_id, "Approved", "Collaborative workflow test passes all latency and fallback criteria.", "2026-08-15 10:00:00")
    ]
    cur.executemany("""
        INSERT INTO reviews (id, decision_id, reviewer_id, status, comments, reviewed_at)
        VALUES (?, ?, ?, ?, ?, ?);
    """, reviews_data)

    # 7. Activity Logs
    cur.execute("DELETE FROM activity_logs;")
    activity_data = [
        (1, creator_1, "Created Decision", "Decision #1: Final Year Project Selection created", "2026-07-02 18:32:07"),
        (2, reviewer_id, "Approved Decision", "Decision #1 approved by Reviewer", "2026-07-02 18:39:30"),
        (3, creator_2, "Created Decision", "Decision #2: Quarterly Architecture Review created", "2026-08-06 13:59:24"),
        (4, reviewer_id, "Approved Decision", "Decision #2 approved by Reviewer", "2026-08-06 14:05:00"),
        (5, creator_3, "Created Decision", "Decision #3: Enterprise Security Governance created", "2026-08-10 10:15:00"),
        (6, creator_4, "Created Decision", "Decision #4: Real-Time Collaborative Workflow created", "2026-08-15 09:30:00"),
    ]
    cur.executemany("""
        INSERT INTO activity_logs (id, user_id, action, details, created_at)
        VALUES (?, ?, ?, ?, ?);
    """, activity_data)

    conn.commit()
    conn.close()
    print("Database sync completed successfully!")

if __name__ == "__main__":
    sync_data()
