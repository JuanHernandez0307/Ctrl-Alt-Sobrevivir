# API Wars - Fase 1: orquestacion y Postman
Fecha de verificacion documental: 2026-11-04.
Estado: contratos y colecciones preparados. Sin llamadas autenticadas ejecutadas ni backend implementado.

## 1. Alcance que podemos defender
- Discovery descubre eventos y rangos orientativos. La reserva/compra de inventario Ticketmaster exige Partner API y una relacion oficial de distribucion.
- El MVP vende boletos DE DEMOSTRACION de una promotora colombiana. Los resultados Discovery enriquecen la experiencia, pero no otorgan permisos para revender ni generan entradas oficiales.
- Mostramos equivalencias en USD, EUR, GBP, MXN y CAD. La moneda de cobro y del fixture de facturacion es COP.
- Factus Pay documenta recaudos COP por QR/Bre-B: no hay cobro en USD/EUR ni tarjeta internacional en las APIs aportadas. No prometer que un turista puede pagar desde cualquier banco extranjero. La demo usa el simulador.
- ExchangeRate Free actualiza diariamente, no tick a tick. Mostrar hora de la tasa y cachear hasta time_next_update_unix.
- Factus Sandbox demuestra la integracion y la validacion de prueba. No es una factura fiscal de produccion. CUFE no acredita que un boleto Ticketmaster sea genuino ni garantiza ausencia de fraude.
- El payload financiero usa un SERVICIO GENERICO de prueba: base 100000 COP + IVA de prueba 19% = total 119000 COP. No establece el tratamiento tributario de conciertos. Configurar el producto real con la promotora y su responsable tributario antes de produccion.
- El comprador es una persona extranjera de prueba: documento 41 (pasaporte), pais US. El campo municipio se omite porque no se inventa un municipio colombiano para una direccion extranjera.

## 2. Mini API Gateway (diseno, aun sin implementar)
Una app FastAPI en Render, organizada por adaptadores Ticketmaster, FX, Pay y Factus. El frontend consume solo nuestras rutas.
PostgreSQL guarda ordenes, cotizaciones, inventario propio demo, referencias de pago, facturas, notificaciones y tareas pendientes.
La base de datos y la tabla de tareas/outbox deben persistir fuera del filesystem efimero de Render.

| Ruta propia propuesta | Funcion | Quien llama |
| --- | --- | --- |
| GET /api/v1/events | Consultar Discovery + conversiones; indicar fuentes y datos no disponibles | Frontend |
| POST /api/v1/quotes | Calcular una cotizacion desde IDs/cantidad y catalogo de la promotora | Frontend |
| POST /api/v1/orders | Persistir la orden y crear un recaudo COP usando la cotizacion | Frontend autenticado |
| GET /api/v1/orders/{orderId} | Leer estado de la DB y factura; validar propiedad de la orden | Frontend autenticado |
| POST /api/v1/webhooks/factus-pay | Validar key, guardar notificacion y trabajo duradero; responder rapido | Factus Pay |

Decisiones:
- La cantidad y precio final se validan en servidor; no aceptar un monto calculado por el navegador.
- Preservar precios monetarios como decimales/cadenas; usar Decimal en las fases de Python.
- Una referencia por orden para Pay y Factus; Idempotency-Key en NUESTRA ruta de ordenes (no se inventa ese header para los proveedores).
- Un evento Discovery no es un SKU vendible automaticamente. El checkout requiere inventario/precio propios de la promotora; la demo etiqueta claramente los eventos simulados.
- El webhook usa la llave query key documentada, no una firma HMAC inventada. Comparar la llave en tiempo constante y ocultarla en logs. Confirmar referencia, monto y paid con GET autenticado a Pay.
- Guardar el evento y una tarea en DB antes de responder 2xx. Procesar facturacion despues; una tarea persistente se recupera tras reinicios. No depender solo de BackgroundTasks o memoria.
- Estados de pago: pending, paid, expired. Estados de factura: not_created, pending, validated, requires_review. Un pago confirmado se conserva aunque Factus no este disponible.
- Un fallo de Factus deja paymentStatus=paid e invoiceStatus=pending. Reintentar con la misma referencia y conciliar respuestas ambiguas. No inventar CUFE ni afirmar validacion mientras falte.
- Llamar a esto facturacion pendiente/reintento: no equivale a activar automaticamente un procedimiento legal de contingencia DIAN.
- Antes de entregar una entrada demo, verificar pago. La validacion de acceso del boleto se implementara como uso unico con cambio atomico en DB; CUFE no reemplaza ese control.
- CORS pertenece a nuestra API: permitir los origenes exactos del frontend. Postman Desktop no necesita una politica CORS del proveedor.

