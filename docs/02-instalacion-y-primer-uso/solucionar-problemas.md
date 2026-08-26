# 2.6 Solución de problemas

Revisar primero `/api/health`, el estado de Ollama, los logs y `allowed_roots`. Si LiteLLM no está instalado, usar `pip install -e '.[litellm]'` o cambiar temporalmente `ollama_backend` a `urllib`.
