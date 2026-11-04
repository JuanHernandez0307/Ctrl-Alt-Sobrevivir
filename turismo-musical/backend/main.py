import base64
import hashlib
import hmac
import io
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Literal

import qrcode
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, Field, field_validator
from reportlab.pdfgen import canvas
from sqlalchemy import String, Text, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from backend.ticketmaster import router as ticketmaster_router

load_dotenv()
MODO = os.getenv('APP_MODE', 'demo')
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./turismo.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql+psycopg://', 1)
elif DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://', 1)
engine = create_engine(DATABASE_URL, connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Orden(Base):
    __tablename__ = 'ordenes'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    idempotencia: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    acceso_hash: Mapped[str] = mapped_column(String(64))
    referencia: Mapped[str] = mapped_column(String(60), unique=True)
    evento_id: Mapped[str] = mapped_column(String(50))
    cantidad: Mapped[int]
    total: Mapped[str] = mapped_column(String(30))
    estado: Mapped[str] = mapped_column(String(30))
    creado: Mapped[str] = mapped_column(String(40))
    vence: Mapped[str] = mapped_column(String(40))
    documento_tipo: Mapped[str] = mapped_column(String(20))
    documento: Mapped[str] = mapped_column(String(40))
    nombre: Mapped[str] = mapped_column(String(120))
    correo: Mapped[str] = mapped_column(String(254))
    historial: Mapped[str] = mapped_column(Text, default='created,awaiting_payment')

app = FastAPI(title='Ritmo - demo turismo musical', version='0.1.0')
app.include_router(ticketmaster_router)
app.add_middleware(CORSMiddleware, allow_origins=[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:5173').split(',') if x.strip()], allow_methods=['GET','POST'], allow_headers=['Content-Type','Idempotency-Key','X-Order-Key'])

@app.on_event('startup')
def inicio():
    Base.metadata.create_all(engine)

def db():
    with SessionLocal() as sesion:
        yield sesion

EVENTOS = [
    {'id':'demo-bogota','nombre':'Noches de Bogotá','artista':'Colectivo Sonoro','ciudad':'Bogotá','pais':'Colombia','recinto':'Escenario Central','fecha':'2027-08-14T19:00:00-05:00','precio':'119000.00','color':'violet','etiqueta':'INDIE / POP'},
    {'id':'demo-medellin','nombre':'Medellín en vivo','artista':'Las Montañas','ciudad':'Medellín','pais':'Colombia','recinto':'Jardín Musical','fecha':'2027-09-18T19:00:00-05:00','precio':'89000.00','color':'orange','etiqueta':'ALTERNATIVA'},
    {'id':'demo-cali','nombre':'Ritmos del Pacífico','artista':'Ensamble Aurora','ciudad':'Cali','pais':'Colombia','recinto':'Plaza Cultural','fecha':'2027-10-09T18:00:00-05:00','precio':'75000.00','color':'pink','etiqueta':'FESTIVAL'},
]
# Tasas ilustrativas: no se conectan a un proveedor real.
TASAS = {'COP':Decimal('1'), 'USD':Decimal('0.00025'), 'EUR':Decimal('0.00023'), 'GBP':Decimal('0.00020'), 'JPY':Decimal('0.038')}

class Cliente(BaseModel):
    tipo: Literal['CC','NIT','PASAPORTE']
    documento: str = Field(min_length=3, max_length=30)
    nombre: str = Field(min_length=2, max_length=120)
    correo: EmailStr
    acepta_datos: Literal[True]
    @field_validator('documento')
    @classmethod
    def validar_documento(cls, valor: str):
        if not valor.isalnum() or not valor.isascii():
            raise ValueError('Usa letras y números sin espacios ni símbolos')
        return valor

class SolicitudOrden(BaseModel):
    evento_id: str
    cantidad: int = Field(ge=1, le=6)
    cliente: Cliente
    acceso: str = Field(min_length=32, max_length=128, pattern=r'^[A-Za-z0-9_-]+$')

class Cotizacion(BaseModel):
    evento_id: str
    cantidad: int = Field(ge=1, le=6)

def demo():
    if MODO != 'demo':
        raise HTTPException(503, 'El modo real aún no está implementado ni validado. Usa APP_MODE=demo.')

def evento_por_id(identificador: str):
    evento = next((e for e in EVENTOS if e['id'] == identificador), None)
    if not evento:
        raise HTTPException(404, 'Evento no encontrado')
    return evento

def cotizar(evento_id: str, cantidad: int):
    evento = evento_por_id(evento_id)
    try:
        total = (Decimal(evento['precio']) * cantidad).quantize(Decimal('0.01'))
    except (InvalidOperation, TypeError):
        raise HTTPException(500, 'Precio no disponible')
    if not Decimal('10000') <= total <= Decimal('12100000'):
        raise HTTPException(422, 'El total debe estar entre 10.000 y 12.100.000 COP')
    conversiones = {moneda:str((total * tasa).quantize(Decimal('1') if moneda in ('COP','JPY') else Decimal('0.01'), rounding=ROUND_HALF_UP)) for moneda,tasa in TASAS.items()}
    return {'evento':evento,'cantidad':cantidad,'total_cop':str(total),'conversiones':conversiones,'tasas_demostracion':True}

def buscar_orden(sesion: Session, identificador: str, acceso: str | None):
    orden = sesion.get(Orden, identificador)
    digest = hashlib.sha256((acceso or '').encode()).hexdigest()
    if not orden or not hmac.compare_digest(orden.acceso_hash, digest):
        raise HTTPException(404, 'Orden no encontrada')
    return orden

def salida(orden: Orden):
    return {'id':orden.id,'referencia':orden.referencia,'evento':evento_por_id(orden.evento_id),'cantidad':orden.cantidad,'total_cop':orden.total,'estado':orden.estado,'vence':orden.vence,'historial':orden.historial.split(','),'modo':'demo','aviso':'Boleto de demostración. No es un boleto oficial de Ticketmaster.'}

@app.get('/api/v1/health')
def salud():
    return {'status':'ok','modo':MODO,'base_datos':engine.url.get_backend_name(), 'catalogo_ticketmaster_configurado':bool(os.getenv('TICKETMASTER_API_KEY')), 'factus_sandbox_configurado':all(os.getenv(k) for k in ('FACTUS_PAY_TOKEN','FACTUS_USERNAME','FACTUS_PASSWORD','FACTUS_CLIENT_ID','FACTUS_CLIENT_SECRET'))}

@app.get('/api/v1/events')
def eventos(q: str = '', pais: str = ''):
    demo()
    termino = q.strip().casefold()
    return {'eventos':[e for e in EVENTOS if termino in f"{e['nombre']} {e['artista']} {e['ciudad']}".casefold() and pais.casefold() in e['pais'].casefold()], 'origen':'demo', 'tasas_demostracion':True}

@app.get('/api/v1/events/{evento_id}')
def detalle(evento_id: str):
    demo()
    return cotizar(evento_id, 1)

@app.post('/api/v1/quotes')
def presupuesto(datos: Cotizacion):
    demo()
    return cotizar(datos.evento_id, datos.cantidad)

@app.post('/api/v1/orders', status_code=201)
def crear_orden(datos: SolicitudOrden, idempotency_key: str = Header(min_length=8,max_length=120,pattern=r'^[A-Za-z0-9_-]+$'), sesion: Session = Depends(db)):
    demo()
    if datos.cliente.tipo in ('CC','NIT') and not datos.cliente.documento.isdigit():
        raise HTTPException(422, 'La cédula y el NIT deben ser numéricos')
    previa = sesion.scalar(select(Orden).where(Orden.idempotencia == idempotency_key))
    if previa:
        return salida(buscar_orden(sesion, previa.id, datos.acceso))
    importe = cotizar(datos.evento_id, datos.cantidad)['total_cop']
    ahora = datetime.now(timezone.utc)
    orden = Orden(id=str(uuid.uuid4()), idempotencia=idempotency_key, acceso_hash=hashlib.sha256(datos.acceso.encode()).hexdigest(), referencia='DEMO-'+uuid.uuid4().hex[:12].upper(), evento_id=datos.evento_id, cantidad=datos.cantidad, total=importe, estado='awaiting_payment', creado=ahora.isoformat(), vence=(ahora+timedelta(minutes=15)).isoformat(), documento_tipo=datos.cliente.tipo, documento=datos.cliente.documento, nombre=datos.cliente.nombre, correo=str(datos.cliente.correo))
    sesion.add(orden)
    try:
        sesion.commit()
    except IntegrityError:
        sesion.rollback()
        previa = sesion.scalar(select(Orden).where(Orden.idempotencia == idempotency_key))
        if not previa:
            raise HTTPException(409, 'No se pudo registrar la orden')
        return salida(buscar_orden(sesion, previa.id, datos.acceso))
    return salida(orden)

@app.get('/api/v1/orders/{orden_id}')
def ver_orden(orden_id: str, x_order_key: str | None = Header(default=None), sesion: Session = Depends(db)):
    demo()
    orden = buscar_orden(sesion, orden_id, x_order_key)
    if orden.estado == 'awaiting_payment' and datetime.now(timezone.utc) > datetime.fromisoformat(orden.vence):
        orden.estado = 'payment_expired'; orden.historial += ',payment_expired'; sesion.commit()
    return salida(orden)

@app.post('/api/v1/orders/{orden_id}/simulate-payment')
def simular(orden_id: str, x_order_key: str | None = Header(default=None), sesion: Session = Depends(db)):
    demo()
    orden = buscar_orden(sesion, orden_id, x_order_key)
    if orden.estado == 'completed':
        return salida(orden)
    if orden.estado != 'awaiting_payment' or datetime.now(timezone.utc) > datetime.fromisoformat(orden.vence):
        raise HTTPException(409, 'La orden no puede pagarse: venció o cambió de estado')
    orden.estado = 'completed'; orden.historial += ',paid,invoicing,completed'; sesion.commit()
    return salida(orden)

@app.get('/api/v1/orders/{orden_id}/qr')
def qr_demo(orden_id: str, x_order_key: str | None = Header(default=None), sesion: Session = Depends(db)):
    demo()
    orden = buscar_orden(sesion, orden_id, x_order_key)
    imagen = qrcode.make('DEMO SIN PAGO REAL: '+orden.referencia)
    salida_png = io.BytesIO(); imagen.save(salida_png, format='PNG'); salida_png.seek(0)
    return StreamingResponse(salida_png, media_type='image/png', headers={'Cache-Control':'no-store'})

@app.get('/api/v1/orders/{orden_id}/ticket')
def ticket(orden_id: str, x_order_key: str | None = Header(default=None), sesion: Session = Depends(db)):
    demo()
    orden = buscar_orden(sesion, orden_id, x_order_key)
    if orden.estado != 'completed':
        raise HTTPException(409, 'El boleto estará disponible al completar la simulación')
    buffer = io.BytesIO(); pdf = canvas.Canvas(buffer)
    pdf.setFont('Helvetica-Bold', 20); pdf.drawString(48, 760, 'RITMO - BOLETO DEMO')
    pdf.setFont('Helvetica', 12); pdf.drawString(48, 725, 'No es un boleto oficial de Ticketmaster.')
    pdf.drawString(48, 700, 'Evento: '+evento_por_id(orden.evento_id)['nombre'])
    pdf.drawString(48, 680, 'Referencia: '+orden.referencia)
    pdf.drawString(48, 660, 'Cantidad: '+str(orden.cantidad))
    pdf.drawString(48, 640, 'Importe simulado: COP '+orden.total)
    pdf.drawString(48, 610, 'Este documento no constituye una factura electronica.')
    pdf.showPage(); pdf.save(); buffer.seek(0)
    return StreamingResponse(buffer, media_type='application/pdf', headers={'Content-Disposition':'attachment; filename="boleto-demo.pdf"','Cache-Control':'no-store'})

# El router registra su tabla antes de que se ejecute el evento de inicio.
from backend.sandbox_checkout import router as sandbox_router
app.include_router(sandbox_router)
