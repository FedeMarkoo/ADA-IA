import unittest
from unittest.mock import patch

from ada.infrastructure.persistence.sqlite import Memory
from ada.mcps.manager import MCPManager
from mcps.memory.server import create_memory_server


class MemoryMCPTests(unittest.TestCase):
    def test_server_exposes_crud_tools_with_mutation_confirmation(self):
        server = create_memory_server(Memory(":memory:"))
        self.assertEqual(set(server.tools), {"memory.search", "memory.add", "memory.update", "memory.delete"})
        self.assertFalse(server.tools["memory.search"]["requires_confirmation"])
        self.assertTrue(server.tools["memory.add"]["requires_confirmation"])
        self.assertTrue(server.tools["memory.update"]["requires_confirmation"])
        self.assertTrue(server.tools["memory.delete"]["requires_confirmation"])

    def test_memory_mcp_crud_round_trip(self):
        memory = Memory(":memory:")
        server = create_memory_server(memory)
        added = server.handlers["memory.add"]({"content": "Vive en Córdoba", "kind": "profile", "_confirmed": True})
        self.assertTrue(added["ok"])
        memory_id = added["id"]
        found = server.handlers["memory.search"]({"query": "Córdoba", "kind": "profile"})
        self.assertEqual(found["memories"][0]["id"], memory_id)
        updated = server.handlers["memory.update"]({"id": memory_id, "content": "Vive en Rosario", "_confirmed": True})
        self.assertTrue(updated["ok"])
        self.assertEqual(server.handlers["memory.search"]({"query": "Rosario"})["count"], 1)
        deleted = server.handlers["memory.delete"]({"id": memory_id, "_confirmed": True})
        self.assertTrue(deleted["ok"])
        self.assertEqual(server.handlers["memory.search"]({"query": "Rosario"})["count"], 0)

    def test_manager_registers_memory_tools_and_requires_confirmation(self):
        manager = MCPManager()
        names = {tool["name"] for tool in manager.list_tools(category="memory")}
        self.assertEqual(names, {"memory.search", "memory.add", "memory.update", "memory.delete"})
        with patch("ada.mcps.manager.MCP_IN_FLIGHT.labels"):
            result = manager.execute_tool("memory.add", {"content": "sin confirmación"})
        self.assertEqual(result["error"], "confirmation_required")


if __name__ == "__main__":
    unittest.main()
