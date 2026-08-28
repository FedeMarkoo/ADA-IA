# Reglas de código

## Kotlin

- Kotlin oficial con formato ktlint y compilación estricta de nullability.
- Un único tipo top-level por archivo: una clase, interfaz, enum o `object` por
  archivo, con el mismo nombre que el archivo. Esto facilita navegación,
  ownership, revisión y cambios atómicos.
- Los DTOs viven en el package de su frontera: REST en
  `infrastructure.in.rest.dto`, application en `application.dto` y proveedores
  externos en `infrastructure.out.<provider>.dto`. Nunca se declaran DTOs junto
  a controllers, casos de uso, puertos o entidades. Los DTOs solo transportan
  datos y no contienen reglas de negocio.
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
- Los nombres de archivo, package e imports deben reflejar la responsabilidad
  real; no usar archivos comodín como `Models.kt`, `Dtos.kt` o `Common.kt`.
- Un provider de prompt, LLM, persistencia o servicio externo es un adapter de
  salida y vive bajo `infrastructure.out`; un controller, mapper o DTO HTTP es
  un adapter de entrada bajo `infrastructure.in`.

## Spring

- `@Component` solo para adaptadores, estrategias, filtros y casos de uso que
  necesiten wiring; preferir constructores explícitos.
- Configurar beans y clientes en clases `@Configuration`.
- Controllers delgados: protocolo HTTP hacia un puerto de entrada.
- Transacciones en el borde de aplicación/persistencia, nunca en entidades de
  dominio.

## Pruebas

- Unitarias para dominio, filtros y estrategias.
- Tests de integración para adaptadores SQLite, LiteLLM y HTTP.
- Tests de contrato para puertos externos.
- Cada bug corregido incorpora un test que lo reproduce.
- No depender de red, reloj real o base de datos compartida en unit tests.
