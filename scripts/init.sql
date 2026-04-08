CREATE EXTENSION IF NOT EXISTS vector;
DROP TABLE IF EXISTS strikes CASCADE;
DROP TABLE IF EXISTS candidate_embeddings CASCADE;
DROP TABLE IF EXISTS outbox CASCADE;
DROP TABLE IF EXISTS candidates CASCADE;

CREATE TABLE candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    external_id TEXT UNIQUE NOT NULL,
    name TEXT,
    email TEXT,
    github_url TEXT,
    status TEXT DEFAULT 'PENDING',
    tier TEXT,
    reasoning TEXT,
    technical_score INT DEFAULT 0,
    quality_score INT DEFAULT 0,
    strike_count INT DEFAULT 0,
    raw_answer TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE candidate_embeddings (
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    embedding vector(768),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE strikes (
    id SERIAL PRIMARY KEY,
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX ON candidate_embeddings USING hnsw (embedding vector_cosine_ops);

-- Track the conversation round and history
ALTER TABLE candidates ADD COLUMN current_round INT DEFAULT 1;
ALTER TABLE candidates ADD COLUMN conversation_history JSONB DEFAULT '[]'::jsonb;

-- New scores for Component 2 (The 5-Year Builder)
ALTER TABLE candidates ADD COLUMN longevity_score INT DEFAULT 0;
ALTER TABLE candidates ADD COLUMN hunger_score INT DEFAULT 0;
