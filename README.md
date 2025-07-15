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
