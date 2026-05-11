"""
Smart Cache Service - Cache Inteligente com TTL 24h
Para endpoints de analise de mercado (LMR, ANVISA busca medicamento).

Caracteristicas:
- TTL padrao de 24 horas (1440 minutos)
- Chaves baseadas em hash MD5 dos parametros
- Invalidacao manual via clear() ou clear_namespace()
- Compativel com o cache_service.py existente (10min para buscas rapidas)
- Stats detalhadas por namespace
"""

from datetime import datetime, timedelta
from typing import Any, Optional
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

TTL_24H = 1440  # minutos


class SmartCacheService:
    def __init__(self, default_ttl_minutes: int = TTL_24H):
        self._store = {}
        self._default_ttl = timedelta(minutes=default_ttl_minutes)
        self._hits = 0
        self._misses = 0
        logger.info(f"SmartCache iniciado (TTL: {default_ttl_minutes} min / {default_ttl_minutes / 60:.0f}h)")

    def _key(self, namespace: str, **params) -> str:
        sorted_params = sorted((k, v) for k, v in params.items() if v is not None)
        raw = f"{namespace}:{json.dumps(sorted_params, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, namespace: str, **params) -> Optional[Any]:
        key = self._key(namespace, **params)
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        if datetime.now() > entry['expires_at']:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return entry['value']

    def set(self, value: Any, namespace: str, ttl_minutes: Optional[int] = None, **params):
        key = self._key(namespace, **params)
        ttl = timedelta(minutes=ttl_minutes) if ttl_minutes else self._default_ttl
        self._store[key] = {
            'value': value,
            'expires_at': datetime.now() + ttl,
            'created_at': datetime.now(),
            'namespace': namespace,
        }

    def clear(self):
        count = len(self._store)
        self._store.clear()
        self._hits = 0
        self._misses = 0
        logger.info(f"SmartCache limpo: {count} entradas removidas")
        return count

    def clear_namespace(self, namespace: str) -> int:
        keys_to_remove = [k for k, v in self._store.items() if v.get('namespace') == namespace]
        for k in keys_to_remove:
            del self._store[k]
        logger.info(f"SmartCache namespace '{namespace}' limpo: {len(keys_to_remove)} entradas")
        return len(keys_to_remove)

    def get_stats(self) -> dict:
        now = datetime.now()
        total = len(self._store)
        expired = sum(1 for e in self._store.values() if now > e['expires_at'])
        active = total - expired

        namespaces = {}
        for entry in self._store.values():
            ns = entry.get('namespace', 'unknown')
            namespaces[ns] = namespaces.get(ns, 0) + 1

        total_requests = self._hits + self._misses
        hit_rate = round((self._hits / total_requests * 100), 1) if total_requests > 0 else 0

        return {
            'total_entries': total,
            'active_entries': active,
            'expired_entries': expired,
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate_percent': hit_rate,
            'ttl_hours': self._default_ttl.total_seconds() / 3600,
            'namespaces': namespaces,
        }


# Instancia global (24h TTL)
smart_cache = SmartCacheService(default_ttl_minutes=TTL_24H)
