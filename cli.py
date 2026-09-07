"""
CLI Interface for Semantic Search Over Group Chat.
Provides interactive search loop and single-query execution.
Shows parsed query slots, checkable verbatim context window, and synthesized answers.
"""

import sys
import argparse
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from search.query_parser import QueryParser
from search.retriever import GroupChatRetriever
from search.synthesizer import AnswerSynthesizer


def format_separator(title: str = "", char: str = "=", width: int = 70):
    if title:
        side = (width - len(title) - 2) // 2
        return f"{char * side} {title} {char * side}"
    return char * width


def run_search(query: str, parser: QueryParser, retriever: GroupChatRetriever, synthesizer: AnswerSynthesizer, top_k: int = 3):
    print("\n" + format_separator("SEARCH PIPELINE"))
    print(f"Query: \"{query}\"")

    # 1. Parse slots
    parsed = parser.parse(query)
    print("\n[1] Extracted Slots:")
    print(f"  • Semantic Meaning : '{parsed.semantic_query}'")
    print(f"  • Sender Filter    : {parsed.sender_filter or 'None'}")
    print(f"  • Date Range       : {parsed.date_range or 'None'}")
    print(f"  • Open-Ended Query : {parsed.is_open_ended}")
    print(f"  • Clarification    : {parsed.needs_clarification}")

    if parsed.needs_clarification:
        print("\n" + format_separator("CLARIFICATION REQUIRED", "-"))
        print(f"❓ {parsed.clarification_prompt}")
        return

    # 2. Retrieve
    hits = retriever.retrieve(parsed, top_k=top_k)
    print(f"\n[2] Retrieval: Found {len(hits)} matching windows from Qdrant.")

    if not hits:
        print("No messages matched the specified criteria.")
        return

    # Special case: open-ended date-only queries
    if parsed.is_open_ended:
        print("\n" + format_separator("OPEN-ENDED TEMPORAL SUMMARY", "-"))
        summary = synthesizer.synthesize_open_ended(query, hits)
        print(f"Analyzed {summary['total_matches']} messages in this timeframe:")
        for idx, bucket in enumerate(summary["topic_buckets"], 1):
            print(f"\n  Topic {idx}: {bucket['topic']} ({bucket['time_range']})")
            print(f"  Active: {', '.join(bucket['active_participants'])}")
            print("  Highlights:")
            for sample in bucket["sample_messages"]:
                print(f"    - \"{sample}\"")
        return

    # 3. Context Expansion & Display
    print("\n[3] Matched Evidence & Surrounding Conversation:")
    top_hit = hits[0]

    for rank, hit in enumerate(hits[:top_k], 1):
        c_id = hit["center_message_id"]
        score = hit["score"]
        sender = hit["sender"]
        ts = hit["timestamp"].replace("T", " ")
        print(f"\n--- Result #{rank} [Score: {score:.4f} | Msg: {c_id} | {sender} | {ts}] ---")
        context_msgs = synthesizer.expand_context(c_id, above=4, below=3)
        print(synthesizer.format_verbatim_context(context_msgs))

    # 4. Synthesize Natural Language Answer
    top_context = synthesizer.expand_context(top_hit["center_message_id"], above=4, below=3)
    answer = synthesizer.synthesize_answer(query, top_hit, top_context)
    print("\n" + format_separator("AI SYNTHESIZED ANSWER", "*"))
    print(f"💡 {answer}")
    print(format_separator("*") + "\n")


def main():
    parser = argparse.ArgumentParser(description="Semantic Search Over WhatsApp Group Chat")
    parser.add_argument("--query", "-q", type=str, help="Single query to execute non-interactively")
    parser.add_argument("--top_k", "-k", type=int, default=3, help="Number of retrieved results to display")
    args = parser.parse_args()

    print("Initializing Group Chat Search Engine...")
    q_parser = QueryParser()
    retriever = GroupChatRetriever()
    synthesizer = AnswerSynthesizer()
    print("Engine ready!\n")

    if args.query:
        run_search(args.query, q_parser, retriever, synthesizer, top_k=args.top_k)
        return

    # Interactive REPL
    print(format_separator("GROUP CHAT SEMANTIC SEARCH CLI"))
    print("Ask any question in plain English or Hinglish.")
    print("Examples:")
    print("  • 'when did we decide on Manali'")
    print("  • 'what did Priya say about the budget'")
    print("  • 'what did we discuss in April'")
    print("  • 'who confirmed the travel dates in May'")
    print("Type 'exit' or 'quit' to exit.\n")

    while True:
        try:
            q = input("Search> ").strip()
            if not q:
                continue
            if q.lower() in ("exit", "quit", "q"):
                print("Goodbye!")
                break
            run_search(q, q_parser, retriever, synthesizer, top_k=args.top_k)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break


if __name__ == "__main__":
    main()
