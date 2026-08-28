# Arquitectura

## Decisión base

ADA usa arquitectura hexagonal (ports and adapters) con organización por
contexto funcional. Hexagonal define la dirección de dependencias; los
paquetes por contexto evitan que el proyecto se convierta en un único paquete
`service` o `util`.

```text
infrastructure/in  ->  application  ->  domain
infrastructure/out ->  application  ->  domain
                    ^
                    |
          puertos definidos por application
```

Spring Boot queda en el borde: configuración, inyección, HTTP, persistencia,
clientes y métricas. El dominio debe poder probarse sin levantar Spring.

## Estructura inicial

```text
src/main/kotlin/com/ada/
├── shared/
│   ├── domain/          tipos y errores transversales mínimos
│   └── application/     clock, ids, resultado y políticas comunes
├── conversation/
│   ├── domain/
│   ├── application/
│   │   ├── dto/         contratos internos de casos de uso
│   │   ├── port/in/     casos de uso públicos
│   │   └── port/out/    dependencias requeridas
│   └── infrastructure/
│       ├── in/rest/     controllers, dto/ y mapper/
│       └── out/         LiteLLM, SQLite, auditoría
├── memory/
├── capability/
├── model/
└── observability/
```

Los nombres concretos pueden variar por contexto, pero no se mezclan entradas,
casos de uso, dominio y salidas en la misma clase.

## Separación de modelos

```text
infrastructure.in.rest.dto  -> JSON HTTP; no sale del adapter REST
infrastructure.in.rest.mapper -> mapeos HTTP <-> application
application.dto              -> entrada/salida de casos de uso
application.mapper           -> mapeos internos de application, si fueran necesarios
shared.infrastructure.dto    -> configuración transversal transportada como DTO
domain.entity                -> identidad, persistencia y ciclo de vida
domain.bo                    -> reglas de negocio e invariantes
infrastructure.out.*.dto     -> formato específico de un proveedor externo
infrastructure.out.*.mapper  -> mapeos application <-> proveedor externo
```

Un controller transforma explícitamente su DTO REST a un DTO de application.
Un adapter externo transforma entre el contrato de application y su DTO de
infraestructura. Entidades y BO nunca se exponen directamente por HTTP.

`DefaultSystemPromptProvider` es un adapter de salida: implementa un puerto de
application y vive en `conversation.infrastructure.out.prompt`. No es una
entrada REST ni debe ubicarse junto a controllers o DTOs HTTP.

## Strategy y Filter

Las variantes dinámicas se registran como componentes y se inyectan como
colecciones de interfaces:

```kotlin
interface ModelSelectionStrategy {
    fun supports(request: ModelSelectionRequest): Boolean
    fun select(request: ModelSelectionRequest): ModelSelection
}

interface RequestFilter {
    fun supports(request: ChatRequest): Boolean
    fun apply(request: ChatRequest): ChatRequest
}

class SelectModelUseCase(
    private val strategies: List<ModelSelectionStrategy>,
    private val filters: List<RequestFilter>,
)
```

Reglas:

- cada implementación declara explícitamente cuándo aplica;
- el orden se controla con `@Order` o una prioridad documentada;
- si ninguna estrategia aplica, el caso de uso falla con un error tipado;
- el agregador no conoce las clases concretas;
- no se resuelve comportamiento leyendo nombres de beans o con reflexión propia;
- filtros puros se ejecutan en una cadena determinista y observable.

## Flujo de una solicitud

1. Un adaptador de entrada valida formato y autenticación.
2. Un caso de uso crea el contexto de correlación y aplica filtros.
3. Una estrategia selecciona proveedor/modelo según política, capacidad,
   costo, latencia y disponibilidad.
4. Un puerto de salida invoca LiteLLM.
5. El caso de uso persiste resultado y auditoría mediante puertos.
6. Métricas, logs y errores se emiten sin filtrar secretos.

Las acciones potencialmente destructivas o externas requieren confirmación
explícita y deben poder producir un manifiesto de reversión cuando sea viable.
