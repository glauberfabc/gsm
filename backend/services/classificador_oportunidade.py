"""
Classificador de Oportunidades - Padrão GSM V3
====================================================

🎯 OBJETIVO:
Classificar como ATIVA toda oportunidade ACIONÁVEL HOJE, independente da modalidade.

📌 CONCEITO CHAVE (CORREÇÃO V3):
- ATIVA = Oportunidade que permite participação/adesão AGORA
- Credenciamentos vigentes SÃO oportunidades ativas (principal fonte no mercado de saúde!)
- Badge diferenciado mantido para distinção visual

📌 REGRAS V3:

1) ATIVA (DEFAULT - INCLUI CREDENCIAMENTOS):
   - Modalidades competitivas: data_abertura >= hoje E <= 90 dias
   - Credenciamentos/Chamamentos: vigência não expirada (permite adesão)
   - Badge diferenciado: 🟢 ATIVA (competitivo) vs 🔵 ATIVA - Credenciamento

2) FUTURA:
   - Processos que ainda NÃO permitem adesão/participação
   - Publicados mas com abertura > 90 dias (competitivos)
   - Credenciamentos ainda não abertos para adesão

3) ENCERRADA:
   - Prazo passou OU status encerrado/cancelado

4) COMPORTAMENTO DEFAULT:
   - Mostra TODAS as oportunidades ATIVAS (competitivas + credenciamentos vigentes)
   - Checkbox opcional para EXCLUIR credenciamentos (não incluir!)

🚫 ERRO ANTERIOR (V2):
Credenciamentos vigentes eram excluídos do default, fazendo com que buscas por
"canabidiol", "insulina" retornassem zero resultados - comportamento oposto ao Agregador.
"""

from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Optional, List
import logging

logger = logging.getLogger(__name__)


class StatusOportunidade(str, Enum):
    """
    ENUM de status de oportunidade - V3
    
    🟢 ATIVA - Oportunidade acionável AGORA (inclui credenciamentos vigentes!)
    🟡 FUTURA - Publicada mas ainda não permite participação
    🔴 ENCERRADA - Prazo passou ou cancelada
    """
    ATIVA = "ATIVA"
    FUTURA = "FUTURA"
    ENCERRADA = "ENCERRADA"


class TipoModalidade(str, Enum):
    """Tipos de modalidade para diferenciação visual (não para exclusão!)"""
    COMPETITIVA = "COMPETITIVA"
    CREDENCIAMENTO = "CREDENCIAMENTO"  # Renomeado para clareza


