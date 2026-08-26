"""Prompt construction kept independent from model/provider execution."""

import logging

logger = logging.getLogger("ada.prompts")


class PromptBuilder:
    def __init__(self, memory, mcp_manager=None):
        self.memory = memory
        self.mcp_manager = mcp_manager
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
        template = self.memory.prompt_template("agent_system", fallback)
        prompt = template.replace("{language}", "Responde en español." if str(language).startswith("es") else "")
        # This rule is appended even when the system template comes from an
        # existing database, so upgraded installations gain the behavior too.
        prompt += (
            "\nReglas de ejecución y respuesta:"
            "\n1. Si el pedido es una consulta sobre Google Calendar, Google Drive o Gmail (por ejemplo 'cuál es mi próximo evento', 'busca en octubre'), no pidas rutas de archivos locales ni confirmaciones repetitivas si la herramienta o contexto permite consultar directamente."
            "\n2. Si el usuario confirma o pide buscar en un rango de fechas ('sí', 'busca en ese rango', 'busca en octubre'), procede de inmediato sin volver a preguntar lo mismo."
            "\n3. Si el pedido es un análisis, explicación o comparación autocontenida, respondelo completo ahora usando supuestos razonables. No pidas rutas, sistema operativo ni datos técnicos innecesarios."
            "\n4. Si no conocés un dato, tenés dudas, o la respuesta puede haber cambiado, usá web_search.search para investigar y basá la respuesta en los resultados; no inventes."
        )
        query = task.get("prompt", "")
        knowledge = self.memory.knowledge(query, limit=2)
        if knowledge:
            prompt += "\nReferencias confiables del proyecto; respetalas y no inventes reglas:\n" + "\n---\n".join(
                knowledge
            )
        procedures = self.memory.find_procedures(query)
        if procedures:
            prompt += "\nProcedimientos aprendidos relevantes:\n" + "\n".join(
                f"- {item['name']}: {item['instructions']}" for item in procedures
            )
        if self.mcp_manager:
            try:
                servers = self.mcp_manager.list_servers()
                tools = self.mcp_manager.list_tools()
                active = {s["name"] for s in servers if s.get("status") == "active"}
                available = [t for t in tools if t.get("enabled") and t.get("server") in active]
                prompt += "\nInventario vivo de herramientas MCP disponibles ahora (no inventes otras):\n"
                for tool in available:
                    prompt += (
                        f"- {tool.get('name')}: {tool.get('description', '')} "
                        f"[servidor={tool.get('server')}, riesgo={tool.get('risk_level')}, "
                        f"requiere_confirmación={bool(tool.get('requires_confirmation'))}]\n"
                    )
                prompt += "Si te preguntan qué podés hacer, basate en este inventario y distinguí herramientas activas de detenidas."
            except Exception as exc:
                # MCP discovery must never prevent a normal conversational reply.
                logger.debug("mcp_discovery_failed: %s", exc)
        conversation = str(task.get("conversation_context") or "").strip()
        if conversation:
            prompt += (
                "\nContexto reciente de esta conversación. Usalo para resolver referencias como "
                "‘eso’, ‘ahí’, ‘lo que tiene’ o nombres mencionados antes; no inventes datos:\n" + conversation[-3500:]
            )
        return prompt + "\nSolicitud del usuario:\n" + (query or str(task))
