# ADR-003: librería compartida de observabilidad

## Decisión

ADA consume `com.ada:ada-observability` para emitir una operación estructurada
por ejecución del chat. El caso de uso registra metadatos técnicos mínimos y
el resultado (`success`/`failure`) sin persistir prompts ni respuestas del
modelo en el log automático.

La librería se desarrolla en el repo hermano `ada-observability` y se integra en
ADA como una dependencia Maven vendorizada en `libs/ada-observability`. El
código se mantiene como subtree para que un clone limpio y la imagen Docker de
Git sean autosuficientes.
Si luego se publica en un registry interno, podrá reemplazarse el módulo por la
dependencia remota.

## Integración local

Desde el checkout de ADA:

```bash
mvn -DskipTests -f libs/ada-observability/pom.xml install
mvn verify
```

La configuración queda bajo `ada.observability` y usa los headers propios
`x-ada-correlationid`, `x-ada-caller` y `x-ada-ini-caller`.
