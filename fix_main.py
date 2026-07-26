path = "main.py"
with open(path, "r", encoding="utf-8") as f:
    code = f.read()

code = code.replace(
    'profile["patient_profile_id"] if profile else None',
    'profile.id if profile else None'
)

with open(path, "w", encoding="utf-8") as f:
    f.write(code)
print("Fixed main.py")