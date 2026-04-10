-- 1. Infrastructure Setup
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 2. Clean Start: Remove existing tables/views in correct order
DROP VIEW IF EXISTS candidate_master_profiles CASCADE;
DROP TABLE IF EXISTS strikes CASCADE;
DROP TABLE IF EXISTS candidate_embeddings CASCADE;
DROP TABLE IF EXISTS outbox CASCADE;
DROP TABLE IF EXISTS candidates CASCADE;

-- 3. Candidates Table (The "Unified Profile" Source)
-- Handles Component 2 (Intelligence), Component 3 (State), and Component 6 (Integration)
CREATE TABLE candidates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    external_id TEXT UNIQUE NOT NULL,      -- ID from Internshala
    name TEXT,
    email TEXT,
    github_url TEXT,
    status TEXT DEFAULT 'PENDING',         -- PENDING -> SCORED -> CONTACTED -> ROUND_2_COMPLETE
    tier TEXT,                             -- FAST-TRACK, STANDARD, REJECT, REJECT (Fraud)
    
    -- Scoring Metrics (Component 2: Deep Intelligence)
    technical_score INT DEFAULT 0,
    longevity_score INT DEFAULT 0,         -- Signals of a 'Builder' vs Mass-Applier
    hunger_score INT DEFAULT 0,
    reasoning TEXT,                        -- Detailed AI analysis
    
    -- Anti-Cheat State (Component 4)
    strike_count INT DEFAULT 0,
    raw_answer TEXT,
    
    -- Conversation State Machine (Component 3: Engagement)
    current_round INT DEFAULT 1,
    conversation_history JSONB DEFAULT '[]'::jsonb, -- Stores full Q&A history
    
    -- Timing & Re-engagement (Component 6)
    last_interaction_at TIMESTAMP DEFAULT NOW(),
    next_action_due_at TIMESTAMP DEFAULT NOW() + interval '24 hours',
    created_at TIMESTAMP DEFAULT NOW()
);

-- 4. Vector Store (Component 4: Anti-Cheat)
-- Optimized for 768-dimension Matryoshka Embeddings
CREATE TABLE candidate_embeddings (
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    embedding vector(768),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 5. Reliability Outbox (Component 6: Integration)
-- Ensures atomicity between DB updates and RabbitMQ events
CREATE TABLE outbox (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 6. Fraud Log (Component 4: Security)
CREATE TABLE strikes (
    id SERIAL PRIMARY KEY,
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 7. PERFORMANCE: HNSW Index for Semantic Search
-- Crucial for handling 1,000+ candidates efficiently
CREATE INDEX ON candidate_embeddings USING hnsw (embedding vector_cosine_ops);

-- 8. UNIFIED PROFILE VIEW (Component 6)
-- This is the "Master Record" for human review
CREATE OR REPLACE VIEW candidate_master_profiles AS
SELECT 
    c.id,
    c.name,
    c.tier,
    c.status,
    (c.technical_score + c.longevity_score + c.hunger_score) AS potential_rank,
    c.technical_score,
    c.longevity_score,
    c.hunger_score,
    c.reasoning AS ai_summary,
    c.conversation_history,
    c.strike_count,
    (SELECT json_agg(s.reason) FROM strikes s WHERE s.candidate_id = c.id) AS strike_details
FROM candidates c;