"""Consulta de catálogo Ticketmaster Discovery; no vende ni reserva entradas."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

# La API exige la clave en la URL. httpx registra URLs a nivel INFO por defecto.
logging.getLogger('httpx').setLevel(logging.WARNING)
router = APIRouter(prefix='/api/v1/ticketmaster', tags=['Ticketmaster'])
_lock = asyncio.Lock()
_cache: OrderedDict[tuple[str, str], tuple[float, dict[str, Any]]] = OrderedDict()
_last_request = 0.0
_requests: list[float] = []
_ENDPOINT = 'https://app.ticketmaster.com/discovery/v2/events.json'


def _evento(item: dict[str, Any]) -> dict[str, Any]:
    sedes = item.get('_embedded', {}).get('venues', [])
    sede = sedes[0] if sedes else {}
    fechas = item.get('dates', {}).get('start', {})
    precios = item.get('priceRanges') or []
    return {
        'id': item.get('id'), 'nombre': item.get('name'),
        'fecha_local': fechas.get('localDate'), 'hora_local': fechas.get('localTime'),
        'ciudad': sede.get('city', {}).get('name'), 'pais': sede.get('country', {}).get('name'),
        'recinto': sede.get('name'), 'url_ticketmaster': item.get('url'),
        'precios': [{'moneda': p.get('currency'), 'minimo': p.get('min'), 'maximo': p.get('max')} for p in precios],
    }


@router.get('/events')
async def eventos_ticketmaster(q: str = Query(default='', max_length=80),
                               pais: str = Query(default='', max_length=2, pattern=r'^([A-Za-z]{2})?$')):
    token = os.getenv('TICKETMASTER_API_KEY', '').strip()
    if not token:
        raise HTTPException(503, 'Falta configurar TICKETMASTER_API_KEY en el backend.')
    key = (q.strip().casefold(), pais.upper())
    global _last_request
    # Caché y acceso serializado por proceso: protege contra ráfagas accidentales.
    async with _lock:
        ahora = time.monotonic()
        cached = _cache.get(key)
        if cached and ahora - cached[0] < 300:
            _cache.move_to_end(key)
            return cached[1]
        _requests[:] = [t for t in _requests if ahora - t < 3600]
        if len(_requests) >= 200:
            raise HTTPException(429, 'Límite temporal de consultas alcanzado. Intenta más tarde.')
        await asyncio.sleep(max(0, 0.25 - (ahora - _last_request)))
        _last_request = time.monotonic()
        _requests.append(_last_request)
        params = {'apikey': token, 'classificationName': 'music', 'size': 20, 'sort': 'date,asc',
                  'startDateTime': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}
        if q.strip(): params['keyword'] = q.strip()
        if pais: params['countryCode'] = pais.upper()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                respuesta = await client.get(_ENDPOINT, params=params)
        except httpx.RequestError:
            raise HTTPException(502, 'No fue posible contactar a Ticketmaster.') from None
        if respuesta.status_code == 429:
            raise HTTPException(429, 'Ticketmaster alcanzó su límite de solicitudes. Intenta más tarde.')
        if respuesta.status_code in (401, 403):
            raise HTTPException(502, 'Ticketmaster rechazó la clave. Verifica la configuración del servidor.')
        if respuesta.is_error:
            raise HTTPException(502, 'Ticketmaster no pudo procesar la consulta.')
        try:
            data = respuesta.json()
            events = data.get('_embedded', {}).get('events', [])
            result = {'origen': 'Ticketmaster Discovery', 'eventos': [_evento(x) for x in events],
                      'aviso': 'Catálogo informativo; no permite reservar ni comprar entradas.'}
        except (ValueError, TypeError, AttributeError, KeyError):
            raise HTTPException(502, 'Ticketmaster devolvió una respuesta inválida.') from None
        _cache[key] = (time.monotonic(), result)
        while len(_cache) > 128: _cache.popitem(last=False)
        return result
