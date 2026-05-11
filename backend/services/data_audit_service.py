"""
Serviço de Auditoria de Dados - P3
===================================

🎯 OBJETIVO:
Garantir que nenhuma licitação inconsistente seja apresentada como oportunidade válida.

📋 CLASSIFICAÇÕES DE AUDITORIA:
- DATA_SUSPEITA: abertura - publicação > 60 dias
- PLANEJAMENTO_LONGO: abertura > hoje + 365 dias (exceto credenciamentos)
- DATA_INCONSISTENTE: abertura < publicação
- DADOS_VALIDOS: passa em todas as verificações

🔒 REGRAS:
- Nunca descartar automaticamente → apenas classificar
- Credenciamentos com adesão contínua NÃO são afetados por PLANEJAMENTO_LONGO
- Transparência total: informar, não esconder
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class AuditStatus(str, Enum):
    """Status de auditoria temporal"""
    DADOS_VALIDOS = "DADOS_VALIDOS"
    DATA_SUSPEITA = "DATA_SUSPEITA"
    PLANEJAMENTO_LONGO = "PLANEJAMENTO_LONGO"
    DATA_INCONSISTENTE = "DATA_INCONSISTENTE"
    SEM_DATAS = "SEM_DATAS"


class DataAuditService:
    """
    Serviço de auditoria temporal e de consistência de dados.
    
    Classifica cada licitação quanto à confiabilidade das datas,
    sem descartar automaticamente - apenas informa.
    """
    
    # Limites de auditoria
    LIMITE_INTERVALO_SUSPEITO = 60  # dias entre publicação e abertura
    LIMITE_PLANEJAMENTO_LONGO = 365  # dias até abertura
    
    def __init__(self):
        pass
    
    def auditar(self, edital: Dict) -> Dict:
        """
        Audita um edital e adiciona informações de confiabilidade.
        
        Adiciona:
        - audit_status: DADOS_VALIDOS | DATA_SUSPEITA | PLANEJAMENTO_LONGO | etc
        - audit_flags: Lista de problemas detectados
        - audit_message: Mensagem amigável para o usuário
        
        ⚠️ EXCEÇÃO PNCP: Se o edital já tem quality_score >= 70 (dados PNCP confiáveis),
        marca como DADOS_VALIDOS automaticamente sem recalcular.
        
        Args:
            edital: Dict com dados da licitação
            
        Returns:
            edital enriquecido com informações de auditoria
        """
        # 🔒 EXCEÇÃO: Dados PNCP com alta qualidade são considerados válidos
        existing_quality = edital.get('quality_score')
        if existing_quality is not None and isinstance(existing_quality, (int, float)) and existing_quality >= 70:
            edital['audit_status'] = AuditStatus.DADOS_VALIDOS.value
            edital['audit_flags'] = ['PNCP_CONFIAVEL']
            edital['audit_message'] = 'Dados validados do PNCP'
            return edital
        
        agora = datetime.now(timezone.utc)
        
        # Extrair datas
        data_abertura = self._parse_data(edital.get('data_abertura'))
        data_publicacao = self._parse_data(edital.get('data_publicacao'))
        
        # Verificar se é credenciamento (exceção para PLANEJAMENTO_LONGO)
        is_credenciamento = edital.get('is_credenciamento', False)
        modalidade = (edital.get('modalidade') or edital.get('tipo_modalidade') or '').lower()
        if 'credenciamento' in modalidade or 'chamamento' in modalidade:
            is_credenciamento = True
        
        # Coletar flags de auditoria
        flags = []
        mensagens = []
        status = AuditStatus.DADOS_VALIDOS
        
        # =====================================================================
        # 1. VERIFICAR SE TEM DATAS
        # =====================================================================
        if not data_abertura and not data_publicacao:
            status = AuditStatus.SEM_DATAS
            flags.append("SEM_DATAS")
            mensagens.append("Datas não informadas")
        
        # =====================================================================
        # 2. VERIFICAR ABERTURA NO PASSADO
        # =====================================================================
        if data_abertura:
            dias_ate_abertura = (data_abertura - agora).days
            
            if dias_ate_abertura < 0 and not is_credenciamento:
                # Para não-credenciamentos, abertura passada = problema
                flags.append("ABERTURA_PASSADA")
                mensagens.append(f"Abertura há {abs(dias_ate_abertura)} dias")
                status = AuditStatus.DATA_INCONSISTENTE
        
        # =====================================================================
        # 3. VERIFICAR INTERVALO PUBLICAÇÃO-ABERTURA (DATA_SUSPEITA)
        # =====================================================================
        if data_abertura and data_publicacao:
            intervalo_dias = (data_abertura - data_publicacao).days
            
            if intervalo_dias > self.LIMITE_INTERVALO_SUSPEITO:
                flags.append("INTERVALO_LONGO")
                mensagens.append(f"Intervalo de {intervalo_dias} dias entre publicação e abertura")
                
                # Só marca como suspeito se não for credenciamento
                if not is_credenciamento:
                    status = AuditStatus.DATA_SUSPEITA
            
            # Verificar inconsistência (abertura antes da publicação)
            if intervalo_dias < 0:
                flags.append("ABERTURA_ANTES_PUBLICACAO")
                mensagens.append("Abertura antes da publicação")
                status = AuditStatus.DATA_INCONSISTENTE
        
        # =====================================================================
        # 4. VERIFICAR PLANEJAMENTO LONGO (> 365 dias)
        # =====================================================================
        if data_abertura:
            dias_ate_abertura = (data_abertura - agora).days
            
            if dias_ate_abertura > self.LIMITE_PLANEJAMENTO_LONGO:
                flags.append("PLANEJAMENTO_LONGO")
                mensagens.append(f"Abertura em {dias_ate_abertura} dias (> 1 ano)")
                
                # EXCEÇÃO: Credenciamentos com adesão contínua NÃO são afetados
                if not is_credenciamento:
                    status = AuditStatus.PLANEJAMENTO_LONGO
        
        # =====================================================================
        # 5. ENRIQUECER EDITAL
        # =====================================================================
        edital['audit_status'] = status.value
        edital['audit_flags'] = flags
        edital['audit_message'] = "; ".join(mensagens) if mensagens else None
        
        # Gerar aviso amigável para o frontend
        edital['audit_warning'] = self._gerar_aviso(status, flags, is_credenciamento)
        
        return edital
    
    def _gerar_aviso(
        self, 
        status: AuditStatus, 
        flags: List[str],
        is_credenciamento: bool
    ) -> Optional[Dict]:
        """
        Gera aviso amigável para exibição no frontend.
        
        Returns:
            Dict com emoji, texto e nível de severidade, ou None se ok
        """
        if status == AuditStatus.DADOS_VALIDOS:
            return None
        
        avisos = {
            AuditStatus.DATA_SUSPEITA: {
                "emoji": "⚠️",
                "texto": "Datas atípicas detectadas",
                "nivel": "warning",
                "cor": "yellow"
            },
            AuditStatus.PLANEJAMENTO_LONGO: {
                "emoji": "🧪",
                "texto": "Processo em planejamento",
                "nivel": "info",
                "cor": "blue"
            },
            AuditStatus.DATA_INCONSISTENTE: {
                "emoji": "❌",
                "texto": "Datas inconsistentes",
                "nivel": "error",
                "cor": "red"
            },
            AuditStatus.SEM_DATAS: {
                "emoji": "❓",
                "texto": "Datas não informadas",
                "nivel": "info",
                "cor": "gray"
            }
        }
        
        aviso = avisos.get(status)
        if aviso:
            aviso = aviso.copy()
            aviso['flags'] = flags
            
            # Ajustar para credenciamentos
            if is_credenciamento and "INTERVALO_LONGO" in flags:
                aviso['texto'] = "Credenciamento com vigência longa"
                aviso['nivel'] = "info"
                aviso['cor'] = "blue"
        
        return aviso
    
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
    
    def auditar_lote(self, editais: List[Dict]) -> List[Dict]:
        """Audita uma lista de editais"""
        return [self.auditar(e) for e in editais]
    
    def get_estatisticas(self, editais: List[Dict]) -> Dict:
        """
        Retorna estatísticas de auditoria.
        """
        if not editais:
            return {
                "total": 0,
                "dados_validos": 0,
                "data_suspeita": 0,
                "planejamento_longo": 0,
                "data_inconsistente": 0,
                "sem_datas": 0
            }
        
        stats = {
            "total": len(editais),
            "dados_validos": 0,
            "data_suspeita": 0,
            "planejamento_longo": 0,
            "data_inconsistente": 0,
            "sem_datas": 0
        }
        
        for e in editais:
            status = e.get('audit_status', 'DADOS_VALIDOS')
            if status == 'DADOS_VALIDOS':
                stats['dados_validos'] += 1
            elif status == 'DATA_SUSPEITA':
                stats['data_suspeita'] += 1
            elif status == 'PLANEJAMENTO_LONGO':
                stats['planejamento_longo'] += 1
            elif status == 'DATA_INCONSISTENTE':
                stats['data_inconsistente'] += 1
            elif status == 'SEM_DATAS':
                stats['sem_datas'] += 1
        
        return stats


# Singleton
_instance = None

def get_data_audit_service() -> DataAuditService:
    """Retorna instância do serviço"""
    global _instance
    if _instance is None:
        _instance = DataAuditService()
    return _instance
