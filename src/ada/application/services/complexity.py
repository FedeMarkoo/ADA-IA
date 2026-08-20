"""Deterministic task complexity estimation."""


class ComplexityEstimator:
    @staticmethod
    def estimate(text):
        value = str(text or "").lower()
        if any(
            word in value
            for word in ("analizá", "analiza", "analizar", "diseñá", "diseña", "investiga", "complejo", "script nuevo")
        ):
            return 8
        if any(word in value for word in ("adaptá", "adapta", "modifica", "explica", "compará", "compara")):
            return 5
        if any(word in value for word in ("ejecuta", "corré", "corre", "lista", "mostrame", "reporte")):
            return 2
        return 3
