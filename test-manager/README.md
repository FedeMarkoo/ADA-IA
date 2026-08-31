# ADA Test Manager

Gestor local de casos de prueba para ADA. Permite organizar prompts por categoría,
ejecutarlos, reejecutarlos y revisar respuesta, tokens, contexto, memorias y tools.

Variables: `ADA_URL` (por defecto `http://ada:8080`), `PORT` (8088),
`DB_PATH` (`/data/test-manager.sqlite`), `ADA_TIMEOUT_SECONDS` (900) y
`ADA_POLL_SECONDS` (2). Cada ejecución usa una conversación aislada. La imagen
no incluye una SQLite de prueba: la base se crea en `DB_PATH` y Compose la
persiste mediante `ADA_TEST_MANAGER_DATA_DIR`. Para cargar categorías y
prompts, usá `POST /api/categories` y `POST /api/prompts`; los ejemplos
completos están en `docs/test-manager.md`.
