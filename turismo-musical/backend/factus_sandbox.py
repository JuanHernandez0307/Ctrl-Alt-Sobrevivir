"""Clientes aislados para Factus Pay y Factus Facturación en Sandbox.

Este módulo aún no está conectado al flujo de órdenes. Antes de hacerlo se
necesitan almacenamiento persistente, datos fiscales y pruebas de integración.
"""
from __future__ import annotations

import asyncio
import os
import time
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote

import httpx

PAY_BASE = 'https://pay-api-sandbox.factus.com.co'
FACTUS_BASE = 'https://api-sandbox.factus.com.co'


class SandboxError(Exception):
    """Error sin credenciales ni datos del cliente en el mensaje."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


async def _request(client: httpx.AsyncClient, method: str, url: str, *,
                   safe_retry: bool = False, **kwargs: Any) -> dict[str, Any]:
    # Solo GET o acciones cuya idempotencia esté garantizada por el proveedor.
    attempts = 3 if safe_retry else 1
    for attempt in range(attempts):
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.RequestError as exc:
            if attempt + 1 < attempts:
                await asyncio.sleep(0.5 * 2**attempt)
                continue
            raise SandboxError('No se pudo contactar el servicio Sandbox; concilia la referencia antes de reintentar.') from exc
        if response.status_code == 429 and attempt + 1 < attempts:
            try:
                delay = min(max(float(response.headers.get('Retry-After', '1')), 0.0), 10.0)
            except ValueError:
                delay = 1.0
            await asyncio.sleep(delay)
            continue
        if response.is_error:
            raise SandboxError('El servicio Sandbox rechazó la solicitud.', response.status_code)
        try:
            result = response.json()
        except ValueError as exc:
            raise SandboxError('El servicio Sandbox devolvió una respuesta inválida.') from exc
        if not isinstance(result, dict):
            raise SandboxError('El servicio Sandbox devolvió un formato inesperado.')
        return result
    raise SandboxError('El servicio Sandbox no respondió.')


class FactusPaySandbox:
    def __init__(self, client: httpx.AsyncClient, token: str):
        if not token.strip():
            raise SandboxError('Falta FACTUS_PAY_TOKEN en el servidor.')
        self.client = client
        self.headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}

    async def crear_recaudo(self, referencia: str, total_cop: str, segundos: int = 900) -> dict[str, Any]:
        if not referencia or len(referencia) > 100 or segundos <= 0:
            raise ValueError('Referencia o expiración inválida.')
        try:
            monto = Decimal(total_cop)
            if not monto.is_finite() or not Decimal('1000') <= monto <= Decimal('12100000') or monto.as_tuple().exponent < -2:
                raise ValueError('Monto fuera de los límites de Factus Pay Sandbox.')
        except InvalidOperation as exc:
            raise ValueError('Monto inválido.') from exc
        # La API documenta idempotencia al repetir exactamente referencia y monto.
        result = await _request(self.client, 'POST', f'{PAY_BASE}/v1/collections',
                                safe_retry=True, headers=self.headers,
                                json={'reference_code': referencia, 'amount': str(monto), 'expiration': segundos})
        return self._comprobar(result, referencia, monto)

    async def consultar_recaudo(self, referencia: str, total_cop: str) -> dict[str, Any]:
        result = await _request(self.client, 'GET', f'{PAY_BASE}/v1/collections/{quote(referencia, safe="")}',
                                safe_retry=True, headers=self.headers)
        return self._comprobar(result, referencia, Decimal(total_cop))

    @staticmethod
    def _comprobar(result: dict[str, Any], referencia: str, monto: Decimal) -> dict[str, Any]:
        data = result.get('data')
        try:
            if not isinstance(data, dict) or data.get('reference_code') != referencia or Decimal(str(data.get('amount'))) != monto:
                raise SandboxError('La referencia o el monto del recaudo no coincide.')
        except InvalidOperation as exc:
            raise SandboxError('El recaudo tiene un monto inválido.') from exc
        return data


class FactusSandbox:
    def __init__(self, client: httpx.AsyncClient, *, client_id: str, client_secret: str, username: str, password: str):
        if not all((client_id, client_secret, username, password)):
            raise SandboxError('Faltan credenciales de Factus Facturación Sandbox en el servidor.')
        self.client = client
        self.credentials = {'client_id': client_id, 'client_secret': client_secret}
        self.password_credentials = {'username': username, 'password': password}
        self.access_token: str | None = None
        self.refresh_token: str | None = None
        self.expires_at = 0.0
        self.lock = asyncio.Lock()

    async def _token(self, force: bool = False, previous: str | None = None) -> str:
        async with self.lock:
            if self.access_token and time.monotonic() < self.expires_at and (not force or self.access_token != previous):
                return self.access_token
            data = {**self.credentials}
            if self.refresh_token:
                data.update(grant_type='refresh_token', refresh_token=self.refresh_token)
            else:
                data.update(grant_type='password', **self.password_credentials)
            try:
                result = await _request(self.client, 'POST', f'{FACTUS_BASE}/oauth/token', data=data,
                                        headers={'Accept': 'application/json'})
            except SandboxError as exc:
                if not self.refresh_token or exc.status not in (400, 401):
                    raise
                self.refresh_token = None
                data = {**self.credentials, **self.password_credentials, 'grant_type': 'password'}
                result = await _request(self.client, 'POST', f'{FACTUS_BASE}/oauth/token', data=data,
                                        headers={'Accept': 'application/json'})
            token = result.get('access_token')
            if not isinstance(token, str) or not token:
                raise SandboxError('Factus no devolvió un token válido.')
            try:
                lifetime = int(result['expires_in'])
            except (KeyError, ValueError, TypeError) as exc:
                raise SandboxError('Factus no indicó la vigencia del token.') from exc
            self.access_token = token
            self.refresh_token = result.get('refresh_token')
            self.expires_at = time.monotonic() + max(lifetime - 60, 0)
            return token

    async def _authenticated(self, method: str, path: str, *, safe_retry: bool = False, **kwargs: Any) -> dict[str, Any]:
        token = await self._token()
        for attempt in range(2):
            try:
                return await _request(self.client, method, FACTUS_BASE + path, safe_retry=safe_retry,
                                      headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'}, **kwargs)
            except SandboxError as exc:
                if exc.status != 401 or attempt:
                    raise
                token = await self._token(force=True, previous=token)
        raise SandboxError('No fue posible autenticar con Factus.')

    async def validar_factura(self, factura: dict[str, Any]) -> dict[str, Any]:
        if not all(factura.get(k) for k in ('reference_code', 'customer', 'items', 'payment_details')):
            raise ValueError('Faltan referencia, cliente, ítems o detalles de pago.')
        # Jamás reintentar automáticamente un POST ambiguo: consultar la referencia.
        return await self._authenticated('POST', '/v2/bills/validate', json=factura)

    async def buscar_referencia(self, referencia: str) -> dict[str, Any]:
        return await self._authenticated('GET', '/v2/bills', safe_retry=True,
                                         params={'filter[reference_code]': referencia})

    async def descargar(self, numero: str, formato: str) -> dict[str, Any]:
        if formato not in ('pdf', 'xml'):
            raise ValueError('Formato no soportado.')
        return await self._authenticated('GET', f'/v2/bills/{quote(numero, safe="")}/download-{formato}', safe_retry=True)


def desde_entorno(client: httpx.AsyncClient) -> tuple[FactusPaySandbox, FactusSandbox]:
    return (FactusPaySandbox(client, os.getenv('FACTUS_PAY_TOKEN', '')),
            FactusSandbox(client, client_id=os.getenv('FACTUS_CLIENT_ID', ''),
                          client_secret=os.getenv('FACTUS_CLIENT_SECRET', ''),
                          username=os.getenv('FACTUS_USERNAME', ''), password=os.getenv('FACTUS_PASSWORD', '')))
