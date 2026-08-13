import sys, os
sys.path.insert(0, os.path.abspath('backend'))
from app.services.ai_support_service import generate_ai_response

test_queries = [
    "what problem did i add for this title Cloud mitigation",
    "what is the problem statement for Select Cloud Provider",
    "what problem did i add for Risk Mitigation on Resource Allocation",
    "what are the alternatives for Cloud Provider",
    "what is the status of DEC-28",
    "what decisions did i create",
    "show my decisions"
]

for idx, q in enumerate(test_queries, 1):
    resp = generate_ai_response(q, user_name="Naveen", user_id=30)
    print(f"\n=======================================================")
    print(f"TEST {idx}: \"{q}\"")
    print(f"SOURCE: {resp.get('source')}")
    print(f"REPLY:\n{resp.get('reply')}")
    print(f"CHIPS: {resp.get('suggested_actions')}")
