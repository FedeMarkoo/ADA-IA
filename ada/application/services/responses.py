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


def _drive_summary(result):
    """Readable Drive listing, preserving direct cloud links."""
    files = result.get("files") or []
    if not files:
        return "No encontré archivos en Google Drive."
    lines = [f"Encontré {len(files)} archivos en Google Drive.", ""]
    for item in files[:10]:
        if isinstance(item, dict):
            name = item.get("name") or item.get("id") or "archivo sin nombre"
            link = item.get("webViewLink") or item.get("link")
            lines.append(f"• {name}" + (f" — {link}" if link else ""))
        else:
            lines.append(f"• {item}")
    if len(files) > 10:
        lines.append(f"\nHay {len(files) - 10} más.")
    return "\n".join(lines)


def text_from_result(result):
    if isinstance(result, dict):
        # MCP transports wrap the actual payload in {ok, result}.  Unwrap
        # that envelope before formatting so chat never exposes a transport
        # object instead of the data returned by the selected tool.
        if "ok" in result and "result" in result and set(result).issubset({"ok", "result"}):
            if result.get("ok") is False:
                return text_from_result({"error": result.get("error", "La herramienta MCP falló")})
            return text_from_result(result.get("result"))
        if result.get("error"):
            error = str(result.get("error"))
            if "allowlist" in error.lower() or "fuera de" in error.lower():
                return "No pude acceder a esa carpeta porque está fuera de las ubicaciones autorizadas de ADA."
            known = {
                "item_not_found": "No encontré ese elemento.",
                "recipe_not_found": "No encontré esa receta guardada.",
                "unknown_domain": "No pude determinar qué sección de comida usar.",
                "dir not found": "Esa carpeta ya no está disponible en el disco.",
            }
            if "proveedor no pudo" in error.lower() or "provider" in error.lower():
                return "El modelo no pudo completar esta respuesta. Reintentá una vez; si vuelve a fallar, ADA cambiará de modelo automáticamente."
            return known.get(error, f"No pude completar la operación: {error}.")
        if result.get("action") == "list_dirs" and "dirs" in result:
            return _filesystem_summary(result, "dirs", "carpetas")
        if result.get("fallback") == "google-rest" and "files" in result:
            return _drive_summary(result)
        if result.get("fallback") == "google-rest" and result.get("kind") == "calendar#calendarList":
            calendars = result.get("items") or []
            if not calendars:
                return "No encontré calendarios en Google Calendar."
            names = [
                str(item.get("summary") or item.get("id") or item)
                if isinstance(item, dict) else str(item)
                for item in calendars
            ]
            return "Calendarios encontrados:\n" + "\n".join(f"• {name}" for name in names)
        if result.get("fallback") == "google-rest" and result.get("kind") == "calendar#events":
            events = result.get("items") or []
            if not events:
                query = result.get("search_query")
                if query:
                    return f"No encontré eventos relacionados con «{query}» en Google Calendar."
                month = result.get("search_month")
                if month:
                    return f"No encontré eventos en Google Calendar durante {month[:7]} .".replace(" .", ".")
                return "No encontré eventos próximos en Google Calendar durante los próximos días; no hay título, fecha ni hora para mostrar."
            lines = ["Eventos encontrados:"]
            for event in events[:20]:
                title = (event.get("summary") or "(sin título)") if isinstance(event, dict) else str(event)
                start = event.get("start") if isinstance(event, dict) else None
                if isinstance(start, dict):
                    start = start.get("dateTime") or start.get("date")
                lines.append(f"• {title} — {start or 'fecha no informada'}")
            return "\n".join(lines)
        if result.get("action") in {"list_files", "search"} and "files" in result:
            label = "archivos"
            if result.get("action") == "search":
                query = str(result.get("query") or "").strip()
                if query:
                    label = f"archivos que coinciden con «{query}»"
            return _filesystem_summary(result, "files", label)
        if result.get("action") in {"move_files", "copy_files", "undo"} and "count" in result:
            return f"Operación completada: {result['count']} archivos procesados."
        if isinstance(result.get("calendars"), list):
            calendars = result["calendars"]
            if not calendars:
                return "No encontré calendarios en Google Calendar."
            names = [
                str(item.get("summary") or item.get("name") or item.get("id") or item)
                if isinstance(item, dict) else str(item)
                for item in calendars
            ]
            return "Calendarios encontrados:\n" + "\n".join(f"• {name}" for name in names)
        if isinstance(result.get("events"), list):
            events = result["events"]
            if not events:
                return "No encontré eventos en el rango consultado."
            lines = ["Eventos encontrados:"]
            for event in events[:20]:
                if isinstance(event, dict):
                    title = event.get("summary") or event.get("title") or "(sin título)"
                    start = event.get("start")
                    if isinstance(start, dict):
                        start = start.get("dateTime") or start.get("date")
                    lines.append(f"• {title} — {start or 'fecha no informada'}")
                else:
                    lines.append(f"• {event}")
            return "\n".join(lines)
        if result.get("action") == "list" and result.get("domain") in {"shopping", "inventory", "recipes"}:
            domain = result.get("domain")
            items = result.get("items") if domain != "recipes" else result.get("recipes")
            items = items or []
            empty = {
                "shopping": "Tu lista de compras está vacía.",
                "inventory": "Todavía no hay ingredientes cargados en tu alacena.",
                "recipes": "Todavía no hay recetas guardadas.",
            }
            if not items:
                return empty[domain]
            names = [str(item.get("item") or item.get("name") or item) for item in items[:10]]
            title = {"shopping": "Lista de compras", "inventory": "Alacena", "recipes": "Recetas"}[domain]
            return f"{title}:\n" + "\n".join(f"• {name}" for name in names)
        value = result.get("text") or result.get("reply") or result.get("result")
        return str(value) if value is not None else "La operación se completó correctamente."
    return str(result or "")
