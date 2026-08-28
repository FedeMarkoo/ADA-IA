# Decisiones

## REST y eventos primero

ADA no usa SOAP ni WebFlux actualmente. Se omiten esos adaptadores para no
agregar dependencias ni superficie de configuración. Se podrán incorporar como
módulos separados cuando exista un consumidor real.

## Contexto explícito

El contexto se guarda en `ThreadLocal` y la API permite iniciar una operación
con `TraceContext` recibido desde headers. Las tareas asincrónicas deben copiar
ese contexto explícitamente; la librería no presume que un cambio de thread sea
seguro.