class ClassificadorOportunidade:
    """
    Classificador de oportunidades V3 - Padrão GSM
    
    🎯 CONCEITO PRINCIPAL:
    ATIVA = Oportunidade acionável AGORA, independente da modalidade
    
    Credenciamentos vigentes são incluídos no default porque:
    - Permitem adesão imediata
    - São a principal fonte de oportunidades no mercado de saúde
    - Agregador mostra credenciamentos como oportunidades ativas
    """
    
    # Limite em dias para considerar ATIVA (modalidades competitivas)
    LIMITE_DIAS_ATIVA = 90
    
    # =====================================================================
    # MODALIDADES COMPETITIVAS
    # =====================================================================
    MODALIDADES_COMPETITIVAS = [
        "pregão",
        "pregao",
        "pregão eletrônico",
        "pregao eletronico",
        "concorrência",
        "concorrencia",
        "tomada de preços",
        "tomada de precos",
        "convite",
        "leilão",
        "leilao",
        "rdc",
        "dispensa",
        "cotação",
        "cotacao",
    ]
    
    # =====================================================================
    # MODALIDADES DE CREDENCIAMENTO (acionáveis continuamente)
    # =====================================================================
    MODALIDADES_CREDENCIAMENTO = [
        "credenciamento",
        "chamamento",
        "chamamento público",
        "chamamento publico",
        "cadastro",
        "registro de preços",
        "ata de registro",
        "srp",
        "inexigibilidade",
    ]
    
    def __init__(self):
        pass
    
    def _identificar_tipo_modalidade(self, modalidade: str, objeto: str) -> TipoModalidade:
        """
        Identifica se a modalidade é COMPETITIVA ou CREDENCIAMENTO
        (para diferenciação visual, não para exclusão!)
        """
        modalidade_lower = modalidade.lower().strip()
        objeto_lower = objeto.lower() if objeto else ""
        
        # Verificar se é CREDENCIAMENTO
        for cred in self.MODALIDADES_CREDENCIAMENTO:
            if cred in modalidade_lower or cred in objeto_lower:
                return TipoModalidade.CREDENCIAMENTO
        
        # Default: competitiva
        return TipoModalidade.COMPETITIVA
    
    def classificar(self, edital: Dict) -> Dict:
        """
        Classifica uma licitação como ATIVA, FUTURA ou ENCERRADA
        
        🎯 V3: Credenciamentos vigentes são ATIVA (não excluídos!)
        
        Adiciona:
        - status_oportunidade: ATIVA | FUTURA | ENCERRADA
        - tipo_modalidade: COMPETITIVA | CREDENCIAMENTO (para badge visual)
        - badge_status: Dados para renderização
        - is_acionavel: Boolean - True para ATIVAS
        - is_credenciamento: Boolean - para filtro opcional
        """
        agora = datetime.now(timezone.utc)
        
        # Extrair datas
        data_abertura = self._parse_data(edital.get('data_abertura'))
        data_publicacao = self._parse_data(edital.get('data_publicacao'))
        
        # Extrair modalidade e objeto
        modalidade = edital.get('modalidade') or edital.get('tipo_modalidade') or ''
        objeto = edital.get('objeto') or ''
        
        # Status da fonte
        status_fonte = (edital.get('status') or '').lower()
        
        # Verificar origem do dado (licitacoes sem data são considerados ativos)
        origem = edital.get('_origem', '')
        sem_datas = not data_abertura and not data_publicacao
        
        # =====================================================================
        # 1. IDENTIFICAR TIPO DE MODALIDADE (para diferenciação visual)
        # =====================================================================
        tipo_modalidade = self._identificar_tipo_modalidade(modalidade, objeto)
        
        # =====================================================================
        # 2. CLASSIFICAR - V3: CREDENCIAMENTOS VIGENTES SÃO ATIVA!
        # =====================================================================
        # 🔄 FALLBACK: Dados de licitacoes sem data são tratados como ATIVA
        # porque foram encontrados em busca e são relevantes
        if sem_datas and origem == 'licitacoes':
            status = StatusOportunidade.ATIVA
        elif tipo_modalidade == TipoModalidade.CREDENCIAMENTO:
            status = self._classificar_credenciamento(
                data_abertura=data_abertura,
                data_publicacao=data_publicacao,
                status_fonte=status_fonte,
                agora=agora
            )
        else:
            status = self._classificar_competitiva(
                data_abertura=data_abertura,
                data_publicacao=data_publicacao,
                status_fonte=status_fonte,
                agora=agora
            )
        
        # =====================================================================
        # 3. CALCULAR METADADOS
        # =====================================================================
        dias_ate_abertura = None
        if data_abertura:
            delta = data_abertura - agora
            dias_ate_abertura = delta.days
        
        # =====================================================================
        # 4. ENRIQUECER EDITAL
        # =====================================================================
        edital['status_oportunidade'] = status.value
        edital['tipo_modalidade'] = tipo_modalidade.value
        
        # is_acionavel = True para TODAS as ATIVAS (competitivas E credenciamentos!)
        edital['is_acionavel'] = (status == StatusOportunidade.ATIVA)
        
        # Flag para filtro opcional (excluir credenciamentos se desejado)
        edital['is_credenciamento'] = (tipo_modalidade == TipoModalidade.CREDENCIAMENTO)
        
        edital['dias_ate_abertura'] = dias_ate_abertura
        
        # Badge para frontend
        edital['badge_status'] = self._gerar_badge(status, dias_ate_abertura, tipo_modalidade)
        
        return edital
    
    def _classificar_competitiva(
        self,
        data_abertura: Optional[datetime],
        data_publicacao: Optional[datetime],
        status_fonte: str,
        agora: datetime
    ) -> StatusOportunidade:
        """
        Classifica MODALIDADE COMPETITIVA
        
        Regras:
        - ATIVA: abertura >= hoje E abertura <= hoje + 90 dias
        - FUTURA: abertura > hoje + 90 dias
        - ENCERRADA: abertura < hoje OU status encerrado
        """
        # Status da fonte indica encerrado
        if status_fonte in ['encerrado', 'cancelado', 'revogado', 'anulado', 'homologado', 'adjudicado', 'suspenso']:
            return StatusOportunidade.ENCERRADA
        
        # Sem data de abertura
        if not data_abertura:
            if data_publicacao:
                dias_desde_pub = (agora - data_publicacao).days
                if dias_desde_pub <= 30:
                    return StatusOportunidade.ATIVA  # Publicação recente, provável ativa
                elif dias_desde_pub <= 90:
                    return StatusOportunidade.FUTURA
            return StatusOportunidade.ENCERRADA
        
        # Com data de abertura
        dias_ate_abertura = (data_abertura - agora).days
        
        # Abertura já passou
        if dias_ate_abertura < 0:
            return StatusOportunidade.ENCERRADA
        
        # Abertura dentro do limite
        if dias_ate_abertura <= self.LIMITE_DIAS_ATIVA:
            return StatusOportunidade.ATIVA
        
        # Abertura distante
        return StatusOportunidade.FUTURA
    
    def _classificar_credenciamento(
        self,
        data_abertura: Optional[datetime],
        data_publicacao: Optional[datetime],
        status_fonte: str,
        agora: datetime
    ) -> StatusOportunidade:
        """
        Classifica CREDENCIAMENTO/CHAMAMENTO
        
        🎯 V3: Credenciamentos vigentes são ATIVA (não excluídos!)
        
        Regras:
        - ATIVA: Vigência não expirou (permite adesão agora)
        - ENCERRADA: Vigência expirou ou status encerrado
        - FUTURA: Ainda não aberto para adesão (raro)
        """
        # Status da fonte indica encerrado
        if status_fonte in ['encerrado', 'cancelado', 'revogado', 'anulado', 'suspenso']:
            return StatusOportunidade.ENCERRADA
        
        # Para credenciamentos, data_abertura geralmente é data de vigência/encerramento
        if data_abertura:
            dias_ate_encerramento = (data_abertura - agora).days
            
            # Vigência expirou
            if dias_ate_encerramento < 0:
                return StatusOportunidade.ENCERRADA
            
            # Vigência ativa = OPORTUNIDADE ATIVA!
            return StatusOportunidade.ATIVA
        
        # Sem data de vigência, verificar publicação
        if data_publicacao:
            dias_desde_pub = (agora - data_publicacao).days
            
            # Publicação muito antiga (> 2 anos) sem data de vigência
            if dias_desde_pub > 730:
                return StatusOportunidade.ENCERRADA
            
            # Publicação recente = provavelmente ainda vigente
            return StatusOportunidade.ATIVA
        
        # Sem datas, assumir encerrado por segurança
        return StatusOportunidade.ENCERRADA
    
    def _parse_data(self, valor) -> Optional[datetime]:
        """Parse de data para datetime com timezone"""
        if not valor:
            return None
        
        if isinstance(valor, datetime):
            if valor.tzinfo is None:
                return valor.replace(tzinfo=timezone.utc)
            return valor
        
        if isinstance(valor, str):
            try:
                dt = datetime.fromisoformat(valor.replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except:
                pass
        
        return None
    
    def _gerar_badge(
        self, 
        status: StatusOportunidade, 
        dias: Optional[int],
        tipo_modalidade: TipoModalidade
    ) -> Dict:
        """
        Gera dados para o badge visual no frontend
        
        V3: Credenciamentos ATIVOS têm badge diferenciado mas NÃO são excluídos
        """
        # Badge base por status
        badges = {
            StatusOportunidade.ATIVA: {
                "cor": "green",
                "icone": "🟢",
                "texto": "ATIVA",
                "classe_css": "bg-green-500 text-white border-green-600",
            },
            StatusOportunidade.FUTURA: {
                "cor": "yellow",
                "icone": "🟡",
                "texto": "FUTURA",
                "classe_css": "bg-yellow-500 text-white border-yellow-600",
            },
            StatusOportunidade.ENCERRADA: {
                "cor": "gray",
                "icone": "🔴",
                "texto": "ENCERRADA",
                "classe_css": "bg-gray-400 text-white border-gray-500",
            },
        }
        
        badge = badges.get(status, badges[StatusOportunidade.ENCERRADA]).copy()
        
        # V3: Credenciamentos ATIVOS têm badge diferenciado (mas ainda são ATIVA!)
        if status == StatusOportunidade.ATIVA and tipo_modalidade == TipoModalidade.CREDENCIAMENTO:
            badge["cor"] = "blue"
            badge["icone"] = "🔵"
            badge["texto"] = "ATIVA - Credenciamento"
            badge["classe_css"] = "bg-blue-500 text-white border-blue-600"
        
        # Subtexto com dias
        if dias is not None:
            if tipo_modalidade == TipoModalidade.CREDENCIAMENTO:
                if dias > 0:
                    badge["subtexto"] = f"Vigente (até {dias} dias)"
                elif dias == 0:
                    badge["subtexto"] = "Último dia!"
                else:
                    badge["subtexto"] = "Vigência expirada"
            else:
                if dias == 0:
                    badge["subtexto"] = "Hoje!"
                elif dias == 1:
                    badge["subtexto"] = "Amanhã"
                elif dias > 0:
                    badge["subtexto"] = f"Em {dias} dias"
                else:
                    badge["subtexto"] = f"Há {abs(dias)} dias"
        
        badge["tipo_modalidade"] = tipo_modalidade.value
        badge["is_credenciamento"] = (tipo_modalidade == TipoModalidade.CREDENCIAMENTO)
        
        return badge
    
    def classificar_lote(self, editais: List[Dict]) -> List[Dict]:
        """Classifica uma lista de editais"""
        return [self.classificar(e) for e in editais]
    
    def filtrar_ativos(self, editais: List[Dict]) -> List[Dict]:
        """
        Retorna editais com status ATIVO
        
        V3: INCLUI credenciamentos vigentes (são oportunidades ativas!)
        """
        classificados = self.classificar_lote(editais)
        return [e for e in classificados if e.get('status_oportunidade') == StatusOportunidade.ATIVA.value]
    
    def filtrar_por_status(
        self, 
        editais: List[Dict], 
        incluir_ativas: bool = True,
        incluir_futuras: bool = False,
        incluir_encerradas: bool = False,
        excluir_credenciamentos: bool = False  # V3: INVERTIDO - excluir, não incluir!
    ) -> List[Dict]:
        """
        Filtra editais por status
        
        V3 DEFAULT: 
        - Inclui ATIVAS (competitivas E credenciamentos!)
        - Checkbox opcional para EXCLUIR credenciamentos
        """
        classificados = self.classificar_lote(editais)
        
        status_permitidos = set()
        if incluir_ativas:
            status_permitidos.add(StatusOportunidade.ATIVA.value)
        if incluir_futuras:
            status_permitidos.add(StatusOportunidade.FUTURA.value)
        if incluir_encerradas:
            status_permitidos.add(StatusOportunidade.ENCERRADA.value)
        
        resultado = []
        for e in classificados:
            status = e.get('status_oportunidade')
            is_credenciamento = e.get('is_credenciamento', False)
            
            # V3: Excluir credenciamentos apenas se explicitamente solicitado
            if excluir_credenciamentos and is_credenciamento:
                continue
            
            if status in status_permitidos:
                resultado.append(e)
        
        return resultado


# Singleton
_instance = None

def get_classificador() -> ClassificadorOportunidade:
    """Retorna instância do classificador"""
    global _instance
    if _instance is None:
        _instance = ClassificadorOportunidade()
    return _instance
