"""
Chunker module: Sliding window construction over chat messages.
Builds a window of 5 messages above, center message, 3 messages below (window size ~9, stride 1).
"""

from datetime import datetime
from typing import List, Dict, Any


def build_windows(messages: List[Dict[str, Any]], above: int = 5, below: int = 3) -> List[Dict[str, Any]]:
    """
    Build sliding windows centered at every message in the corpus.
    
    Args:
        messages: List of message dictionaries with keys:
                  'message_id', 'sender', 'timestamp', 'text', 'thread_id'
        above: Number of messages preceding the center message (default 5)
        below: Number of messages following the center message (default 3)
        
    Returns:
        List of window dictionaries ready for embedding and Qdrant ingestion.
    """
    windows = []
    total = len(messages)

    for i, msg in enumerate(messages):
        start = max(0, i - above)
        end = min(total, i + below + 1)
        window_msgs = messages[start:end]

        # Format multi-turn context
        window_lines = []
        for m in window_msgs:
            prefix = f"{m['sender']}: {m['text']}"
            if m["message_id"] == msg["message_id"]:
                # The center message anchors this window
                window_lines.append(f"{m['sender']}: {m['text']}")
            else:
                window_lines.append(prefix)
        window_text = "\n".join(window_lines)

        # Parse timestamp to unix timestamp (seconds) for Qdrant Range filtering
        dt = datetime.fromisoformat(msg["timestamp"])
        timestamp_unix = int(dt.timestamp())

        windows.append({
            "center_message_id": msg["message_id"],
            "window_text": window_text,
            "sender": msg["sender"],
            "timestamp": msg["timestamp"],
            "timestamp_unix": timestamp_unix,
            "thread_id": msg.get("thread_id"),
            "raw_text": msg["text"],
            "window_start_id": window_msgs[0]["message_id"],
            "window_end_id": window_msgs[-1]["message_id"],
            "window_size": len(window_msgs)
        })

    return windows


if __name__ == "__main__":
    import json
    from pathlib import Path
    
    messages_path = Path(__file__).resolve().parent.parent / "data" / "messages.json"
    if messages_path.exists():
        with open(messages_path, "r", encoding="utf-8") as f:
            msgs = json.load(f)
        sample_windows = build_windows(msgs[:20], above=5, below=3)
        print(f"Constructed {len(sample_windows)} test windows from 20 messages.")
        print("\nSample window for center message:", sample_windows[10]["center_message_id"])
        print("Sender:", sample_windows[10]["sender"])
        print("Timestamp Unix:", sample_windows[10]["timestamp_unix"])
        print("Window Text:\n" + "-"*40)
        print(sample_windows[10]["window_text"])
        print("-"*40)
