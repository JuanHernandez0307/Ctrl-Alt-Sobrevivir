> **Actualización Sandbox:** El catálogo Ticketmaster y el flujo de prueba de Factus están implementados; la ejecución de Pay y Factus requiere credenciales y pruebas reales. La factura es un servicio ficticio y no es una factura de producción. El frontend muestra por separado los conciertos reales y los productos de demostración.

# Ritmo — prototipo de turismo musical

Este proyecto contiene un frontend React/TypeScript y una API FastAPI para demostrar la búsqueda, cotización, registro de orden, QR ficticio, pago simulado y descarga de un boleto de demostración. **Es un prototipo ejecutable en modo demo; no es todavía la integración completa solicitada.**

## Qué está preparado y qué falta

| Función | Estado |
| --- | --- |
| Búsqueda de eventos y detalle | Catálogo de Ticketmaster en una sección independiente; el checkout demo conserva tres eventos ficticios. |
| Cinco monedas | Conversión con Decimal y tasas ficticias; no son cotizaciones actuales. |
| Cotización y orden | Funciona con datos ficticios, idempotencia y almacenamiento SQLAlchemy. |
| QR y pago | La sección demo simula un QR; otra sección utiliza Factus Pay Sandbox cuando las credenciales estén configuradas. |
| Boleto PDF | PDF de demostración que indica que no es oficial de Ticketmaster. |
| Factus Pay real, Factus API, CUFE y PDF/XML fiscal | Flujo Sandbox implementado; requiere credenciales, rango y prueba real de extremo a extremo. |
| Webhook, conciliación duradera y facturación sin duplicados | Conciliación mediante consultas implementada; faltan webhook y reintentos duraderos. |
| Proveedor de eventos y proveedor de tasas | Ticketmaster integrado para catálogo; tasa externa pendiente. |
| Reglas tributarias y consentimiento | Pendientes de confirmar con los responsables del proyecto. |

El archivo original marca esas decisiones como pendientes. El flujo de compra demo requiere `APP_MODE=demo`; las rutas `/sandbox` utilizan exclusivamente proveedores de prueba.

**Para cualquier demo usa datos inventados.** El acceso a cada orden usa una clave temporal en la pestaña; al recargarla se pierde el acceso a esa orden. La aplicación no incorpora cuentas de usuario, límites de tasa, migraciones, conciliador, boleto de un solo uso ni controles suficientes para producción.

## Ejecutar localmente en Windows CMD

Abre CMD en la carpeta extraída y ejecuta:

```cmd
py -3.13 -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -r backend\requirements.txt
copy .env.example .env
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

En una segunda ventana CMD, desde la misma carpeta:

```cmd
cd frontend
npm install
npm run dev
```

Abre la dirección local que imprima Vite. La API está en `http://127.0.0.1:8000` y su documentación en `http://127.0.0.1:8000/docs`. El proxy local de Vite dirige `/api` a FastAPI. Necesitas Python 3.13 y Node.js compatibles con Vite 6.

## Configuración antes de subir a Render

Las claves se configuran en **Environment** de Render; no hay que pegarlas en el código ni subir `.env` al repositorio. Las credenciales de Ticketmaster y de Factus se consumen solamente desde el servidor; el flujo Factus se limita a Sandbox.

1. Extrae el ZIP y sube su contenido a GitHub. Si lo subes a un repositorio existente, revisa que no sobrescribas trabajo del equipo.
2. Crea o conecta una base de datos PostgreSQL. Copia su URL interna de conexión desde Render. SQLite sirve localmente, pero en un disco efímero de Render se perderán las órdenes al reiniciar o desplegar.
3. Crea un **Web Service** conectado al repositorio. Usa la raíz del proyecto como Root Directory, entorno Python y estas opciones:

   - Build Command: `pip install -r backend/requirements.txt`
   - Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
   - Health Check Path: `/api/v1/health`
   - `APP_MODE=demo`
   - `DATABASE_URL`: URL interna de PostgreSQL.
   - `CORS_ORIGINS`: URL exacta HTTPS del frontend, sin barra final. Actualízala después de crear el frontend.

4. Crea un **Static Site** desde el mismo repositorio:

   - Root Directory: `frontend`
   - Build Command: `npm install && npm run build`
   - Publish Directory: `dist`
   - `VITE_API_BASE_URL`: URL pública HTTPS del backend, sin barra final.

5. Actualiza `CORS_ORIGINS` en el backend con la URL del Static Site y vuelve a desplegarlo. Abre `/api/v1/health` en el backend y comprueba `modo: demo`; después abre el sitio y realiza una compra con datos inventados.

La URL de backend es la única variable `VITE_` prevista. No pongas API Keys ni contraseñas en variables del frontend: Vite las incluye en el código público.

## Datos que el equipo debe proporcionar para completar el modo real

1. Comprobar la cobertura de Ticketmaster para las ciudades objetivo.
2. Nombre, documentación y ejemplo sanitizado del proveedor de tasas; confirmar unidades por 1 COP y frecuencia.
3. Respuestas reales sanitizadas de OAuth Factus, rangos, creación y consulta Pay, y factura V2 validada.
4. Tipo de documento, unidad, régimen, impuestos y demás códigos tributarios aprobados para el producto real.
5. Definición de autenticación de compradores y recuperación segura de órdenes.

Con esos datos aún se debe implementar y verificar la integración real. Un token de Pay se configura desde el servidor; no se ejecuta una rotación automática. No introduzcas contraseñas o claves en capturas, chats, ZIPs ni commits.

## Documentación oficial

- [Despliegue de FastAPI en Render](https://render.com/docs/deploy-fastapi)
- [Versión de Python en Render](https://render.com/docs/python-version)
- [Static Sites en Render](https://render.com/docs/static-sites)
- [Factus Pay](https://pay-developers.factus.com.co/)
- [Factus API V2](https://developers.factus.com.co/)

## Factus Sandbox: configurar en Render

En el Web Service agrega `FACTUS_PAY_TOKEN`, `FACTUS_USERNAME`, `FACTUS_PASSWORD`, `FACTUS_CLIENT_ID` y `FACTUS_CLIENT_SECRET`. `FACTUS_NUMBERING_RANGE_ID` es opcional si la cuenta tiene un solo rango activo. No subas los valores a Git. `DATABASE_URL` debe ser PostgreSQL. El sistema no solicita automáticamente un token de Pay; usa el vigente.

El botón de prueba crea un recaudo de 119.000 COP, correspondiente a un servicio ficticio de base 100.000 más IVA 19 % como fixture de prueba. No es tratamiento tributario para conciertos. La referencia se guarda antes de consultar Pay y se verifica el monto y estado antes de solicitar la factura. Respuestas ambiguas quedan pendientes de conciliación; no se reenvían facturas automáticamente. Al validar deben existir número y CUFE de prueba.

Esta integración todavía necesita pruebas de punta a punta con los Sandbox, confirmación del rango y validación por el equipo. Una factura Sandbox no equivale a una factura DIAN de producción. La recuperación de pagos se hace por consultas del navegador: falta un webhook y un proceso persistente para reintentos sin la página abierta. El boleto de la sección demo no representa entradas oficiales.
