"""Provider result normalization and concise user-facing tool summaries."""


def _filesystem_summary(result, item_key, label):
    """Summarize large filesystem listings instead of dumping every path into chat."""
    items = result.get(item_key) or []
    count = result.get("count", len(items))
    location = result.get("dir") or result.get("source") or result.get("path")
    location_text = f" en {location}" if location else ""
    if not items:
        return f"No encontré {label}{location_text}."

    # Keep Telegram/web chat readable. The complete result remains available
    # to callers through the structured response.
    preview_limit = 10
    preview = items[:preview_limit]
    lines = [f"Encontré {count} {label}{location_text}."]
    if count <= preview_limit:
        lines.append("")
        lines.extend(f"• {item}" for item in preview)
    else:
        lines.append("")
        lines.append(f"Primeros {preview_limit}:")
        lines.extend(f"• {item}" for item in preview)
        lines.append("")
        lines.append(f"Hay {count - preview_limit} más. Si querés, te muestro el listado completo.")
    return "\n".join(lines)


def text_from_result(result):
    if isinstance(result, dict):
        if result.get("action") == "list_dirs" and "dirs" in result:
            return _filesystem_summary(result, "dirs", "carpetas")
        if result.get("action") in {"list_files", "search"} and "files" in result:
            label = "archivos"
            if result.get("action") == "search":
                query = str(result.get("query") or "").strip()
                if query:
                    label = f"archivos que coinciden con «{query}»"
            return _filesystem_summary(result, "files", label)
        if result.get("action") in {"move_files", "copy_files", "undo"} and "count" in result:
            return f"Operación completada: {result['count']} archivos procesados."
        value = result.get("text") or result.get("reply") or result.get("result")
        return str(value) if value is not None else str(result)
    return str(result or "")
