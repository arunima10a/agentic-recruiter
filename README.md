#  AR-1: Autonomous Hiring Agent

AR-1 is a distributed AI agent designed to handle the full recruitment process for high-volume roles (1000+ applicants).  
It doesn’t just filter resumes — it evaluates skills, detects suspicious activity, and manages multi-step candidate interactions automatically.

---

#  System Architecture

The system follows **Hexagonal Architecture**, separating the “Brain” (AI logic) from the “Body” (infrastructure).

## 1. Distributed Backend (Go + RabbitMQ)

- **High concurrency:** Go handles ingestion (data collection) and communication (messaging).
- **Reliable processing:** Uses a transactional outbox pattern so no important event (like sending emails) is lost.

## 2. Intelligence Engine (Python + Gemini + pgvector)

- **Candidate scoring:** Evaluates technical strength and consistency.
- **Similarity detection:** Uses vector embeddings and pgvector to detect duplicate or copied answers.
- **AI comparison:** Compares candidate responses with AI-generated baselines.
- **Adaptive learning:** Improves scoring over time based on previous strong candidates.

---

#  Key Features

- **Automated Access Handling:** Uses browser automation (Go-Rod) to work with active sessions smoothly.
- **Session Management:** Saves and restores cookies for continuous operation.
- **Re-engagement System:** Automatically follows up with inactive candidates.
- **Unified Candidate View:** Combines scores, flags, and interactions into one database view.

---

# ⚙️ Setup & Installation

## Step 1: Start Infrastructure

Run the database (with pgvector) and RabbitMQ:

```bash
docker-compose up -d
```

---

## Step 2: Initialize Database

Set up schema and required extensions:

```bash
psql -h localhost -U postgres -d hiring_agent_db -f scripts/init.sql
```

*(Mac users: replace `postgres` with your local username if needed)*

---

## Step 3: Configure Environment

1. Copy the example file:

```bash
cp .env.example .env
```

2. Add your API key inside `.env`:

```
GEMINI_API_KEY=your_key_here
```

---

#  Running the Agent

Open **5 terminals** and run services in this order:

---

## 1. Brain (Python Analyzer)

Handles scoring and evaluation:

```bash
export PYTHONPATH=$PYTHONPATH:. && python3 cmd/analyzer/main.py
```

---

## 2. Relay (Go Outbox Poller)

Ensures reliable communication between services:

```bash
go run cmd/outbox_poller/main.go
```

---

## 3. Voice (Go Communicator)

Sends emails to candidates:

```bash
go run cmd/communicator/main.go
```

---

## 4. Nudger (Go Re-engagement)

Follows up with inactive candidates:

```bash
go run cmd/nudger/main.go
```

---

## 5. Feeder (Go Ingestor)

Adds candidates to the system:

```bash
# Run with mock data
go run cmd/ingestor/main.go -mode=mock

# Run with real data (requires Chrome debugging port 9222)
go run cmd/ingestor/main.go -mode=real
```

---

#  Viewing Results

Check processed candidates in the database:

```sql
\x on
SELECT * FROM candidate_master_profiles;
```

---

# 🎯 Example: Duplicate Detection

During testing:

- Candidate A submitted a strong original answer → marked **FAST-TRACK**
- Candidate B submitted a very similar answer shortly after

**Result:**  
The system detected high similarity using vector comparison and flagged it automatically.

---

# 🛠️ Tech Stack

- **Languages:** Go (v1.22), Python (v3.12)  
- **Database:** PostgreSQL 16 + pgvector  
- **Message Broker:** RabbitMQ  
- **AI:** Google Gemini (reasoning + embeddings)  
- **Automation:** Go-Rod (browser automation)