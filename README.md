#  AR-1: The Smart Hiring Agent

AR-1 is an automated hiring system designed to handle the pressure of 1,000+ job applications. Instead of just filtering by keywords, it **thinks**, **vets**, and **interacts** with candidates like a real recruiter would.

It uses a "Distributed Nervous System" to ensure that even if the internet blinks or a server restarts, no candidate is ever lost.

---

##  How it Works (The Simple View)

The system is split into four "Workers" that talk to each other through a message broker (RabbitMQ):

1. **The Feeder (Go):** Scrapes applicant data and saves it to the database.  
2. **The Brain (Python):** Uses AI (Gemini) to score answers and check for cheating.  
3. **The Relay (Go):** Moves data between the database and the "Brain" safely using the **Transactional Outbox Pattern**.  
4. **The Voice (Go):** Sends personalized, contextual emails to candidates based on their results.  

---

##  Key Features

### 1. Anti-Cheat Engine (Component 4)
Many candidates use ChatGPT or copy from friends. AR-1 has a two-layer defense:
- **AI Fingerprinting:** It scans for common "AI phrases" (like *"In today's rapidly evolving landscape"*).
- **Semantic Similarity:** It uses **Vector Search (pgvector)** to compare every new answer to every old answer. If two people submit the same project description, the agent flags them instantly.

### 2. Technical Intelligence (Component 2)
The agent doesn't just look for length. It looks for "Technical Density." It rewards candidates who explain **how** they built something and penalizes generic buzzwords.

### 3. Reliability (Component 6)
We use the **Transactional Outbox Pattern**. This is a professional engineering standard. If the AI scores a candidate but the email system is down, the database "remembers" the intent and sends the email as soon as the system is back online.

---

##  The Tech Stack

- **Go:** High-performance concurrency for the "Body" (Ingestion & Messaging)  
- **Python:** Advanced AI processing and Vector math for the "Brain"  
- **PostgreSQL + pgvector:** Relational memory with semantic search capabilities  
- **RabbitMQ:** The event bus that keeps all workers connected  
- **Google Gemini API:** For technical reasoning and text embeddings  

---

## ⚙️ Setup & Installation

### Prerequisites

- **Docker**
- **Go** (v1.22+)
- **Python** (v3.10+)
- **Gemini API Key** (from Google AI Studio)

---

### Step 1: Start the Infrastructure

In the root folder, run:

```bash
docker-compose up -d
```

---

### Step 2: Initialize the Database

Run the provided SQL script to create tables, enable vector search, and set up indexing:

```bash
psql -h localhost -U postgres -d hiring_agent_db -f scripts/init.sql
```

> ⚠️ **Note (Mac Users):** You may need to use your Mac username instead of `postgres`.

---

### Step 3: Configure Environment

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Open `.env` and add your API key:

```env
GEMINI_API_KEY=your_api_key_here
```

---

##  Running the Agent

To run the distributed system, open **4 separate terminal windows** and execute the services in the following order:

### 1.  The Brain (Python Analyzer)

```bash
export PYTHONPATH=$PYTHONPATH:. && python3 cmd/analyzer/main.py
```

---

### 2.  The Relay (Go Outbox Poller)

```bash
go run cmd/outbox_poller/main.go
```

---

### 3.  The Voice (Go Communicator)

```bash
go run cmd/communicator/main.go
```

---

### 4.  The Feeder (Go Ingestor)

```bash
go run cmd/ingestor/main.go
```

---

##  Proof of Concept: Anti-Cheat Validation

During the final test run, the system processed **4 candidates**. The **Anti-Cheat Engine** behaved as expected:

### Case 1: Vikram Singh
- Submitted a legitimate technical answer  
- System classified him as: **STANDARD**

---

### Case 2: Sameer Gupta
- Submitted the **exact same answer** as Vikram (test case)

#### System Behavior:
- Python Analyzer generated a **vector embedding**
- Performed **Cosine Similarity search** in PostgreSQL
- Detected a **99% similarity match** with Vikram’s answer  

####  Outcome:
- Issued an automatic **Strike**  
- Flagged candidate as: **REJECT (Fraud)**  
- Generated a contextual rejection message  
- All actions performed **without human intervention**  