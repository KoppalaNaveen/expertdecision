import sys, os, difflib, re
sys.path.insert(0, os.path.abspath('backend'))
from app.database.connection import SessionLocal
from app.models.decision import Decision

db = SessionLocal()
decisions = db.query(Decision).all()
print(f"Total decisions found: {len(decisions)}")
for d in decisions:
    print(f"DEC-{d.id}: Title='{d.title}', Status='{d.status}', CreatedBy={d.created_by}")
    print(f"   Desc='{d.description}'")
    print(f"   Dept='{d.department}', Priority='{d.priority_level}'")
db.close()