## 3. Archivos
- [API_Wars_Fase1.postman_collection.json](../postman/collections/API_Wars_Fase1.postman_collection.json): 16 solicitudes, 8 respuestas guardadas para mocks; scripts try/catch.
- [API_Wars_Sandbox.postman_environment.json](../postman/environments/API_Wars_Sandbox.postman_environment.json): plantilla con secretos vacios.
- Esta guia.

## 4. Crear el espacio de trabajo
1. Crear un Workspace privado para el equipo. Importar coleccion y entorno.
2. Seleccionar el entorno. Duplicarlo por desarrollador para separar sus referencias de orden y estado.
3. Compartir URLs y valores de prueba. Introducir claves y contrasenas solo en valores LOCALES o Postman Vault. Marcar un campo como secret enmascara su valor; no autoriza compartirlo.
4. Usar la app de escritorio o Desktop Agent si se trabaja desde Postman web.
5. Un responsable prueba pagos y emision contra Sandbox; el frontend y los otros integrantes usan mocks.
6. No ejecutar TODA la coleccion en Runner: hay autenticaciones manuales, un paso humano de simulador y mocks. No programar monitores de /auth.
7. Si se hace un Run de un subconjunto, una sola iteracion; la coleccion espacia las llamadas de proveedor al menos 1 segundo por esta instancia. Eso no es un limitador global entre todos los equipos/dispositivos.

## 5. Variables que debes completar
| Variable | Valor que corresponde |
| --- | --- |
| tm_api_key | Consumer/API Key de tu aplicacion en Ticketmaster Developer Portal |
| fx_api_key | API key propia de ExchangeRate-API |
| pay_email / pay_password | Credenciales del usuario Sandbox de Factus Pay que autentica por /auth |
| pay_token | Se captura desde token de la respuesta Pay |
| factus_client_id / factus_client_secret | Credenciales OAuth Sandbox de Factus Facturacion |
| factus_username / factus_password | Usuario y contrasena Sandbox de Factus Facturacion |
| factus_access_token / factus_refresh_token | Se capturan desde respuesta OAuth |
| factus_expires_at_ms | Se calcula usando expires_in de la respuesta, sin asumir una hora |
| numbering_range_id | ID del rango vigente devuelto por V2, sin copiar el ID de un ejemplo |
| order_reference | Se genera una vez al crear el recaudo si esta vacio; conservar al reintentar |
| webhook_key | Llave aleatoria que tu equipo configura en panel Pay y backend |
| gateway_base | URL del Mock Server en esta fase; localhost/Render cuando exista backend |

Nunca reutilizar tokens entre Factus y Factus Pay.
Pay no usa el client_id/client_secret de Factus. Segun la documentacion vigente, Pay autentica email/password en /auth y devuelve token; consultar con el mentor si el panel del evento presenta credenciales distintas.
Cada POST Pay /auth revoca el token anterior del mismo usuario. Reutilizarlo; pay_rotate_token=true solo para una rotacion deliberada y coordinada.
El token Pay no tiene expiracion temporal documentada; Factus OAuth si devuelve expires_in.
La documentacion Factus muestra duraciones distintas en ejemplos y texto: manda la respuesta real del servidor.

## 6. URLs exactas y encabezados
Todas las solicitudes llevan Accept:application/json.

| Metodo | URL | Autenticacion y cuerpo |
| --- | --- | --- |
| GET | https://app.ticketmaster.com/discovery/v2/events.json?apikey={{tm_api_key}}&classificationName=music&countryCode={{tm_country}}&size=5&page=0&sort=date,asc | API key en query; sin Body |
| GET | https://app.ticketmaster.com/discovery/v2/events/{{tm_event_id}}.json?apikey={{tm_api_key}} | API key en query; sin Body |
| GET | https://v6.exchangerate-api.com/v6/{{fx_api_key}}/latest/COP | API key en ruta; sin Body |
| POST | https://pay-api-sandbox.factus.com.co/auth | Content-Type:application/json; email,password |
| POST | https://pay-api-sandbox.factus.com.co/v1/collections | Authorization:Bearer {{pay_token}}; JSON |
| GET | https://pay-api-sandbox.factus.com.co/v1/collections/{{order_reference}} | Authorization:Bearer {{pay_token}}; sin Body |
| POST | https://api-sandbox.factus.com.co/oauth/token | Content-Type:application/x-www-form-urlencoded; password o refresh grant |
| GET | https://api-sandbox.factus.com.co/v2/numbering-ranges?filter[document]=21&filter[is_active]=1 | Authorization:Bearer {{factus_access_token}}; sin Body |
| POST | https://api-sandbox.factus.com.co/v2/bills/validate | Authorization:Bearer {{factus_access_token}}; Content-Type:application/json |
| GET | https://api-sandbox.factus.com.co/v2/bills/{{factus_bill_number}} | Authorization:Bearer {{factus_access_token}}; sin Body |

