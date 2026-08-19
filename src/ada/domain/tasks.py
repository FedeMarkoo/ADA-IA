"""Technology-independent task and planning contracts."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class Action:
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = 'low'
    permissions: List[str] = field(default_factory=list)
    reversible: bool = False
    requires_confirmation: bool = False


@dataclass
class Plan:
    actions: List[Action] = field(default_factory=list)
    explanation: str = ''
    plan_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    dry_run: bool = True

    def high_risk(self):
        return any(action.risk_level in {'high', 'critical'} for action in self.actions)


@dataclass
class Task:
    request: str
    plan: Optional[Plan] = None
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    session_id: str = 'main'
    metadata: Dict[str, Any] = field(default_factory=dict)
