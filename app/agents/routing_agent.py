import logging
import json
from groq import Groq
from app.config import GROQ_API_KEY, GROQ_MODEL
from app.orchestrator.state import AgentState
from app.services import workflow_service
from app.database.session import get_db
from app.database.models import Department

logger = logging.getLogger("agentcare.agents.routing")

ROUTING_SYSTEM_PROMPT = """
You are the Department Routing Agent for a hospital administration system.

Your ONLY job: read a patient's administrative request and map it to one of the
valid departments listed below, based on what the patient EXPLICITLY asked for.

Rules:
- Route based on the patient's stated intent (e.g. "cardiology appointment" -> Cardiology).
- NEVER infer a department from symptoms. If the patient describes symptoms
  ("my chest hurts", "I get headaches") without naming a department or service,
  respond with UNCLEAR. Choosing a department from symptoms is a medical judgment
  and is not allowed.
- If the request mentions a department or specialty not in the valid list,
  respond with UNCLEAR.
- If the request is not about appointments or departments at all, respond with UNCLEAR.

{department_list}

Respond ONLY in this exact JSON format, nothing else:
{{
  "department": "exact department name from the list, or UNCLEAR",
  "department_id": the integer id, or 0 if UNCLEAR,
  "reasoning": "one short sentence explaining the routing decision"
}}
""".strip()


def _get_departments() -> list:
    """Fetch active departments from DB so the prompt always matches reality."""
    with get_db() as db:
        departments = db.query(Department).filter(Department.active == True).all()
        return [{"id": d.id, "name": d.name} for d in departments]


def run_routing_agent(state: AgentState) -> AgentState:
    """
    Reads user_message from state.
    Fetches valid departments from DB, injects into prompt.
    LLM classifies administrative intent -> department.
    Writes department + department_id to state.
    UNCLEAR -> is_safe stays True but department_id=0 signals escalation path.
    """
    logger.info(f"Routing agent running for workflow_run_id={state.get('workflow_run_id')}")

    departments = _get_departments()
    dept_lines = "\n".join([f"- {d['name']} (id={d['id']})" for d in departments])
    department_list = f"Valid departments:\n{dept_lines}"

    prompt = ROUTING_SYSTEM_PROMPT.format(department_list=department_list)

    client = Groq(api_key=GROQ_API_KEY)

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user",   "content": state["user_message"]}
            ],
            temperature=0,
            max_tokens=200
        )

        raw = response.choices[0].message.content.strip()
        logger.debug(f"Routing agent raw response: {raw}")

        result = json.loads(raw)
        department = result.get("department", "UNCLEAR")
        department_id = result.get("department_id", 0)
        reasoning = result.get("reasoning", "")

        valid_ids = {d["id"] for d in departments}
        if department != "UNCLEAR" and department_id not in valid_ids:
            logger.warning(f"LLM returned invalid department_id={department_id} - forcing UNCLEAR")
            department = "UNCLEAR"
            department_id = 0
            reasoning = "LLM returned a department not in the valid list"

    except json.JSONDecodeError as e:
        logger.error(f"Routing agent JSON parse error: {e}")
        department = "UNCLEAR"
        department_id = 0
        reasoning = "Could not parse LLM response"

    except Exception as e:
        logger.error(f"Routing agent error: {e}")
        department = "UNCLEAR"
        department_id = 0
        reasoning = f"Routing error: {str(e)}"
        state["errors"].append(f"Routing agent: {str(e)}")

    state["department"] = department
    state["department_id"] = department_id

    logger.info(f"Routing decision: {department} (id={department_id}) | {reasoning}")

    try:
        workflow_service.update_workflow_state(
            workflow_run_id=state["workflow_run_id"],
            current_step="routing",
            state=state,
            status="running"
        )
    except Exception as e:
        logger.error(f"Failed to update workflow state after routing: {e}")
        state["errors"].append(f"Workflow state update failed: {str(e)}")

    return state
