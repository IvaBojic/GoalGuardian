import pandas as pd
from pathlib import Path
from openai import OpenAI
import time, requests, json
from datetime import datetime
from fastapi import FastAPI, Request

# === Configuration ===
OA_URL = "http://oa:8000/new_sessions"

SESSION_METADATA_FILE = Path("memory/session_metadata_mock.json")
SESSION_NOTES_FILE = Path("memory/session_notes_mock.json")
WEEKLY_GOALS_FILE = Path("memory/weekly_smart_goals_mock.json")

MODEL_NAME = "gpt-4.1" 


# === Initialization ===
app = FastAPI()
client = OpenAI()

open_tool_schema = [
    {
        "type": "function",
        "function": {
            "name": "extract_patient_info",
            "description": "Extract structured patient info from health coaching session notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "preferred_name": {"type": "string"},
                    "hobbies": {"type": "array", "items": {"type": "string"}},
                    "family": {"type": "array", "items": {"type": "string"}},
                    "friends": {"type": "array", "items": {"type": "string"}},
                    "travel": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["preferred_name", "hobbies", "family", "friends", "travel"]
            }
        }
    }
]

goal_tool_schema = [
    {
        "type": "function",
        "function": {
            "name": "extract_weekly_smart_goals",
            "description": "Extract only weekly SMART goals. Ignore long-term or monthly goals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goals": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of weekly SMART goals"
                    }
                },
                "required": ["goals"]
            }
        }
    }
]


# === GPT Wrappers ===
def extract_patient_info(note_text: str) -> dict:
    """Extract structured personal information from health coaching notes."""
    PATIENT_INFO_EXTRACTION_PROMPT = (
        "You are an expert at extracting structured information from health coaching session notes. "
        "Extract the exact parts of text, don't rephrase the text! "  
        "This is an NLU task, and not an NLG task! "      
        "For the preferred name, extract only actual first names or nicknames — do not return generic terms like "
        "'patient', 'pt', 'he', 'she', or 'client'. If a valid name cannot be found, leave the field empty. "
        "Hobbies must not include exercise or food-related activities. "
        "Avoid repeating text across family, friends, or travel fields. "
        "Include only concrete travel plans or experiences in 'travel' (not desires or dreams). "
        "If travel is family-related, keep it in 'family' and not 'travel'."
        "Always return valid JSON output. "
    )
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": PATIENT_INFO_EXTRACTION_PROMPT},
                {"role": "user", "content": f"Extract structured info from:\n{note_text}"}
            ],
            tools=open_tool_schema,
            tool_choice="auto",
            response_format={"type": "json_object"}
        )
        if response.choices[0].message.tool_calls:
            args = response.choices[0].message.tool_calls[0].function.arguments
            return json.loads(args)
    except Exception as e:
        print(f"Error during patient info extraction: {e}", flush=True)

    return {
        "preferred_name": "",
        "hobbies": [],
        "family": [],
        "friends": [],
        "travel": []
    }

def extract_weekly_goals(note_text: str) -> dict:
    """Extract SMART weekly goals from coaching session notes."""
    GOAL_EXTRACTION_PROMPT = (
        "You are an expert assistant that extracts only SMART weekly goals from health coaching session notes. " 
        "Extract the exact parts of text, don't rephrase the text! "  
        "This is an NLU task, and not an NLG task! "    
        "Only include goals that are: Specific, Measurable, Achievable, Relevant, and Time-bound (SMART). "
        "Do not include vague or broad categories like 'Exercise', 'Medication', or 'Diet' unless they are written as specific SMART goals. "
        "Ignore 6-month, long-term, or vague intentions. Focus only on short-term, concrete weekly SMART goals that the patient committed to."
        "Always respond in JSON format."
    )
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": GOAL_EXTRACTION_PROMPT},
                {"role": "user", "content": f"Extract weekly SMART goals from the following:\n{note_text}"}
            ],
            tools=goal_tool_schema,
            tool_choice="auto",
            response_format={"type": "json_object"}
        )
        if response.choices[0].message.tool_calls:
            args = response.choices[0].message.tool_calls[0].function.arguments
            return json.loads(args)
    except Exception as e:
        print(f"Weekly SMART goal extraction error: {e}", flush=True)

    return {"goals": []}


