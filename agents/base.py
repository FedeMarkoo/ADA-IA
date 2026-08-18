"""Small building blocks for extensible specialist agents."""
from dataclasses import dataclass
from typing import Any, Dict, Iterable


@dataclass
class AgentResult:
    agent: str
    ok: bool
    data: Dict[str, Any]


class SpecialistAgent:
    """A focused unit with one responsibility and a stable output contract."""

    name = 'specialist'

    def run(self, task: Dict[str, Any]) -> AgentResult:
        raise NotImplementedError


class AgentRegistry:
    """Registry that lets new specialists be added without changing ADA's core."""

    def __init__(self, agents: Iterable[SpecialistAgent] = ()):
        self._agents = {agent.name: agent for agent in agents}

    def register(self, agent: SpecialistAgent):
        self._agents[agent.name] = agent

    def get(self, name):
        return self._agents[name]

    def names(self):
        return tuple(sorted(self._agents))
