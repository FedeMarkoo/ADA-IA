CREATE TABLE IF NOT EXISTS system_prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);;

CREATE INDEX IF NOT EXISTS idx_system_prompts_active_version
    ON system_prompts(active, version DESC);;

CREATE TABLE IF NOT EXISTS ada_secrets (
    name TEXT PRIMARY KEY,
    value BLOB NOT NULL
);;

CREATE TABLE IF NOT EXISTS rag_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);;

CREATE VIRTUAL TABLE IF NOT EXISTS rag_documents_fts USING fts5(
    source,
    content,
    content='rag_documents',
    content_rowid='id'
);;

CREATE TRIGGER IF NOT EXISTS rag_documents_ai AFTER INSERT ON rag_documents BEGIN
    INSERT INTO rag_documents_fts(rowid, source, content)
    VALUES (new.id, new.source, new.content);
END;;

CREATE TRIGGER IF NOT EXISTS rag_documents_ad AFTER DELETE ON rag_documents BEGIN
    INSERT INTO rag_documents_fts(rag_documents_fts, rowid, source, content)
    VALUES ('delete', old.id, old.source, old.content);
END;;

CREATE TRIGGER IF NOT EXISTS rag_documents_au AFTER UPDATE ON rag_documents BEGIN
    INSERT INTO rag_documents_fts(rag_documents_fts, rowid, source, content)
    VALUES ('delete', old.id, old.source, old.content);
    INSERT INTO rag_documents_fts(rowid, source, content)
    VALUES (new.id, new.source, new.content);
END;;

CREATE TABLE IF NOT EXISTS scheduled_triggers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    cron_expression TEXT NOT NULL,
    timezone TEXT NOT NULL,
    prompt TEXT NOT NULL,
    conversation_id TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    next_run_at TEXT NOT NULL,
    last_run_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);;

CREATE INDEX IF NOT EXISTS idx_scheduled_triggers_due
    ON scheduled_triggers(enabled, next_run_at);;
