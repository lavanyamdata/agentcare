content = '''import logging
import json
from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL
from app.orchestrator.state import AgentState
from app.services import appointment_service, workflow_service

logger = logging.getLogger("agentcare.agents.appointment")

APPOINTMENT_SYSTEM_PROMPT = """
You are the Appointment Agent for a hospital administration system.

The patient's request and department are already validated. Your job:
1. Call list_available_slots to see open slots for the department.
2. Pick the earliest slot that reasonably matches the patient's request
   (e.g. "next week" means prefer slots roughly 5-10 days out; if nothing
   matches the preference, pick the earliest available).
3. Call book_slot with that slot_id and a short administrative reason
   summarizing the patient's request (never a diagnosis).
4. After booking succeeds, respond with a one-sentence plain-text
   confirmation for the patient.

Rules:
- Book exactly ONE appointment. Never book twice.
- If list_available_slots returns no slots, do NOT book anything —
  respond exactly: NO_SLOTS_AVAILABLE
- Never invent slot ids. Only use ids returned by list_available_slots.
""".strip()


def run_appointment_agent(state: AgentState) -> AgentState:
    """Tool-calling agent: LLM decides which tools to call and when.
    Code executes the tools against real services and feeds results back."""
    logger.info(f"Appointment agent running for workflow_run_id={state.get('workflow_run_id')}")

    client = Groq(api_key=GROQ_API_KEY)

    # Tool schemas the LLM can call. Patient identity comes from state,
    # never from the LLM - it only chooses slot_id and reason.
    tools = [
        {
            "type": "function",
            "function": {
                "name": "list_available_slots",
                "description": "List open appointment slots for the patient's department.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "book_slot",
                "description": "Book one appointment slot for the patient.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "slot_id": {"type": "integer", "description": "id from list_available_slots"},
                        "reason": {"type": "string", "description": "short administrative reason"},
                    },
                    "required": ["slot_id", "reason"],
                },
            },
        },
    ]

    def execute_tool(name: str, args: dict) -> dict:
        """Map LLM tool calls to real service functions. Identity injected from state."""
        if name == "list_available_slots":
            slots = appointment_service.get_available_slots(
                department_id=state["department_id"]
            )
            return {"slots": slots}
        if name == "book_slot":
            conflict = appointment_service.check_conflicts(
                patient_profile_id=state["patient_profile_id"],
                slot_id=args["slot_id"],
            )
            if conflict.get("has_conflict"):
                return {"error": "conflict", "detail": conflict}
            result = appointment_service.book_appointment(
                patient_profile_id=state["patient_profile_id"],
                slot_id=args["slot_id"],
                reason=args["reason"],
                actor_role=state["actor_role"],
                actor_id=state["user_id"],
            )
            state["slot_id"] = args["slot_id"]
            state["appointment_id"] = result.get("appointment_id", 0)
            return result
        return {"error": f"unknown tool {name}"}

    messages = [
        {"role": "system", "content": APPOINTMENT_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"Department: {state['department']} (id={state['department_id']}). "
            f"Patient request: {state['user_message']}"
        )},
    ]

    try:
        for iteration in range(5):  # hard cap - never loop forever
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0,
                max_tokens=500,
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                state["final_response"] = (msg.content or "").strip()
                logger.info(f"Appointment agent finished after {iteration} tool rounds")
                break

            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                logger.info(f"LLM called tool: {tc.function.name}({args})")
                result = execute_tool(tc.function.name, args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str),
                })
        else:
            logger.warning("Appointment agent hit iteration cap without finishing")
            state["errors"].append("Appointment agent iteration cap reached")

    except Exception as e:
        logger.error(f"Appointment agent error: {e}")
        state["errors"].append(f"Appointment agent: {str(e)}")

    try:
        workflow_service.update_workflow_state(
            workflow_run_id=state["workflow_run_id"],
            current_step="appointment",
            state=state,
            status="running",
        )
    except Exception as e:
        logger.error(f"Failed to update workflow state after appointment: {e}")
        state["errors"].append(f"Workflow state update failed: {str(e)}")

    return state
'''

with open("app/agents/appointment_agent.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Created: app/agents/appointment_agent.py")