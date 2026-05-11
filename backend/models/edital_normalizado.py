"""
Modelo Canônico de Edital Normalizado
=====================================

Este modelo é o CONTRATO DE DADOS do sistema.
Todos os editais, independente da fonte, devem ser convertidos para este formato.

Fontes suportadas:
- PNCP (Portal Nacional de Contratações Públicas)
- ComprasNet (Federal)
- Portais Municipais (scrapers)

Regra de Ouro:
- Nunca escreva lógica de negócio em dados "raw"
- Raw é descartável. Normalizado é contrato.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime
from enum import Enum
import hashlib
import re
import unicodedata


class FonteEdital(str, Enum):
    """Fontes de dados suportadas"""
    PNCP = "PNCP"
    COMPRASNET = "COMPRASNET"
    MUNICIPAL = "MUNICIPAL"
    ESTADUAL = "ESTADUAL"
    OUTRO = "OUTRO"


class StatusEdital(str, Enum):
    """Status possíveis de um edital"""
    ABERTO = "Aberto"
    EM_ANDAMENTO = "Em Andamento"
    SUSPENSO = "Suspenso"
    ENCERRADO = "Encerrado"
    CANCELADO = "Cancelado"
    DESERTO = "Deserto"
    ADJUDICADO = "Adjudicado"
    HOMOLOGADO = "Homologado"
    PUBLICADO = "Publicado"
    REVOGADO = "Revogado"
    OUTRO = "Outro"


class EsferaEdital(str, Enum):
    """Esfera administrativa"""
    FEDERAL = "Federal"
    ESTADUAL = "Estadual"
    MUNICIPAL = "Municipal"
    DISTRITAL = "Distrital"


class OrigemDados(BaseModel):
    """Metadados de origem para auditoria e debug"""
    url: Optional[str] = None
    raw_id: Optional[str] = None  # ID na collection raw (editais_sync)
    fonte_original: Optional[str] = None
    data_extracao: Optional[datetime] = None


class EditalNormalizado(BaseModel):
    """
    Modelo Canônico de Edital
    
    Este é o contrato de dados central do sistema.
    Qualquer fonte de dados deve ser normalizada para este formato.
    """
    
    # Identificadores
    id_externo: str = Field(..., description="ID original na fonte")
    fonte: FonteEdital = Field(..., description="Fonte de origem dos dados")
    
    # Localização
    municipio: Optional[str] = Field(None, description="Nome do município")
    uf: str = Field(..., min_length=2, max_length=2, description="Sigla do estado (UF)")
    esfera: Optional[EsferaEdital] = Field(None, description="Esfera administrativa")
    
    # Órgão
    orgao: str = Field(..., description="Nome do órgão licitante")
    cnpj_orgao: Optional[str] = Field(None, description="CNPJ do órgão (14 dígitos, sem formatação)")
    
    # Objeto
    objeto: str = Field(..., description="Descrição completa do objeto")
    objeto_resumido: Optional[str] = Field(None, description="Resumo do objeto (para NLP futuro)")
    
    # Valores
    valor_estimado: Optional[float] = Field(None, ge=0, description="Valor estimado total")
    valor_estimado_min: Optional[float] = Field(None, ge=0, description="Valor mínimo (quando faixa)")
    valor_estimado_max: Optional[float] = Field(None, ge=0, description="Valor máximo (quando faixa)")
    
    # Modalidade e Status
    modalidade: Optional[str] = Field(None, description="Modalidade da licitação")
    status: Optional[StatusEdital] = Field(None, description="Status atual")
    numero_processo: Optional[str] = Field(None, description="Número do processo")
    
    # Datas
    data_abertura: Optional[datetime] = Field(None, description="Data de abertura das propostas")
    data_publicacao: Optional[datetime] = Field(None, description="Data de publicação")
    
    # Links
    link_edital: Optional[str] = Field(None, description="Link para o edital completo")
    link_anexos: List[str] = Field(default_factory=list, description="Links para anexos")
    
    # Classificação automática
    tags: List[str] = Field(default_factory=list, description="Tags auto-geradas (saúde, TI, etc)")
    ncm_detectados: List[str] = Field(default_factory=list, description="Códigos NCM detectados no objeto")
    is_saude: bool = Field(default=False, description="Flag: edital relacionado a saúde")
    
    # Metadados de origem
    origem_dados: Optional[OrigemDados] = Field(None, description="Dados de auditoria")
    
    # Deduplicação
    hash_dedup: Optional[str] = Field(None, description="Hash SHA256 para deduplicação cross-fonte")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        use_enum_values = True
        json_schema_extra = {
            "example": {
                "id_externo": "2024/001234",
                "fonte": "PNCP",
                "municipio": "São Paulo",
                "uf": "SP",
                "esfera": "Municipal",
                "orgao": "Secretaria Municipal de Saúde",
                "objeto": "Aquisição de medicamentos hospitalares",
                "valor_estimado": 500000.00,
                "modalidade": "Pregão Eletrônico",
                "status": "Aberto",
                "data_abertura": "2024-12-20T10:00:00",
                "tags": ["saúde", "medicamentos", "hospitalar"],
                "is_saude": True
            }
        }
    
    @validator('uf', pre=True)
    def normalizar_uf(cls, v):
        """Normaliza UF para maiúsculas"""
        if v:
            return v.upper().strip()
        return v
    
    @validator('cnpj_orgao', pre=True)
    def limpar_cnpj(cls, v):
        """Remove formatação do CNPJ"""
        if v:
            return re.sub(r'[^\d]', '', str(v))
        return v
    
    @validator('objeto', pre=True)
    def limpar_objeto(cls, v):
        """Normaliza texto do objeto"""
        if v:
            # Remove espaços extras
            v = ' '.join(v.split())
            return v.strip()
        return v
    
    def calcular_hash_dedup(self) -> str:
        """
        Calcula hash SHA256 para deduplicação cross-fonte
        
        Componentes do hash:
        - cnpj_orgao OU orgao_normalizado (se CNPJ não disponível)
        - objeto_normalizado (sem acentos, lowercase)
        - data_abertura (formato ISO)
        
        Returns:
            str: Hash SHA256 hexadecimal
        """
        # Normalizar orgao
        orgao_norm = self._normalizar_texto(self.orgao)
        
        # Usar CNPJ se disponível, senão usar orgao normalizado
        identificador_orgao = self.cnpj_orgao or orgao_norm
        
        # Normalizar objeto
        objeto_norm = self._normalizar_texto(self.objeto)
        
        # Formatar data
        data_str = ""
        if self.data_abertura:
            data_str = self.data_abertura.strftime("%Y-%m-%d")
        
        # Compor string para hash
        componentes = f"{identificador_orgao}|{objeto_norm}|{data_str}"
        
        # Calcular SHA256
        return hashlib.sha256(componentes.encode('utf-8')).hexdigest()
    
    @staticmethod
    def _normalizar_texto(texto: str) -> str:
        """
        Normaliza texto para comparação:
        - Remove acentos
        - Converte para lowercase
        - Remove caracteres especiais
        - Remove espaços extras
        """
        if not texto:
            return ""
        
        # Remove acentos
        texto = unicodedata.normalize('NFKD', texto)
        texto = ''.join(c for c in texto if not unicodedata.combining(c))
        
        # Lowercase
        texto = texto.lower()
        
        # Remove caracteres especiais (mantém apenas letras, números e espaços)
        texto = re.sub(r'[^a-z0-9\s]', '', texto)
        
        # Remove espaços extras
        texto = ' '.join(texto.split())
        
        return texto.strip()
    
    def gerar_objeto_resumido(self, max_chars: int = 150) -> str:
        """
        Gera resumo do objeto (para NLP futuro)
        
        Args:
            max_chars: Tamanho máximo do resumo
            
        Returns:
            str: Objeto resumido
        """
        if not self.objeto:
            return ""
        
        # Se já é curto, retorna como está
        if len(self.objeto) <= max_chars:
            return self.objeto
        
        # Trunca no último espaço antes do limite
        resumo = self.objeto[:max_chars]
        ultimo_espaco = resumo.rfind(' ')
        
        if ultimo_espaco > max_chars * 0.7:  # Só trunca se não perder muito
            resumo = resumo[:ultimo_espaco]
        
        return resumo + "..."
    
    def detectar_tags_saude(self) -> List[str]:
        """
        Detecta tags relacionadas a saúde no objeto
        
        Returns:
            List[str]: Tags detectadas
        """
        texto = self.objeto.lower() if self.objeto else ""
        
        categorias_saude = {
            'hospitalar': ['hospital', 'uti', 'upa', 'ubs', 'pronto socorro', 'emergência'],
            'medicamentos': ['medicament', 'fármaco', 'antibiótico', 'analgésico', 'insulina'],
            'equipamentos_medicos': ['equipamento médico', 'ventilador', 'monitor', 'desfibrilador'],
            'laboratorio': ['laborat', 'exame', 'reagente', 'diagnóstico'],
            'insumos': ['seringa', 'luva', 'máscara', 'epi', 'algodão', 'gaze'],
            'odontologia': ['odontológic', 'dental', 'dentista'],
            'oftalmologia': ['oftalmológic', 'lente', 'colírio', 'óculos'],
            'oncologia': ['oncológic', 'quimioterapia', 'radioterapia'],
            'cardiologia': ['cardiológic', 'stent', 'marca-passo'],
            'saude_geral': ['saúde', 'sus', 'secretaria de saúde', 'médico', 'enfermagem']
        }
        
        tags_encontradas = []
        for categoria, keywords in categorias_saude.items():
            for keyword in keywords:
                if keyword in texto:
                    tags_encontradas.append(categoria)
                    break  # Só adiciona uma vez por categoria
        
        return list(set(tags_encontradas))


# Função auxiliar para criar EditalNormalizado com hash
def criar_edital_normalizado(**kwargs) -> EditalNormalizado:
    """
    Factory function para criar EditalNormalizado com hash_dedup calculado
    
    Args:
        **kwargs: Campos do EditalNormalizado
        
    Returns:
        EditalNormalizado com hash_dedup preenchido
    """
    edital = EditalNormalizado(**kwargs)
    
    # Calcular hash se não foi fornecido
    if not edital.hash_dedup:
        edital.hash_dedup = edital.calcular_hash_dedup()
    
    # Gerar objeto resumido se não foi fornecido
    if not edital.objeto_resumido:
        edital.objeto_resumido = edital.gerar_objeto_resumido()
    
    # Detectar tags de saúde
    if not edital.tags:
        edital.tags = edital.detectar_tags_saude()
        edital.is_saude = len(edital.tags) > 0
    
    return edital
