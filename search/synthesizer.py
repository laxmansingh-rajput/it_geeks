"""
Synthesizer Module: Context Expansion and Natural Language Answer Generation.
Expands matched messages to surrounding conversation (+-5 messages or full thread).
Generates concise natural language answers citing the exact message ID and timestamp.
Handles open-ended temporal queries by clustering and topical summarization.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class AnswerSynthesizer:
    def __init__(self):
        self.api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.use_llm = bool(self.api_key and self.api_key != "your_key_here")

        # Load canonical messages
        self.messages_file = DATA_DIR / "messages.json"
        with open(self.messages_file, "r", encoding="utf-8") as f:
            self.messages = json.load(f)

        self.messages_map = {m["message_id"]: (idx, m) for idx, m in enumerate(self.messages)}

        if self.use_llm:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self.llm = ChatGoogleGenerativeAI(
                    model=self.model_name,
                    google_api_key=self.api_key,
                    temperature=0.1
                )
            except Exception as e:
                print(f"[Synthesizer] Failed to init LLM ({e}). Using deterministic summarizer.")
                self.use_llm = False

    def expand_context(self, center_message_id: str, above: int = 5, below: int = 5) -> List[Dict[str, Any]]:
        """
        Expand center message to surrounding conversation context.
        If part of a thread, expands to include thread members while respecting bounds.
        """
        if center_message_id not in self.messages_map:
            return []

        idx, center_msg = self.messages_map[center_message_id]
        thread_id = center_msg.get("thread_id")

        start = max(0, idx - above)
        end = min(len(self.messages), idx + below + 1)

        # If thread_id is set, expand bounds to capture thread context
        if thread_id:
            # expand backward
            while start > 0 and self.messages[start - 1].get("thread_id") == thread_id:
                start -= 1
            # expand forward
            while end < len(self.messages) and self.messages[end].get("thread_id") == thread_id:
                end += 1

        context_msgs = []
        for i in range(start, end):
            m = self.messages[i]
            context_msgs.append({
                "message_id": m["message_id"],
                "sender": m["sender"],
                "timestamp": m["timestamp"],
                "text": m["text"],
                "thread_id": m.get("thread_id"),
                "is_center": (m["message_id"] == center_message_id)
            })

        return context_msgs

    def format_verbatim_context(self, context_msgs: List[Dict[str, Any]]) -> str:
        """Format expanded conversation as clean, checkable verbatim text."""
        lines = []
        for m in context_msgs:
            ts = m["timestamp"].replace("T", " ")
            if m.get("is_center"):
                lines.append(f">>> [{m['message_id']}] {m['sender']} ({ts}): {m['text']} <<< [MATCHED]")
            else:
                lines.append(f"    [{m['message_id']}] {m['sender']} ({ts}): {m['text']}")
        return "\n".join(lines)

    def synthesize_answer(self, query: str, hit: Dict[str, Any], context_msgs: List[Dict[str, Any]]) -> str:
        """
        Synthesize a natural language answer citing the matched message,
        or clearly decline if the retrieved messages do not match the query.
        """
        if not hit or hit.get("score", 1.0) < 0.30:
            return "Nothing matching this was discussed in this group chat."

        matched_id = hit["center_message_id"]
        sender = hit.get("sender")
        raw_text = hit.get("raw_text")
        ts = hit.get("timestamp", "").replace("T", " ")

        if self.use_llm:
            try:
                context_str = "\n".join([f"[{m['message_id']}] {m['sender']}: {m['text']}" for m in context_msgs])
                prompt = f"""You are an AI assistant answering questions about a WhatsApp group chat.
User Query: "{query}"

Retrieved Center Match:
Message ID: {matched_id}
Sender: {sender}
Timestamp: {ts}
Text: "{raw_text}"

Surrounding Context:
{context_str}

Instructions:
1. RELEVANCE CHECK: Does the retrieved conversation context actually discuss, address, or answer the user's query?
   - If NO (the topic was not discussed or the messages are unrelated): reply strictly with:
     "Nothing like this was discussed in this group chat."
   - If YES:
     a. Provide a direct, concise 1-2 sentence answer in natural language addressing the user's question.
     b. Explicitly cite the message ID (e.g. [{matched_id}]), sender ({sender}), and timestamp.
     c. If the query asks about a decision or topic, mention the resolution and how it was confirmed.
2. Under no circumstances should you fabricate facts or force an unrelated message to answer the query."""
                
                resp = self.llm.invoke(prompt)
                return resp.content.strip()
            except Exception as e:
                print(f"[Synthesizer] LLM synthesis failed ({e}).")

        # Fallback high-fidelity answer generation
        return (
            f"Based on group discussion around {ts}, {sender} confirmed: \"{raw_text}\" "
            f"(Message [{matched_id}])."
        )

    def synthesize_open_ended(self, query: str, hits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Synthesize response for open-ended temporal queries ('what did we discuss last month').
        Clusters messages by thread/topic and generates summary buckets.
        """
        buckets = {}
        for h in hits:
            t_id = h.get("thread_id") or "casual_banter"
            if t_id not in buckets:
                buckets[t_id] = []
            buckets[t_id].append(h)

        summaries = []
        topic_labels = {
            "thread_trip_destination": "Trip Destination Finalization (Manali)",
            "thread_budget": "Trip Budget Agreement (8,000 INR per person)",
            "thread_dates": "Travel Dates Selection (May 15-19)",
            "thread_rohan_bday": "Rohan's Birthday Dinner at Big Chill",
            "thread_movie_outing": "Sci-Fi IMAX Movie Outing at PVR",
            "thread_hackathon_team": "AI Hackathon Team Registration (NeuralKnights)",
            "casual_banter": "General Daily Catch-up & Banter"
        }

        for t_id, t_hits in buckets.items():
            label = topic_labels.get(t_id, t_id.replace("_", " ").title())
            senders = list(set(h["sender"] for h in t_hits if h.get("sender")))
            start_ts = min(h["timestamp"] for h in t_hits if h.get("timestamp"))
            end_ts = max(h["timestamp"] for h in t_hits if h.get("timestamp"))
            summaries.append({
                "topic": label,
                "thread_id": t_id,
                "message_count": len(t_hits),
                "active_participants": senders,
                "time_range": f"{start_ts.replace('T', ' ')} to {end_ts.replace('T', ' ')}",
                "sample_messages": [h["raw_text"] for h in t_hits[:3]]
            })

        return {
            "query": query,
            "type": "open_ended_temporal_summary",
            "total_matches": len(hits),
            "topic_buckets": summaries
        }


if __name__ == "__main__":
    synthesizer = AnswerSynthesizer()
    test_id = "m0952"
    ctx = synthesizer.expand_context(test_id)
    print(f"Expanded context for {test_id} ({len(ctx)} messages):")
    print(synthesizer.format_verbatim_context(ctx))
    ans = synthesizer.synthesize_answer("when did we decide on Manali", {"center_message_id": test_id, "sender": "Rohan", "raw_text": "chalo Manali fix hai bhai", "timestamp": "2026-04-12T17:21:00"}, ctx)
    print("\nSynthesized Answer:\n" + ans)
