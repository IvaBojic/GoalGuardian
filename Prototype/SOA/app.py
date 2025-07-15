import requests, json
from pathlib import Path
from openai import OpenAI
from fastapi import FastAPI, Request  # type: ignore

# === Configuration ===
MMA_URL = "http://mma:8000/patient_notes"
OA_URL = "http://oa:8000/receive_message"
GRA_URL = "http://oa:8000/trigger_agent"

MEMORY_FILE = Path("/app/memory/soa_conversations.json")

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
            print("Warning: Could not decode memory file. Returning empty list.", flush=True)
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
    if not patient_id:
        return {"status": "error", "reason": "Missing patient_id"}

    print(f"SOA was triggered to do weekly SMART goal review for patient {patient_id}", flush=True)

    try:
        response = requests.get(f"{MMA_URL}/{patient_id}")
        if response.status_code == 200:
            notes = response.json()
            print(f"Retrieved {notes} from MMA for patient {patient_id}", flush=True)
        else:
            print(f"Failed to fetch notes from MMA (status {response.status_code})", flush=True)
            return {"status": "failed", "reason": "MMA fetch error"}
    except Exception as e:
        print(f"Error contacting MMA: {e}", flush=True)
        return {"status": "failed", "reason": str(e)}

    preferred_name = notes.get("preferred_name")

    system_prompt = "You are a warm, empathetic health coach opening a session."
    initial_prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "assistant", "content": f"Greet '{preferred_name}' and ask about energy level."}
    ]

    # GPT generation placeholder
    assistant_reply = ask_gpt(initial_prompt)
    #assistant_reply = "Hi there, what is your energy level?"

    chat_history = [{"role": "assistant", "content": assistant_reply}]

    save_message({
        "patient_id": patient_id,
        "notes": notes,
        "chat_history": chat_history
    })

    try:
        oa_response = requests.post(OA_URL, json={
            "patient_id": patient_id,
            "turn_index": 1,
            "message": assistant_reply
        })
        if oa_response.status_code == 200:
            print(f"Sent HC message to OA for patient {patient_id} (turn 1)", flush=True)
        else:
            print(f"Failed to send message to OA (status {oa_response.status_code})", flush=True)
    except Exception as e:
        print(f"Error sending message to OA: {e}", flush=True)

    return {"status": "SOA triggered", "patient_id": patient_id}

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

    notes = patient_entry.get("notes", {})

    fallback_sources = ["family", "friends", "travel", "hobbies"]
    fallback_text = ""
    for source in fallback_sources:
        values = notes.get(source, [])
        if values:
            fallback_text = values[0]
            break

    turn_index += 1

    assistant_prompt = ""
    if turn_index == 2:
        assistant_prompt = f"The client said: '{user_input}'. If number, ask what it means. If mood, ask why."
    elif turn_index == 3:
        assistant_prompt = f"The client said: '{user_input}'. Reflect empathetically and ask for a positive health moment from last week."
    elif turn_index == 4:
        if user_input.strip():
            assistant_prompt = f"The client said: '{user_input}'. Reflect positively and ask a light follow-up."
        else:
            assistant_prompt = f"The client didn’t share much. Use fallback: '{fallback_text}' to keep the conversation going."
    elif turn_index == 5:
        if user_input.strip():
            assistant_prompt = f"The client said: '{user_input}'. Reflect positively. Do not say goodbye."
        else:
            assistant_prompt = "The client didn’t say much. Share a short encouraging comment without saying goodbye."

    assistant_reply = ""
    if turn_index < 6:
        full_prompt = [
                {"role": "system", "content": "You are a warm, empathetic health coach opening a session."},
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
    elif turn_index == 6:
        agent_to_trigger = "GRA"
        try:
            oa_response = requests.post(GRA_URL, json={
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
