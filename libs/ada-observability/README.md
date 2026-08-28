# ADA Observability

Librería pequeña para producir una línea JSON por operación de ADA. Está
orientada a REST y eventos de aplicación, con trazabilidad, redacción de
secretos, llamadas externas y métricas Micrometer.

## Uso en ADA

Agregar el artefacto publicado. La trazabilidad HTTP usa los headers propios
de ADA `x-ada-correlationid`, `x-ada-caller` y `x-ada-ini-caller`:

```xml
<dependency>
  <groupId>com.ada</groupId>
  <artifactId>ada-observability</artifactId>
  <version>0.1.0-SNAPSHOT</version>
</dependency>
```

La auto-configuración registra `AdaObservabilityFilter` y la métrica
`ada.operation.duration`. Configuración mínima:

```yaml
ada:
  observability:
    application-name: ada
    hidden-fields: [authorization, token, password, apiKey, client_secret, prompt]
    ignored-paths: [/actuator/health, /actuator/metrics]
```

Para un evento del pipeline:

```java
try (var operation = observability.start("chat.use-case", "EVENT")) {
  operation.event("stage", "model_invoke").request(metadata).response(result);
}
```

Los objetos de negocio no dependen de Spring. Los adapters Spring son
opcionales y no se activa ningún logging de payload si la aplicación no los
usa. La primera versión no incluye SOAP ni WebFlux; la propagación asincrónica
debe hacerse explícitamente al ejecutar una tarea fuera del thread actual.
