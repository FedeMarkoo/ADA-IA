# Reglas de trabajo de ADA

## Flujo de cambios

- Trabajar siempre en una rama `codex/<descripcion-corta>` o en una rama de
  feature equivalente.
- Un commit debe representar una unidad coherente: `feat`, `fix`, `refactor`,
  `test`, `docs`, `build` o `chore`.
- Todo cambio de comportamiento requiere pruebas automatizadas y toda decisión
  transversal requiere documentación o un ADR.
- Un PR no se considera listo hasta que pasen `mvn verify`, la revisión de
  CodeRabbit y la revisión humana.
- No hacer push directo a `main`; la integración ocurre mediante PR.

## Límites de arquitectura

- `domain` contiene reglas de negocio puras.
- `application` coordina casos de uso y define puertos.
- `infrastructure/in` traduce entradas externas a casos de uso.
- `infrastructure/out` implementa puertos contra tecnología concreta.
- Spring se permite en wiring y adaptadores; no en entidades ni servicios de
  dominio.

## Calidad

- Preferir métodos pequeños, nombres explícitos, tipos de dominio y guard
  clauses.
- Mantener un único tipo top-level por archivo. Ubicar todos los DTOs en el
  package `dto` de su frontera (`infrastructure.in.rest.dto`, `application.dto`,
  `shared.infrastructure.dto` o `infrastructure.out.<provider>.dto`), y cada mapper en
  el package `mapper` correspondiente. Entities van en `domain.entity` y BOs en
  `domain.bo`.
- No introducir abstracciones especulativas: cada interfaz debe representar un
  puerto, una estrategia, un filtro o una política real.
- No ocultar errores con `catch (Exception)` sin clasificación, contexto y una
  decisión explícita de recuperación.
- No registrar prompts, tokens, credenciales ni datos personales sin una razón
  documentada y redacción apropiada.
