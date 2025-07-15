# How the system works

Once started, the system automatically launches the `orchestration_loop` located in: `OA/app.py`. This loop runs **every hour** and checks for scheduled review sessions based on the `review_schedule.json` file.

### Example: `review_schedule.json`

```json
{
  "patients": {
    "patient_1": { "next_review_time": "2025-07-11T09:00:00" },
    "patient_2": { "next_review_time": "2025-05-29T09:00:00" },
    "patient_3": { "next_review_time": "2025-07-10T09:00:00" },
    "patient_4": { "next_review_time": "2025-06-29T09:00:00" },
    "patient_5": { "next_review_time": "2025-07-21T09:00:00" }
  }
}
```

If the current time matches a patient's `next_review_time`, a full weekly SMART goal review session is automatically triggered.

## Daily Information Extraction

Once per day, at **midnight**, the system triggers the **Memory Manager Agent (MMA)** to extract:

- SMART goals  
- Personal information  

from the `session_notes_mock.json` file.

### Example: `session_notes_mock.json`

```json
[
  {
    "study_id": "patient_1",
    "health_coach": "HC_1",
    "date": "2025-07-04",
    "title": "3-month follow-up",
    "note": "Client, Daniel, returned from a family trip to Penang. He shared that he enjoyed swimming in the hotel pool daily.\nHe lives with his wife and their two teenage sons. His eldest son recently started university overseas.\nHe enjoys photography and often brings his camera on trips.\n\nGoals Review:\n(1) Took medications consistently every morning — 100% adherence.\n(2) Switched from fried noodles to brown rice at lunch 3 times a week (Success: 90%).\n(3) Added 10 minutes of stretching before bed, 4 days a week.\n\nGoals setting:\n1. Continue to take medications 7 days a week.\n2. Homecook dinner on the weekend, once per week (e.g., Sundays).\n3. Increase the duration of jogging to 45 mins, once per week, every Saturday morning."
  },
  {
    "study_id": "patient_2",
    "health_coach": "HC_2",
    "date": "2025-05-22",
    "title": "Regular check-in",
    "note": "Client, Aisha, is a retired teacher who enjoys reading detective novels and knitting. She mentioned planning a trip to Japan with her book club in September.\nShe is close to her younger sister who lives nearby, and they meet twice a week for walks.\n\nMedication adherence has been consistent. She finds it easier to take morning doses with breakfast.\n\nGoals setting:\n1. Walk 40 minutes with her sister every Tuesday and Thursday morning.\n2. Eat two servings of vegetables at dinner, five days per week.\n3. Practice mindful breathing for 5 minutes before sleep, every night."
  }
]
```

## Manual triggering

The system can also be manually triggered to start a conversation with a specific patient. To do so, run the following command in your terminal:

```bash
curl -X POST localhost:8002/trigger \
  -H "Content-Type: application/json" \
  -d '{"patient_id": "patient_1"}'
```

Replace `patient_1` with the desired patient_id. This will initiate a SMART goal review session immediately for that patient, bypassing the scheduled review time.
