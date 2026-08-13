import sys, os, re
sys.path.insert(0, os.path.abspath('backend'))
from app.database.connection import SessionLocal
from app.models.decision import Decision
from app.models.alternative import Alternative

db = SessionLocal()
decisions = db.query(Decision).all()

def find_matching_decisions(query):
    stop_words = {'what', 'problem', 'did', 'i', 'add', 'for', 'this', 'title', 'is', 'the', 'a', 'an', 'in', 'of', 'to', 'my', 'decision', 'about', 'show', 'me', 'details', 'tell', 'give'}
    q_clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', query.lower())
    q_tokens = [w for w in q_clean.split() if w not in stop_words and len(w) > 1]
    
    scored = []
    for d in decisions:
        alts = db.query(Alternative).filter(Alternative.decision_id == d.id).all()
        alts_text = " ".join([f"{a.title} {a.description or ''}" for a in alts]).lower()
        d_text = f"{d.title} {d.description} {d.department or ''} {d.tags or ''} {alts_text}".lower()
        
        score = 0
        for t in q_tokens:
            if t in d.title.lower():
                score += 3
            elif t in d.description.lower():
                score += 2
            elif t in alts_text:
                score += 2
            elif t in d_text:
                score += 1
                
        if score > 0:
            scored.append((score, d, alts))
            
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored

queries = [
    "what problem did i add for this title Cloud mitigation",
    "what is the problem statement for Select Cloud Provider",
    "what problem did i add for Risk Mitigation on Resource Allocation",
    "what are the alternatives for Cloud Provider",
    "what decisions did i create",
    "status of DEC-28"
]

for q in queries:
    print(f"\n==========================================")
    print(f"QUERY: '{q}'")
    results = find_matching_decisions(q)
    print(f"FOUND {len(results)} MATCHES:")
    for score, d, alts in results:
        print(f"  [Score {score}] DEC-{d.id}: '{d.title}' (Status: {d.status})")
        print(f"    Problem/Description: '{d.description}'")
        print(f"    Alternatives: {[a.title for a in alts]}")

db.close()
