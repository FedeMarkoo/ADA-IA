CREATE TABLE IF NOT EXISTS system_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_system_prompts_active_version
    ON system_prompts(active, version DESC);

CREATE TABLE IF NOT EXISTS ada_secrets (
    name TEXT PRIMARY KEY,
    value BLOB NOT NULL
);
