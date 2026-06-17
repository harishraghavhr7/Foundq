-- VentureMind AI — Feature 1: Startup Idea Submission
-- PostgreSQL schema for the `ideas` table.

CREATE TABLE IF NOT EXISTS ideas (
    id          SERIAL PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    description TEXT         NOT NULL,
    industry    VARCHAR(100) NOT NULL,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Common access pattern: list newest ideas first.
CREATE INDEX IF NOT EXISTS idx_ideas_created_at ON ideas (created_at DESC);
