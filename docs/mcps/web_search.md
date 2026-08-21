# MCP Web Search

El servidor MCP **`mcps/web_search/`** proporciona búsqueda en la web en vivo sin requerir claves de API pagas, utilizando DuckDuckGo con fallback a scrape seguro.

---

## 🛠️ Herramientas Expuestas

### `web_search.search`
- **Descripción**: Realiza búsquedas en la web y devuelve títulos, fragmentos de texto (snippets) y URLs relevantes.
- **Riesgo**: `safe`.
- **Parámetros**:
  - `query` (string, requerido): Término o pregunta a buscar en internet.
  - `limit` (integer, opcional): Número máximo de resultados (por defecto: 5).
