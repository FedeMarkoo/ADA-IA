"""Prompt construction kept independent from model/provider execution."""

import logging

from ada.infrastructure.prometheus_metrics import estimate_token_count

logger = logging.getLogger("ada.prompts")


class PromptWithUsage(str):
    """String prompt carrying a breakdown for observability."""

    def __new__(cls, value, token_usage=None):
        instance = super().__new__(cls, value)
        instance.token_usage = dict(token_usage or {})
        return instance


class PromptBuilder:
    def __init__(self, memory, mcp_manager=None, configuration_store=None, tool_store=None):
        self.memory = memory
        self.mcp_manager = mcp_manager
        self.configuration_store = configuration_store
        self.tool_store = tool_store
        self._proc_cache = (0.0, {})

    @staticmethod
    def system(language="auto"):
        response_language = "Responde en español." if str(language).startswith("es") else ""
        return (
            "Eres ADA, un agente de IA neutral y práctico. Tu modo permanente es AGENTE, no chatbot: "
            "no preguntes al usuario si quiere chat o agente ni ofrezcas elegir entre esos modos. "
            "Interpretá la intención, proponé el siguiente paso concreto y usá las herramientas disponibles "
            "cuando la solicitud corresponda a una acción. No inventes ejecuciones ni resultados. "
            "Si no podés ejecutar una acción, explicá claramente qué falta. En consultas conceptuales "
            "autocontenidas, respondé directamente y usá supuestos razonables: no pidas rutas, sistema "
            "operativo ni detalles técnicos que no sean indispensables. Respetá la cantidad de alternativas "
            "pedida y cerrá con una recomendación concreta. Sé breve y claro. " + response_language
        )

    def task(self, task, language="auto"):
        fallback = self.system(language)
        if self.configuration_store:
            self.configuration_store.ensure_system_prompt(fallback, priority=100)
            fallback = self.configuration_store.system_prompt(fallback)
        # The agent identity and response policy belong to configurations.db,
        # never to the MCP/tool store.
        template = fallback
        prompt = template.replace("{language}", "Responde en español." if str(language).startswith("es") else "")
        # This rule is appended even when the system template comes from an
        # existing database, so upgraded installations gain the behavior too.
        prompt += (
            "\nReglas de ejecución y respuesta:"
            "\n1. Si el pedido es una consulta sobre Google Calendar, Google Drive o Gmail (por ejemplo 'cuál es mi próximo evento', 'busca en octubre'), no pidas rutas de archivos locales ni confirmaciones repetitivas si la herramienta o contexto permite consultar directamente."
            "\n2. Si el usuario confirma o pide buscar en un rango de fechas ('sí', 'busca en ese rango', 'busca en octubre'), procede de inmediato sin volver a preguntar lo mismo."
            "\n3. Si el pedido es un análisis, explicación o comparación autocontenida, respondelo completo ahora usando supuestos razonables. No pidas rutas, sistema operativo ni datos técnicos innecesarios."
            "\n4. Si no conocés un dato, tenés dudas, o la respuesta puede haber cambiado, usá web_search.search para investigar y basá la respuesta en los resultados; no inventes."
            '\n5. Si necesitás un recuerdo persistente que no está en el contexto, podés pedir una única búsqueda devolviendo SOLO {"tool_call":{"name":"memory.search","arguments":{"query":"...","limit":3}}}. No inventes ids ni uses otra herramienta en este mecanismo.'
        )
        query = task.get("prompt", "")
        system_tokens = estimate_token_count(prompt)
        memory_tokens = 0
        selected_records = self.memory.memory_records_by_ids(task.get("memory_ids"), limit=3)
        knowledge = [item["content"] for item in selected_records]
        procedures = [] if selected_records else self.memory.find_procedures(query)
        if not selected_records:
            knowledge = self.memory.knowledge(query, limit=2)
        if knowledge:
            memory_text = "\nReferencias confiables del proyecto; respetalas y no inventes reglas:\n" + "\n---\n".join(
                knowledge
            )
            prompt += memory_text
            memory_tokens += estimate_token_count(memory_text)
        if procedures:
            memory_text = "\nProcedimientos aprendidos relevantes:\n" + "\n".join(
                f"- {item['name']}: {item['instructions']}" for item in procedures
            )
            prompt += memory_text
            memory_tokens += estimate_token_count(memory_text)
        tools_tokens = 0
        if self.mcp_manager:
            try:
                servers = self.mcp_manager.list_servers()
                tools = self.mcp_manager.list_tools()
                active = {s["name"] for s in servers if s.get("status") == "active"}
                available = [t for t in tools if t.get("enabled") and t.get("server") in active]
                tools_text = "\nInventario vivo de herramientas MCP disponibles ahora (no inventes otras):\n"
                for tool in available:
                    tools_text += (
                        f"- {tool.get('name')}: {tool.get('description', '')} "
                        f"[servidor={tool.get('server')}, riesgo={tool.get('risk_level')}, "
                        f"requiere_confirmación={bool(tool.get('requires_confirmation'))}]\n"
                    )
                tools_text += "Si te preguntan qué podés hacer, basate en este inventario y distinguí herramientas activas de detenidas."
                prompt += tools_text
                tools_tokens = estimate_token_count(tools_text)
            except Exception as exc:
                # MCP discovery must never prevent a normal conversational reply.
                logger.debug("mcp_discovery_failed: %s", exc)
        conversation = str(task.get("conversation_context") or "").strip()
        if conversation:
            memory_text = (
                "\nContexto reciente de esta conversación. Usalo para resolver referencias como "
                "‘eso’, ‘ahí’, ‘lo que tiene’ o nombres mencionados antes; no inventes datos:\n" + conversation[-3500:]
            )
            prompt += memory_text
            memory_tokens += estimate_token_count(memory_text)
        request_text = "\nSolicitud del usuario:\n" + (query or str(task))
        prompt += request_text
        return PromptWithUsage(
            prompt,
            {
                "system": system_tokens,
                "memory": memory_tokens,
                "tools": tools_tokens,
                "prompt": estimate_token_count(request_text),
            },
        )
