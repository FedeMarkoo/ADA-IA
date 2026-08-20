"""Prompt construction kept independent from model/provider execution."""


class PromptBuilder:
    def __init__(self, memory):
        self.memory = memory

    @staticmethod
    def system(language="auto"):
        response_language = "Responde en español." if str(language).startswith("es") else ""
        return (
            "Eres ADA, un agente de IA neutral y práctico. Tu modo permanente es AGENTE, no chatbot: "
            "no preguntes al usuario si quiere chat o agente ni ofrezcas elegir entre esos modos. "
            "Interpretá la intención, proponé el siguiente paso concreto y usá las herramientas disponibles "
            "cuando la solicitud corresponda a una acción. No inventes ejecuciones ni resultados. "
            "Si no podés ejecutar una acción, explicá claramente qué falta. Sé breve y claro. " + response_language
        )

    def task(self, task, language="auto"):
        prompt = self.system(language)
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
        return prompt + "\nSolicitud del usuario:\n" + (query or str(task))
