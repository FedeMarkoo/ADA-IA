# Contrato de arquitectura y desarrollo

Este documento define las condiciones mínimas que debe cumplir cualquier
cambio de ADA. Es normativo: si una decisión nueva contradice este contrato,
debe documentarse primero en un ADR.

## 1. Plataforma base

- Java 21.
- Spring Boot y Maven.
- MapStruct para mapeos entre fronteras.
- SQLite en una carpeta externa configurada por `ADA_DATA_DIR`.
- LiteLLM como gateway HTTP para poder cambiar de proveedor o modelo sin
  acoplar el dominio.
- Micrometer, Actuator y Prometheus para métricas.

## 2. Arquitectura hexagonal

La dirección de dependencias siempre apunta hacia el centro:

```text
adapter de entrada -> application -> domain
adapter de salida  -> application -> domain
                         ^
                         |
                 puertos de application
```

### Capas

`domain` contiene entidades, BOs, invariantes y errores de negocio. No conoce
Spring, HTTP, JDBC, LiteLLM, MapStruct ni Micrometer.

`application` contiene casos de uso, políticas, DTOs internos y puertos. Los
casos de uso coordinan el flujo; no conocen implementaciones concretas.

`infrastructure.in` contiene controllers, filtros y DTOs HTTP.

`infrastructure.out` contiene persistencia, clientes externos, proveedores de
prompt, estado y DTOs específicos de cada integración.

`shared` solo contiene capacidades transversales realmente independientes del
contexto. No debe depender de `conversation`, `model` ni otro bounded context.

### Paquetes obligatorios

```text
com.ada.<context>.domain.entity
com.ada.<context>.domain.bo
com.ada.<context>.application.dto
com.ada.<context>.application.port.in
com.ada.<context>.application.port.out
com.ada.<context>.infrastructure.in.rest.dto
com.ada.<context>.infrastructure.in.rest.mapper
com.ada.<context>.infrastructure.out.<provider>.dto
com.ada.<context>.infrastructure.out.<provider>.mapper
```

Reglas:

- Una clase pública por archivo.
- El archivo debe tener el mismo nombre que la clase pública.
- Todos los DTOs viven en un package `dto` de su frontera.
- Los mappers viven en un package `mapper` y usan MapStruct.
- No se exponen entidades ni BOs directamente por HTTP.
- Los puertos de salida se declaran en `application.port.out`.
- Los adapters dependen de puertos; nunca al revés.
- No se resuelven implementaciones por nombres de beans ni reflexión propia.

## 3. Flujo de un mensaje

El flujo debe conservar estas transiciones y reflejarlas en
`MessageExecutionState`:

```text
recibir mensaje
  -> filtrar si es comando
  -> seleccionar modelo
  -> crear contexto
  -> invocar modelo
  -> si requiere tool: invocar tool -> invocar modelo
  -> repetir hasta respuesta final o máximo configurado
  -> responder al usuario
```

La API debe entregar el `messageId` al iniciar el procesamiento y responder
`202 Accepted` cuando el procesamiento sea asíncrono. El estado se consulta con
`GET /api/v1/chat/{messageId}/status`.

Los estados deben informar el detalle relevante, por ejemplo `modelName` en
`invoking_model` y `toolName` en `invoking_tool`. Los errores deben conservar
el estado `failed` y exponerse mediante un `@RestControllerAdvice` sin filtrar
detalles internos ni secretos.

El loop de tools tiene un máximo explícito. Nunca se permite un loop infinito.
Cada `TOOL` conserva su `toolCallId` y lo serializa como `tool_call_id`.

## 4. Strategy y Filter

Las variantes reemplazables se registran como componentes Spring y se reciben
como listas de interfaces:

```java
List<RequestFilter> filters;
List<ModelSelectionStrategy> strategies;
List<ContextItem> contextItems;
List<ToolExecutor> toolExecutors;
```

Cada implementación debe declarar `supports(...)`, tener una única intención y
respetar `@Order` o una prioridad documentada. El agregador solo conoce la
interfaz y aplica la cadena de forma determinista.

No se agrega Strategy o Filter solo para ocultar un `if` simple. Se usa cuando
existe una variante reemplazable, una política o una cadena real de reglas.

## 5. Contexto enviado al modelo

El contexto se construye en `conversation.context` mediante `List<ContextItem>`.
Cada item recibe el estado acumulado y devuelve el estado siguiente:

```text
system -> prompt -> tools -> memories -> tool_response
       -> compacted_prompt -> response
```

Cada componente tiene una clase propia y solo agrega o transforma su parte.
`system` siempre sale de SQLite mediante un puerto de application; no se
permite un prompt default hardcodeado.

