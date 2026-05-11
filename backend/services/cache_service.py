"""
Serviço de Cache em Memória com TTL (Time-To-Live)

Implementa cache simples para otimizar buscas repetidas
e reduzir chamadas a APIs externas lentas.
"""

from datetime import datetime, timedelta
from typing import Any, Optional
import hashlib
import json
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """
    Cache em memória com TTL para resultados de busca
    
    Características:
    - TTL configurável (padrão: 10 minutos)
    - Chave gerada automaticamente a partir dos parâmetros
    - Limpeza automática de entradas expiradas
    - Thread-safe para uso em ambiente async
    """
    
    def __init__(self, default_ttl_minutes: int = 10):
        """
        Inicializa o serviço de cache
        
        Args:
            default_ttl_minutes: Tempo de vida padrão em minutos
        """
        self.cache = {}
        self.default_ttl = timedelta(minutes=default_ttl_minutes)
        logger.info(f"🗄️ Cache Service iniciado (TTL: {default_ttl_minutes} min)")
    
    def _generate_key(self, **params) -> str:
        """
        Gera chave única baseada nos parâmetros de busca
        
        Args:
            **params: Parâmetros da busca
            
        Returns:
            Hash MD5 dos parâmetros
        """
        # Ordenar e serializar parâmetros
        sorted_params = sorted(params.items())
        params_str = json.dumps(sorted_params, sort_keys=True)
        
        # Gerar hash
        key = hashlib.md5(params_str.encode()).hexdigest()
        return key
    
    def get(self, **params) -> Optional[Any]:
        """
        Busca valor no cache
        
        Args:
            **params: Parâmetros da busca
            
        Returns:
            Valor em cache ou None se não encontrado/expirado
        """
        key = self._generate_key(**params)
        
        if key not in self.cache:
            logger.debug(f"❌ Cache MISS: {key[:8]}...")
            return None
        
        # Verificar expiração
        entry = self.cache[key]
        if datetime.now() > entry['expires_at']:
            logger.debug(f"⏰ Cache EXPIRED: {key[:8]}...")
            del self.cache[key]
            return None
        
        logger.info(f"✅ Cache HIT: {key[:8]}... (age: {self._get_age(entry)}s)")
        return entry['value']
    
    def set(self, value: Any, ttl_minutes: Optional[int] = None, **params):
        """
        Armazena valor no cache
        
        Args:
            value: Valor a ser armazenado
            ttl_minutes: TTL customizado (opcional)
            **params: Parâmetros da busca (usados como chave)
        """
        key = self._generate_key(**params)
        
        # Calcular expiração
        ttl = timedelta(minutes=ttl_minutes) if ttl_minutes else self.default_ttl
        expires_at = datetime.now() + ttl
        
        # Armazenar
        self.cache[key] = {
            'value': value,
            'expires_at': expires_at,
            'created_at': datetime.now()
        }
        
        logger.info(f"💾 Cache SET: {key[:8]}... (TTL: {ttl.total_seconds():.0f}s)")
    
    def clear(self):
        """Limpa todo o cache"""
        count = len(self.cache)
        self.cache.clear()
        logger.info(f"🗑️ Cache limpo: {count} entradas removidas")
    
    def cleanup_expired(self):
        """Remove entradas expiradas do cache"""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self.cache.items()
            if now > entry['expires_at']
        ]
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.info(f"🧹 Cache cleanup: {len(expired_keys)} entradas expiradas removidas")
    
    def get_stats(self) -> dict:
        """
        Retorna estatísticas do cache
        
        Returns:
            Dict com estatísticas
        """
        now = datetime.now()
        
        total_entries = len(self.cache)
        expired_entries = sum(
            1 for entry in self.cache.values()
            if now > entry['expires_at']
        )
        active_entries = total_entries - expired_entries
        
        # Calcular idade média
        if active_entries > 0:
            ages = [
                (now - entry['created_at']).total_seconds()
                for entry in self.cache.values()
                if now <= entry['expires_at']
            ]
            avg_age = sum(ages) / len(ages)
        else:
            avg_age = 0
        
        return {
            'total_entries': total_entries,
            'active_entries': active_entries,
            'expired_entries': expired_entries,
            'avg_age_seconds': round(avg_age, 2),
            'ttl_seconds': self.default_ttl.total_seconds()
        }
    
    def _get_age(self, entry: dict) -> int:
        """Retorna idade da entrada em segundos"""
        age = (datetime.now() - entry['created_at']).total_seconds()
        return int(age)


# Instância global do cache (singleton)
search_cache = CacheService(default_ttl_minutes=10)
