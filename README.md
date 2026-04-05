# AR-1: Autonomous Hiring Agent (Internshala Edition)

AR-1 is a **distributed, polyglot worker system** designed to automate the end-to-end recruitment lifecycle. It is built to handle high-volume applications (1,000+) using an event-driven architecture that ensures 100% reliability and real-time fraud detection.

## System Architecture

The system follows **Hexagonal Architecture** principles, decoupling the "Brain" (AI Reasoning) from the "Body" (Infrastructure & Automation).

### 1. The Distributed Nervous System (Go + RabbitMQ)
- **High Concurrency:** Go handles the Ingestor (Scraping) and Communicator (Messaging) layers to manage 100+ parallel browser sessions and email threads.
- **Reliability (Transactional Outbox Pattern):** Implemented a Go-based **Outbox Poller**. Workers write to a local Postgres outbox table in an atomic transaction, ensuring no candidate is lost during network or API outages.

### 2. The Intelligence & Anti-Cheat Brain (Python + Gemini + pgvector)
- **Semantic Intelligence:** Uses Google Gemini-1.5-Flash to evaluate technical depth, problem-solving ability, and "Builder" signals vs. mass-application patterns.
- **Anti-Cheat (Component 4):** 
    - **Vector Similarity:** Every answer is converted into a 768-dimension vector using **Matryoshka Embeddings**.
    - **Cross-Candidate Detection:** Uses `pgvector` with a Cosine Distance threshold (< 0.15) to identify "Copy-Rings" in real-time.
    - **AI Fingerprinting:** A RegEx-based engine detects common LLM stylistic markers.

### 3. Multi-Round Engagement (Go State Machine)
- **Contextual Memory:** Tracks candidate state (`PENDING` → `SCORED` → `CONTACTED`) in PostgreSQL.
- **Context-Aware Replies:** Before generating a message, the system fetches the full conversation history to ensure Round 2 technical questions are progressively deeper.

---

## Components & Workflow

1.  **ACCESS:** Uses a **CDP (Chrome DevTools Protocol) Hijack** strategy. Instead of brittle headless logins, the agent attaches to a human-authenticated browser session to bypass reCAPTCHA Enterprise. *(Currently in MOCK mode due to platform verification constraints).*
2.  **INTELLIGENCE:** Automated scoring based on technical density and "hunger" signals.
3.  **ANTI-CHEAT:** Caught "Sameer Gupta" (Mock) for copying "Vikram Singh" (Mock) using semantic similarity.
4.  **SELF-LEARNING:** A background "Optimizer" worker analyzes rejection trends to update the hiring rubric dynamically.

---

## Tech Stack
- **Languages:** Go 1.23, Python 3.12
- **Broker:** RabbitMQ
- **Database:** PostgreSQL 16 + `pgvector`
- **AI:** Google Gemini API (Flash + Embeddings)
- **Automation:** Go-Rod (CDP Hijacking)

---

## ⚙️ Setup & Installation

### 1. Infrastructure
Ensure Docker is running, then launch the database and message broker:
```bash
docker-compose up -d