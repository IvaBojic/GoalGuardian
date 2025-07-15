from pathlib import Path
from openai import OpenAI
import requests, json, threading
from fastapi import FastAPI, Request  # type: ignore

# === Configuration ===
MMA_URL = "http://mma:8000/patient_goals"
OA_URL = "http://oa:8000/receive_message"
SCA_URL = "http://oa:8000/trigger_agent"

MEMORY_FILE = Path("/app/memory/gra_conversations.json")

MODEL_NAME = "gpt-4.1"


# === Initialization ===
app = FastAPI()
client = OpenAI()


# === GPT Wrapper ===
def ask_gpt(messages):
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.7
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
    for existing in records:
        if existing.get("patient_id") == new_record.get("patient_id"):
            if "chat_history" in new_record:
                existing["chat_history"] = new_record["chat_history"]
            if "selected_goal" in new_record:
                existing["selected_goal"] = new_record["selected_goal"]
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

    print(f"GRA was triggered to do weekly SMART goal review for patient {patient_id}", flush=True)

    try:
        response = requests.get(f"{MMA_URL}/{patient_id}")
        if response.status_code == 200:
            response_data = response.json()
            print(f"Retrieved {response_data} from MMA for patient {patient_id}", flush=True)
        else:
            print(f"Failed to fetch SMART goals from MMA: {response.status_code}", flush=True)
            return {"status": "failed", "reason": "MMA fetch error"}
    except Exception as e:
        print(f"Error contacting MMA: {e}", flush=True)
        return {"status": "failed", "reason": str(e)}

    preferred_name = response_data.get("preferred_name")
    smart_goals = response_data.get("smart_goals", [])

    system_prompt = "You are a warm, empathetic health coach helping a patient review their SMART goals."

    if smart_goals:
        goal_list = "\n".join([f"{i+1}. {g}" for i, g in enumerate(smart_goals)])
        user_prompt = (
            f"Turn {turn_index}. The patient's name is {preferred_name}. Their SMART goals are:\n{goal_list}\n\n"
            "Remind them of these goals and ask which one they'd like to review during this session. Do not greet them."
        )
    else:
        user_prompt = (
            f"Turn {turn_index}. The patient's name is {preferred_name}. No SMART goals were set in their last session.\n\n"
            "Let them know that no goals were set and ask if they'd like to set some with their health coach. "
            "Say that you can’t help set goals—only review them."
        )

    initial_prompt = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # GPT generation placeholder
    assistant_reply = ask_gpt(initial_prompt)
    #assistant_reply = "Let's review your goals from the last session."
    chat_history = [{"role": "assistant", "content": assistant_reply}]

    save_message({
        "patient_id": patient_id,
        "chat_history": chat_history,
        "smart_goals": smart_goals
    })

    def notify_oa():
        try:
            requests.post(OA_URL, json={
                "patient_id": patient_id,
                "turn_index": turn_index,
                "message": assistant_reply
            }, timeout=3)
            print(f"Sent HC message to OA for patient {patient_id} (turn {turn_index})", flush=True)
        except Exception as e:
            print(f"Failed to notify OA: {e}", flush=True)

    threading.Thread(target=notify_oa, daemon=True).start()

    return {"status": "GRA triggered", "patient_id": patient_id}

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

    turn_index += 1

    if turn_index == 7:
        selected_goal = user_input.strip()
        patient_entry["selected_goal"] = selected_goal
    else:
        selected_goal = patient_entry.get("selected_goal", "your selected goal")

    assistant_prompt = ""
    if turn_index == 7:
        assistant_prompt = f'The client chose the goal: "{selected_goal}". Ask about their positive experience with it. Don\'t use client name if available.'
    elif turn_index == 8:
        assistant_prompt = f'Reflect warmly on the client\'s positive experience. Then ask: What was the most rewarding or enjoyable part of working on "{selected_goal}" last week? Don\'t mention goal explicitly, but rephrase it.'
    elif turn_index == 9:
        assistant_prompt = f'Encourage deeper reflection. Ask about any challenges they faced with "{selected_goal}", and what they learned about themselves while working through those. Don\'t use client name if available. Don\'t mention goal explicitly, but rephrase it.'
    elif turn_index == 10:
        assistant_prompt = f'Acknowledge their efforts so far. Then ask: How would you rate your success with "{selected_goal}" on a scale from 0% to 100%? Don\'t use client name if available. Don\'t mention goal explicitly, but rephrase it.'
    elif turn_index == 11:
        assistant_prompt = f'Reflect gently on the percentage they shared. Follow up with: What made you choose that number? Don\'t mention goal explicitly, but rephrase it.'
    elif turn_index == 12:
        assistant_prompt = f'Affirm the client’s reflections and thank them. End with an encouraging statement. Do not ask additional questions. Don\'t mention goal explicitly, but rephrase it.'

    assistant_reply = ""
    if turn_index < 13:
        full_prompt = [
                {"role": "system", "content": "You are a warm, empathetic health coach helping a patient review their SMART goals."},
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
    elif turn_index == 13:
        agent_to_trigger = "SCA"
        try:
            oa_response = requests.post(SCA_URL, json={
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
        "chat_history": chat_history,
        "selected_goal": selected_goal
    })

    return {"status": "message processed", "turn_index": turn_index}