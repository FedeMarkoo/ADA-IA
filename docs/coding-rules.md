# Reglas de código

## Java

- Java 21 como lenguaje principal, compilado con Maven.
- Spotless ejecuta Google Java Format; el formato se valida con `mvn verify`.
- Un único tipo top-level por archivo: una clase, interfaz, enum o `object` por
  archivo, con el mismo nombre que el archivo. Esto facilita navegación,
  ownership, revisión y cambios atómicos.
- Todos los DTOs viven en el package `dto` de su frontera: REST en
  `infrastructure.in.rest.dto`, application en `application.dto`, configuración
  transversal en `shared.infrastructure.dto` y proveedores externos en
  `infrastructure.out.<provider>.dto`. Nunca se declaran DTOs junto a
  controllers, casos de uso, puertos, mappers o entidades. Los DTOs solo
  transportan datos y no contienen reglas de negocio.
- Las entidades viven en `domain.entity` y los objetos de negocio (BO) en
  `domain.bo`; ninguno se expone directamente por HTTP.
- Inmutabilidad por defecto: `val`, colecciones de solo lectura y `data class`
  para datos; mutabilidad encapsulada cuando sea necesaria.
- `Result` o errores de dominio tipados para flujos esperables; excepciones para
  fallos técnicos o violaciones de invariantes.
- No usar `!!`, `Any`, `Map<String, Any>` ni strings mágicos en contratos de
  aplicación salvo en un adaptador y con conversión inmediata a tipos propios.
- Coroutines solo donde aporten concurrencia real; no mezclar bloqueante y
  suspendido sin documentar el límite.

## Clean Code con sentido

- Métodos pequeños, con una sola intención y nombres que expliquen el porqué.
- Separar decisión, efecto externo y mapeo de datos.
- Evitar clases anémicas cuando existe una regla de negocio; evitar servicios
  gigantes que solo delegan todo.
- La duplicación se elimina cuando el conocimiento es el mismo, no cuando solo
  se parecen dos líneas.
- Comentarios para decisiones, invariantes o riesgos; no para repetir el código.
- No introducir patrones por obligación: Strategy y Filter se usan cuando hay
  variantes reemplazables o una cadena de reglas real.
- Las partes del contexto enviado al modelo son componentes independientes bajo
  `conversation.context`. Se agregan mediante `List<ContextItem>` y orden
  explícito; no se centralizan variantes en un `if/when` creciente.
- Los nombres de archivo, package e imports deben reflejar la responsabilidad
  real; no usar archivos comodín como `Models.kt`, `Dtos.kt` o `Common.kt`.
- Un provider de prompt, LLM, persistencia o servicio externo es un adapter de
  salida y vive bajo `infrastructure.out`; un controller, mapper o DTO HTTP es
  un adapter de entrada bajo `infrastructure.in`.
- Los mapeos entre DTOs de frontera se hacen con MapStruct en un mapper dedicado.
  Los mappers viven en el package `mapper` de la frontera correspondiente:
  `infrastructure.in.rest.mapper` o `infrastructure.out.<provider>.mapper`.
  Los clientes externos solo invocan el mapper; no construyen DTOs wire.
  No construir DTOs externos con `copy`, constructores manuales dentro del
  controller ni reflexión. El dominio y los casos de uso no dependen de
  MapStruct.
- Las métricas transversales de componentes se implementan con AOP cuando la
  medición es uniforme. Los componentes de contexto deben declarar su nombre
  con `@MeasuredContextItem`; no agregan llamadas manuales a métricas.

## Spring

- `@Component` solo para adaptadores, estrategias, filtros y casos de uso que
  necesiten wiring; preferir constructores explícitos.
- Configurar beans y clientes en clases `@Configuration`.
- Controllers delgados: protocolo HTTP hacia un puerto de entrada.
- El flujo conversacional debe expresar sus transiciones mediante estados de
  mensaje; no ocultar el loop modelo-tool en el adapter HTTP.
- Transacciones en el borde de aplicación/persistencia, nunca en entidades de
  dominio.

## Pruebas

- Unitarias para dominio, filtros y estrategias.
- Tests de integración para adaptadores SQLite, LiteLLM y HTTP.
- Tests de contrato para puertos externos.
- Cada bug corregido incorpora un test que lo reproduce.
- No depender de red, reloj real o base de datos compartida en unit tests.

## CI gratuito

- El workflow `CI` está organizado por dependencias: `validate` habilita
  `test` y `quality` en paralelo; `package` espera ambas etapas y `coverage`
  corre en paralelo después de los tests.
- `mvn verify` sigue siendo el check funcional local principal. El job de
  cobertura ejecuta `mvn test jacoco:report` y publica `target/site/jacoco`.
- Spotless valida formato y el compilador de Maven bloquea errores de código.
- CodeQL analiza seguridad de Java y publica los resultados en GitHub
  Code Scanning.
- El workflow `Security` bloquea secretos con Gitleaks, archivos privados y
  rutas locales con una política versionada, y vulnerabilidades altas nuevas
  con Dependency Review cuando `DEPENDENCY_GRAPH_ENABLED=true` está configurado
  en el repositorio. Un secreto detectado debe revocarse, no solamente borrarse
  del commit. Las excepciones de Gitleaks requieren fingerprint exacto y
  justificación.
- CodeRabbit complementa estas herramientas con revisión contextual del diff;
  no reemplaza los checks deterministas del CI.
