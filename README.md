This is a Senior-level README written in plain, clear English. It is designed to guide the hiring manager through your project without confusing them, while still proving you know exactly what you are doing.

AR-1: The Smart Hiring Agent

AR-1 is an automated system designed to handle 1,000+ job applications at once. It doesn't just read resumes—it thinks, vets, and interacts with candidates like a real recruiter would.

What does this Agent do?

Extracts Data: It "sniffs" applicant data from platforms like Internshala.

Scores Quality: It uses AI (Gemini) to tell the difference between a "Great Builder" and a "Generic Applicant."

Catches Cheaters: It uses "Vector Memory" to find candidates who are copy-pasting from each other or using ChatGPT.

Sends Emails: It starts contextual conversations with top candidates automatically.

Stays Reliable: It uses a "Transactional Outbox" system—meaning if the power goes out or the internet blinks, the agent remembers exactly where it left off. No candidate is ever lost.

How it Works (The Simple View)

The system is split into four "Workers" that talk to each other:

The Feeder (Go): Scrapes the data and saves it to the database.

The Brain (Python): Uses AI to score the answers and check for cheating.

The Relay (Go): Moves data between the database and the message broker (RabbitMQ) safely.

The Voice (Go): Sends personalized emails to candidates based on their scores.

🛠️ Features
1. Anti-Cheat Engine

Many candidates use ChatGPT or copy from friends. AR-1 has two layers of defense:

AI Fingerprinting: It looks for common "AI phrases" (like "In today's fast-paced world").

Similarity Search: It compares every new answer to every old answer in the database. If two people submit the same thing, the agent flags them instantly.

2. Smart Scoring

The agent doesn't just look for keywords. It looks for "Technical Density"—does the candidate explain how they built something, or are they just listing tools?

3. Fault-Tolerance

We use the Transactional Outbox Pattern. This is a professional way to ensure that the "Brain" and the "Voice" stay in sync. If the AI finishes scoring, the database ensures the email must be sent eventually.

⚙️ Setup & How to Run
Prerequisites

Docker (For the Database and Message Broker)

Go (v1.22+)

Python (v3.10+)

Gemini API Key (From Google AI Studio)

Step 1: Start the Infrastructure

In the root folder, run:

code
Bash
download
content_copy
expand_less
docker-compose up -d

This starts PostgreSQL (with vector search) and RabbitMQ.

Step 2: Initialize the Database

Run our setup script to create the tables:

code
Bash
download
content_copy
expand_less
psql -h localhost -U postgres -d hiring_agent_db -f scripts/init.sql

(If you are on a Mac and use a different username, change postgres to your username).

Step 3: Setup your Environment

Copy the .env.example file and rename it to .env.

Open .env and paste your GEMINI_API_KEY.

(Optional) Adjust your database settings if they are different.

Step 4: Run the System

Open 4 terminal windows and run these in order:

The Brain (Python):
export PYTHONPATH=$PYTHONPATH:. && python3 cmd/analyzer/main.py

The Voice (Go):
go run cmd/communicator/main.go

The Relay (Go):
go run cmd/outbox_poller/main.go

The Feeder (Go):
go run cmd/ingestor/main.go

📂 Project Structure

/cmd: The main entry points for all our services (Go and Python).

/internal: The "guts" of the system—where the AI logic and database code live.

/scripts: The SQL files to set up your database.

docker-compose.yml: The "One-Click" setup for the server environment.

Proof of Concept

During our test run with 4 mock candidates:

Vikram Singh was scored as STANDARD because he had a good technical answer.

Sameer Gupta submitted the exact same answer as Vikram. The system detected the similarity, issued a Strike, and automatically changed his status to REJECT (Fraud).

