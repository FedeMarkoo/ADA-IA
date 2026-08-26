"""Legacy MCP entrypoint for explicitly enabled in-process capabilities."""

from ada.application.agent import Agent
from ada.capabilities.registry import capability_specs
from ada.config import load_config
from ada.infrastructure.integrations.mcp_server import serve


def main():
    config = load_config()
    agent = Agent(config)
    if not agent.capabilities_enabled:
        raise RuntimeError(
            "El MCP legacy de capabilities está deshabilitado; usá servidores MCP dedicados."
        )
    specs = capability_specs()
    descriptions = {name: spec.description for name, spec in specs.items()}
    schemas = {name: spec.argument_schema for name, spec in specs.items() if spec.argument_schema}
    serve(agent.skills, descriptions=descriptions, schemas=schemas)


if __name__ == "__main__":
    main()