# === API Endpoints ===
@app.post("/extract")
async def extract(request: Request):
    data = await request.json()
    print(f"Received {len(data)} session entries for processing.", flush=True)

    # 1. Update session metadata
    session_df = pd.DataFrame(data)[['health_coach', 'study_id', 'date']]
    if SESSION_METADATA_FILE.exists():
        with open(SESSION_METADATA_FILE) as f:
            existing = pd.DataFrame(json.load(f))
    else:
        existing = pd.DataFrame(columns=session_df.columns)

    combined_sessions = pd.concat([existing, session_df], ignore_index=True)
    combined_sessions.drop_duplicates(subset=['study_id', 'date'], inplace=True)
    combined_sessions.sort_values(by=['study_id', 'date'], ascending=[False, False], inplace=True)

    with open(SESSION_METADATA_FILE, "w") as f:
        json.dump(combined_sessions.to_dict(orient="records"), f, indent=2)

    print(f"Session metadata updated with {len(combined_sessions)} sessions.", flush=True)

    # 2. Extract structured session notes
    patient_notes = {}
    if SESSION_NOTES_FILE.exists():
        with open(SESSION_NOTES_FILE) as f:
            patient_notes = json.load(f)

    for row in data:
        patient_id = row["study_id"]
        note = row["note"]
        structured = extract_patient_info(note)
        time.sleep(1)

        for key in ["hobbies", "family", "friends", "travel"]:
            if isinstance(structured[key], str):
                structured[key] = [structured[key]] if structured[key] else []

        if patient_id not in patient_notes:
            patient_notes[patient_id] = {
                "patient_id": patient_id,
                "input": [],
                "output": {
                    "preferred_name": structured["preferred_name"],
                    "hobbies": [],
                    "family": [],
                    "friends": [],
                    "travel": []
                }
            }

        entry = patient_notes[patient_id]
        if note not in entry["input"]:
            entry["input"].append(note)

        for key in ["hobbies", "family", "friends", "travel"]:
            entry["output"][key] = list(set(entry["output"][key] + structured[key]))

        if structured["preferred_name"]:
            entry["output"]["preferred_name"] = structured["preferred_name"]

    with open(SESSION_NOTES_FILE, "w") as f:
        json.dump(patient_notes, f, indent=2)

    print(f"Session notes updated with {len(patient_notes)} patients.", flush=True)

    # 3. Extract SMART goals
    smart_goals = {}
    if WEEKLY_GOALS_FILE.exists():
        with open(WEEKLY_GOALS_FILE) as f:
            for item in json.load(f):
                smart_goals[f"{item['patient_id']}|{item['date']}"] = item

    for row in data:
        patient_id = row["study_id"]
        date = row["date"]
        full_text = row["note"].strip()

        result = extract_weekly_goals(full_text)
        goals = result.get("goals", [])

        if goals:
            key = f"{patient_id}|{date}"
            if key not in smart_goals:
                smart_goals[key] = {
                    "patient_id": patient_id,
                    "input": full_text,
                    "date": date,
                    "output": {"goals": []}
                }
            entry = smart_goals[key]

            def clean(g): return g.strip().rstrip(".,").lower()

            existing = {clean(g) for g in entry["output"]["goals"]}
            new_goals = {clean(g) for g in goals if len(g.strip().split()) > 3}
            merged = existing.union(new_goals)

            entry["output"]["goals"] = sorted({g.capitalize() for g in merged})

        time.sleep(1)

    with open(WEEKLY_GOALS_FILE, "w") as f:
        json.dump(sorted(smart_goals.values(), key=lambda x: (x["patient_id"], x["date"]), reverse=True), f, indent=2)

    print(f"SMART goals updated with {len(smart_goals)} entries.", flush=True)

    # 4. Notify OA with latest session dates
    latest_sessions = (
        combined_sessions.sort_values(by=["study_id", "date"], ascending=[True, False])
        .drop_duplicates(subset="study_id", keep="first")
        .to_dict(orient="records")
    )

    time.sleep(1)
    try:
        res = requests.post(OA_URL, json=latest_sessions)
        if res.status_code == 200:
            print(f"Sent {len(latest_sessions)} session entries to OA.", flush=True)
        else:
            print(f"OA responded with error: {res.status_code} - {res.text}", flush=True)
    except Exception as e:
        print(f"Error sending session metadata to OA: {e}", flush=True)

    return {
        "status": "saved",
        "sessions": len(combined_sessions),
        "patients": len(patient_notes),
        "goals": len(smart_goals)
    }

@app.get("/patient_notes/{patient_id}")
def get_notes(patient_id: str):
    if SESSION_NOTES_FILE.exists():
        with open(SESSION_NOTES_FILE) as f:
            notes = json.load(f)
        if patient_id in notes:
            print(f"Sent notes to SOA for patient {patient_id}", flush=True)
            return notes[patient_id]["output"]
    return {}

@app.get("/patient_goals/{patient_id}")
def get_goals(patient_id: str):
    if WEEKLY_GOALS_FILE.exists():
        with open(WEEKLY_GOALS_FILE) as f:
            all_goals = json.load(f)
    else:
        all_goals = []

    patient_goals = [g for g in all_goals if g["patient_id"] == patient_id]
    recent_goals = []

    if patient_goals:
        latest = max(patient_goals, key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d"))
        recent_goals = latest.get("output", {}).get("goals", [])
    else:
        print(f"No SMART goals found for {patient_id}", flush=True)

    preferred_name = "there"
    if SESSION_NOTES_FILE.exists():
        with open(SESSION_NOTES_FILE) as f:
            session_data = json.load(f)
        preferred_name = session_data.get(patient_id, {}).get("output", {}).get("preferred_name", "there")

    print(f"Sent SMART goals to GRA for patient {patient_id}", flush=True)
    return {
        "preferred_name": preferred_name,
        "smart_goals": recent_goals
    }