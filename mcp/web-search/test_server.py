import importlib.util
import io
import pathlib
import sys
import unittest
from unittest.mock import patch


MODULE_PATH = pathlib.Path(__file__).with_name("server.py")
SPEC = importlib.util.spec_from_file_location("web_search_server", MODULE_PATH)
SERVER = importlib.util.module_from_spec(SPEC)
sys.modules["web_search_server"] = SERVER
SPEC.loader.exec_module(SERVER)


class WebSearchTest(unittest.TestCase):
    def test_reads_chunked_http_body(self):
        stream = io.BytesIO(b"4\r\ntest\r\n5\r\n body\r\n0\r\n\r\n")

        self.assertEqual(SERVER.read_chunked_body(stream), b"test body")

    @patch("web_search_server.urllib.request.urlopen")
    def test_search_parses_result(self, urlopen):
        response = urlopen.return_value.__enter__.return_value
        response.read.return_value = (
            b'<a href="https://example.com" class="result-link">Title</a>'
            b"<td class='result-snippet'>Snippet</td>"
        )

        result = SERVER.search("ada", 1)

        self.assertEqual(result[0]["title"], "Title")
        self.assertEqual(result[0]["url"], "https://example.com")

    def test_initialize_advertises_web_search(self):
        payload = SERVER.json.loads(
            SERVER.rpc_response("1", result={"tools": [SERVER.TOOL]})
        )

        self.assertEqual(payload["result"]["tools"][0]["name"], "web_search")


if __name__ == "__main__":
    unittest.main()
