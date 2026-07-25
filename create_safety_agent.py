import os

content = '''import logging
import json
from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL
from app.orchestrator.state import AgentState
from app.services import escalation_service, workflow_service

logger = logging.getLogger("agentcare.agents.safety")

# ── System prompt — this is what makes it a distinct agent ──
SAFETY_SYSTEM_PROMPT = """
You are the Safety and Escalation Agent for a hospital administration system.

Your ONLY job is to read a patient message and decide if it is safe to process
administratively, or if it must be escalated to a human immediately.

Escalate immediately if the message contains ANY of:
- Emergency or life-threatening language (chest pain, can't breathe, stroke, 
  heart attack, severe bleeding, unconscious, suicide)
- A request for diagnosis ("what disease do I have", "do I have cancer")
- A request for medication, dosage, or prescription
- A request to change an existing treatment or prescription

If NONE of the above apply, it is safe — routine admin requests like booking
appointments, uploading documents, or checking schedules are always safe.

Respond ONLY in this exact JSON format, nothing else:
{
  "is_safe": true or false,
  "escalation_reason": "reason if unsafe, empty string if safe"
}
""".strip()

# ── The agent function ───────────────────────────────────────
def run_safety_agent(state: AgentState) -> AgentState:
    """
    Reads the patient message from state.
    Calls LLM with safety system prompt.
    Writes is_safe and escalation_reason back to state.
    If unsafe, creates an escalation record in DB.
    """
    logger.info(f"Safety agent running for workflow_run_id={state.get('workflow_run_id')}")

    client = Groq(api_key=GROQ_API_KEY)
    try:
        # ── Call LLM with safety prompt ──────────────────────
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": SAFETY_SYSTEM_PROMPT},
                {"role": "user",   "content": state["user_message"]}
            ],
            temperature=0,        # 0 = deterministic, no creativity for safety decisions
            max_tokens=150        # safety decision is short, no need for more
        )

        raw = response.choices[0].message.content.strip()
        logger.debug(f"Safety agent raw response: {raw}")

        # ── Parse LLM JSON response ──────────────────────────
        result = json.loads(raw)
        is_safe = result.get("is_safe", True)
        escalation_reason = result.get("escalation_reason", "")

    except json.JSONDecodeError as e:
        # LLM returned something we couldn't parse — fail safe by escalating
        logger.error(f"Safety agent JSON parse error: {e} | raw={raw}")
        is_safe = False
        escalation_reason = "Safety agent could not parse LLM response — escalating as precaution"

    except Exception as e:
        logger.error(f"Safety agent error: {e}")
        is_safe = False
        escalation_reason = f"Safety agent encountered an error: {str(e)}"

    # ── Write decision to state ──────────────────────────────
    state["is_safe"] = is_safe
    state["escalation_reason"] = escalation_reason

    # ── If unsafe, create escalation record in DB ────────────
    if not is_safe:
        logger.warning(f"Unsafe request detected: {escalation_reason}")
        try:
            escalation_service.create_escalation(
                workflow_run_id=state["workflow_run_id"],
                reason=escalation_reason
            )
        except Exception as e:
            logger.error(f"Failed to create escalation record: {e}")
            state["errors"].append(f"Escalation record failed: {str(e)}")

    # ── Persist state snapshot to DB ─────────────────────────
    try:
        workflow_service.update_workflow_state(
            workflow_run_id=state["workflow_run_id"],
            current_step="safety",
            state=state,
            status="running" if is_safe else "escalated"
        )
    except Exception as e:
        logger.error(f"Failed to update workflow state after safety check: {e}")
        state["errors"].append(f"Workflow state update failed: {str(e)}")

    logger.info(f"Safety agent complete: is_safe={is_safe}")
    return state
'''

os.makedirs("app/agents", exist_ok=True)

with open("app/agents/__init__.py", "w", encoding="utf-8") as f:
    f.write("")

with open("app/agents/safety_agent.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Created: app/agents/__init__.py")
print("Created: app/agents/safety_agent.py")
print("Done.")