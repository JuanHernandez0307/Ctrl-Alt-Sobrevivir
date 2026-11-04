# Equipo y tareas · API Wars

## Estado que podemos compartir

La Fase 1 tiene una colección de Postman importable, entorno vacío, contratos del Mini API Gateway y ejemplos para el frontend. Se comprobaron los scripts localmente. Falta obtener las claves propias de Ticketmaster y ExchangeRate y ejecutar el flujo autenticado en Sandbox.

El backend y el despliegue están pendientes de las fases siguientes. Ninguna tarea de esta lista declara que ya se procesaron pagos o se emitieron facturas en las APIs.

## Asignación sugerida

Completar los nombres entre el equipo; no hay personas asignadas automáticamente.

| Rol | Integrante | Responsabilidad inmediata |
| --- | --- | --- |
| Integración y Postman | Por asignar | Workspace, credenciales locales, token Pay y ejecución del Sandbox. |
| Backend y datos | Por asignar | Revisar contratos, referencias y estados de órdenes; preparar Fase 2 cuando se confirme. |
| Frontend y experiencia | Por asignar | Configurar mocks y trabajar sobre precios, checkout y estados de factura. |
| Pruebas, demo y documentación | Por asignar | Reunir evidencia sin secretos y preparar la secuencia de demostración. |

## Fase 1: pendiente de ejecución del equipo

- [x] Preparar colección, entorno, documentación y scripts para GitHub.
- [x] Publicar los archivos en el repositorio del equipo.
- [x] Preparar 16 solicitudes y 8 respuestas sintéticas para mocks.
- [x] Compilar los scripts y ejecutar 12 comprobaciones locales.
- [ ] Crear el Workspace privado de Postman e importar ambos JSON.
- [ ] Obtener y configurar API Keys de Ticketmaster y ExchangeRate.
- [ ] Configurar las credenciales Factus y Pay solo en valores locales o Vault.
- [ ] Ejecutar búsqueda Discovery; conservar un ID real y su moneda, si hay precio disponible.
- [ ] Consultar ExchangeRate y comprobar USD, EUR, GBP, MXN y CAD.
- [ ] Autenticar Factus y seleccionar un rango activo del Sandbox.
- [ ] Designar un responsable para el token Pay y autenticar una vez.
- [ ] Crear un recaudo con una referencia única y conservarla durante los reintentos.
- [ ] Completar el pago de prueba en el simulador oficial.
- [ ] Consultar Pay y verificar `paid`, importe y referencia.
- [ ] Enviar la factura V2 de prueba y comprobar validación, número y CUFE.
- [ ] Crear el Mock Server y probar los estados pendiente, pagado con factura pendiente y completado.
- [ ] Registrar resultados sin contraseñas, tokens, llaves ni datos personales reales.
- [ ] Confirmar el cierre de Fase 1 antes de implementar Fase 2.

## Qué hace cada parte

| Actividad | Equipo en sus dispositivos | Apoyo técnico del asistente |
| --- | --- | --- |
| Cuentas y claves | Crear cuentas, acceder a paneles y completar secretos locales. | Explicar los campos y corregir la configuración. |
| Postman | Importar archivos, seleccionar entorno y ejecutar solicitudes. | Mantener colección, scripts y contratos; diagnosticar respuestas. |
| Simulador | Confirmar el pago Sandbox del QR correcto. | Revisar que el pago concilie con la referencia e importe. |
| Código | Ejecutar los comandos locales y revisar los cambios del equipo. | Implementar y verificar el backend cuando se confirme la fase. |
| GitHub | Coordinar revisiones y asignaciones. | Organizar archivos y preparar o subir cambios autorizados. |
| Demo | Grabar el flujo real del Sandbox. | Preparar README, arquitectura y guion de demostración. |

## Fase 2: plan pendiente de confirmación

- Adaptador asíncrono Ticketmaster y normalización de eventos.
- Adaptador ExchangeRate con caché y fecha de actualización.
- Un JSON consolidado para el frontend, preservando la moneda de origen.
- Precios ausentes explícitos, manejo de cuotas, timeouts y HTTP 429.
- Separación entre descubrimiento global e inventario de demostración de la promotora.

## Fase 3: plan pendiente de confirmación

- Guardar órdenes, referencias, estados y tareas en PostgreSQL.
- Calcular el total en servidor y comprobar disponibilidad.
- Crear recaudos COP y verificar pago con Pay autenticado.
- Validar la llave del webhook y guardar notificaciones antes de responder.
- Emitir factura V2 sin duplicarla y conservar pagos aunque Factus falle.
- Reintentos persistentes y conciliación de resultados inciertos.
- Autenticación, propietario de la orden y uso único del boleto demo.
- Despliegue en Render y demostración de punta a punta.

## Criterios para la demo

Mostrar por separado qué datos vienen de APIs reales, cuáles son sintéticos y cuál es el inventario propio de prueba. Las equivalencias en divisas no cambian que el recaudo sea COP. El CUFE Sandbox pertenece al documento de prueba y no acredita una entrada oficial de Ticketmaster.

La guía técnica y las fuentes están en [FASE1_GUIA.md](FASE1_GUIA.md).
