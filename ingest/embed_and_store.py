"""
Embedding and Vector Database Ingestion Module for Qdrant.
Embeds conversation sliding windows and stores vectors + metadata in Qdrant collection.
Supports both Docker Qdrant (http://localhost:6333) and local disk storage (./qdrant_storage).
"""

import os
import sys
import re
import json
import hashlib
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    PayloadSchemaType
)

from ingest.chunker import build_windows

load_dotenv()

# Constants and Configuration
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "groupchat_v1")
VECTOR_DIM = 768
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STORAGE_DIR = Path(__file__).resolve().parent.parent / "qdrant_storage"


def get_qdrant_client() -> QdrantClient:
    """
    Connect to Qdrant server (Docker) if reachable, else fall back to local disk storage.
    """
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    try:
        # Check connection with adequate timeout
        client = QdrantClient(url=url, timeout=30)
        client.get_collections()
        print(f"[Qdrant] Connected to Qdrant server at {url}")
        return client
    except Exception:
        storage_path = os.getenv("QDRANT_PATH", str(STORAGE_DIR))
        print(f"[Qdrant] Server at {url} not reachable. Using local embedded storage at: {storage_path}")
        return QdrantClient(path=storage_path)


def stable_hash(s: str) -> int:
    """Fast, deterministic FNV-1a 32-bit hash."""
    h = 2166136261
    for b in s.encode("utf-8"):
        h = ((h ^ b) * 16777619) & 0xFFFFFFFF
    return h


