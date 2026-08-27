"""Canonical locations for ADA's independent SQLite stores."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DatabasePaths:
    """Resolve ADA-owned databases without leaking MCP data into the core."""

    data_dir: Path
    memories: Path
    tools: Path
    configurations: Path
    credentials: Path
    operations: Path
    tests: Path
    mcp_dir: Path

    @classmethod
    def from_config(cls, config=None):
        config = config or {}
        data_dir = Path(config.get("data_dir") or Path.home() / "Desktop" / "ADA_Data").expanduser()
        configured = config.get("database_paths") or {}

        def path(name, fallback):
            value = configured.get(name) or config.get(f"{name}_db_path") or fallback
            candidate = Path(value).expanduser()
            return candidate if candidate.is_absolute() else data_dir / candidate

        mcp_dir = Path(config.get("mcp_data_dir") or data_dir / "mcp_data").expanduser()
        return cls(
            data_dir=data_dir,
            memories=path("memories", data_dir / "memories.db"),
            tools=path("tools", data_dir / "tools.db"),
            configurations=path("configurations", data_dir / "configurations.db"),
            credentials=path("credentials", data_dir / "credentials.db"),
            operations=path("operations", data_dir / "operations.db"),
            tests=path("tests", data_dir / "tests.db"),
            mcp_dir=mcp_dir,
        )

    def mcp_database(self, mcp_name):
        """Return an MCP-private database path, never an ADA-owned database."""
        safe_name = "".join(char if char.isalnum() or char in "-_" else "_" for char in str(mcp_name))
        return self.mcp_dir / safe_name / f"{safe_name}.db"

    def ensure_directories(self):
        for database in (self.memories, self.tools, self.configurations, self.credentials, self.operations, self.tests):
            database.parent.mkdir(parents=True, exist_ok=True)
        self.mcp_dir.mkdir(parents=True, exist_ok=True)

