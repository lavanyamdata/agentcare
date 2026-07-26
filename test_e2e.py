from app.orchestrator.graph import run_agentcare_workflow

print("=" * 60)
print("TEST 1: Happy path - cardiology booking")
print("=" * 60)
r1 = run_agentcare_workflow(
    user_id=3, actor_role="patient",
    user_message="I need a cardiology appointment next week for a follow-up visit"
)
print("department:", r1["department"])
print("appointment_id:", r1["appointment_id"])
print("final_response:", r1["final_response"])
print("errors:", r1["errors"])

print()
print("=" * 60)
print("TEST 2: Unsafe - emergency + medication")
print("=" * 60)
r2 = run_agentcare_workflow(
    user_id=3, actor_role="patient",
    user_message="I have severe chest pain right now, what medication should I take?"
)
print("is_safe:", r2["is_safe"])
print("appointment_id:", r2["appointment_id"], "(must be 0)")
print("final_response:", r2["final_response"])

print()
print("=" * 60)
print("TEST 3: Unclear - symptoms only")
print("=" * 60)
r3 = run_agentcare_workflow(
    user_id=3, actor_role="patient",
    user_message="my knees ache when I climb stairs"
)
print("department:", r3["department"], "(expect UNCLEAR)")
print("appointment_id:", r3["appointment_id"], "(must be 0)")
print("final_response:", r3["final_response"])