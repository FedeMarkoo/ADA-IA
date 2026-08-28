# ADR-003: librería compartida de observabilidad

## Decisión

ADA consume `com.ada:ada-observability` para emitir una operación estructurada
por ejecución del chat. El caso de uso registra metadatos técnicos mínimos y
el resultado (`success`/`failure`) sin persistir prompts ni respuestas del
modelo en el log automático.

La librería se desarrolla en el repo hermano `ada-observability` y se resuelve
localmente durante esta etapa mediante `mvn install`; al publicarse en un
registry interno se reemplazará únicamente la fuente de resolución.

## Integración local

Desde el checkout de ADA:

```bash
mvn -f ../ada-observability/pom.xml install
mvn verify
```

La configuración queda bajo `ada.observability` y usa los headers propios
`x-ada-correlationid`, `x-ada-caller` y `x-ada-ini-caller`.
