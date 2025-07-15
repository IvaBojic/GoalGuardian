import json
from pathlib import Path
from openai import OpenAI
from fastapi import FastAPI, Request # type: ignore

# === Configuration ===
SUMMARY_FILE = Path("memory/session_summaries.json")

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
def save_summary_to_file(patient_id, chat_history, summary):
    if SUMMARY_FILE.exists():
        with open(SUMMARY_FILE) as f:
            summaries = json.load(f)
    else:
        summaries = []

    summaries.append({
        "patient_id": patient_id,
        "chat_history": chat_history,
        "summary": summary
    })

    SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_FILE, "w") as f:
        json.dump(summaries, f, indent=2)

    print(f"Session summary for {patient_id} saved", flush=True)


# === API Endpoints ===
@app.post("/trigger")
async def trigger(request: Request):
    data = await request.json()
    chat_history = data.get("chat_history", [])
    patient_id = data.get("patient_id")

    if not patient_id or not chat_history:
        return {"status": "error", "reason": "Missing patient_id or chat_history"}

    # Format chat history
    summary_input = "Here is the full conversation between the health coach and the patient:\n\n"
    for turn in chat_history:
        role = turn.get("role").capitalize()
        content = turn.get("content", "")
        summary_input += f"{role}: {content}\n"

    # Ask GPT for summary
    messages = [
        {"role": "system", "content": "You are a summarization assistant for health coaching conversations."},
        {"role": "user", "content": summary_input}
    ]
    summary = ask_gpt(messages)
    #summary = "This is summary!"

    # Save to file
    save_summary_to_file(patient_id, chat_history, summary)

    return {"status": "ok", "summary": summary}