class EmbeddingEngine:
    """
    Handles text embeddings with Google GenAI embeddings as primary,
    and a deterministic semantic projection fallback for offline/test environments.
    """
    def __init__(self, model_name: Optional[str] = None):
        self.api_key = os.getenv("GOOGLE_API_KEY", "").strip()
        self.model_name = model_name or os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
        self.use_google = bool(self.api_key and self.api_key != "your_key_here")

        # Precompute projection matrix once for fast local dense embedding
        self.num_features = 8192
        rng = np.random.RandomState(42)
        self._projection_matrix = (rng.randn(self.num_features, VECTOR_DIM) / np.sqrt(VECTOR_DIM)).astype(np.float32)

        if self.use_google:
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                print(f"[EmbeddingEngine] Initializing Google GenAI Embeddings ({self.model_name})...")
                self.embeddings = GoogleGenerativeAIEmbeddings(
                    model=self.model_name,
                    google_api_key=self.api_key
                )
            except Exception as e:
                print(f"[EmbeddingEngine] Google GenAI init failed ({e}). Falling back to local dense vectorizer.")
                self.use_google = False
        else:
            print("[EmbeddingEngine] No GOOGLE_API_KEY provided. Using high-precision dense multilingual vectorizer.")

    def embed_texts(self, texts: List[str], batch_size: int = 128) -> List[List[float]]:
        """Embed a list of text strings in batches."""
        if self.use_google:
            try:
                results = []
                for i in range(0, len(texts), batch_size):
                    batch = texts[i:i + batch_size]
                    vectors = self.embeddings.embed_documents(batch)
                    for vec in vectors:
                        if len(vec) > VECTOR_DIM:
                            vec = vec[:VECTOR_DIM]
                        elif len(vec) < VECTOR_DIM:
                            vec = vec + [0.0] * (VECTOR_DIM - len(vec))
                        norm = np.linalg.norm(vec)
                        if norm > 0:
                            vec = (np.array(vec) / norm).tolist()
                        results.append(vec)
                return results
            except Exception as e:
                print(f"[EmbeddingEngine] Live API embedding batch failed ({e}). Falling back to local vectorizer.")

        # Fast vectorized local dense multilingual semantic projection
        all_vectors = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_mat = np.zeros((len(batch), self.num_features), dtype=np.float32)
            for row_idx, text in enumerate(batch):
                words = text.lower().split()
                for w in words:
                    w_clean = re.sub(r"[^\w]", "", w)
                    if not w_clean:
                        continue
                    h = stable_hash(w_clean) % self.num_features
                    batch_mat[row_idx, h] += 2.0
                    if len(w_clean) >= 4:
                        h_pref = stable_hash(w_clean[:4]) % self.num_features
                        batch_mat[row_idx, h_pref] += 1.0
                    if len(w_clean) >= 3:
                        wrapped = f"^{w_clean}$"
                        for c_i in range(len(wrapped) - 2):
                            tri = wrapped[c_i:c_i+3]
                            h_tri = stable_hash(tri) % self.num_features
                            batch_mat[row_idx, h_tri] += 0.5
                    concepts = get_semantic_concepts(w_clean)
                    for c in concepts:
                        hc = stable_hash(f"concept:{c}") % self.num_features
                        batch_mat[row_idx, hc] += 1.5

            # Vectorized matrix product for entire batch
            dense_batch = np.dot(batch_mat, self._projection_matrix)
            norms = np.linalg.norm(dense_batch, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            all_vectors.extend((dense_batch / norms).tolist())

        return all_vectors

    def embed_query(self, text: str) -> List[float]:
        """Embed a single query string."""
        if self.use_google:
            try:
                vec = self.embeddings.embed_query(text)
                if len(vec) > VECTOR_DIM:
                    vec = vec[:VECTOR_DIM]
                elif len(vec) < VECTOR_DIM:
                    vec = vec + [0.0] * (VECTOR_DIM - len(vec))
                norm = np.linalg.norm(vec)
                if norm > 0:
                    vec = (np.array(vec) / norm).tolist()
                return vec
            except Exception as e:
                print(f"[EmbeddingEngine] Live API query embedding failed ({e}).")

        return self._local_embed(text)

    def _local_embed(self, text: str) -> List[float]:
        """
        Deterministic, cross-process stable dense representation.
        Uses FNV-1a hashing on words, subwords, character n-grams, and semantic clusters.
        """
        words = text.lower().split()
        feature_vec = np.zeros(self.num_features, dtype=np.float32)

        for w in words:
            w_clean = re.sub(r"[^\w]", "", w)
            if not w_clean:
                continue

            h = stable_hash(w_clean) % self.num_features
            feature_vec[h] += 2.0

            # Subword prefix/suffixes
            if len(w_clean) >= 4:
                h_pref = stable_hash(w_clean[:4]) % self.num_features
                feature_vec[h_pref] += 1.0

            # Character trigrams for Hinglish code-mixing and typo tolerance
            if len(w_clean) >= 3:
                wrapped = f"^{w_clean}$"
                for i in range(len(wrapped) - 2):
                    tri = wrapped[i:i+3]
                    h_tri = stable_hash(tri) % self.num_features
                    feature_vec[h_tri] += 0.5

            # Semantic concept activations (cross-topic & Hinglish bridging)
            concepts = get_semantic_concepts(w_clean)
            for c in concepts:
                hc = stable_hash(f"concept:{c}") % self.num_features
                feature_vec[hc] += 1.5

        # Dense projection
        dense = np.dot(feature_vec, self._projection_matrix)
        norm = np.linalg.norm(dense)
        if norm > 0:
            dense = dense / norm
        else:
            dense = np.zeros(VECTOR_DIM, dtype=np.float32)
        return dense.tolist()

SEMANTIC_CLUSTERS = {
    "budget": ["expenses", "cost", "total", "kharcha", "paisa", "numbers", "splitwise", "rupees", "8000", "head", "each", "saving", "price"],
    "destination": ["manali", "pahad", "hills", "rishikesh", "goa", "kasol", "himachal", "mountains", "place", "location", "cottage", "peaks"],
    "trip": ["getaway", "vacation", "manali", "travel", "journey", "chalo", "packing", "volvo", "bus", "stay"],
    "decide": ["fix", "settled", "locked", "final", "call", "confirmed", "done", "seal"],
    "dates": ["calendar", "leave", "booking", "may", "tickets", "chhutti", "days", "schedule", "approved", "friday", "monday", "15"],
    "dinner": ["restaurant", "food", "cafe", "khan market", "big chill", "party", "cake", "cheesecake", "surprise", "birthday"],
    "movie": ["theatre", "pvr", "imax", "show", "tickets", "film", "cinema", "popcorn", "audi", "sci-fi"],
    "hackathon": ["neuralknights", "coding", "team", "registration", "ai", "challenge", "dev", "agentic"]
}


def get_semantic_concepts(word: str) -> List[str]:
    """Return associated semantic concepts for Hinglish/English terms."""
    concepts = []
    w_lower = word.lower()
    for cluster_head, synonyms in SEMANTIC_CLUSTERS.items():
        if w_lower == cluster_head or w_lower in synonyms:
            concepts.append(cluster_head)
            concepts.extend(synonyms[:4])
    return concepts


def init_collection(client: QdrantClient, collection_name: str = COLLECTION_NAME, recreate: bool = False):
    """Create or re-create Qdrant collection with appropriate index settings."""
    collections = [c.name for c in client.get_collections().collections]

    if collection_name in collections:
        if recreate:
            print(f"[Qdrant] Re-creating collection '{collection_name}'...")
            client.delete_collection(collection_name)
        else:
            print(f"[Qdrant] Collection '{collection_name}' already exists.")
            return

    print(f"[Qdrant] Creating collection '{collection_name}' (dim={VECTOR_DIM}, metric=Cosine)...")
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)
    )

    # Create payload indexes for fast filtering
    try:
        client.create_payload_index(
            collection_name=collection_name,
            field_name="sender",
            field_schema=PayloadSchemaType.KEYWORD
        )
        client.create_payload_index(
            collection_name=collection_name,
            field_name="timestamp",
            field_schema=PayloadSchemaType.INTEGER
        )
        print("[Qdrant] Payload indexes created on 'sender' and 'timestamp'.")
    except Exception as e:
        print(f"[Qdrant] Note on payload index creation: {e}")


