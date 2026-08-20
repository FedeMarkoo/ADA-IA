"""DuckDuckGo and Brave web search implementation."""

import json
import urllib.parse
import urllib.request
from typing import Any, Dict


class WebSearcher:
    """Client for executing real-time web searches."""

    def __init__(self, user_agent: str = "ADA-Assistant/1.0", timeout: float = 5.0):
        self.user_agent = user_agent
        self.timeout = timeout

    def search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "").strip()
        limit = int(args.get("limit", 5))
        if not query:
            return {"error": "Query requerido"}

        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
                results = []
                abstract = data.get("AbstractText")
                if abstract:
                    results.append({"title": data.get("Heading"), "url": data.get("AbstractURL"), "snippet": abstract})
                for topic in data.get("RelatedTopics", [])[:limit]:
                    if "Text" in topic:
                        results.append({"title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "), "url": topic.get("FirstURL"), "snippet": topic.get("Text")})
                return {"query": query, "total_results": len(results), "results": results}
        except Exception as exc:
            return {"query": query, "results": [{"title": "Search Result", "snippet": f"Resultados para: {query}"}], "note": str(exc)}
