import streamlit as st
import json, requests, threading, time, base64
from pathlib import Path
from app import save_message


# === Configuration ===
MAX_TURNS = {"SOA": 6, "GRA": 13, "SCA": 15}

SOA_URL = "http://soa:8000/receive_message"
GRA_URL = "http://gra:8000/receive_message"
SCA_URL = "http://sca:8000/receive_message"

REVIEWS_FILE = Path("memory/goal_reviews.json")

# === Page Setup ===
icon = "icon.png"

st.set_page_config(page_title="GoalGuardian", 
                   page_icon=icon, 
                   layout="centered"
                   )

# Read and encode image to base64
with open(icon, "rb") as f:
    data = f.read()
    encoded = base64.b64encode(data).decode()

# Display icon + title
st.markdown(f'''
    <h1><img src="data:image/png;base64,{encoded}" width="80" style="vertical-align:middle;"> GoalGuardian</h1>
''', unsafe_allow_html=True)


# === Wait until conversation file exists ===
waiting = st.empty()
while not REVIEWS_FILE.exists():
    waiting.subheader("Waiting for health coach to start the session...")
    time.sleep(1)
waiting.empty()

# === Load Session State ===
with open(REVIEWS_FILE) as f:
    file_data = json.load(f)

entry = file_data[0]
patient_id = entry.get("patient_id", "")
turn_index = int(entry.get("turn_index", 1))
chat_history = entry.get("chat_history", [])

# === Display Chat ===
#st.subheader("Conversation")
for turn in chat_history:
    if turn["role"] == "assistant":
        st.markdown(f"**Health coach:** {turn['content']}")
    elif turn["role"] == "user":
        st.markdown(f"<div style='text-align:right'><i>You:</i> {turn['content']}</div>", unsafe_allow_html=True)

query_params = st.query_params
if query_params.get("clear"):
    st.session_state["user_reply"] = ""
    st.query_params.clear()

# === Submit Form ===
with st.form("reply_form"):
    session_complete = turn_index >= MAX_TURNS["SCA"] - 1
    user_input = st.text_area(
        "Your reply:", 
        key="user_reply", 
        height=100, 
        disabled=session_complete
    )
    submitted = st.form_submit_button("Send reply", disabled=session_complete)    
    
    if "user_reply" not in st.session_state:
        st.session_state["user_reply"] = ""

    if session_complete:
        st.info("This session is complete. No further replies can be sent.")

# === Submit Action ===
if submitted and st.session_state.user_reply.strip():
    reply = st.session_state.user_reply.strip()
    chat_history.append({"role": "user", "content": reply})

    updated_record = {
        "patient_id": patient_id,
        "turn_index": turn_index,
        "chat_history": [{"role": "user", "content": reply}]
    }
    save_message(updated_record)

    def notify_agent():
        payload = {
            "patient_id": patient_id,
            "turn_index": turn_index,
            "user_input": reply
        }
        try:
            if turn_index < MAX_TURNS["SOA"]:
                requests.post(SOA_URL, json=payload, timeout=1)
            elif turn_index < MAX_TURNS["GRA"]:
                requests.post(GRA_URL, json=payload, timeout=1)
            elif turn_index < MAX_TURNS["SCA"]:
                requests.post(SCA_URL, json=payload, timeout=1)
        except Exception as e:
            print(f"Send failed: {e}")

    threading.Thread(target=notify_agent, daemon=True).start()

    # Trigger UI refresh
    time.sleep(3)
    st.query_params.update({"clear": "true"})
    st.rerun()