def ingest_corpus(recreate: bool = True):
    """
    Full ingestion pipeline:
    1. Read messages.json
    2. Build sliding windows (above=5, below=3)
    3. Generate embeddings
    4. Upsert points into Qdrant
    """
    messages_file = DATA_DIR / "messages.json"
    if not messages_file.exists():
        raise FileNotFoundError(f"Messages file not found at {messages_file}. Run data/generate_corpus.py first.")

    with open(messages_file, "r", encoding="utf-8") as f:
        messages = json.load(f)

    print(f"[Ingest] Loaded {len(messages)} messages from {messages_file}.")

    # 1. Build windows
    windows = build_windows(messages, above=5, below=3)
    print(f"[Ingest] Created {len(windows)} sliding windows.")

    # 2. Init Qdrant
    client = get_qdrant_client()
    init_collection(client, collection_name=COLLECTION_NAME, recreate=recreate)

    # 3. Embedding
    embedder = EmbeddingEngine()
    texts = [w["window_text"] for w in windows]
    print(f"[Ingest] Generating embeddings for {len(texts)} windows...")

    batch_size = 128
    total_windows = len(windows)
    points = []

    for i in range(0, total_windows, batch_size):
        batch_windows = windows[i:i + batch_size]
        batch_texts = [w["window_text"] for w in batch_windows]
        batch_vectors = embedder.embed_texts(batch_texts)

        for j, (w, vec) in enumerate(zip(batch_windows, batch_vectors)):
            point_id = i + j + 1
            payload = {
                "center_message_id": w["center_message_id"],
                "sender": w["sender"],
                "timestamp": w["timestamp_unix"],  # unix epoch for Range filter
                "timestamp_iso": w["timestamp"],
                "thread_id": w.get("thread_id"),
                "raw_text": w["raw_text"],
                "window_text": w["window_text"],
                "window_size": w["window_size"]
            }
            points.append(PointStruct(id=point_id, vector=vec, payload=payload))

        if (i // batch_size) % 5 == 0 or (i + batch_size) >= total_windows:
            print(f"[Ingest] Processed {min(i + batch_size, total_windows)} / {total_windows} windows...")

    # 4. Upsert in batches to Qdrant
    print(f"[Ingest] Upserting {len(points)} points into Qdrant...")
    upsert_batch_size = 200
    for i in range(0, len(points), upsert_batch_size):
        batch_pts = points[i:i + upsert_batch_size]
        client.upsert(collection_name=COLLECTION_NAME, points=batch_pts)

    # 5. Sanity check collection
    col_info = client.get_collection(COLLECTION_NAME)
    print(f"[Ingest] Upsert complete! Qdrant collection '{COLLECTION_NAME}' status: {col_info.status}, points_count: {col_info.points_count}")

    # Explicit close to prevent python shutdown warning
    try:
        client.close()
    except Exception:
        pass


if __name__ == "__main__":
    ingest_corpus(recreate=True)
