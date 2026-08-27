# Métricas de tokens por componente

## Objetivo

Permitir ver cuánto contexto consume cada llamada al modelo y detectar qué parte está presionando el límite: instrucciones del sistema, memoria recuperada, inventario de tools, pedido del usuario o respuesta generada.

## Estado

Implementada en el commit de esta mejora.

## Checklist

- [x] Gauge Prometheus único con desglose por componente.
- [x] Conteo de `system`, `memory`, `tools` y `prompt` al construir el prompt de ADA.
- [x] Conteo de `response` al finalizar la llamada al proveedor.
- [x] Gauge `total` como suma del contexto de entrada y la respuesta.
- [x] Cobertura de tests para el desglose y el total.
- [x] Documentación de nombres, semántica y limitaciones.

## Métrica

La métrica es `ada_llm_tokens{component="..."}` y expone el valor de la última llamada observada por el proceso. Los componentes posibles son:

| Componente | Qué incluye |
| --- | --- |
| `system` | Plantilla de instrucciones permanentes y reglas de ejecución. |
| `memory` | Referencias, procedimientos aprendidos y contexto reciente recuperado. |
| `tools` | Inventario MCP que ADA inyecta en el prompt. |
| `prompt` | Marcador y pedido actual del usuario. |
| `response` | Texto generado por el modelo. |
| `total` | Suma de los cinco componentes anteriores. |

El conteo usa una estimación portable de aproximadamente un token cada cuatro caracteres cuando el proveedor no devuelve usage exacto. Por eso sirve para comparar consumo y anticipar presión de contexto, pero no reemplaza el conteo nativo de cada tokenizer.

## Implementación

- Construcción y desglose: `ada/application/services/prompts.py`.
- Publicación Prometheus: `ada/infrastructure/prometheus_metrics.py`.
- Actualización de respuesta: `ada/infrastructure/engines/model_manager.py`.
- Endpoint de exposición: `ada/interfaces/web/routes/core.py`.

## Consulta rápida

```promql
ada_llm_tokens{component="memory"}
```

Para graficar la composición, usar `component` como leyenda. Como el gauge representa la última llamada, las tendencias históricas deben persistirse en Prometheus mediante el scrape normal.