La coleccion ya contiene los Bodies completos. El grant password lleva: grant_type=password, client_id, client_secret, username, password; el de renovacion: grant_type=refresh_token, client_id, client_secret, refresh_token.
Los datos OAuth son campos de formulario, no JSON. La coleccion usa urlencoded, como el ejemplo Node/curl de la documentacion oficial.

## 7. Secuencia manual de pruebas
1. Completar claves TM/FX y credenciales Sandbox en valores locales.
2. Ticketmaster buscar -> detalle. Se captura el ID. Si no hay priceRanges, se indica no disponible; no se inventa precio. tm_country inicia US para explorar. Probar CO si hay cobertura, sin garantizar resultados.
3. ExchangeRate latest/COP. Capturar conversion_rates, time_last_update_unix y time_next_update_unix. Una peticion entrega las cinco divisas; revisar fx_display_amounts.
4. Factus obtener token -> consultar rangos. Si hay varios activos, elegir uno manualmente y repetir la consulta.
5. Pay autenticar UNA VEZ con el responsable de integracion. Si ya hay token, no reautenticar.
6. Pay crear recaudo. El fixture es 119000 COP; conservar order_reference. Se guarda pay_qr y pay_breb_key.
7. Abrir https://pay-api-sandbox.factus.com.co/simulator y simular el pago de ESE QR/referencia. No se inventa un endpoint HTTP para confirmar pagos.
8. Pay consultar y verificar pago. Solo data.status=paid y monto/referencia coincidentes dejan la evidencia local de verificacion. Si retorna ready, seguir esperando.
9. Factus emitir factura. El pre-request se detiene si no se verifico ese pago y monto, si la verificacion tiene mas de 5 minutos, si falta rango o si el fixture no cuadra.
10. Confirmar data.is_validated=true, data.number y data.cufe. Se guardan factus_bill_number y factus_cufe. Consultar factura por numero si hace falta.
11. Un pedido nuevo necesita otra referencia: limpiar order_reference y volver al paso 6. Un REINTENTO conserva la misma.

El bloqueo de factura de Postman es una ayuda para este ejercicio, no una medida de seguridad del backend. La fase 3 debera hacer sus propias verificaciones y transacciones en DB.
No se han probado estas solicitudes contra una cuenta real: faltan keys propias TM/FX y la ejecucion manual del Sandbox. Haber validado scripts/JSON no acredita una integracion de punta a punta.

## 8. Mocks para frontend
1. Crear Mock Server desde esta coleccion. Las respuestas guardadas estan en la carpeta 05 de Gateway.
2. Seleccionar un entorno de MOCK independiente y poner el dominio entregado por Postman en gateway_base, por ejemplo https://<id>.mock.pstmn.io. La URL real se obtiene al crear el mock; no es una URL provisionada por estos archivos.
3. Las respuestas solo contienen datos sinteticos y campos isMock:true. Un mock no tiene estados persistentes: no espera pagos ni factura.
4. La solicitud de consulta de ordenes trae x-mock-response-name:GW_ORDER_PENDING. Cambiarlo por GW_ORDER_PAID_INVOICE_PENDING, GW_ORDER_COMPLETED o GW_ORDER_RATE_LIMITED.
5. Los demas nombres estan precargados: GW_EVENTS_OK, GW_QUOTE_OK, GW_ORDER_CREATED, GW_WEBHOOK_ACCEPTED.
6. Si un mock privado exige x-api-key, esa es una clave de POSTMAN, no la de Factus. No incluirla en un frontend publicado; usar un proxy o un mock solo con datos sinteticos sin credenciales.
7. Configurar CORS de nuestra API al implementar backend. La prueba Postman no demuestra que el navegador este correctamente autorizado.

## 9. Webhook real (configuracion futura, no se despliega en fase 1)
En el panel Pay registrar la futura URL HTTPS de Render terminada en /api/v1/webhooks/factus-pay y configurar la llave separada. El proveedor agrega ?key=...
El cuerpo recibido contiene data.reference_code,data.amount,data.status='paid'. payer es opcional.
El receptor debe persistir evento/tarea y responder 2xx en menos del limite documentado de 10 segundos, sin esperar a Factus. Si no se pudo guardar, no confirmar recepcion.
Luego el trabajo verifica Pay via GET autenticado y factura usando la referencia guardada.
El POST de webhook en la carpeta mock no demuestra que exista un receptor real ni un pago.

