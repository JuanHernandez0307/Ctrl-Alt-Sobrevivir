# Ctrl-Alt-Sobrevivir · API Wars

Prototipo de una plataforma de conciertos que combina descubrimiento de eventos, equivalencias en cinco divisas, recaudo Sandbox en COP y facturación electrónica de prueba con Factus V2.

**Estado actual: Fase 1 preparada.** El repositorio contiene la colección de Postman, contratos, mocks, documentación y validación local. Las llamadas autenticadas a las APIs están pendientes de ejecución por el equipo. El backend FastAPI y el despliegue en Render corresponden a las fases siguientes.

## Empezar en Postman

1. Instala Postman y crea un Workspace privado para el equipo.
2. Importa la [colección de Fase 1](postman/collections/API_Wars_Fase1.postman_collection.json) y la [plantilla de entorno Sandbox](postman/environments/API_Wars_Sandbox.postman_environment.json).
3. Selecciona el entorno y completa las claves y credenciales en sus **valores locales** o Vault. La plantilla publicada tiene los secretos vacíos.
4. Sigue la [guía de Fase 1](docs/FASE1_GUIA.md) para ejecutar cada solicitud y configurar los mocks.
5. Coordina un único responsable para autenticar Factus Pay: volver a autenticar el mismo usuario invalida su token anterior.

**Secuencia de prueba:** buscar evento → consultar divisas → autenticar Factus → elegir rango → autenticar Pay → crear recaudo → usar simulador → verificar `paid` → emitir factura V2.

La colección tiene **16 solicitudes y 8 respuestas de ejemplo**. No ejecutes toda la colección con Runner: la autenticación y la confirmación de pago requieren pasos manuales. Cada nuevo pedido usa una referencia nueva; un reintento conserva su referencia.

## APIs y alcance del MVP

| API | Uso | Límite que refleja la demo |
| --- | --- | --- |
| Ticketmaster Discovery | Eventos y rangos orientativos de precios | Discovery no reserva ni vende inventario. El checkout utilizará boletos de demostración de la promotora. |
| ExchangeRate-API | Equivalencias en USD, EUR, GBP, MXN y CAD | El plan Free actualiza las tasas diariamente; se muestra su fecha. |
| Factus Pay | Crear recaudo y verificar pago | Recaudo Sandbox en COP por QR/Bre-B; no se ofrece cobro en moneda extranjera. |
| Factus Facturación V2 | Factura de prueba asociada al recaudo | La validación Sandbox y su CUFE de prueba no son una factura fiscal de producción. |

El ejemplo financiero factura un servicio genérico de prueba: base de 100.000 COP más IVA de prueba del 19 %, total de 119.000 COP. Ese ejemplo no determina el tratamiento tributario de entradas de conciertos.

## Diseño previsto

El frontend consumirá un Mini API Gateway de FastAPI desplegado en Render. Los adaptadores separarán Ticketmaster, divisas, Pay y Factus. PostgreSQL conservará órdenes, pagos, facturas y tareas pendientes.

| Ruta propia propuesta | Función |
| --- | --- |
| `GET /api/v1/events` | Buscar eventos y consolidar equivalencias monetarias. |
| `POST /api/v1/quotes` | Calcular una cotización desde el catálogo de la promotora. |
| `POST /api/v1/orders` | Crear la orden y su recaudo COP con una referencia persistente. |
| `GET /api/v1/orders/{orderId}` | Consultar el estado de una orden de su propietario. |
| `POST /api/v1/webhooks/factus-pay` | Guardar la notificación y programar la verificación del pago. |

Estas rutas son contratos y mocks; todavía no hay un servidor que las implemente. Si Factus falla después de un pago, el diseño conserva la orden pagada con factura pendiente y reintenta desde una tarea persistente.

## Archivos del equipo

| Archivo o carpeta | Contenido |
| --- | --- |
| `postman/collections/` | Colección importable con scripts y ejemplos sintéticos. |
| `postman/environments/` | Entorno importable sin secretos. |
| [docs/FASE1_GUIA.md](docs/FASE1_GUIA.md) | URLs, headers, autenticación, pruebas, mocks y fuentes oficiales. |
| [docs/EQUIPO_Y_TAREAS.md](docs/EQUIPO_Y_TAREAS.md) | Responsabilidades, pendientes y criterios para cerrar cada fase. |
| [scripts/validate-postman.cjs](scripts/validate-postman.cjs) | Validador local de scripts y escenarios con datos sintéticos. |
| [.env.example](.env.example) | Variables propuestas para el backend futuro, sin credenciales. |

## Validación local

Con Node.js 20 o superior, desde la raíz del repositorio:

```cmd
node scripts/validate-postman.cjs
```

El validador compila 24 scripts y ejecuta 12 escenarios, incluidos referencia idempotente, comprobación de monto, bloqueo de factura sin pago, expiración OAuth y HTTP 429. No instala paquetes ni consume APIs.

Estas comprobaciones no prueban conectividad, aceptación de payloads por el proveedor ni validación DIAN de punta a punta. La evidencia real se obtiene en Postman usando el Sandbox.

## Configuración y colaboración

- La plantilla `.env.example` documenta variables para las fases siguientes; aún no existe código que la consuma.
- Guarda la configuración real en `.env`, excluido por `.gitignore`. Las contraseñas y los tokens tampoco se publican en capturas o exports de Postman.
- Cada integrante usa su entorno local. Un responsable coordina el token Pay y las pruebas de pago/factura; el frontend puede consumir los mocks.
- Trabaja en una rama y abre un PR con el cambio y su comprobación. No avances de fase sin confirmación del equipo.

## Fases

| Fase | Estado |
| --- | --- |
| 1. Orquestación y Postman | Archivos preparados y verificados localmente; ejecución autenticada pendiente. |
| 2. Búsqueda y divisas | Pendiente de confirmación e implementación. |
| 3. Pagos y facturación | Pendiente de confirmación e implementación. |

Integrantes y asignaciones: completar en [EQUIPO_Y_TAREAS.md](docs/EQUIPO_Y_TAREAS.md).
