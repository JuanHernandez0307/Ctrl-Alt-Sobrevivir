"""Flujo de pruebas Factus Sandbox para un servicio ficticio de 119.000 COP.

No se usa para vender entradas de Ticketmaster ni procesa pagos de producción.
"""
from __future__ import annotations
import base64
import binascii
import hashlib
import hmac
import os
import time
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import String, Text, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from backend.main import Base, db, engine
from backend.factus_sandbox import FactusPaySandbox, FactusSandbox, SandboxError

router = APIRouter(prefix='/api/v1/sandbox', tags=['Factus Sandbox'])
TOTAL = '119000.00'
_attempts: list[float] = []

class OrdenSandbox(Base):
    __tablename__ = 'ordenes_factus_sandbox'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idempotencia: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    acceso_hash: Mapped[str] = mapped_column(String(64))
    referencia: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    estado: Mapped[str] = mapped_column(String(32), default='creating_payment')
    facturacion: Mapped[str] = mapped_column(String(32), default='waiting_payment')
    factura_numero: Mapped[str | None] = mapped_column(String(100), nullable=True)
    factura_cufe: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado: Mapped[str] = mapped_column(String(40))

class OrdenNueva(BaseModel):
    acceso: str = Field(min_length=32, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')


def verificar_configuracion():
    if engine.url.get_backend_name() != 'postgresql':
        raise HTTPException(503, 'El Sandbox requiere PostgreSQL persistente.')
    nombres = ('FACTUS_PAY_TOKEN', 'FACTUS_USERNAME', 'FACTUS_PASSWORD', 'FACTUS_CLIENT_ID', 'FACTUS_CLIENT_SECRET')
    if any(not os.getenv(x, '').strip() for x in nombres):
        raise HTTPException(503, 'Falta configurar las credenciales Sandbox de Factus Pay y Factus en Render.')
    rango = os.getenv('FACTUS_NUMBERING_RANGE_ID', '').strip()
    if rango and not rango.isdigit():
        raise HTTPException(503, 'FACTUS_NUMBERING_RANGE_ID debe ser numérico.')


def obtener_orden(db_sesion: Session, orden_id: str, acceso: str | None) -> OrdenSandbox:
    orden = db_sesion.get(OrdenSandbox, orden_id)
    digesto = hashlib.sha256((acceso or '').encode()).hexdigest()
    if orden is None or not hmac.compare_digest(orden.acceso_hash, digesto):
        raise HTTPException(404, 'Orden no encontrada.')
    return orden


def mostrar(orden: OrdenSandbox) -> dict:
    return {'id': orden.id, 'referencia': orden.referencia, 'estado': orden.estado,
            'facturacion': orden.facturacion, 'total_cop': TOTAL, 'factura_numero': orden.factura_numero,
            'cufe': orden.factura_cufe, 'ambiente': 'sandbox',
            'aviso': 'Servicio ficticio Sandbox; no es una entrada oficial ni factura de producción.'}


def ejemplo_factura(referencia: str) -> dict:
    # Mismo fixture financiero de Postman: base 100.000 + IVA 19 %, para prueba.
    body = {'reference_code': referencia, 'document': '01', 'operation_type': '10', 'send_email': False,
            'observation': 'API Wars: servicio ficticio Sandbox, no es entrada oficial.',
            'payment_details': [{'payment_form': '1', 'payment_method_code': '47', 'reference_code': referencia, 'amount': TOTAL}],
            'customer': {'identification_document_code': '41', 'identification': 'AA1234567', 'names': 'Ana Turista Demo',
                         'address': '100 Demo Street', 'email': 'buyer@example.com', 'legal_organization_code': '2',
                         'tribute_code': 'ZZ', 'country_code': 'US', 'responsibilities': ['R-99-PN']},
            'items': [{'code_reference': 'APIW-DEMO-SERVICE', 'name': 'Servicio de demostracion API Wars Sandbox',
                       'quantity': '1.00', 'price': '100000.00', 'unit_measure_code': '94', 'standard_code': '999',
                       'taxes': [{'code': '01', 'rate': '19.00'}]}]}
    rango = os.getenv('FACTUS_NUMBERING_RANGE_ID', '').strip()
    if rango: body['numbering_range_id'] = int(rango)
    return body


def cliente_factus(http: httpx.AsyncClient) -> FactusSandbox:
    return FactusSandbox(http, client_id=os.environ['FACTUS_CLIENT_ID'], client_secret=os.environ['FACTUS_CLIENT_SECRET'],
                         username=os.environ['FACTUS_USERNAME'], password=os.environ['FACTUS_PASSWORD'])


def procesar_respuesta_factura(orden: OrdenSandbox, data: object):
    if not isinstance(data, dict): return
    if data.get('reference_code') != orden.referencia: return
    if data.get('is_validated') is True and data.get('number') and data.get('cufe'):
        orden.facturacion = 'validated'
        orden.factura_numero = str(data['number'])
        orden.factura_cufe = str(data['cufe'])
    else:
        orden.facturacion = 'pending_review'

async def conciliar_factura(orden: OrdenSandbox, sesion: Session, http: httpx.AsyncClient):
    api = cliente_factus(http)
    # Un solo proceso reclama el envío; un resultado incierto jamás se reenvía automáticamente.
    if orden.facturacion == 'waiting_payment':
        resultado = sesion.execute(update(OrdenSandbox).where(OrdenSandbox.id == orden.id,
                                  OrdenSandbox.facturacion == 'waiting_payment')
                                  .values(facturacion='sending'))
        sesion.commit()
        if resultado.rowcount:
            try:
                respuesta = await api.validar_factura(ejemplo_factura(orden.referencia))
                sesion.refresh(orden)
                procesar_respuesta_factura(orden, respuesta.get('data'))
                if orden.facturacion == 'sending': orden.facturacion = 'pending_review'
                sesion.commit()
            except (SandboxError, ValueError):
                sesion.refresh(orden)
                orden.facturacion = 'uncertain'
                sesion.commit()
            return
    sesion.refresh(orden)
    if orden.facturacion in ('sending', 'uncertain', 'pending_review'):
        try:
            respuesta = await api.buscar_referencia(orden.referencia)
            resultados = respuesta.get('data', {}).get('data', [])
            if isinstance(resultados, list):
                coincidencia = next((x for x in resultados if isinstance(x, dict) and x.get('reference_code') == orden.referencia), None)
                if coincidencia:
                    procesar_respuesta_factura(orden, coincidencia)
                    sesion.commit()
        except (SandboxError, AttributeError):
            pass

@router.post('/orders', status_code=201)
async def crear(datos: OrdenNueva, idempotency_key: str = Header(min_length=8, max_length=120, pattern=r'^[A-Za-z0-9_-]+$'),
                sesion: Session = Depends(db)):
    verificar_configuracion()
    ahora = time.monotonic()
    _attempts[:] = [x for x in _attempts if ahora-x < 3600]
    if len(_attempts) >= 20: raise HTTPException(429, 'Límite de pruebas alcanzado; intenta más tarde.')
    _attempts.append(ahora)
    previa = sesion.scalar(select(OrdenSandbox).where(OrdenSandbox.idempotencia == idempotency_key))
    if previa:
        orden = obtener_orden(sesion, previa.id, datos.acceso)
    else:
        orden = OrdenSandbox(id=str(uuid.uuid4()), idempotencia=idempotency_key,
                             acceso_hash=hashlib.sha256(datos.acceso.encode()).hexdigest(),
                             referencia='RITMO-SBX-'+uuid.uuid4().hex.upper(),
                             estado='creating_payment', facturacion='waiting_payment', creado=datetime.now(timezone.utc).isoformat())
        sesion.add(orden)
        try: sesion.commit()
        except IntegrityError:
            sesion.rollback()
            previa = sesion.scalar(select(OrdenSandbox).where(OrdenSandbox.idempotencia == idempotency_key))
            if not previa: raise HTTPException(409, 'No se pudo registrar la orden.')
            orden = obtener_orden(sesion, previa.id, datos.acceso)
    if orden.estado != 'creating_payment': return mostrar(orden)
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            await FactusPaySandbox(http, os.environ['FACTUS_PAY_TOKEN']).crear_recaudo(orden.referencia, TOTAL, 900)
        orden.estado = 'awaiting_payment'; sesion.commit()
    except SandboxError as exc:
        if exc.status in (401, 403):
            detail = 'Factus Pay rechazó el token Sandbox. Revisa FACTUS_PAY_TOKEN.'
        elif exc.status == 422:
            detail = 'Factus Pay rechazó los datos de prueba (HTTP 422). Revisa la configuración del recaudo.'
        elif exc.status == 429:
            detail = 'Factus Pay alcanzó su límite de solicitudes. Intenta más tarde.'
        elif exc.status is None:
            detail = 'Factus Pay no confirmó el recaudo. Conserva esta orden y reintenta más tarde.'
        else:
            detail = f'Factus Pay no confirmó el recaudo (HTTP {exc.status}). Conserva esta orden.'
        raise HTTPException(503, detail) from None
    return mostrar(orden)

@router.get('/orders/{orden_id}')
async def estado(orden_id: str, x_order_key: str | None = Header(default=None), sesion: Session = Depends(db)):
    verificar_configuracion()
    orden = obtener_orden(sesion, orden_id, x_order_key)
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            if orden.estado in ('awaiting_payment', 'creating_payment'):
                pago = await FactusPaySandbox(http, os.environ['FACTUS_PAY_TOKEN']).consultar_recaudo(orden.referencia, TOTAL)
                if pago.get('status') == 'paid':
                    orden.estado = 'paid'; sesion.commit()
            if orden.estado == 'paid' and orden.facturacion != 'validated':
                await conciliar_factura(orden, sesion, http)
    except SandboxError:
        raise HTTPException(503, 'No fue posible consultar el pago Sandbox. Intenta de nuevo.') from None
    return mostrar(orden)

@router.get('/orders/{orden_id}/qr')
async def obtener_qr(orden_id: str, x_order_key: str | None = Header(default=None), sesion: Session = Depends(db)):
    verificar_configuracion()
    orden = obtener_orden(sesion, orden_id, x_order_key)
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            pago = await FactusPaySandbox(http, os.environ['FACTUS_PAY_TOKEN']).consultar_recaudo(orden.referencia, TOTAL)
        qr = pago.get('qr')
        if not isinstance(qr, str) or not qr.startswith('data:image/png;base64,'):
            raise HTTPException(409, 'QR Sandbox no disponible.')
        return {'qr': qr, 'estado': pago.get('status'), 'vence': pago.get('qr_expires_at')}
    except SandboxError:
        raise HTTPException(503, 'No se pudo consultar el QR Sandbox.') from None

@router.get('/orders/{orden_id}/invoice/pdf')
async def factura_pdf(orden_id: str, x_order_key: str | None = Header(default=None), sesion: Session = Depends(db)):
    verificar_configuracion()
    orden = obtener_orden(sesion, orden_id, x_order_key)
    if orden.facturacion != 'validated' or not orden.factura_numero:
        raise HTTPException(409, 'La factura Sandbox aún no está validada.')
    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            respuesta = await cliente_factus(http).descargar(orden.factura_numero, 'pdf')
        info = respuesta.get('data') or {}
        encoded = info.get('pdf_base_64_encoded')
        if not isinstance(encoded, str) or len(encoded) > 8_000_000: raise ValueError()
        contenido = base64.b64decode(encoded, validate=True)
        if not contenido.startswith(b'%PDF-'): raise ValueError()
        return Response(contenido, media_type='application/pdf', headers={'Cache-Control':'no-store', 'Content-Disposition':'attachment; filename="factura-sandbox.pdf"'})
    except (SandboxError, ValueError, binascii.Error, AttributeError):
        raise HTTPException(502, 'No se pudo descargar la factura Sandbox.') from None
