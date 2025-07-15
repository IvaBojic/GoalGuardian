from pathlib import Path
from openai import OpenAI
import requests, json, threading
from datetime import datetime, timedelta
from fastapi import FastAPI, Request  # type: ignore

# === Configuration ===
OA_URL = "http://oa:8000/receive_message"
SSA_URL = "http://oa:8000/trigger_agent"

MEMORY_FILE = Path("/app/memory/sca_conversations.json")

MODEL_NAME = "gpt-4.1"


# === Initialization ===
app = FastAPI()
client = OpenAI()


# === GPT Wrapper ===
def ask_gpt(messages):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.7,
    )
    return response.choices[0].message.content


# === Memory Handlers ===
def load_memory():
    if not MEMORY_FILE.exists():
        return []
    with open(MEMORY_FILE) as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            print("Warning: Memory file is not valid JSON. Starting fresh.", flush=True)
            return []

def save_message(new_record):
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    records = load_memory()

    updated = False
    for record in records:
        if record.get("patient_id") == new_record.get("patient_id"):
            if "chat_history" in new_record:
                record["chat_history"] = new_record.get("chat_history", [])
            updated = True
            break

    if not updated:
        records.append(new_record)

    with open(MEMORY_FILE, "w") as f:
        json.dump(records, f, indent=2)


# === API Endpoints ===
@app.post("/trigger")
async def trigger(request: Request):
    data = await request.json()
    patient_id = data.get("patient_id")
    turn_index = data.get("turn_index")

    if not patient_id:
        return {"status": "error", "reason": "Missing patient_id"}

    print(f"SCA was triggered to do weekly SMART goal review for patient {patient_id}", flush=True)

    system_prompt = "You are a warm, empathetic health coach closing a session."
    initial_prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "assistant", "content": (
            f"Thank the client for joining this check-in session. "
            "Ask if they have any feedback or suggestions for how to improve these conversations."
        )}
    ]

    # GPT generation placeholder
    assistant_reply = ask_gpt(initial_prompt)
    #assistant_reply = "Thank you for this session"

    chat_history = [{"role": "assistant", "content": assistant_reply}]

    save_message({
        "patient_id": patient_id,
        "chat_history": chat_history
    })

    def notify_oa():
        try:
            response = requests.post(OA_URL, json={
                "patient_id": patient_id,
                "turn_index": turn_index,
                "message": assistant_reply
            }, timeout=3)
            print(f"Sent HC message to OA for patient {patient_id} (turn {turn_index})", flush=True)
        except Exception as e:
            print(f"Failed to notify OA: {e}", flush=True)

    threading.Thread(target=notify_oa, daemon=True).start()

    return {"status": "SCA triggered", "patient_id": patient_id}

@app.post("/receive_message")
async def receive_message(request: Request):
    data = await request.json()
    patient_id = data.get("patient_id")
    user_input = data.get("user_input")
    turn_index = int(data.get("turn_index"))

    if not patient_id:
        return {"status": "error", "reason": "Missing patient_id"}

    print(f"Received '{user_input}' from {patient_id} (turn {turn_index})", flush=True)

    records = load_memory()
    patient_entry = next((r for r in records if r.get("patient_id") == patient_id), None)
    if not patient_entry:
        return {"status": "error", "reason": "Patient session not found"}

    chat_history = patient_entry.get("chat_history")
    chat_history.append({"role": "user", "content": user_input})

    # Compute review date for next week at 9 AM
    next_review = (datetime.now() + timedelta(weeks=1)).strftime("%A, %B %d at 9:00 AM")

    turn_index += 1

    if(turn_index >= 15):
         return {"status": "done", "reason": "Did all turns"}

    assistant_prompt = (
        f"The client said: '{user_input}'. Thank them for their feedback! Tell them that we will take that into account. "
        f"Your next weekly check-in will be on {next_review}. See you then!"
    )

    # GPT generation placeholder
    full_prompt = [
                {"role": "system", "content": "You are a warm, empathetic health coach closing a session."},
                *chat_history,
                {"role": "user", "content": assistant_prompt}
            ]
    assistant_reply = ask_gpt(full_prompt)
    #assistant_reply = assistant_prompt
    chat_history.append({"role": "assistant", "content": assistant_reply})
    try:
        oa_response = requests.post(OA_URL, json={
            "patient_id": patient_id,
            "turn_index": turn_index,
            "message": assistant_reply
        })
        if oa_response.status_code == 200:
            print(f"Sent HC message to OA for patient {patient_id} (turn {turn_index})", flush=True)
        else:
            print(f"Failed to send message to OA (status {oa_response.status_code})", flush=True)
    except Exception as e:
        print(f"Error sending message to OA: {e}", flush=True)

    try:
        agent_to_trigger = "SSA"
        oa_response = requests.post(SSA_URL, json={
            "patient_id": patient_id,
            "turn_index": turn_index,
            "agent_to_trigger": agent_to_trigger
        })
        if oa_response.status_code == 200:
            print(f"Triggered {agent_to_trigger} for patient {patient_id}", flush=True)
        else:
            print(f"Failed to trigger {agent_to_trigger} for patient {patient_id} (status {oa_response.status_code})", flush=True)
    except Exception as e:
        print(f"Error triggering {agent_to_trigger} for patient {patient_id}: {e}", flush=True)

    save_message({
        "patient_id": patient_id,
        "chat_history": chat_history
    })

    return {"status": "message processed", "turn_index": turn_index}
