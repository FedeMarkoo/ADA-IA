# Estructura de carpetas

La estructura agrupa el código por responsabilidad. La aplicación, sus
capabilities y la infraestructura viven dentro de `src/ada`; la raíz conserva
solo el entrypoint, configuración, documentación, pruebas y la interfaz web.

```text
ADA/
├── README.md
├── ada.py                         entrypoint único
├── config.json                    configuración local
├── pyproject.toml                 configuración del paquete
├── requirements.txt               dependencias
├── docs/
│   ├── README.md
│   ├── project/                   producto, arquitectura y roadmap
│   └── capabilities/              contratos de capabilities
├── src/ada/
│   ├── agents/                    coordinadores y agentes especialistas
│   ├── application/               casos de uso y routing
│   ├── capabilities/              herramientas invocables por ADA
│   │   ├── data/
│   │   ├── files/
│   │   ├── photography/
│   │   └── system/
│   ├── domain/                    reglas del producto
│   │   └── photography/
│   ├── infrastructure/            Ollama, SQLite, imagen y recursos
│   │   ├── engines/
│   │   ├── imaging/
│   │   ├── integrations/
│   │   ├── persistence/
│   │   └── runtime/
│   └── interfaces/                entradas web y CLI
├── tests/                         pruebas automatizadas
└── ui/                            frontend web
```

## Criterios

- `domain/` contiene reglas independientes de tecnologías concretas.
- `application/` coordina casos de uso y selección de agentes.
- `agents/` aporta especialistas para tareas complejas, como fotografía.
- `capabilities/` expone funciones que ADA puede descubrir y ejecutar.
- `infrastructure/` implementa motores, persistencia, decodificación y límites
  de recursos.
- `interfaces/` transforma mensajes web o de CLI en solicitudes de aplicación.

Ollama está en `infrastructure/engines` porque es un proveedor de inferencia.
El ciclo de vida y los límites de CPU están en `infrastructure/runtime`.
Fotografía es un dominio propio: RAW/JPG son entradas y no justifican una
carpeta genérica `media`.

## Regla para agregar código

Antes de crear un archivo hay que clasificarlo como regla de negocio, caso de
uso, capability, integración tecnológica o interfaz. Si no pertenece a una de
esas responsabilidades, no se agrega una carpeta nueva: se modifica el módulo
existente más cercano.

Los módulos vacíos, scripts de prueba descartables, modelos descargados y
memoria generada no forman parte del repositorio. Los datos locales quedan
fuera de Git mediante `.gitignore`.
