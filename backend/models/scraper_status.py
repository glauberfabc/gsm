"""
Modelo para status e saúde dos scrapers
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict


class ScraperExecution(BaseModel):
    """Registro de execução de um scraper"""
    fonte: str = Field(..., description="Nome da fonte (PNCP, ComprasNet, BEC SP, etc.)")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(), description="Data/hora da execução")
    status: str = Field(..., description="Status: success, error, timeout")
    resultados_count: int = Field(default=0, description="Número de resultados retornados")
    termo_busca: Optional[str] = Field(None, description="Termo pesquisado")
    tempo_execucao_ms: Optional[int] = Field(None, description="Tempo de execução em ms")
    erro_mensagem: Optional[str] = Field(None, description="Mensagem de erro se falhou")
    
    class Config:
        json_schema_extra = {
            "example": {
                "fonte": "PNCP",
                "timestamp": "2024-12-10T18:00:00",
                "status": "success",
                "resultados_count": 15,
                "termo_busca": "insulina",
                "tempo_execucao_ms": 2500,
                "erro_mensagem": None
            }
        }


class ScraperHealthStatus(BaseModel):
    """Status de saúde de um scraper"""
    fonte: str
    status: str  # UP, DOWN, DEGRADED
    ultima_execucao_sucesso: Optional[datetime] = None
    ultima_execucao_erro: Optional[datetime] = None
    total_execucoes_24h: int = 0
    total_sucessos_24h: int = 0
    total_erros_24h: int = 0
    total_resultados_24h: int = 0
    taxa_sucesso_24h: float = 0.0
    tempo_medio_execucao_ms: Optional[int] = None
    ultima_mensagem_erro: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "fonte": "PNCP",
                "status": "UP",
                "ultima_execucao_sucesso": "2024-12-10T18:30:00",
                "ultima_execucao_erro": None,
                "total_execucoes_24h": 145,
                "total_sucessos_24h": 142,
                "total_erros_24h": 3,
                "total_resultados_24h": 2150,
                "taxa_sucesso_24h": 97.9,
                "tempo_medio_execucao_ms": 2300,
                "ultima_mensagem_erro": None
            }
        }


class SystemHealthStatus(BaseModel):
    """Status geral de saúde do sistema"""
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    status_geral: str  # HEALTHY, DEGRADED, DOWN
    total_fontes: int
    fontes_up: int
    fontes_down: int
    fontes_degraded: int
    scrapers: List[ScraperHealthStatus]
    
    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2024-12-10T18:30:00",
                "status_geral": "HEALTHY",
                "total_fontes": 3,
                "fontes_up": 3,
                "fontes_down": 0,
                "fontes_degraded": 0,
                "scrapers": []
            }
        }
