"""
Modelo de Alertas - P5

Define a estrutura de dados para alertas de email.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class FrequenciaAlerta(str, Enum):
    DIARIO = "diario"
    SEMANAL = "semanal"


class FiltrosAlerta(BaseModel):
    """Filtros opcionais para o alerta"""
    estados: Optional[List[str]] = None
    esfera: Optional[str] = None
    apenas_saude: bool = True
    excluir_credenciamentos: bool = False


class AlertaCreate(BaseModel):
    """Schema para criação de alerta"""
    email: EmailStr
    termo: str = Field(..., min_length=2, max_length=100, description="Termo de busca")
    frequencia: FrequenciaAlerta = FrequenciaAlerta.DIARIO
    filtros: Optional[FiltrosAlerta] = None


class AlertaUpdate(BaseModel):
    """Schema para atualização de alerta"""
    ativo: Optional[bool] = None
    frequencia: Optional[FrequenciaAlerta] = None
    filtros: Optional[FiltrosAlerta] = None


class AlertaResponse(BaseModel):
    """Schema de resposta do alerta"""
    id: str
    email: str
    termo: str
    frequencia: str
    ativo: bool
    filtros: Optional[FiltrosAlerta] = None
    ultimo_envio: Optional[str] = None
    total_enviados: int = 0
    created_at: str


class AlertaDB(BaseModel):
    """Schema completo do alerta no banco"""
    id: str
    email: str
    termo: str
    frequencia: str
    ativo: bool = True
    filtros: dict = {}
    ultimo_envio: Optional[datetime] = None
    editais_enviados: List[str] = []  # IDs dos editais já enviados
    total_enviados: int = 0
    created_at: datetime
    updated_at: Optional[datetime] = None