## 10. Resiliencia para la implementacion posterior
- Ticketmaster: cache de busquedas y detalles. Limite propio conservador de 1 req/s por clave para la demo; sus paginas oficiales publican cifras diferentes de 2 y 5 req/s. Atender los headers reales y coordinar consumo del equipo.
- FX: cache persistente hasta proxima actualizacion; manejar result:error/error-type=quota-reached ademas de HTTP 429. Si se usa tasa previa, indicar antiguedad y no presentar como actual.
- Factus: limite publicado 80 req/min/usuario. Reutilizar token hasta expires_in; renovar bajo exclusión para evitar carreras.
- Pay: no inventar un limite numerico no publicado; espaciar consultas y atender 429. Reutilizar token.
- HTTP 429: guardar cooldown por proveedor, atender Retry-After (segundos o fecha HTTP) y detener Runner. No hay reintentos automaticos ciegos en esta coleccion.
- En Python: timeout de conexion/lectura; reintentos limitados con backoff y jitter solo para fallos transitorios, usando la misma referencia. No reintentar 422 sin corregir datos; resolver 401 con renovacion controlada.
- Factus 409 y resultados inciertos: inspeccionar la factura de la referencia; no cambiar la referencia para forzar otra factura ni eliminar documentos automaticamente.
- Si la respuesta Pay se pierde: consultar/recrear con MISMA referencia. Nunca volver a cobrar como solucion a un fallo fiscal.
- La emision pendiente requiere reintento duradero y conciliacion; no una cola solo en RAM.
- El cobro y una factura no garantizan ausencia de fraude. Agregar control de propietario, monto en servidor, inventario atomico y uso unico del boleto.

## 11. Evidencia para cerrar fase 1
- Busqueda Discovery con ID real; rangos de precios presentes o ausencia explicitada.
- Respuesta FX de la cuenta del equipo con las cinco conversiones.
- Recaudo Sandbox con referencia y monto.
- Consulta autenticada Pay que devuelve paid despues del simulador.
- Factura V2 validada con el mismo reference_code, numero y CUFE de prueba.
- Frontend consumiendo ejemplos propios sin depender de tokens de proveedor.
- Ningun secreto en capturas, coleccion exportada ni repositorio publico.
Esto es una lista de pruebas por realizar, no evidencia de que se ejecutaron.

## 12. Fuentes oficiales
- [Ticketmaster Discovery](https://developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2/)
- [Ticketmaster Partner](https://developer.ticketmaster.com/products-and-docs/apis/partner/)
- [Ticketmaster cuotas FAQ](https://developer.ticketmaster.com/support/faq/)
- [ExchangeRate Standard](https://www.exchangerate-api.com/docs/standard-requests)
- [ExchangeRate planes](https://www.exchangerate-api.com/)
- [Pay autenticacion](https://pay-developers.factus.com.co/autenticacion/)
- [Pay recaudos](https://pay-developers.factus.com.co/recaudos/crear/)
- [Pay consulta](https://pay-developers.factus.com.co/recaudos/ver/)
- [Pay webhook](https://pay-developers.factus.com.co/webhooks/)
- [Pay simulador](https://pay-developers.factus.com.co/sandbox/simulator/)
- [Factus OAuth](https://developers.factus.com.co/autenticacion/auth/)
- [Factus rangos](https://developers.factus.com.co/rangos-de-numeracion/facturaci%C3%B3n/obtener-rangos/)
- [Factus V2 emision](https://developers.factus.com.co/facturas/crear-y-validar/)
- [Factus tablas V2](https://developers.factus.com.co/tablas-de-referencia/tablas/)
- [Factus limites](https://developers.factus.com.co/limite-de-request)
- [Postman variables](https://learning.postman.com/docs/use/send-requests/variables/variables)
- [Postman mocks](https://learning.postman.com/v11/docs/design-apis/mock-apis/tutorials/mock-with-api)


## 13. Validacion local completada
JSON analizado, variables referenciadas verificadas, 24 scripts compilados y 12 escenarios de control superados con datos sinteticos. Cero solicitudes autenticadas ejecutadas. Los tests locales no sustituyen la prueba de Sandbox del equipo.

Para repetir las comprobaciones desde la raíz del repositorio: `node scripts/validate-postman.cjs`. El script usa Node.js y datos sintéticos, sin credenciales ni acceso a las APIs.