`CompactedPromptContextItem` puede eliminar mensajes anteriores y reemplazarlos
por un resumen cuando se supera el límite de tokens. Debe preservar las reglas
del sistema y medir su propia duración e invocaciones con AOP y `Timer`.

## 6. LiteLLM y contratos externos

El dominio usa DTOs de application. El adapter LiteLLM usa DTOs wire separados
y un mapper dedicado.

El payload de tools debe respetar el contrato OpenAI-compatible:

```json
{
  "type": "function",
  "function": {
    "name": "...",
    "description": "...",
    "parameters": {}
  }
}
```

Las respuestas pueden tener `content: null` cuando contienen tool calls. Los
DTOs de request y response no deben confundirse si sus contratos divergen.
Nunca se registran API keys, prompts completos, headers de autenticación ni
datos personales en logs.

## 7. Métricas y observabilidad

La instrumentación debe permitir decidir qué modelo, filtro, estrategia o tool
conviene mantener. Se usan Micrometer y métricas de cardinalidad controlada.

Métricas mínimas:

- requests por contexto, caso de uso y resultado;
- duración de requests y llamadas externas;
- invocaciones y duración por `ContextItem`;
- modelo solicitado y efectivo;
- tokens de entrada y salida por `LlmRequest`;
- tokens estimados por componente (`system`, `prompt`, `tools`, etc.);
- costo estimado, reintentos, timeouts y fallbacks;
- estrategia elegida y filtros aplicados;
- operaciones de persistencia y auditoría.

Los tokens se calculan en un componente de observabilidad, nunca dentro de un
DTO. El cálculo puede devolver un componente `total` para análisis, pero el
contador por componente no debe emitirlo nuevamente ni producir doble conteo.
La información del proveedor ausente se representa como `unknown`.

No se usan como labels prompts, texto libre, IDs de usuario, argumentos de
tools ni excepciones completas. Esos datos, si son necesarios, van a logs
redactados o auditoría controlada.

## 8. Persistencia y estado

- `ADA_DATA_DIR` queda fuera del workspace y contiene `db`, `logs`, `backups`,
  `exports`, `models` y `runtime`.
- SQLite debe crear `db/ada.sqlite` antes de abrir la conexión.
- Las migraciones deben ser versionadas y las operaciones importantes deben
  poder auditarse.
- El tracker en memoria debe tener límite máximo y TTL; para producción se debe
  evaluar persistencia o una cache compartida.

## 9. Clean Code con sentido

- Métodos pequeños, con una única responsabilidad y nombres explícitos.
- Separar decisión, efecto externo y conversión de datos.
- Preferir inmutabilidad y DTOs data-only (`record`).
- No crear servicios gigantes que deleguen todo.
- No abstraer por anticipado ni aplicar patrones por obligación.
- Comentarios solo para decisiones, invariantes y riesgos.
- Errores esperables deben tener contratos tipados; no usar `catch` genérico
  para ocultar fallos.
- No mezclar lógica de infraestructura dentro del dominio.
- Cada bug corregido debe incluir una prueba que lo reproduzca.

## 10. Seguridad y privacidad

El workflow `Security` debe bloquear:

- secretos, API keys, tokens y private keys;
- archivos `.env`, certificados, keystores y credenciales;
- SQLite, backups, logs y modelos locales;
- rutas absolutas del equipo del desarrollador;
- dependencias nuevas con vulnerabilidades altas, cuando Dependency Graph esté
  habilitado.

Las excepciones de secret scanning requieren fingerprint exacto y justificación.
Un secreto real debe revocarse, aunque se elimine del commit.

## 11. Tests y CI

Todo cambio debe pasar:

1. `validate` de Maven.
2. Tests unitarios y de integración aplicables.
3. Formato Spotless/Google Java Format.
4. Compilación.
5. Coverage JaCoCo.
6. Empaquetado.
7. CodeQL.
8. Security policy y secret scan.
9. CodeRabbit sobre el diff actual.

Las etapas independientes se ejecutan en paralelo; las etapas que dependen de
otra usan `needs`. El PR no se mergea con checks obligatorios fallidos ni con
comentarios accionables sin resolver.

## 12. Checklist para cada PR

- [ ] La dependencia de capas apunta hacia el dominio.
- [ ] Los DTOs y mappers están en packages correctos.
- [ ] Hay una clase pública por archivo.
- [ ] Las variantes usan listas de interfaces cuando corresponde.
- [ ] El flujo actualiza el estado del mensaje.
- [ ] El contexto es componible y el compactador puede reemplazar mensajes.
- [ ] Las llamadas y tokens tienen métricas sin doble conteo.
- [ ] No hay secretos, rutas privadas ni artefactos locales.
- [ ] Hay tests para contratos externos y regresiones.
- [ ] Spotless, Maven, seguridad, CodeQL y CodeRabbit están verdes.
