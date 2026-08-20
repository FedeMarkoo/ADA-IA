import unittest

from ada.interfaces.lightroom_mcp_server import TOOL_SCHEMAS, _tools


class LightroomMcpTests(unittest.TestCase):
    def test_exposes_safe_and_mutating_tools(self):
        tools = _tools()
        self.assertEqual(
            set(tools),
            {
                "lightroom_count_photos",
                "lightroom_analyze",
                "lightroom_plan",
                "lightroom_simulate",
                "lightroom_apply",
                "lightroom_recover",
            },
        )

    def test_mutating_tools_require_explicit_confirmation(self):
        self.assertEqual(TOOL_SCHEMAS["lightroom_apply"]["required"], ["confirm"])
        self.assertEqual(TOOL_SCHEMAS["lightroom_apply"]["properties"]["confirm"]["const"], True)
        self.assertEqual(TOOL_SCHEMAS["lightroom_recover"]["required"], ["confirm"])

    def test_read_only_tools_do_not_require_confirmation(self):
        for name in ("lightroom_count_photos", "lightroom_analyze", "lightroom_plan", "lightroom_simulate"):
            self.assertNotIn("required", TOOL_SCHEMAS[name])


if __name__ == "__main__":
    unittest.main()
