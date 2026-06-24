from openai import OpenAI
from memory.memory_engine import MemoryEngine
from skills.email_skill import EmailSkill
from skills.calendar_skill import CalendarSkill
import json


class Orchestrator:
    """
    The brain. Flow:
    1. Take user message
    2. Pull relevant memory (episodic + semantic)
    3. Ask LLM to decide: just reply, or call a skill (function-calling style)
    4. Execute skill if needed
    5. Store conversation as episodic memory
    """

    SKILL_REGISTRY = {
        "email": EmailSkill,
        "calendar": CalendarSkill,
    }

    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "email_action",
                "description": "Read, search, send, or draft-reply to emails",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["read_unread", "search", "send", "draft_reply"]},
                        "params": {"type": "object"},
                    },
                    "required": ["action", "params"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_action",
                "description": "List, create, or delete calendar events",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "enum": ["list_upcoming", "create_event", "delete_event"]},
                        "params": {"type": "object"},
                    },
                    "required": ["action", "params"],
                },
            },
        },
    ]

    def __init__(self, config):
        self.config = config
        self.llm = OpenAI(api_key=config.OPENROUTER_API_KEY, base_url=config.OPENROUTER_BASE_URL)
        self.memory = MemoryEngine(config.CHROMA_PERSIST_DIR)

    def handle_message(self, user_id: int, message: str) -> dict:
        # 1. Pull context
        relevant_memories = self.memory.recall(user_id, message, top_k=5)
        recent_chat = self.memory.get_recent_episodic(user_id, limit=6)

        context = "\\n".join(relevant_memories)
        history_text = "\\n".join([f"{m.created_at}: {m.content}" for m in reversed(recent_chat)])

        system_prompt = f"""You are Axa, a personal AI assistant with real action capability.
You have access to the user's email and calendar (only if permission granted).
Relevant long-term memory:
{context}

Recent conversation:
{history_text}

If the user wants you to take an action (read email, schedule meeting, etc.), call the appropriate tool.
Otherwise just respond naturally and helpfully in the user's language (Hindi/English mix is fine)."""

        response = self.llm.chat.completions.create(
            model=self.config.LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            tools=self.TOOLS,
        )

        choice = response.choices[0]
        final_reply = ""
        actions_taken = []

        if choice.message.tool_calls:
            for tool_call in choice.message.tool_calls:
                fn_name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                skill_key = fn_name.replace("_action", "")

                skill_class = self.SKILL_REGISTRY.get(skill_key)
                if not skill_class:
                    continue

                skill = skill_class(user_id)
                result = skill.run(args["action"], args["params"])
                actions_taken.append({"skill": skill_key, "action": args["action"], "result": result})

            final_reply = self._summarize_actions(message, actions_taken)
        else:
            final_reply = choice.message.content

        # Store this turn as episodic memory
        self.memory.store(user_id, f"User: {message}\\nAxa: {final_reply}", "episodic", "chat")

        # Extract facts/tasks in background-style (synchronous here for simplicity)
        self.memory.extract_and_store(user_id, message, self.llm, self.config.LLM_MODEL, "chat")

        return {"reply": final_reply, "actions": actions_taken}

    def _summarize_actions(self, original_message, actions_taken):
        prompt = f"""User asked: {original_message}
Actions taken: {json.dumps(actions_taken, default=str)}

Summarize what happened in a short, natural reply to the user (Hindi/English mix ok)."""
        response = self.llm.chat.completions.create(
            model=self.config.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content
