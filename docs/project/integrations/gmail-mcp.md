# Gmail mediante MCP

ADA tiene una sola superficie canónica para Gmail: las capabilities
`gmail_read`, `gmail_draft` y `gmail_send`. `gmail_read` y `gmail_draft` pueden
usar la API directa o el servidor MCP remoto oficial de Google según
`gmail_backend`; no existe una segunda capability `gmail` que compita con ellas
en el router.

Google documenta el endpoint
[`https://gmailmcp.googleapis.com/mcp/v1`](https://developers.google.com/workspace/gmail/api/reference/mcp)
como Developer Preview. Su toolset permite buscar/leer hilos y crear borradores,
pero no enviar correo. Por eso `gmail_send` siempre usa la API directa y sigue
requiriendo confirmación explícita; crear un borrador no envía nada y no requiere
ese gate.

## Configuración

1. Crear o seleccionar un proyecto de Google Cloud.
2. Habilitar Gmail API y Gmail MCP API.
3. Configurar el consentimiento OAuth con los scopes `gmail.readonly` y
   `gmail.compose`; agregar `gmail.send` si ADA enviará correo.
4. Ejecutar `ada auth-gmail` para guardar la credencial OAuth con refresh token
   en el credential store cifrado o en el archivo local con permisos `0600`.
5. Elegir `"gmail_backend": "mcp"` y configurar el servidor:

```json
{
  "gmail_backend": "mcp",
  "gmail_mcp_server": "gmail",
  "gmail_mcp_allowed_hosts": ["gmailmcp.googleapis.com"],
  "mcp_servers": {
    "gmail": {
      "type": "http",
      "url": "https://gmailmcp.googleapis.com/mcp/v1"
    }
  }
}
```

La URL vive únicamente en configuración. Antes de cada llamada, ADA carga la
credencial existente, renueva el access token cuando expiró y persiste el token
actualizado. El header `Authorization` se construye en memoria; no se guarda un
access token en `config.json`, `.vscode/mcp.json` ni variables de entorno.

Si `gmail_credential_name` está configurado, `ADA_CREDENTIAL_KEY` es obligatorio
y ADA falla antes de iniciar OAuth si no puede cifrar la credencial. Para usar
el archivo local en su lugar, hay que omitir `gmail_credential_name`.

Para evitar enviar credenciales a un host inesperado, el endpoint debe usar
HTTPS y su hostname debe aparecer en `gmail_mcp_allowed_hosts`.

## Comportamiento canónico

- `gmail_read` + backend `mcp` llama `search_threads`.
- `gmail_draft` + backend `mcp` llama `create_draft` sin confirmación.
- `gmail_send` usa Gmail API y exige confirmación antes del envío.
- Con `"gmail_backend": "api"`, lectura y borradores también usan Gmail API.

El MCP oficial también expone tools de etiquetas. ADA no las publica como una
capability paralela; pueden incorporarse en el futuro ampliando las capabilities
canónicas con permisos y política explícitos.

## Seguridad

El contenido de un correo es entrada no confiable y puede contener prompt
injection indirecta. No debe convertirse por sí solo en instrucciones para
invocar tools. Las acciones de envío permanecen detrás de revisión y
confirmación humana.
