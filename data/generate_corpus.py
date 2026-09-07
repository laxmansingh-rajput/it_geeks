"""
Corpus Generator for WhatsApp-style Group Chat.
Generates >=4000 messages across 8 participants and 6 months (2026-03-01 to 2026-09-01).
Maintains participant voices, Hinglish code-mixing, typos, forwards, one-word replies,
and 3 critical decision threads with non-keyword resolving messages.
"""

import json
import os
import random
import re
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Load seed specification
SEED_PATH = Path(__file__).resolve().parent.parent / "seed" / "seed.json"
DATA_DIR = Path(__file__).resolve().parent

with open(SEED_PATH, "r", encoding="utf-8") as f:
    SEED = json.load(f)

PARTICIPANTS = SEED["participants"]
START_DATE = datetime.fromisoformat(SEED["date_range"]["start"])
END_DATE = datetime.fromisoformat(SEED["date_range"]["end"])
TARGET_COUNT = SEED.get("message_count_target", 4200)

# Stylistic vocabulary and chatter patterns per participant
STYLES = {
    "Priya": {
        "topics": ["work update", "deadlines", "lunch coordination", "scheduling", "quick confirmations"],
        "phrases": [
            "Hey all, hope you are having a productive week!",
            "Quick question - has anyone checked the client email?",
            "Haan let's do that. Sounds like a solid plan.",
            "Can we connect for 10 mins post lunch?",
            "Wrapping up this sprint by tomorrow evening.",
            "Please update the shared sheet so we don't duplicate work.",
            "Great progress today team.",
            "Let's sync up around 4 PM?",
            "Haan exactly my point.",
            "Shared the notes on Slack as well.",
            "Nice, looks good to me.",
            "Chalo done, I will take care of the documentation.",
            "Will review and get back before 6 PM.",
            "Are we still on for the evening catchup?"
        ]
    },
    "Rohan": {
        "topics": ["chai breaks", "weekend plans", "gaming", "casual banter"],
        "phrases": [
            "bhai chai peene chalen?",
            "arrey yaar code fatt gya mera 💀",
            "kl milte h pkka",
            "bhai ye bug samjh ni aa rha kch",
            "sahi h boss",
            "kya chl rha h sbka",
            "swiggy se kya order kre aaj?",
            "bhai mast movie thi sach me",
            "yaar monday wapas aa gya",
            "haan bhai bilkul",
            "scene kya h weekend ka?",
            "arre tension mt le ho jayega",
            "haha bhai epic tha wo",
            "batao kidhar aana hai"
        ]
    },
    "Amit": {
        "topics": ["reactions", "agreements", "short checks"],
        "phrases": [
            "👍", "Haan", "cool", "Done", "😂", "lol", "ok", "yes", "nice",
            "👍👍", "sorted", "sure", "sahi hai", "🔥", "haha", "ok boss"
        ]
    },
    "Sara": {
        "topics": ["itinerary", "planning", "recommendations", "organization"],
        "phrases": [
            "Hey guys, just organizing our calendar for this month.",
            "Can everyone please fill in their preferences by tonight?",
            "I checked the reviews and this place has 4.8 stars!",
            "Here is the draft agenda, let me know if you want any edits.",
            "Let's make sure we book well in advance to avoid last minute surge.",
            "Sent the calendar invite to everyone's email.",
            "We should probably finalize the headcount first.",
            "I have compiled all the suggestions into a single doc.",
            "Looking forward to this! It's going to be so much fun.",
            "Reminder: please keep your IDs handy for check-in."
        ]
    },
    "Karan": {
        "topics": ["forwards", "tech articles", "interesting links", "random facts"],
        "phrases": [
            "*Forwarded*: 10 Productivity Hacks Every Developer Needs to Know in 2026.",
            "*Forwarded*: Breaking: New high-speed train corridor announced connecting Delhi and Shimla.",
            "*Forwarded*: Top 10 mountain cafes you must visit once in your lifetime.",
            "*Forwarded*: Important update regarding cloud outages across APAC region today.",
            "Found this cool open-source repo for local vector search: https://github.com/qdrant/qdrant",
            "Check out this thread on tech salaries: https://x.com/tech_insider/status/198234",
            "*Forwarded*: Weather alert - heavy rainfall expected across northern plains this weekend.",
            "Did anyone see the latest Google DeepMind research paper on agentic coding?"
        ]
    },
    "Neha": {
        "topics": ["budgeting", "splitwise", "finances", "precision"],
        "phrases": [
            "Added the expenses to Splitwise, please settle when free.",
            "Let's ensure we stay within our realistic budget limit.",
            "We need to keep a 10% emergency buffer for unexpected cab fares.",
            "Can someone send me the GST invoice for the group booking?",
            "Total came out to be slightly lower than projected, which is great.",
            "Please transfer the advance to Rohan so he can make the down payment.",
            "Double checked the calculations, everything tallies now.",
            "Formal reminder: please don't pay cash, keep UPI records for tracking."
        ]
    },
    "Vikram": {
        "topics": ["humor", "sarcasm", "roasting", "food"],
        "phrases": [
            "bhai tu pehle so ke uth ja fir bolna 😂",
            "paisa kiski jeb se jaa raha hai pehle ye batao",
            "kya baat hai, itna dedication work pe? hike confirm hai lagta hai",
            "weekend pe sone do bhagwan ke liye",
            "arrey bhai bhai bhai, itna aggressive kyu ho rahe ho",
            "biryani mangwao koi chup chaap",
            "tum sab plan banaoge aur end me cancel karoge, record hai apna",
            "wah kya scene hai! main to ready hu",
            "bhai petrol ka daam dekh ke hi chakkar aa gaya",
            "legend says Rohan is still debugging that one line of CSS"
        ]
    },
    "Divya": {
        "topics": ["night owl chatter", "podcasts", "deep thoughts", "music"],
        "phrases": [
            "guys cannot sleep, listening to this indie playlist on Spotify...",
            "hey just woke up, what did I miss in the last 6 hours??",
            "wait wait wait let me explain what actually happened today",
            "late night chai session anyone? I am awake till 3am anyway",
            "did anyone watch the sunrise today? absolute magic",
            "omg that podcast episode on cognitive biases blew my mind",
            "voice note bheju kya? bohot lamba type karna padega haha",
            "random 2 AM thought: why do we always overcomplicate simple things"
        ]
    }
}

