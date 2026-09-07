"""
Retriever Module: Vector Search + Payload Filtering over Qdrant.
Combines semantic similarity with sender_filter and date_range filters.
Dedupes hits by center_message_id (keeping highest score).
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, Range

from ingest.embed_and_store import get_qdrant_client, EmbeddingEngine, COLLECTION_NAME
from search.query_parser import ParsedQuery


def to_unix(iso_str: str) -> int:
    """Convert ISO timestamp string to unix epoch seconds."""
    dt = datetime.fromisoformat(iso_str)
    return int(dt.timestamp())


class GroupChatRetriever:
    def __init__(self, client: Optional[QdrantClient] = None, collection_name: str = COLLECTION_NAME, min_score_threshold: float = 0.32):
        self.client = client or get_qdrant_client()
        self.collection_name = collection_name
        self.embedder = EmbeddingEngine()
        self.min_score_threshold = min_score_threshold

    def retrieve(self, parsed_query: ParsedQuery, top_k: int = 8, min_score: Optional[float] = None) -> List[Dict[str, Any]]:
        """
        Execute filtered vector search or temporal scroll.
        Returns deduplicated ranked list of hits.
        Filters out low-similarity hits when no hard filters are present.
        """
        # Build Qdrant payload filters
        conditions = []

        if parsed_query.sender_filter:
            conditions.append(
                FieldCondition(
                    key="sender",
                    match=MatchValue(value=parsed_query.sender_filter)
                )
            )

        if parsed_query.date_range:
            start_unix = to_unix(parsed_query.date_range["start"])
            end_unix = to_unix(parsed_query.date_range["end"])
            conditions.append(
                FieldCondition(
                    key="timestamp",
                    range=Range(gte=start_unix, lte=end_unix)
                )
            )

        qfilter = Filter(must=conditions) if conditions else None

        # Handle open-ended date-only query without specific semantic topic
        if parsed_query.is_open_ended or not parsed_query.semantic_query:
            return self._scroll_filtered(qfilter, limit=top_k * 3)

        # Generate query vector
        query_vector = self.embedder.embed_query(parsed_query.semantic_query)

        # Execute search in Qdrant
        raw_hits = self._search_qdrant(query_vector, qfilter, limit=top_k * 2)

        # Determine threshold: relaxed for filtered queries, strict for open semantic queries
        threshold = min_score if min_score is not None else (0.0 if conditions else self.min_score_threshold)

        # Deduplicate hits by center_message_id, retaining highest score
        seen_centers = set()
        deduped_hits = []

        for hit in raw_hits:
            score = float(hit.score)
            if score < threshold:
                continue
            payload = hit.payload or {}
            center_id = payload.get("center_message_id")
            if not center_id or center_id in seen_centers:
                continue
            seen_centers.add(center_id)
            deduped_hits.append({
                "center_message_id": center_id,
                "score": score,
                "sender": payload.get("sender"),
                "timestamp": payload.get("timestamp_iso"),
                "thread_id": payload.get("thread_id"),
                "raw_text": payload.get("raw_text"),
                "window_text": payload.get("window_text")
            })

            if len(deduped_hits) >= top_k:
                break

        return deduped_hits

    def _search_qdrant(self, query_vector: List[float], qfilter: Optional[Filter], limit: int):
        """Invoke search across various qdrant-client versions."""
        try:
            # search method
            return self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=qfilter,
                limit=limit
            )
        except AttributeError:
            # query_points fallback in newer clients
            res = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=qfilter,
                limit=limit
            )
            return res.points

    def _scroll_filtered(self, qfilter: Optional[Filter], limit: int) -> List[Dict[str, Any]]:
        """Scroll points when only filters apply without vector search."""
        points, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=qfilter,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        hits = []
        for p in points:
            payload = p.payload or {}
            hits.append({
                "center_message_id": payload.get("center_message_id"),
                "score": 1.0,
                "sender": payload.get("sender"),
                "timestamp": payload.get("timestamp_iso"),
                "thread_id": payload.get("thread_id"),
                "raw_text": payload.get("raw_text"),
                "window_text": payload.get("window_text")
            })
        return hits


if __name__ == "__main__":
    from search.query_parser import QueryParser

    parser = QueryParser()
    retriever = GroupChatRetriever()

    test_q = "when did we decide on Manali"
    parsed = parser.parse(test_q)
    print("Parsed:", parsed)
    results = retriever.retrieve(parsed, top_k=5)
    print(f"\nTop {len(results)} hits for '{test_q}':")
    for idx, r in enumerate(results, 1):
        print(f"{idx}. [{r['center_message_id']}] ({r['score']:.4f}) {r['sender']} ({r['timestamp']}): {r['raw_text']}")
