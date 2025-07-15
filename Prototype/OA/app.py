from pathlib import Path
import time, threading, json, requests
from datetime import datetime, timedelta
from fastapi import FastAPI, Request 

# === Configuration ===
MMA_URL = "http://mma:8000/extract"
AGENT_URL = "http://{agent}:8000/trigger"

SESSION_NOTES_FILE = Path("memory/session_notes_mock.json")
REVIEW_SCHEDULE_FILE = Path("memory/review_schedule.json")
GOAL_REVIEW_FILE = Path("memory/goal_reviews.json")


# === Initialization ===
app = FastAPI()


# === Memory Handlers ===
def load_review_schedule():
    if REVIEW_SCHEDULE_FILE.exists():
        try:
            with open(REVIEW_SCHEDULE_FILE) as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Warning: REVIEW_SCHEDULE_FILE is not valid JSON. Starting fresh.", flush=True)
    return {}

def load_goal_reviews():
    if GOAL_REVIEW_FILE.exists():
        try:
            with open(GOAL_REVIEW_FILE) as f:
                raw = json.load(f)
                return [json.loads(e) if isinstance(e, str) else e for e in raw]
        except json.JSONDecodeError:
            print("Warning: GOAL_REVIEW_FILE is not valid JSON. Starting fresh.", flush=True)
    return []

def save_message(new_record):
    GOAL_REVIEW_FILE.parent.mkdir(parents=True, exist_ok=True)
    records = load_goal_reviews()

    updated = False
    for record in records:
        if record.get("patient_id") == new_record.get("patient_id"):
            if "chat_history" in new_record:
                record["chat_history"].extend(new_record.get("chat_history", []))
            if "turn_index" in new_record:
                record["turn_index"] = new_record.get("turn_index")
            updated = True
            break

    if not updated:
        records.append(new_record)

    with open(GOAL_REVIEW_FILE, "w") as f:
        json.dump(records, f, indent=2)


# === Trigger Helper (used by both loop and endpoint) ===
def trigger_agent_sync(patient_id: str, turn_index: int, agent_to_trigger: str) -> dict:
    agent = agent_to_trigger.lower()
    url = AGENT_URL.format(agent=agent)

    print(f"OA received {agent_to_trigger} trigger request for {patient_id}", flush=True)

    payload = {
        "patient_id": patient_id,
        "turn_index": turn_index  # default for most agents
    }

    # Special logic for SSA
    if agent == "ssa":
        if not GOAL_REVIEW_FILE.exists():
            return {"status": "error", "reason": "Goal review file not found."}

        try:
            with open(GOAL_REVIEW_FILE) as f:
                entries = json.load(f)
            patient_entry = next((e for e in entries if e.get("patient_id") == patient_id), None)

            if not patient_entry:
                return {"status": "error", "reason": f"No entry found in goal_reviews.json for patient {patient_id}"}

            payload = {
                "patient_id": patient_id,
                "chat_history": patient_entry.get("chat_history")
            }

        except Exception as e:
            return {"status": "error", "reason": f"Failed to load SCA payload: {e}"}

    try:
        response = requests.post(url, json=payload)
        print(f"Triggered {agent_to_trigger} for patient {patient_id}", flush=True)
        return {"status": "ok"}
    except Exception as e:
        print(f"Failed to trigger {agent_to_trigger}: {e}", flush=True)
        return {"status": "error", "reason": str(e)}

def trigger_mma():

    if not SESSION_NOTES_FILE.exists():
        return {"status": "error", "reason": "session_notes_mock.json not found"}

    try:
        with open(SESSION_NOTES_FILE) as f:
            payload = json.load(f)

        if not isinstance(payload, list) or not all(isinstance(p, dict) for p in payload):
            return {"status": "error", "reason": "Invalid JSON structure. Expected a list of dicts."}

        mma_response = requests.post(MMA_URL, json=payload)

        return {
            "status": "ok",
            "sent": len(payload),
            "mma_status": mma_response.status_code,
            "mma_response": mma_response.json()
        }

    except Exception as e:
        return {"status": "error", "reason": str(e)}


# === Orchestration Loop ===
def orchestration_loop():
    time.sleep(1)
    print("OA started", flush=True)

    while True:
        now = datetime.now().replace(second=0, microsecond=0)
        
        # Checking if a review session needs to be started every hour
        if now.minute == 0:
            print(f"[{now}] Hourly check-in running...", flush=True)

            schedule = load_review_schedule()
            for patient_id, info in schedule.get("patients", {}).items():
                next_review_time = datetime.fromisoformat(info["next_review_time"])
                if now.date() == next_review_time.date() and now.hour == next_review_time.hour:
                    trigger_agent_sync(patient_id, turn_index=1, agent_to_trigger="SOA")

            # Triggering MMA to extraxct new session notes once a day (at midnight)
            if now.hour == 0:
                print(f"[{now}] Extracting infos from new health coaching notes...", flush=True)
                trigger_mma()

            time.sleep(600)
        else:
            time.sleep(10)


# === API Endpoints ===
@app.post("/new_sessions")
async def receive_new_sessions(request: Request):
    payload = await request.json()
    print(f"OA received new sessions for {len(payload)} patients.", flush=True)

    schedule = load_review_schedule()
    schedule.setdefault("patients", {})

    for entry in payload:
        patient_id = entry.get("study_id")
        if not patient_id or not entry.get("date"):
            continue
        last_session_date = datetime.fromisoformat(entry["date"])
        next_review = last_session_date + timedelta(days=7)
        next_review_time = next_review.replace(hour=9, minute=0, second=0, microsecond=0)

        schedule["patients"][patient_id] = {
            "next_review_time": next_review_time.isoformat()
        }

    with open(REVIEW_SCHEDULE_FILE, "w") as f:
        json.dump(schedule, f, indent=2)

    print(f"OA memory updated for {len(payload)} patients.", flush=True)
    return {"status": "received", "patients": len(payload)}

@app.post("/receive_message")
async def receive_message(request: Request):
    data = await request.json()
    patient_id = data.get("patient_id")
    turn_index = data.get("turn_index")
    assistant_message = data.get("message")

    if not patient_id or assistant_message is None or turn_index is None:
        return {"status": "error", "reason": "Missing data"}

    message = {
        "patient_id": patient_id,
        "turn_index": turn_index,
        "chat_history": [
            {"role": "assistant", "content": assistant_message}
        ]
    }

    save_message(message)
    print(f"Received message '{assistant_message}' from a HC for patient {patient_id} (turn {turn_index})", flush=True)
    return {"status": "ok"}

@app.post("/trigger_agent")
async def trigger_agent(request: Request):
    data = await request.json()
    patient_id = data.get("patient_id")
    turn_index = data.get("turn_index")
    agent_to_trigger = data.get("agent_to_trigger")

    if not patient_id:
        return {"status": "error", "reason": "Missing patient_id"}
    if not turn_index:
        return {"status": "error", "reason": "Missing turn_index"}
    if not agent_to_trigger:
        return {"status": "error", "reason": "Missing agent_to_trigger"}

    return trigger_agent_sync(patient_id, turn_index, agent_to_trigger)


# === Startup Background Thread ===
@app.on_event("startup")
def startup_event():
    thread = threading.Thread(target=orchestration_loop, daemon=True)
    thread.start()