# Decision Threads scripted sequences
DECISION_THREADS_DEF = [
    {
        "thread_id": "thread_trip_destination",
        "topic": "deciding the group trip destination",
        "resolution": "Manali",
        "approx_date": "2026-04-12",
        "sequence": [
            ("Sara", "Guys, we have been talking about a getaway forever. Goa, Rishikesh, or Himachal? Let's take a call today."),
            ("Rohan", "bhai goa bohot hot hoga april me.. pahad chalo"),
            ("Vikram", "Goa me bas daaru aur sunburn milega, I vote hills"),
            ("Neha", "If we go to Rishikesh, rafting is good but hotels are overpriced right now."),
            ("Priya", "Himachal sounds refreshing. Are we thinking Kasol or Manali or Dharamshala?"),
            ("Divya", "Kasol has too much crowd these days. Manali has good cozy cafes in Old Manali."),
            ("Amit", "Manali 👍"),
            ("Karan", "*Forwarded*: Top 5 scenic cottages in Old Manali with mountain view and high speed wifi"),
            ("Sara", "Manali has direct Volvo from Delhi and easier cab connectivity for all 8 of us."),
            ("Rohan", "haan bhai snowy peaks aur mall road cafe hopping sahi rahega"),
            ("Neha", "Distance wise and travel time wise, Manali makes the most practical sense."),
            ("Vikram", "theek hai fir bheed se door old manali me stay dekhte hain"),
            ("Priya", "Is everyone aligned on Himachal then? No one wants beach anymore?"),
            ("Amit", "haan pahad"),
            ("Sara", "Yes! It's settled then, mountain air it is."),
            ("Rohan", "chalo Manali fix hai bhai"), # RESOLVING MESSAGE - no 'decide', 'destination', 'trip'
            ("Neha", "Great. Now next step is to lock the budget per head before booking anything."),
            ("Vikram", "party abhi se shuru! packing list ready karo"),
            ("Amit", "done")
        ],
        "resolving_index": 15
    },
    {
        "thread_id": "thread_budget",
        "topic": "agreeing on per-person budget for the trip",
        "resolution": "8000 rupees per head",
        "approx_date": "2026-04-20",
        "sequence": [
            ("Neha", "Okay everyone, let's talk numbers so there is no awkwardness later on expenses."),
            ("Vikram", "gareeb aadmi hu main, zyada mat bolna koi"),
            ("Sara", "I looked at 3-night stay in Old Manali: stays are around 3500-4000 per room (twin sharing)."),
            ("Priya", "And Volvo tickets return are about 2500 per person from Majnu Ka Tila."),
            ("Rohan", "bhai khane peene ka 2-3k pakad lo easily"),
            ("Neha", "If we do: Travel 2500 + Stay 2000 (shared) + Food 2500 + local cabs 1000 = ~8000 total."),
            ("Karan", "Can we do 12k and stay at a luxury resort with heated pool?"),
            ("Neha", "12k is too high for a short 3-4 day trip, especially with other upcoming commitments."),
            ("Divya", "8k sounds very reasonable and covers everything comfortably without scrimping."),
            ("Amit", "8k 👍"),
            ("Rohan", "haan 8k me mast aish ho jayegi"),
            ("Sara", "Agreed. 8000 per person gives us quality stay plus good food without burning a hole in anyone's pocket."),
            ("Vikram", "agar 8k me trip ho rahi hai toh main 2 baar jaane ko tayyar hu"),
            ("Priya", "8000 each chalega sabko, Neha check kar lena"), # RESOLVING MESSAGE - numeric confirmation buried in casual back-and-forth
            ("Neha", "Noted. 8000 is our benchmark cap. Opening a dedicated Splitwise group for this right now."),
            ("Amit", "cool"),
            ("Rohan", "sorted hai")
        ],
        "resolving_index": 13
    },
    {
        "thread_id": "thread_dates",
        "topic": "finalizing travel dates",
        "resolution": "May 15-19",
        "approx_date": "2026-05-01",
        "sequence": [
            ("Sara", "Now that destination and budget are locked, we need exact calendar dates for leave applications."),
            ("Priya", "My sprint demo is on May 8th so first week of May is completely blocked for me."),
            ("Rohan", "2nd week ya 3rd week of May? weekend club karke 2 din leave leni hogi"),
            ("Neha", "May 15 is Friday. If we take leave on Friday May 15 and Monday May 18, we get a 4-day stretch."),
            ("Vikram", "Thursday night May 14 ko bus pakdo, Friday morning pahucho, Tuesday morning back in Delhi."),
            ("Divya", "May 15 to 19 works perfectly for my college submission schedule too!"),
            ("Karan", "Checking Volvo bus seat availability right now... Thursday May 14 night buses are filling up."),
            ("Sara", "Can all 8 of us apply for leaves for Friday May 15 and Monday May 18 today?"),
            ("Amit", "applied"),
            ("Priya", "My leave got approved just now on the HR portal!"),
            ("Neha", "Mine is approved as well."),
            ("Vikram", "ok booking kar raha hu 15 se"), # RESOLVING MESSAGE - casual confirmation without explicit date-confirmation language
            ("Rohan", "bhai seats aage ki lena piche ulti aati hai"),
            ("Sara", "Awesome! Bus booked for May 15-19 dates. This is officially happening!"),
            ("Amit", "🔥🔥")
        ],
        "resolving_index": 11
    }
]

