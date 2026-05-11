"""
Modelo de Dados: SavedSearch (Busca Salva)
Sistema de Notificações P1 - GSM Buscador de Editais

Este modelo representa uma busca salva pelo usuário que será
monitorada periodicamente pelo sistema de notificações.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from uuid import uuid4


class SavedSearchFilters(BaseModel):
    """Filtros aplicados à busca salva"""
    apenas_futuras: bool = True
    apenas_saude: bool = True
    apenas_urgentes: bool = False
    categorias_saude: List[str] = []  # ["hospitalar", "medicamentos", "laboratorio"]
    esfera_filtro: Optional[str] = None  # "Federal", "Estadual", "Municipal"
    status_filtro: Optional[str] = None  # "Ativa", "Encerrada"
    fontes: List[str] = []  # ["PNCP-OFICIAL", "PORTAL", "SP-TCE"]


class SavedSearchCreate(BaseModel):
    """Schema para criação de busca salva"""
    nome: str = Field(..., min_length=1, max_length=100, description="Nome amigável da busca")
    termo_busca: str = Field(..., min_length=1, max_length=200, description="Termo de busca")
    filtros: SavedSearchFilters = Field(default_factory=SavedSearchFilters)
    notificacoes_ativas: bool = True
    frequencia_verificacao: str = "diario"  # "diario", "semanal", "tempo_real"
    email_notificacao: Optional[str] = None


class SavedSearchUpdate(BaseModel):
    """Schema para atualização de busca salva"""
    nome: Optional[str] = Field(None, min_length=1, max_length=100)
    termo_busca: Optional[str] = Field(None, min_length=1, max_length=200)
    filtros: Optional[SavedSearchFilters] = None
    notificacoes_ativas: Optional[bool] = None
    frequencia_verificacao: Optional[str] = None
    email_notificacao: Optional[str] = None


class SavedSearch(BaseModel):
    """
    Modelo completo de Busca Salva para MongoDB
    
    Campos:
    - id: Identificador único (UUID)
    - user_id: ID do usuário (ou "default" se não autenticado)
    - nome: Nome amigável dado pelo usuário
    - termo_busca: Termo de busca (ex: "insulina", "hospital")
    - filtros: Objeto com todos os filtros aplicados
    - notificacoes_ativas: Se deve enviar notificações
    - frequencia_verificacao: Quando verificar ("diario", "semanal")
    - email_notificacao: Email para envio (opcional)
    - criado_em: Data de criação
    - atualizado_em: Data da última atualização
    - ultima_verificacao: Data da última verificação pelo scheduler
    - total_notificacoes: Contador de notificações enviadas
    - ultimas_licitacoes_ids: IDs das últimas licitações notificadas (evita duplicatas)
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = "default"
    nome: str
    termo_busca: str
    filtros: SavedSearchFilters = Field(default_factory=SavedSearchFilters)
    
    # Configurações de notificação
    notificacoes_ativas: bool = True
    frequencia_verificacao: str = "diario"
    email_notificacao: Optional[str] = None
    
    # Metadados
    criado_em: datetime = Field(default_factory=datetime.utcnow)
    atualizado_em: datetime = Field(default_factory=datetime.utcnow)
    ultima_verificacao: Optional[datetime] = None
    
    # Estatísticas e controle de duplicatas
    total_notificacoes: int = 0
    ultimas_licitacoes_ids: List[str] = []
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def to_mongo_dict(self) -> dict:
        """Converte para dicionário MongoDB (sem _id)"""
        data = self.dict()
        # Converter datetime para ISO string
        for key in ['criado_em', 'atualizado_em', 'ultima_verificacao']:
            if data.get(key):
                data[key] = data[key].isoformat() if isinstance(data[key], datetime) else data[key]
        return data
    
    @classmethod
    def from_mongo_dict(cls, data: dict) -> 'SavedSearch':
        """Cria objeto a partir de documento MongoDB"""
        # Converter ISO strings para datetime
        for key in ['criado_em', 'atualizado_em', 'ultima_verificacao']:
            if data.get(key) and isinstance(data[key], str):
                try:
                    data[key] = datetime.fromisoformat(data[key].replace('Z', '+00:00'))
                except:
                    data[key] = None
        return cls(**data)


class Notification(BaseModel):
    """
    Modelo de Notificação gerada pelo sistema
    
    Armazena alertas de novas licitações encontradas
    """
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str
    busca_id: str  # Referência à SavedSearch
    busca_nome: str  # Nome da busca (para exibição)
    
    # Conteúdo
    titulo: str
    mensagem: str
    licitacoes_ids: List[str] = []  # IDs das licitações encontradas
    total_licitacoes: int = 0
    
    # Status
    lida: bool = False
    email_enviado: bool = False
    
    # Metadados
    criado_em: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# Constantes úteis
FREQUENCIAS_VALIDAS = ["diario", "semanal", "tempo_real"]
MAX_BUSCAS_POR_USUARIO = 20
MAX_LICITACOES_HISTORICO = 100  # Máximo de IDs guardados para evitar duplicatas
