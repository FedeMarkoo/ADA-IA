"""Installable MCP stdio entrypoint exposing ADA capabilities."""

from ada.application.agent import Agent
from ada.capabilities.registry import capability_specs
from ada.config import load_config
from ada.infrastructure.integrations.mcp_server import serve


def _policy_wrapped_tools(agent):
    return {
        name: (lambda args, capability=name: agent.run_skill(capability, args, confirm=args.get("confirm")))
        for name in agent.skills
    }


def main():
    config = load_config()
    agent = Agent(config)
    specs = capability_specs()
    descriptions = {name: spec.description for name, spec in specs.items()}
    schemas = {name: spec.argument_schema for name, spec in specs.items() if spec.argument_schema}
    serve(_policy_wrapped_tools(agent), descriptions=descriptions, schemas=schemas)


if __name__ == "__main__":
    main()