# Minor threads definition
MINOR_THREADS_DEF = [
    {
        "thread_id": "thread_rohan_bday",
        "topic": "Rohan's surprise birthday dinner plan",
        "resolution": "Dinner at Big Chill on Saturday",
        "approx_date": "2026-03-24",
        "sequence": [
            ("Sara", "Hey guys, Rohan's birthday is coming up on Saturday! We should do a dinner."),
            ("Priya", "Yes! Let's keep it surprise. What cuisine does he love?"),
            ("Vikram", "Bhai ko pasta aur cheesecake bohot pasand hai"),
            ("Neha", "Big Chill Cafe in Khan Market?"),
            ("Divya", "Big Chill is perfect! Table booking doesn't happen so we have to reach by 7:30 PM."),
            ("Karan", "I will get the blueberry cheesecake secretly before he enters."),
            ("Amit", "Big Chill 👍"),
            ("Priya", "Saturday 7:30 PM Big Chill Khan Market confirmed. Don't tell Rohan in the other chat!")
        ],
        "resolving_index": 7
    },
    {
        "thread_id": "thread_movie_outing",
        "topic": "Watching the new sci-fi movie together",
        "resolution": "Sunday 4 PM show booked at PVR",
        "approx_date": "2026-06-14",
        "sequence": [
            ("Vikram", "bhai log weekend pe wo nayi sci-fi movie dekhne chale?"),
            ("Rohan", "haan IMAX me dekhna hai visual effects crazy bataye hain"),
            ("Sara", "Which theatre? PVR Select Citywalk or Ambience Mall?"),
            ("Neha", "Select Citywalk has Sunday 4:10 PM IMAX show with good middle row seats available."),
            ("Amit", "book it"),
            ("Vikram", "Sunday 4 PM Select Citywalk IMAX 8 tickets booked! popcorn on Rohan")
        ],
        "resolving_index": 5
    },
    {
        "thread_id": "thread_hackathon_team",
        "topic": "Registering for the weekend AI hackathon",
        "resolution": "Team registered under name NeuralKnights",
        "approx_date": "2026-07-08",
        "sequence": [
            ("Karan", "Hey tech folks, registration for the 48-hour Agentic AI Hackathon closes tomorrow!"),
            ("Priya", "Are we forming a team? We need 4 people."),
            ("Rohan", "main backend aur api sambhal lunga"),
            ("Divya", "I will do the frontend and prompt design!"),
            ("Sara", "What should our team name be?"),
            ("Vikram", "ChaiCode ya BugHunters"),
            ("Priya", "NeuralKnights sounds classy and tech-focused."),
            ("Karan", "Submitted registration under NeuralKnights! Verification email received.")
        ],
        "resolving_index": 7
    }
]

