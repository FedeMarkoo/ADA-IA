from typing import Any, Dict, List
import logging

logger = logging.getLogger("ada.web_search")

try:
    from ddgs import DDGS
except ImportError:  # Web search is optional; the core agent must work offline.
    DDGS = None
    logger.info("web_search_disabled reason=ddgs_not_installed")


def search_web(query, max_results=5):
    """Return simple search results (title, href, snippet) using DDGS.text."""
    if DDGS is None:
        return []
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
        out: List[Dict[str, Any]] = []
        if not results:
            return out
        for r in results:
            out.append(
                {
                    "title": r.get("title") or r.get("text"),
                    "href": r.get("href") or r.get("url"),
                    "body": r.get("body") or r.get("snippet") or r.get("text"),
                }
            )
        return out
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.warning("web_search_failed error=%s", exc)
        return []
