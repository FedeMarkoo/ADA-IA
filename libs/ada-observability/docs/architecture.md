# Arquitectura

La librería separa una API Java sin Spring (`api`) de adaptadores opcionales
(`spring`). `DefaultAdaObservability` mantiene un contexto por thread y emite
un `OperationLog` sólo al cerrar la operación raíz. Esto permite que llamadas
salientes se agreguen al log de la operación activa sin crear una segunda línea
para cada cliente.

La integración de ADA se hace en los bordes: `AdaObservabilityFilter` cubre
HTTP entrante, el interceptor cubre `RestTemplate` y los casos de uso registran
eventos explícitos con `start(..., "EVENT")`. El dominio no necesita conocer
Spring ni la implementación del sink.

Los payloads se serializan únicamente al emitir y se redactan antes de llegar
al logger. La lista configurable se suma a patrones integrados para tokens,
credenciales, contraseñas y claves. No se incluyen prompts ni datos personales
como labels de métricas.