# Common conversational chatter templates
CASUAL_TOPICS = [
    ("chai_traffic", [
        ("Rohan", "bhai traffic itna ganda h gurgaon me aaj 2 ghante ho gye"),
        ("Vikram", "metro le leta bhai, gaadi leke hero ban raha tha"),
        ("Rohan", "galti ho gyi yaar metro hi best h"),
        ("Amit", "lol"),
        ("Priya", "Rain started near Cyber City, traffic will get worse. Leave early if you can.")
    ]),
    ("food_order", [
        ("Divya", "Guys what are we having for lunch today? I'm craving street food"),
        ("Neha", "Eat something healthy Divya, last week you were complaining of stomach ache"),
        ("Vikram", "Chhole bhature order karo chup chaap"),
        ("Rohan", "bhai nagpal ke chhole bhature मंगवाओ"),
        ("Amit", "bhature 🔥")
    ]),
    ("weekend_gym", [
        ("Karan", "*Forwarded*: Why 10,000 steps a day transforms your energy levels"),
        ("Vikram", "karan bhai tu pehle 1000 step chal ke dikha bed se fridge tak"),
        ("Priya", "Haha savage Vikram! But seriously morning walks do help."),
        ("Sara", "I did a 5k run this morning, weather was so pleasant.")
    ]),
    ("tech_meme", [
        ("Rohan", "yaar production pe hotfix daal diya bina test kiye 💀"),
        ("Priya", "Rohan please tell me you did not break the auth service again"),
        ("Rohan", "nhi nhi chal gya thankfully haha"),
        ("Vikram", "Rohan's motto: Test in Production, pray on Slack"),
        ("Amit", "😂")
    ]),
    ("coffee_vibes", [
        ("Divya", "found this aesthetic new cafe in south delhi with great cold brew"),
        ("Sara", "Send location Divya! Always looking for good work cafes."),
        ("Divya", "Blue Tokai near Champa Gali, great natural lighting too"),
        ("Neha", "Their pour-over is quite good, reasonable prices as well.")
    ]),
    ("badminton_game", [
        ("Vikram", "aaj sham ko badminton kon kon aa raha hai DDA complex?"),
        ("Rohan", "main aur karan to pakka hain"),
        ("Priya", "I can join after 7 PM if court is booked."),
        ("Sara", "Court 3 booked 7:30 to 8:30 PM! Bring your rackets.")
    ]),
    ("spotify_podcast", [
        ("Divya", "Has anyone listened to the Huberman podcast on sleep optimization?"),
        ("Karan", "Yes! Morning sunlight viewing within 30 mins of waking up is legit."),
        ("Vikram", "subah 11 baje uthne walo ko kya sunlight milegi bhai"),
        ("Amit", "haha")
    ])
]


