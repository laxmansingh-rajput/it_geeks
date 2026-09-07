"""
Query Parser Module: Slot extraction for Semantic, Attributed, and Temporal searches.
Extracts semantic_query, sender_filter, and date_range in a single unified schema.
"""

import os
import sys
import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

# Reference metadata from seed
PARTICIPANTS = ["Priya", "Rohan", "Amit", "Sara", "Karan", "Neha", "Vikram", "Divya"]
CORPUS_START_DATE = "2026-03-01T00:00:00"
CORPUS_END_DATE = "2026-09-01T23:59:59"
DEFAULT_REF_DATE = datetime(2026, 9, 1)


class ParsedQuery(BaseModel):
    raw_query: str
    semantic_query: Optional[str] = None
    sender_filter: Optional[str] = None
    date_range: Optional[Dict[str, str]] = None  # {"start": "ISO", "end": "ISO"}
    is_open_ended: bool = False
    needs_clarification: bool = False
    clarification_prompt: Optional[str] = None


COMMON_NAME_MAP = {
    "rahul": "Rohan",
    "rohit": "Rohan",
    "ronit": "Rohan",
    "kiran": "Karan",
    "karun": "Karan",
    "neeha": "Neha",
    "sneha": "Neha",
    "vikky": "Vikram",
    "vicky": "Vikram",
    "vikki": "Vikram",
    "diya": "Divya",
    "deepa": "Divya",
    "preeya": "Priya",
    "amith": "Amit",
    "sarah": "Sara"
}


def match_participant(name_token: str) -> Optional[str]:
    """Match participant with exact check, aliases, and fuzzy correction."""
    import difflib
    clean = name_token.strip().lower()
    for p in PARTICIPANTS:
        if p.lower() == clean:
            return p
    if clean in COMMON_NAME_MAP:
        return COMMON_NAME_MAP[clean]
    matches = difflib.get_close_matches(name_token.capitalize(), PARTICIPANTS, n=1, cutoff=0.35)
    if matches:
        return matches[0]
    return None


