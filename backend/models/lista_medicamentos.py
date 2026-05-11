from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime
import uuid


class ListaMedicamentosBase(BaseModel):
    """Base model para Lista de Medicamentos"""
    nome: str = Field(..., min_length=1, max_length=100, description="Nome da lista (ex: 'Canabidiol', 'Importados')")
    medicamentos: List[str] = Field(default_factory=list, description="Lista de nomes de medicamentos")
    descricao: Optional[str] = Field(None, max_length=500, description="Descrição opcional da lista")
    
    @validator('nome')
    def nome_nao_vazio(cls, v):
        """Valida que o nome não seja apenas espaços em branco"""
        if not v or not v.strip():
            raise ValueError('Nome da lista não pode ser vazio')
        return v.strip()
    
    @validator('medicamentos')
    def medicamentos_validos(cls, v):
        """Valida a lista de medicamentos"""
        if not isinstance(v, list):
            raise ValueError('Medicamentos deve ser uma lista')
        
        # Remover strings vazias e duplicatas
        medicamentos_limpos = []
        vistos = set()
        for med in v:
            med_limpo = med.strip().lower()
            if med_limpo and med_limpo not in vistos:
                medicamentos_limpos.append(med.strip())
                vistos.add(med_limpo)
        
        return medicamentos_limpos


class ListaMedicamentosCreate(ListaMedicamentosBase):
    """Model para criação de lista"""
    pass


class ListaMedicamentosUpdate(BaseModel):
    """Model para atualização parcial de lista"""
    nome: Optional[str] = Field(None, min_length=1, max_length=100)
    medicamentos: Optional[List[str]] = None
    descricao: Optional[str] = Field(None, max_length=500)
    
    @validator('nome')
    def nome_nao_vazio(cls, v):
        if v is not None and (not v or not v.strip()):
            raise ValueError('Nome da lista não pode ser vazio')
        return v.strip() if v else v


class ListaMedicamentos(ListaMedicamentosBase):
    """Model completo de Lista de Medicamentos"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = Field(default="default_user", description="ID do usuário (para futuro suporte multi-usuário)")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "nome": "Canabidiol",
                "medicamentos": ["Canabidiol", "Mevatyl", "CBD"],
                "descricao": "Medicamentos à base de canabidiol",
                "user_id": "default_user",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            }
        }