def typo_corrupt(text, rate=0.10):
    """Add realistic typos for casual Hinglish chats."""
    words = text.split()
    corrupted = []
    for w in words:
        if len(w) > 4 and random.random() < rate:
            # swap two adjacent characters or drop a letter
            idx = random.randint(1, len(w) - 2)
            w_list = list(w)
            w_list[idx], w_list[idx+1] = w_list[idx+1], w_list[idx]
            corrupted.append("".join(w_list))
        else:
            corrupted.append(w)
    return " ".join(corrupted)


def generate_corpus():
    random.seed(42)
    messages = []
    manifest = {}
    current_msg_num = 1

    total_days = (END_DATE - START_DATE).days
    total_weeks = total_days // 7
    messages_per_week_target = TARGET_COUNT // total_weeks

    current_date = START_DATE

    # Schedule decision threads and minor threads
    scheduled_threads = {}
    for d in DECISION_THREADS_DEF:
        d_date = datetime.fromisoformat(d["approx_date"]).date()
        scheduled_threads[d_date] = ("decision", d)

    for m in MINOR_THREADS_DEF:
        m_date = datetime.fromisoformat(m["approx_date"]).date()
        scheduled_threads[m_date] = ("minor", m)

    print(f"Generating corpus from {START_DATE.date()} to {END_DATE.date()} across {total_weeks} weeks...")

    for day_offset in range(total_days):
        day_date = (START_DATE + timedelta(days=day_offset)).date()
        day_is_weekend = day_date.weekday() >= 5

        # Check if a scheduled thread happens today
        if day_date in scheduled_threads:
            thread_type, thread_obj = scheduled_threads[day_date]
            thread_id = thread_obj["thread_id"]
            thread_time = datetime.combine(day_date, datetime.min.time()) + timedelta(hours=random.randint(14, 19), minutes=random.randint(5, 45))
            
            resolving_msg_id = None
            resolving_msg_text = None
            resolving_sender = None
            resolving_timestamp = None

            for s_idx, (sender, text) in enumerate(thread_obj["sequence"]):
                thread_time += timedelta(minutes=random.randint(1, 4), seconds=random.randint(5, 50))
                msg_id = f"m{current_msg_num:04d}"

                # Typo if Rohan
                if sender == "Rohan" and random.random() < 0.20:
                    text = typo_corrupt(text, rate=0.2)

                msg = {
                    "message_id": msg_id,
                    "sender": sender,
                    "timestamp": thread_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "text": text,
                    "thread_id": thread_id
                }
                messages.append(msg)

                if s_idx == thread_obj["resolving_index"]:
                    resolving_msg_id = msg_id
                    resolving_msg_text = text
                    resolving_sender = sender
                    resolving_timestamp = msg["timestamp"]

                current_msg_num += 1

            manifest[thread_id] = {
                "topic": thread_obj["topic"],
                "resolution": thread_obj["resolution"],
                "resolving_message_id": resolving_msg_id,
                "resolving_message_text": resolving_msg_text,
                "resolving_sender": resolving_sender,
                "timestamp": resolving_timestamp
            }

        # Daily conversational bursts (2-4 conversation bursts per day)
        num_bursts = random.randint(2, 4) if not day_is_weekend else random.randint(3, 5)
        for _ in range(num_bursts):
            # Pick a time of day
            hour = random.choice([9, 10, 12, 13, 15, 16, 17, 19, 20, 21, 22])
            # Divya night owl chance
            if random.random() < 0.15:
                hour = random.choice([0, 1, 2, 23])

            burst_time = datetime.combine(day_date, datetime.min.time()) + timedelta(
                hours=hour, minutes=random.randint(0, 50), seconds=random.randint(0, 50)
            )

            # Pick a topic or generate participant banter
            if random.random() < 0.40:
                # Use one of the casual banter mini-sequences
                _, sequence = random.choice(CASUAL_TOPICS)
                for sender, text in sequence:
                    burst_time += timedelta(minutes=random.randint(1, 4), seconds=random.randint(10, 45))
                    msg_id = f"m{current_msg_num:04d}"
                    if sender == "Rohan" and random.random() < 0.25:
                        text = typo_corrupt(text, 0.2)
                    messages.append({
                        "message_id": msg_id,
                        "sender": sender,
                        "timestamp": burst_time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "text": text,
                        "thread_id": None
                    })
                    current_msg_num += 1
            else:
                # Dynamic participant banter burst (3 to 7 messages)
                burst_len = random.randint(3, 7)
                active_speakers = random.sample([p["name"] for p in PARTICIPANTS], random.randint(2, 4))
                for _ in range(burst_len):
                    burst_time += timedelta(minutes=random.randint(1, 3), seconds=random.randint(5, 40))
                    speaker = random.choice(active_speakers)
                    # Pick phrase from style
                    speaker_phrases = STYLES[speaker]["phrases"]
                    text = random.choice(speaker_phrases)

                    # Amit one-word reply or emoji behavior
                    if speaker == "Amit":
                        text = random.choice(["👍", "haan", "cool", "Done", "😂", "lol", "ok", "yes", "nice", "🔥", "sorted"])
                    elif speaker == "Rohan" and random.random() < 0.25:
                        text = typo_corrupt(text, 0.2)

                    msg_id = f"m{current_msg_num:04d}"
                    messages.append({
                        "message_id": msg_id,
                        "sender": speaker,
                        "timestamp": burst_time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "text": text,
                        "thread_id": None
                    })
                    current_msg_num += 1

    # If count is below target, fill remaining with realistic chatter
    while len(messages) < TARGET_COUNT:
        random_day = START_DATE + timedelta(days=random.randint(0, total_days - 1))
        hour = random.choice([10, 11, 14, 15, 17, 18, 20, 21])
        t = datetime.combine(random_day.date(), datetime.min.time()) + timedelta(
            hours=hour, minutes=random.randint(0, 59), seconds=random.randint(0, 59)
        )
        speaker = random.choice([p["name"] for p in PARTICIPANTS])
        text = random.choice(STYLES[speaker]["phrases"])
        if speaker == "Amit":
            text = random.choice(["👍", "haan", "cool", "Done", "😂", "lol", "ok", "nice"])
        elif speaker == "Rohan" and random.random() < 0.2:
            text = typo_corrupt(text, 0.2)

        messages.append({
            "message_id": f"m{current_msg_num:04d}",
            "sender": speaker,
            "timestamp": t.strftime("%Y-%m-%dT%H:%M:%S"),
            "text": text,
            "thread_id": None
        })
        current_msg_num += 1

    # Sort messages chronologically
    messages.sort(key=lambda m: m["timestamp"])

    # Re-assign sequential IDs to guarantee strictly monotonic m0001 ... mNNNN
    old_to_new_id = {}
    for idx, msg in enumerate(messages, start=1):
        new_id = f"m{idx:04d}"
        old_to_new_id[msg["message_id"]] = new_id
        msg["message_id"] = new_id

    # Update manifest resolving_message_ids to match newly assigned sequential IDs
    for tid, info in manifest.items():
        if info["resolving_message_id"] in old_to_new_id:
            info["resolving_message_id"] = old_to_new_id[info["resolving_message_id"]]

    # Save to data/messages.json
    messages_file = DATA_DIR / "messages.json"
    manifest_file = DATA_DIR / "decision_threads_manifest.json"

    with open(messages_file, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2, ensure_ascii=False)

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"Generated {len(messages)} messages successfully!")
    print(f"Saved canonical corpus to: {messages_file}")
    print(f"Saved decision threads manifest to: {manifest_file}")
    print("\nDecision Threads Summary:")
    for tid, info in manifest.items():
        print(f" - [{tid}] '{info['topic']}' -> Resolution: '{info['resolution']}' | Resolving msg {info['resolving_message_id']} ({info['resolving_sender']}): \"{info['resolving_message_text']}\"")


if __name__ == "__main__":
    generate_corpus()
