"""
Modelos de dados para o Sistema de Notificações

Estrutura:
- AlertaConfig: Configuração de um alerta (palavras-chave, filtros)
- Notificacao: Notificação individual gerada pelo sistema
- NotificacaoStats: Estatísticas de notificações
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TipoAlerta(str, Enum):
    """Tipos de alerta disponíveis"""
    PALAVRA_CHAVE = "palavra_chave"
    LISTA_CUSTOMIZADA = "lista_customizada"
    ESTADO = "estado"
    MODALIDADE = "modalidade"


class StatusNotificacao(str, Enum):
    """Status de uma notificação"""
    PENDENTE = "pendente"
    LIDA = "lida"
    ARQUIVADA = "arquivada"


class AlertaConfigBase(BaseModel):
    """Base para configuração de alerta"""
    nome: str = Field(..., min_length=1, max_length=100, description="Nome do alerta")
    tipo: TipoAlerta = Field(default=TipoAlerta.PALAVRA_CHAVE, description="Tipo do alerta")
    ativo: bool = Field(default=True, description="Se o alerta está ativo")
    
    # Filtros
    palavras_chave: List[str] = Field(default=[], description="Palavras-chave para busca")
    lista_customizada_id: Optional[str] = Field(default=None, description="ID da lista customizada")
    estados: List[str] = Field(default=[], description="Estados para filtrar (ex: ['SP', 'RJ'])")
    modalidades: List[str] = Field(default=[], description="Modalidades para filtrar")
    
    # Configurações
    frequencia_horas: int = Field(default=6, ge=1, le=24, description="Frequência de verificação em horas")
    
    # Email de notificação customizado por alerta
    email_notificacao: Optional[str] = Field(
        default=None, 
        pattern=r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$|^$',
        description="E-mail específico para receber notificações deste alerta (pode ser diferente do e-mail da conta)"
    )


class AlertaConfigCreate(AlertaConfigBase):
    """Schema para criar alerta"""
    pass


class AlertaConfigUpdate(BaseModel):
    """Schema para atualizar alerta"""
    nome: Optional[str] = None
    ativo: Optional[bool] = None
    palavras_chave: Optional[List[str]] = None
    lista_customizada_id: Optional[str] = None
    estados: Optional[List[str]] = None
    modalidades: Optional[List[str]] = None
    frequencia_horas: Optional[int] = None
    email_notificacao: Optional[str] = Field(
        default=None,
        description="E-mail específico para receber notificações deste alerta"
    )


class AlertaConfig(AlertaConfigBase):
    """Configuração completa de alerta com metadados"""
    id: str = Field(..., description="ID único do alerta")
    criado_em: datetime = Field(default_factory=datetime.now, description="Data de criação")
    atualizado_em: datetime = Field(default_factory=datetime.now, description="Data da última atualização")
    ultima_verificacao: Optional[datetime] = Field(default=None, description="Data da última verificação")
    total_notificacoes: int = Field(default=0, description="Total de notificações geradas")
    
    class Config:
        from_attributes = True


class NotificacaoBase(BaseModel):
    """Base para notificação"""
    alerta_id: str = Field(..., description="ID do alerta que gerou a notificação")
    licitacao_id: str = Field(..., description="ID da licitação relacionada")
    
    # Dados resumidos da licitação
    titulo: str = Field(..., description="Título da licitação")
    orgao: str = Field(default="N/A", description="Órgão licitante")
    estado: str = Field(default="N/A", description="Estado")
    modalidade: str = Field(default="N/A", description="Modalidade")
    data_limite: Optional[datetime] = Field(default=None, description="Data limite")
    link_origem: Optional[str] = Field(default=None, description="Link para a licitação")
    
    # Motivo do alerta
    motivo_match: str = Field(default="", description="Palavra/critério que gerou o match")


class NotificacaoCreate(NotificacaoBase):
    """Schema para criar notificação"""
    pass


class Notificacao(NotificacaoBase):
    """Notificação completa com metadados"""
    id: str = Field(..., description="ID único da notificação")
    status: StatusNotificacao = Field(default=StatusNotificacao.PENDENTE, description="Status da notificação")
    criado_em: datetime = Field(default_factory=datetime.now, description="Data de criação")
    lido_em: Optional[datetime] = Field(default=None, description="Data de leitura")
    
    class Config:
        from_attributes = True


class NotificacaoStats(BaseModel):
    """Estatísticas de notificações"""
    total_pendentes: int = Field(default=0, description="Total de notificações pendentes")
    total_lidas: int = Field(default=0, description="Total de notificações lidas")
    total_arquivadas: int = Field(default=0, description="Total de notificações arquivadas")
    total_alertas_ativos: int = Field(default=0, description="Total de alertas ativos")
    ultima_verificacao: Optional[datetime] = Field(default=None, description="Data da última verificação global")
    proxima_verificacao: Optional[datetime] = Field(default=None, description="Data da próxima verificação")


class NotificacaoListResponse(BaseModel):
    """Resposta para listagem de notificações"""
    notificacoes: List[Notificacao] = Field(default=[], description="Lista de notificações")
    total: int = Field(default=0, description="Total de notificações")
    pendentes: int = Field(default=0, description="Total pendentes")
    pagina: int = Field(default=1, description="Página atual")
    por_pagina: int = Field(default=20, description="Itens por página")


class AlertaListResponse(BaseModel):
    """Resposta para listagem de alertas"""
    alertas: List[AlertaConfig] = Field(default=[], description="Lista de alertas")
    total: int = Field(default=0, description="Total de alertas")
    ativos: int = Field(default=0, description="Total de alertas ativos")
