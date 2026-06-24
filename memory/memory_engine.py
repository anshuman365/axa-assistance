import chromadb
from sentence_transformers import SentenceTransformer
from memory.models import db, MemoryLog, Task
from datetime import datetime
import uuid
import json


class MemoryEngine:
    """
    4 memory types:
    - Episodic   : conversation history
    - Semantic   : facts/preferences, vector-searchable
    - Task       : open loops / pending goals
    - Entity     : people/places/projects (stored as memory_type='entity')
    """

    def __init__(self, persist_dir="./chroma_data"):
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection("axa_memory")
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")

    def store(self, user_id: int, content: str, memory_type: str, source: str = "chat"):
        vector_id = str(uuid.uuid4())
        embedding = self.embedder.encode(content).tolist()

        self.collection.add(
            ids=[vector_id],
            embeddings=[embedding],
            metadatas=[{"user_id": user_id, "memory_type": memory_type, "source": source}],
            documents=[content],
        )

        log = MemoryLog(
            user_id=user_id,
            memory_type=memory_type,
            content=content,
            source=source,
            vector_id=vector_id,
        )
        db.session.add(log)
        db.session.commit()
        return vector_id

    def recall(self, user_id: int, query: str, top_k: int = 5):
        query_embedding = self.embedder.encode(query).tolist()
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"user_id": user_id},
        )
        if not results["documents"] or not results["documents"][0]:
            return []
        return results["documents"][0]

    def get_recent_episodic(self, user_id: int, limit: int = 10):
        return (
            MemoryLog.query.filter_by(user_id=user_id, memory_type="episodic")
            .order_by(MemoryLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def extract_and_store(self, user_id: int, raw_text: str, llm_client, model: str, source="chat"):
        """
        Uses LLM to pull facts/tasks/entities out of any raw input
        (voice note, email, chat message). This is the 'chaotic info organizer'.
        """
        prompt = f"""Extract structured information from this text. Return JSON only, no markdown fences:
{{
  "facts": ["..."],
  "tasks": [{{"title": "...", "due_date": "YYYY-MM-DD or null"}}],
  "entities": ["person/place/project names mentioned"]
}}

Text: {raw_text}"""

        response = llm_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        try:
            extracted = json.loads(raw)
        except json.JSONDecodeError:
            return {"facts": [], "tasks": [], "entities": []}

        for fact in extracted.get("facts", []):
            self.store(user_id, fact, "fact", source)

        for task in extracted.get("tasks", []):
            due = None
            if task.get("due_date"):
                try:
                    due = datetime.strptime(task["due_date"], "%Y-%m-%d")
                except ValueError:
                    pass
            db.session.add(Task(
                user_id=user_id,
                title=task["title"],
                due_date=due,
                source=source,
            ))

        for entity in extracted.get("entities", []):
            self.store(user_id, entity, "entity", source)

        db.session.commit()
        return extracted
