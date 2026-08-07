import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database.connection import SessionLocal, Base, engine
from app.models.role import Role
from app.models.user import User
from app.core.security import hash_password
import hashlib

def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # 1. Seed Roles if empty
    existing_roles = db.query(Role).all()
    if not existing_roles:
        r_admin = Role(id=1, role_name="Administrator", description="Full platform access")
        r_manager = Role(id=2, role_name="Manager", description="Team management and approval")
        r_employee = Role(id=3, role_name="Employee", description="Create and submit decisions")
        r_reviewer = Role(id=4, role_name="Reviewer", description="Review assigned decisions")
        db.add_all([r_admin, r_manager, r_employee, r_reviewer])
        db.commit()
        print("Seeded 4 Roles.")
    else:
        # Make sure role names exist
        role_names = [r.role_name for r in existing_roles]
        if "Administrator" not in role_names:
            db.add(Role(id=1, role_name="Administrator", description="Full platform access"))
        if "Manager" not in role_names:
            db.add(Role(id=2, role_name="Manager", description="Team management and approval"))
        if "Employee" not in role_names:
            db.add(Role(id=3, role_name="Employee", description="Create and submit decisions"))
        if "Reviewer" not in role_names:
            db.add(Role(id=4, role_name="Reviewer", description="Review assigned decisions"))
        db.commit()

    # Use passlib-compatible hashed password
    pass_hash = hash_password("password123")

    def make_email_hash(email):
        return hashlib.sha256(email.strip().lower().encode('utf-8')).hexdigest()

    # ============================================================
    # ORIGINAL USERS from the user's screenshot
    # All passwords reset to password123 (originals unknown)
    # ============================================================
    users_data = [
        # From screenshot row 1
        {"full_name": "Koppala Naveen",  "email": "koppala.naveen@corp.com",   "employee_id": "EMP8749",  "role_id": 3, "designation": "Software",          "phone": "",            "status": "Active",    "is_active": True},
        # From screenshot row 2
        {"full_name": "Manager",          "email": "manager@corp.com",           "employee_id": "MN1297",   "role_id": 2, "designation": "Software",          "phone": "",            "status": "Active",    "is_active": True},
        # From screenshot row 3
        {"full_name": "Admin",            "email": "admin@corp.com",             "employee_id": "AD3341",   "role_id": 1, "designation": "Software",          "phone": "",            "status": "Active",    "is_active": True},
        # From screenshot row 4 (Reviewer - exact ID unclear from screenshot)
        {"full_name": "Reviewer",         "email": "reviewer@corp.com",          "employee_id": "RW1300",   "role_id": 4, "designation": "Developer",         "phone": "",            "status": "Active",    "is_active": True},
        # From screenshot row 5
        {"full_name": "Vaibhav Ingle",    "email": "vaibhav.ingle@corp.com",    "employee_id": "AD01019",  "role_id": 1, "designation": "",                  "phone": "",            "status": "Inactive",  "is_active": False},
        # From screenshot row 6
        {"full_name": "user1",            "email": "user1@replay.com",           "employee_id": "MN1001",   "role_id": 2, "designation": "Software",          "phone": "0000000000",  "status": "Active",    "is_active": True},
        # From screenshot row 7
        {"full_name": "Naveen",           "email": "naveen.classic@corp.com",   "employee_id": "MN06116",  "role_id": 2, "designation": "",                  "phone": "",            "status": "Active",    "is_active": True},
        # From screenshot row 8
        {"full_name": "user3",            "email": "user3@replay.com",           "employee_id": "MN8BP1",   "role_id": 2, "designation": "Software",          "phone": "0000000000",  "status": "Inactive",  "is_active": False},
        # From screenshot row 9
        {"full_name": "User2",            "email": "user2@replay.com",           "employee_id": "MN1800",   "role_id": 2, "designation": "",                  "phone": "0000000000",  "status": "Inactive",  "is_active": False},
        # From screenshot row 10
        {"full_name": "Naveen K",         "email": "naveenk@corp.com",          "employee_id": "AD06116",  "role_id": 1, "designation": "",                  "phone": "",            "status": "Inactive",  "is_active": False},
        # From screenshot row 11
        {"full_name": "Sha",              "email": "sha@corp.com",               "employee_id": "EMP33333", "role_id": 3, "designation": "",                  "phone": "",            "status": "Active",    "is_active": True},
        # From screenshot row 12
        {"full_name": "E2E Test User",    "email": "e2e.test@corp.com",         "employee_id": "EMP589",   "role_id": 3, "designation": "QA",                "phone": "9000000000",  "status": "Inactive",  "is_active": False},
    ]

    updated = 0
    added = 0
    skipped = 0

    for ud in users_data:
        e_hash = make_email_hash(ud["email"])
        approved = ud["status"] == "Active"

        # Find by employee_id first (most reliable key)
        existing = db.query(User).filter(User.employee_id == ud["employee_id"]).first()

        if existing:
            existing.full_name = ud["full_name"]
            existing.email = e_hash
            existing.email_hash = e_hash
            existing.email_original = ud["email"].strip().lower()
            existing.password = pass_hash
            existing.role_id = ud["role_id"]
            existing.designation = ud["designation"]
            existing.phone = ud["phone"]
            existing.approved = approved
            existing.status = ud["status"]
            existing.email_verified = True
            existing.is_active = ud["is_active"]
            try:
                db.commit()
                updated += 1
                print(f"  Updated: {ud['full_name']} ({ud['employee_id']})")
            except Exception as e:
                db.rollback()
                print(f"  WARNING update {ud['full_name']}: {e}")
                skipped += 1
        else:
            new_user = User(
                full_name=ud["full_name"],
                email=e_hash,
                email_hash=e_hash,
                email_original=ud["email"].strip().lower(),
                employee_id=ud["employee_id"],
                password=pass_hash,
                role_id=ud["role_id"],
                designation=ud["designation"],
                phone=ud["phone"],
                approved=approved,
                status=ud["status"],
                email_verified=True,
                is_active=ud["is_active"]
            )
            db.add(new_user)
            try:
                db.commit()
                added += 1
                print(f"  Added:   {ud['full_name']} ({ud['employee_id']})")
            except Exception as e:
                db.rollback()
                print(f"  WARNING add {ud['full_name']}: {e}")
                skipped += 1

    db.close()
    print(f"\nDone! Updated: {updated}, Added: {added}, Skipped: {skipped}")
    print("\nAll login credentials (Employee ID + password123):")
    print("-" * 65)
    for ud in users_data:
        print(f"  {ud['full_name']:<22} | ID: {ud['employee_id']:<12} | Status: {ud['status']}")
    print("-" * 65)
    print("Password for ALL accounts: password123")

if __name__ == "__main__":
    seed_database()
