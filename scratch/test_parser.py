from core.parser import extract_claims_and_signatures

with open('data/targets/test_code.py', 'r') as f:
    source = f.read()

claims = extract_claims_and_signatures(source)
print(f"Total claims found: {len(claims)}")
for i, c in enumerate(claims, 1):
    print(f"{i}. {c['func_name']}: {c['claim']}")
    if c['precondition']:
        print(f"   Precondition: {c['precondition']}")
