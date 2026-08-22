"""Prompt construction kept independent from model/provider execution."""


class PromptBuilder:
    def __init__(self, memory, mcp_manager=None):
        self.memory = memory
        self.mcp_manager = mcp_manager

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
            "\nRegla de respuesta: si el pedido es un análisis, explicación o comparación autocontenida, "
            "respondelo completo ahora usando supuestos razonables. No pidas rutas, sistema operativo, "
            "versión de Python ni otros datos técnicos que no sean indispensables. Si el usuario pide una "
            "cantidad de enfoques, cubrilos y terminá con una recomendación concreta."
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
            except Exception:
                # MCP discovery must never prevent a normal conversational reply.
                pass
        conversation = str(task.get("conversation_context") or "").strip()
        if conversation:
            prompt += (
                "\nContexto reciente de esta conversación. Usalo para resolver referencias como "
                "‘eso’, ‘ahí’, ‘lo que tiene’ o nombres mencionados antes; no inventes datos:\n"
                + conversation[-3500:]
            )
        return prompt + "\nSolicitud del usuario:\n" + (query or str(task))
