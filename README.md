# GoalGuardian
AI Multi-Agent System (MAS) for weekly SMART goal review.

In this repository, you'll find the **prototype implementation** of GoalGuardian, an AI-driven MAS designed for weekly SMART goal reviews in digital health settings.  
⚠️ *This version uses a pretrained GPT-4.1 model and requires a valid `OPENAI_API_KEY` to function.*

## Prototype overview

**GoalGuardian** is a real-world MAS built on GPT-4.1 that enables structured, scalable collaboration between AI agents and clients. Designed to coordinate weekly SMART goal reviews, the prototype demonstrates how persistent memory, modular orchestration, and structured conversational agents can support human-centered interventions at scale.

### Agents

GoalGuardian includes six specialized agents, each fulfilling a specific role in the weekly goal review process:

- **Orchestration Agent (OA):** Manages the workflow, including information extraction and scheduling of review sessions.  
- **Memory Manager Agent (MMA):** Extracts SMART goals and personal details from health coaching (HC) notes and makes this information available to other agents.  
- **Session Opening Agent (SOA):** Welcomes the client and initiates the review session with personalized context.  
- **Goal Review Agent (GRA):** Conducts structured check-ins on client progress toward SMART goals.  
- **Session Closing Agent (SCA):** Wraps up the session, reinforces insights, and confirms next steps or commitments.  
- **Session Summarization Agent (SSA):** Generates structured reports for human health coaches based on the session transcript.

Together, these agents embody a hybrid AI-human collaboration framework that is modular, extensible, and suitable for deployment in real-world healthcare environments.

## Running the GoalGuardian prototype

### Prerequisites

To run the GoalGuardian system locally, ensure you have a valid OpenAI API key in your `.env` file:

```env
OPENAI_API_KEY=your-key-here
```

### Starting the MAS System

To start the multi-agent system using Docker, run:

```bash
COMPOSE_BAKE=true docker compose up --build
```

Once the system is running, open your browser and navigate to:

```
http://localhost:8502/
```

If the system is running on a different machine than the one with the browser, ensure that port forwarding is properly configured or use an SSH tunnel to access the interface.

```
ssh -L 8502:localhost:8502 username@ip_address
```

Then open your browser on the local machine and go to http://localhost:8502/ to access the GoalGuardian's web interface.
