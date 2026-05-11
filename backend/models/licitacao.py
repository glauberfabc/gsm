from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid


class ItemLicitacao(BaseModel):
    """Modelo para item individual de uma licitação"""
    numero: int = Field(..., description="Número do item")
    descricao: str = Field(..., description="Descrição completa do item")
    quantidade: Optional[float] = Field(None, description="Quantidade solicitada")
    unidade: Optional[str] = Field(None, description="Unidade de medida (ex: UNIDADE, CAIXA)")
    valor_estimado: Optional[float] = Field(None, description="Valor unitário estimado")


class Licitacao(BaseModel):
    """Modelo expandido de Licitação com campos adicionais para replicar agregadores profissionais"""
    
    # Campos básicos (existentes)
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    medicamento: str
    principio_ativo: Optional[str] = None
    estado: str  # UF
    status: str  # Ativa, Encerrada, Em Licitação, Contratado, FUTURA
    orgao_licitante: str
    modalidade: str  # Pregão Eletrônico, Dispensa, Inexigibilidade, Concorrência, Cotação
    numero_processo: str
    
    # Datas expandidas
    data_referencia: datetime
    data_abertura: Optional[datetime] = None  # Data de abertura de propostas
    data_inicial: Optional[datetime] = Field(None, description="Data de início da licitação")
    data_final: Optional[datetime] = Field(None, description="Data LIMITE/Encerramento (crítica!)")
    data_publicacao: Optional[datetime] = Field(None, description="Data de publicação no portal")
    
    # Links
    link_origem: str  # URL do portal de origem (página de detalhes)
    link_documento: Optional[str] = None  # Link DIRETO para PDF/ZIP do edital
    
    # Campos adicionais (novos - inspirados em Portal/eLicitacao)
    fonte_nome: Optional[str] = Field(None, description="Nome da fonte (ex: TCE Rio Grande do Sul, PNCP)")
    fonte_id: Optional[str] = Field(None, description="ID no sistema de origem (ex: ID Portal)")
    numero_pregao: Optional[str] = Field(None, description="Número do pregão formatado (ex: 15/2025)")
    uasg: Optional[str] = Field(None, description="Código UASG ou CNPJ do órgão")
    esfera: Optional[str] = Field(None, description="Esfera administrativa (Estadual/Municipal/Federal)")
    objeto: Optional[str] = Field(None, description="Descrição completa do objeto da licitação")
    
    # Itens da licitação (array)
    itens: List[ItemLicitacao] = Field(default_factory=list, description="Lista de itens da licitação")
    
    # Metadados
    tags: List[str] = []  # alto_custo, importado, judicial
    is_mock: bool = False
    fonte: str = 'estadual'  # 'estadual', 'PNCP', 'ComprasNet', 'BEC'
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "medicamento": "Canabidiol",
                "estado": "RS",
                "status": "Ativa",
                "orgao_licitante": "CIS/CAÍ - CONS. INTERM. DO VALE DO RIO CAÍ",
                "modalidade": "Pregão Eletrônico",
                "numero_processo": "15/2025",
                "fonte_nome": "TCE Rio Grande do Sul",
                "fonte_id": "7129870",
                "numero_pregao": "15/2025",
                "uasg": "7147744619858466992",
                "esfera": "Estadual",
                "data_final": "2025-12-12T00:00:00",
                "objeto": "AQUISIÇÃO DE MEDICAMENTOS DE USO HUMANO",
                "itens": [
                    {
                        "numero": 129,
                        "descricao": "Canabidiol 100mg/ml frasco 30ml",
                        "quantidade": 255
                    }
                ]
            }
        }

class LicitacaoCreate(BaseModel):
    medicamento: str
    principio_ativo: Optional[str] = None
    estado: str
    status: str
    orgao_licitante: str
    modalidade: str
    numero_processo: str
    data_referencia: datetime
    data_abertura: Optional[datetime] = None
    link_origem: str
    link_documento: Optional[str] = None
    tags: List[str] = []
    is_mock: bool = False
    fonte: str = 'estadual'

class SearchQuery(BaseModel):
    """Query de busca expandida com filtros avançados"""
    medicamento: Optional[str] = None
    estado: Optional[str] = None
    tags: Optional[List[str]] = None
    apenas_reais: bool = False
    apenas_futuras: bool = False  # Filtrar apenas licitações futuras
    lista_id: Optional[str] = None  # Filtrar por lista customizada
    
    # Novos filtros avançados (inspirados em Portal/eLicitacao)
    status_filtro: Optional[str] = Field(None, description="Filtrar por status: Ativa, Encerrada, Todas")
    modalidade_filtro: Optional[List[str]] = Field(None, description="Filtrar por modalidade: Pregão, Concorrência, Cotação, etc")
    esfera_filtro: Optional[str] = Field(None, description="Filtrar por esfera: Estadual, Municipal, Federal")
    data_limite_inicio: Optional[datetime] = Field(None, description="Filtrar licitações com data final >= esta data")
    data_limite_fim: Optional[datetime] = Field(None, description="Filtrar licitações com data final <= esta data")
    
    # NOVOS: Filtros de Inteligência de Negócios (Saúde)
    apenas_saude: bool = Field(False, description="Filtrar apenas licitações de saúde (is_saude=True)")
    apenas_urgentes: bool = Field(False, description="Filtrar apenas licitações urgentes (is_urgente=True)")
    categorias_saude: Optional[List[str]] = Field(None, description="Filtrar por categorias de saúde: hospitalar, medicamentos, etc")
    
    # Parâmetros de paginação (P1 - Otimização de Performance)
    page: int = Field(1, ge=1, description="Número da página (inicia em 1)")
    per_page: int = Field(50, ge=1, le=200, description="Quantidade de resultados por página (máx: 200)")
