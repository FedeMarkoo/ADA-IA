"""DuckDuckGo and Brave web search implementation."""

import json
import os
from html.parser import HTMLParser
import urllib.parse
import urllib.request
from typing import Any, Dict

from mcps.web_search.budget import SearchBudget


class WebSearcher:
    """Client for executing real-time web searches."""

    def __init__(self, user_agent: str = "ADA-Assistant/1.0", timeout: float = 5.0):
        self.user_agent = user_agent
        self.timeout = timeout
        self.budget = SearchBudget()

    def search(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "").strip()
        limit = int(args.get("limit", 5))
        if not query:
            return {"error": "Query requerido"}

        brave_key = os.environ.get("BRAVE_API_KEY", "").strip()
        if not brave_key:
            try:
                from ada.infrastructure.credentials import SecureVault

                brave_key = str(SecureVault().get("brave_api_key") or "").strip()
            except Exception:
                brave_key = ""
        scraped = self._search_google_scrape(query, limit)
        if scraped.get("provider") == "google" and scraped.get("results"):
            return scraped
        google_key, google_cx = self._google_credentials()
        if google_key and google_cx:
            result = self._search_google(query, limit, google_key, google_cx)
            if result.get("provider") == "google":
                return result
        if brave_key:
            return self._search_brave(query, limit, brave_key)
        return self._search_duckduckgo(query, limit)

    def _search_google_scrape(self, query: str, limit: int) -> Dict[str, Any]:
        """Read public Google result cards without relying on private endpoints."""
        if not self.budget.reserve("google_scrape"):
            return {"query": query, "results": [], "provider": "google", "error": "Límite local de Google alcanzado"}
        # Stable public parameters from Google's AI Mode links. Session-bound
        # values such as smstk/mtid/shmd are intentionally not persisted.
        params = urllib.parse.urlencode(
            {
                "q": query,
                "udm": "50",
                "aep": "34",
                "csuir": "1",
                "source": "sh/x/aim/m1/1",
                "hl": "es",
            }
        )
        url = f"https://www.google.com/search?{params}"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "text/html",
                    "Accept-Language": "es-AR,es;q=0.9,en;q=0.7",
                    "User-Agent": self.user_agent,
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            lowered = html.lower()
            if any(marker in lowered for marker in ("/sorry/", "captcha", "unusual traffic")):
                return {"query": query, "results": [], "provider": "google", "error": "Google solicitó verificación"}
            parser = _GoogleResultsParser()
            parser.feed(html)
            results = parser.results[:limit]
            if not results:
                return {
                    "query": query,
                    "results": [],
                    "provider": "google",
                    "error": "Google no devolvió resultados parseables",
                }
            return {"query": query, "total_results": len(results), "results": results, "provider": "google"}
        except Exception as exc:
            return {"query": query, "results": [], "provider": "google", "error": str(exc)}

    @staticmethod
    def _google_credentials():
        api_key = os.environ.get("GOOGLE_SEARCH_API_KEY", "").strip()
        engine_id = os.environ.get("GOOGLE_SEARCH_ENGINE_ID", "").strip()
        if api_key and engine_id:
            return api_key, engine_id
        try:
            from ada.infrastructure.credentials import SecureVault

            vault = SecureVault()
            return (
                str(vault.get("google_search_api_key") or "").strip(),
                str(vault.get("google_search_engine_id") or "").strip(),
            )
        except Exception:
            return "", ""

    def _search_google(self, query: str, limit: int, api_key: str, engine_id: str) -> Dict[str, Any]:
        if not self.budget.reserve("google"):
            return self._search_duckduckgo(query, limit, note="Límite local de Google alcanzado; se usó DuckDuckGo")
        params = urllib.parse.urlencode({"key": api_key, "cx": engine_id, "q": query, "num": max(1, min(limit, 10))})
        url = f"https://www.googleapis.com/customsearch/v1?{params}"
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": self.user_agent})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
            results = [
                {
                    "title": item.get("title"),
                    "url": item.get("link"),
                    "snippet": item.get("snippet", ""),
                    "source": "google",
                }
                for item in data.get("items", [])[:limit]
            ]
            return {"query": query, "total_results": len(results), "results": results, "provider": "google"}
        except Exception as exc:
            return self._search_duckduckgo(query, limit, note=f"Google Search no disponible: {exc}")

    def _search_brave(self, query: str, limit: int, api_key: str) -> Dict[str, Any]:
        if not self.budget.reserve("brave"):
            return self._search_duckduckgo(query, limit, note="Límite local de Brave alcanzado; se usó DuckDuckGo")
        params = urllib.parse.urlencode({"q": query, "count": max(1, min(limit, 20))})
        url = f"https://api.search.brave.com/res/v1/web/search?{params}"
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": api_key,
                    "User-Agent": self.user_agent,
                },
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
            results = [
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "snippet": item.get("description", ""),
                    "source": "brave",
                }
                for item in data.get("web", {}).get("results", [])[:limit]
            ]
            return {"query": query, "total_results": len(results), "results": results, "provider": "brave"}
        except Exception as exc:
            return self._search_duckduckgo(query, limit, note=f"Brave no disponible: {exc}")

    def _search_duckduckgo(self, query: str, limit: int, note: str = "") -> Dict[str, Any]:
        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
            results = []
            abstract = data.get("AbstractText")
            if abstract:
                results.append(
                    {
                        "title": data.get("Heading"),
                        "url": data.get("AbstractURL"),
                        "snippet": abstract,
                        "source": "duckduckgo",
                    }
                )
            for topic in data.get("RelatedTopics", [])[:limit]:
                if "Text" in topic:
                    results.append(
                        {
                            "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                            "url": topic.get("FirstURL"),
                            "snippet": topic.get("Text"),
                            "source": "duckduckgo",
                        }
                    )
            result = {"query": query, "total_results": len(results), "results": results, "provider": "duckduckgo"}
            if note:
                result["note"] = note
            return result
        except Exception as exc:
            return {"query": query, "results": [], "provider": "duckduckgo", "note": note or str(exc)}


class _GoogleResultsParser(HTMLParser):
    """Small tolerant parser for public result cards; Google markup may change."""

    def __init__(self):
        super().__init__()
        self._anchor = None
        self._h3_depth = 0
        self._title = []
        self.results = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href", "").startswith("http"):
            self._anchor = attrs["href"]
            self._title = []
        elif tag == "h3" and self._anchor:
            self._h3_depth += 1

    def handle_data(self, data):
        if self._anchor and self._h3_depth:
            self._title.append(data)

    def handle_endtag(self, tag):
        if tag == "h3" and self._h3_depth:
            self._h3_depth -= 1
        elif tag == "a" and self._anchor:
            title = " ".join("".join(self._title).split())
            if title and not self._anchor.startswith(("https://www.google.", "https://accounts.google.")):
                self.results.append({"title": title, "url": self._anchor, "snippet": "", "source": "google"})
            self._anchor = None
            self._title = []