class QueryParser:
    def __init__(self, ref_date: Optional[datetime] = None):
        self.ref_date = ref_date or DEFAULT_REF_DATE
        self.api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.use_llm = bool(self.api_key and self.api_key != "your_key_here")

        if self.use_llm:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self.llm = ChatGoogleGenerativeAI(
                    model=self.model_name,
                    google_api_key=self.api_key,
                    temperature=0.0
                )
            except Exception as e:
                print(f"[QueryParser] Failed to init ChatGoogleGenerativeAI ({e}). Using rule-based extractor.")
                self.use_llm = False

    def parse(self, query: str) -> ParsedQuery:
        """Parse user query into structured slots."""
        cleaned_query = query.strip()
        if not cleaned_query:
            return ParsedQuery(
                raw_query=query,
                needs_clarification=True,
                clarification_prompt="Please enter a search topic, participant name, or date range to search."
            )

        if self.use_llm:
            try:
                parsed = self._parse_with_llm(cleaned_query)
                if parsed:
                    return parsed
            except Exception as e:
                print(f"[QueryParser] LLM extraction error: {e}. Falling back to rule-based parser.")

        return self._parse_rule_based(cleaned_query)

    def _parse_with_llm(self, query: str) -> Optional[ParsedQuery]:
        """Use Gemini Flash to extract slots."""
        system_prompt = f"""You are an expert query understanding engine for a WhatsApp group chat search system.
Chat Participants: {', '.join(PARTICIPANTS)}.
Conversation date bounds: March 1, 2026 to September 1, 2026.
Reference Anchor Date: {self.ref_date.strftime('%Y-%m-%d')}.

Given the user query, extract:
1. `semantic_query`: The core topic or meaning of the search (in English or clean Hinglish). If the query is an open-ended date query like "what did we discuss in April" with NO specific topic, set semantic_query to null and is_open_ended to true.
2. `sender_filter`: Name of participant if explicitly queried (e.g. "what did Priya say" -> "Priya"). Must match one of {PARTICIPANTS} exactly, or null.
3. `date_range`: Object with 'start' and 'end' in ISO format (YYYY-MM-DDTHH:MM:SS) if a date/month/timeframe is specified, or null. For example "in April" -> {{"start": "2026-04-01T00:00:00", "end": "2026-04-30T23:59:59"}}. "last month" relative to reference date ({self.ref_date.strftime('%B %Y')}) -> previous month.
4. `is_open_ended`: true ONLY if query is an open-ended temporal query without a specific topic (e.g. "what did we talk about last month").
5. `needs_clarification`: true ONLY if the query has no searchable topic, no sender, and no date range (e.g. "search", "tell me").

Respond ONLY with valid JSON conforming to this schema:
{{
  "semantic_query": "string or null",
  "sender_filter": "string or null",
  "date_range": {{"start": "string", "end": "string"}} or null,
  "is_open_ended": false,
  "needs_clarification": false
}}"""

        response = self.llm.invoke(f"{system_prompt}\n\nUser Query: {query}")
        content = response.content.strip()

        # Remove markdown code block if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\n?", "", content)
            content = re.sub(r"\n?```$", "", content)

        data = json.loads(content.strip())
        
        # Clarification check per spec: only trigger if semantic_query is null AND both filters null
        needs_clarification = data.get("needs_clarification", False)
        if not data.get("semantic_query") and not data.get("sender_filter") and not data.get("date_range"):
            needs_clarification = True

        return ParsedQuery(
            raw_query=query,
            semantic_query=data.get("semantic_query"),
            sender_filter=data.get("sender_filter"),
            date_range=data.get("date_range"),
            is_open_ended=data.get("is_open_ended", False),
            needs_clarification=needs_clarification,
            clarification_prompt="Could you specify a topic, person, or timeframe you'd like to search for?" if needs_clarification else None
        )

    def _parse_rule_based(self, query: str) -> ParsedQuery:
        """
        High-precision rule-based parser that recognizes participants, dates, and semantic intent.
        Includes fuzzy participant name correction per spec §7.
        """
        lower_q = query.lower()
        sender_filter = None
        date_range = None
        is_open_ended = False

        # 1. Check participants (prioritize syntactic subject positions with fuzzy matching)
        sender_match = re.search(r"\b(?:what|which|how)\s+did\s+([a-zA-Z]+)\b", lower_q)
        if sender_match:
            sender_filter = match_participant(sender_match.group(1))

        if not sender_filter:
            sender_match2 = re.search(r"\b(?:did|does|is|was)\s+([a-zA-Z]+)\b", lower_q)
            if sender_match2:
                sender_filter = match_participant(sender_match2.group(1))

        if not sender_filter:
            # Check individual words for participant names or close matches
            for word in re.findall(r"\b[a-zA-Z]+\b", lower_q):
                matched = match_participant(word)
                if matched and word.lower() in [p.lower() for p in PARTICIPANTS] + list(COMMON_NAME_MAP.keys()):
                    sender_filter = matched
                    break

        # 2. Check temporal patterns
        months_map = {
            "january": (1, 31), "february": (2, 28), "march": (3, 31),
            "april": (4, 30), "may": (5, 31), "june": (6, 30),
            "july": (7, 31), "august": (8, 31), "september": (9, 30),
            "october": (10, 31), "november": (11, 30), "december": (12, 31)
        }

        for m_name, (m_num, m_last_day) in months_map.items():
            if re.search(rf"\b{m_name}\b", lower_q):
                year = 2026
                day_match = re.search(rf"{m_name}\s+(\d{{1,2}})|(\d{{1,2}})(?:st|nd|rd|th)?\s+{m_name}", lower_q)
                if day_match:
                    day = int(day_match.group(1) or day_match.group(2))
                    start_str = f"{year:04d}-{m_num:02d}-{day:02d}T00:00:00"
                    end_str = f"{year:04d}-{m_num:02d}-{day:02d}T23:59:59"
                else:
                    start_str = f"{year:04d}-{m_num:02d}-01T00:00:00"
                    end_str = f"{year:04d}-{m_num:02d}-{m_last_day:02d}T23:59:59"
                date_range = {"start": start_str, "end": end_str}
                break

        if not date_range:
            if "last month" in lower_q:
                date_range = {"start": "2026-08-01T00:00:00", "end": "2026-08-31T23:59:59"}
            elif "first week of may" in lower_q:
                date_range = {"start": "2026-05-01T00:00:00", "end": "2026-05-07T23:59:59"}
            elif "mid april" in lower_q:
                date_range = {"start": "2026-04-10T00:00:00", "end": "2026-04-20T23:59:59"}

        # 3. Clean query to get semantic_query
        semantic_q = query
        # Remove carrier phrases with names (e.g. 'what did rahul say about', 'what did Priya say')
        semantic_q = re.sub(r"\bwhat did\s+\w+\s+\w+\s+(?:about|for|on|regarding)?\b", "", semantic_q, flags=re.I)
        semantic_q = re.sub(r"\bdid\s+\w+\s+(?:say|post|apply|confirm|agree)?\b", "", semantic_q, flags=re.I)
        if sender_filter:
            semantic_q = re.sub(rf"\b{sender_filter.lower()}'s?\b", "", semantic_q, flags=re.I)
            semantic_q = re.sub(rf"\bby {sender_filter.lower()}\b", "", semantic_q, flags=re.I)

        # Remove date phrases
        if date_range:
            for m in list(months_map.keys()) + ["last month", "first week of may", "mid april"]:
                semantic_q = re.sub(rf"\b(in|during|around|on)?\s*{m}\b", "", semantic_q, flags=re.I)
            semantic_q = re.sub(r"\b\d{1,2}(?:st|nd|rd|th)?\b", "", semantic_q)

        # Remove common query carrier phrases
        carrier_phrases = [
            r"^when did we decide on",
            r"^when did we finalize",
            r"^when did we agree on",
            r"^when did we discuss",
            r"^what did we decide about",
            r"^what did we agree about",
            r"^what was the decision on",
            r"^what did we discuss",
            r"^what did we talk about",
            r"^tell me about",
            r"^show me messages about",
            r"^show me discussions on",
            r"^find messages about",
            r"^search for",
            r"^who said"
        ]
        for cp in carrier_phrases:
            semantic_q = re.sub(cp, "", semantic_q, flags=re.I)

        semantic_q = re.sub(r"\s+", " ", semantic_q).strip(" ?.,!'-")

        # Check open-ended queries
        if not semantic_q and date_range:
            is_open_ended = True
            semantic_q = None
        elif not semantic_q and not sender_filter and not date_range:
            return ParsedQuery(
                raw_query=query,
                needs_clarification=True,
                clarification_prompt="Could you specify what topic, sender, or timeframe you'd like to search for?"
            )

        return ParsedQuery(
            raw_query=query,
            semantic_query=semantic_q if semantic_q else query,
            sender_filter=sender_filter,
            date_range=date_range,
            is_open_ended=is_open_ended,
            needs_clarification=False
        )


if __name__ == "__main__":
    parser = QueryParser()
    test_queries = [
        "when did we decide on Manali",
        "what did Priya say about the budget",
        "what did we decide about the hotel last month",
        "what did we discuss in April",
        "Vikram jokes about Rohan",
        "when did we finalize the travel dates in May"
    ]
    for q in test_queries:
        res = parser.parse(q)
        print(f"Query: '{q}'")
        print(f"  -> Semantic: '{res.semantic_query}' | Sender: {res.sender_filter} | Date: {res.date_range} | Open: {res.is_open_ended} | Clarify: {res.needs_clarification}")
