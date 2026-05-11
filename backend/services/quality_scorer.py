"""
Serviço de Quality Score - P3
==============================

🎯 OBJETIVO:
Calcular score de qualidade (0-100) para cada licitação,
usado como critério final de corte no feed default.

📊 CRITÉRIOS DE QUALITY SCORE:
- Datas coerentes: +30 pts
- Link funcional: +30 pts
- Itens identificados: +20 pts
- Fonte confiável: +20 pts

🔒 REGRAS:
- quality_score >= 70 → aparece no feed default
- quality_score < 70 → só aparece com filtro explícito
- DATA_SUSPEITA com quality_score < 70 → nunca no default
"""

import logging
from typing import Dict, List
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class QualityScorer:
    """
    Calcula score de qualidade (0-100) para cada licitação.
    
    Este é o CRITÉRIO FINAL de corte do feed default.
    Apenas licitações com quality_score >= 70 aparecem por padrão.
    """
    
    # Pesos dos critérios (total = 100)
    PESO_DATAS = 30          # Datas coerentes e presentes
    PESO_LINK = 30           # Link direto funcional
    PESO_ITENS = 20          # Itens identificados
    PESO_FONTE = 20          # Fonte confiável
    
    # Limite mínimo para feed default
    LIMITE_FEED_DEFAULT = 70
    
    # Fontes confiáveis
    FONTES_CONFIAVEIS = ['PNCP', 'pncp', 'editais_normalizados']
    
    def __init__(self):
        pass
    
    def calcular_quality_score(self, edital: Dict) -> Dict:
        """
        Calcula quality score para uma licitação.
        
        ⚠️ IMPORTANTE: Se o edital já tiver quality_score definido (ex: de sync),
        respeitar esse valor e não recalcular.
        
        Adiciona:
        - quality_score: 0-100
        - quality_level: ALTA | MEDIA | BAIXA
        - quality_breakdown: detalhamento por critério
        - qualifica_feed_default: bool
        
        Args:
            edital: Dict com dados da licitação
            
        Returns:
            edital enriquecido com quality score
        """
        # 🔒 REGRA: Respeitar quality_score já definido (ex: de sync PNCP)
        existing_score = edital.get('quality_score')
        if existing_score is not None and isinstance(existing_score, (int, float)) and existing_score > 0:
            # Score já existe - apenas garantir campos auxiliares
            total = int(existing_score)
            
            if total >= 80:
                level = "ALTA"
            elif total >= 60:
                level = "MEDIA"
            else:
                level = "BAIXA"
            
            edital['quality_score'] = total
            edital['quality_level'] = level
            edital['quality_breakdown'] = {'pre_calculated': total}
            edital['qualifica_feed_default'] = total >= self.LIMITE_FEED_DEFAULT
            
            return edital
        
        # Calcular score do zero
        scores = {
            'datas': self._score_datas(edital),
            'link': self._score_link(edital),
            'itens': self._score_itens(edital),
            'fonte': self._score_fonte(edital)
        }
        
        # Score total
        total = sum(scores.values())
        total = min(100, max(0, total))
        
        # Nível de qualidade
        if total >= 80:
            level = "ALTA"
        elif total >= 60:
            level = "MEDIA"
        else:
            level = "BAIXA"
        
        # Verificar se qualifica para feed default
        qualifica_default = total >= self.LIMITE_FEED_DEFAULT
        
        # Verificar penalizações por auditoria
        audit_status = edital.get('audit_status', 'DADOS_VALIDOS')
        if audit_status in ['DATA_SUSPEITA', 'DATA_INCONSISTENTE']:
            # Penalização adicional para dados suspeitos
            if total < 80:  # Só penaliza se não for muito alto
                qualifica_default = False
        
        # Enriquecer edital
        edital['quality_score'] = round(total)
        edital['quality_level'] = level
        edital['quality_breakdown'] = scores
        edital['qualifica_feed_default'] = qualifica_default
        
        return edital
    
    def _score_datas(self, edital: Dict) -> int:
        """
        Score baseado na presença e coerência das datas.
        
        🔒 P3 REGRA: Auditoria de datas classifica, mas NÃO elimina!
        Dados sem datas não podem sozinhos impedir uma oportunidade de aparecer.
        
        - Ambas datas presentes e coerentes: 30 pts
        - Apenas abertura presente: 20 pts
        - Apenas publicação presente: 15 pts
        - Datas inconsistentes: 5 pts (mínimo, mas não zera)
        - Sem datas: 15 pts (pontuação razoável para não penalizar demais)
        """
        audit_status = edital.get('audit_status', '')
        
        # Penalização por inconsistência (mas não zera!)
        if audit_status == 'DATA_INCONSISTENTE':
            return 5  # Mínimo mas não zera
        
        data_abertura = edital.get('data_abertura')
        data_publicacao = edital.get('data_publicacao')
        
        # Ambas presentes
        if data_abertura and data_publicacao:
            # Verificar se é DATA_SUSPEITA
            if audit_status == 'DATA_SUSPEITA':
                return 15  # Penalização parcial
            return self.PESO_DATAS  # 30
        
        # Apenas abertura
        if data_abertura:
            return int(self.PESO_DATAS * 0.67)  # 20
        
        # Apenas publicação
        if data_publicacao:
            return int(self.PESO_DATAS * 0.5)  # 15
        
        # Sem datas - pontuação razoável (não penaliza demais)
        # 🔒 P3: Dados sem datas podem ser oportunidades válidas
        return 15
    
    def _score_link(self, edital: Dict) -> int:
        """
        Score baseado na qualidade do link.
        
        - Link válido e direto: 30 pts
        - Link presente mas não validado: 20 pts
        - Link de busca/genérico: 10 pts
        - Sem link: 0 pts
        """
        link_status = edital.get('link_status', '')
        link_edital = edital.get('link_edital', '')
        link_pncp = edital.get('link_pncp', '')
        
        # Link validado como direto
        if link_status == 'VALIDO':
            return self.PESO_LINK  # 30
        
        # Link presente mas não validado
        if link_edital and link_edital.startswith('http'):
            # Verificar se é link de busca
            if '?q=' in link_edital or 'search' in link_edital.lower():
                return int(self.PESO_LINK * 0.33)  # 10
            return int(self.PESO_LINK * 0.67)  # 20
        
        # Link PNCP presente
        if link_pncp and link_pncp.startswith('http'):
            return int(self.PESO_LINK * 0.67)  # 20
        
        # Sem link
        return 0
    
    def _score_itens(self, edital: Dict) -> int:
        """
        Score baseado nos itens identificados.
        
        - Itens estruturados do JSON: 20 pts
        - Itens extraídos do texto: 15 pts
        - Item virtual (fallback): 10 pts
        - Sem itens: 0 pts
        """
        itens = edital.get('itens_correspondentes', [])
        total_itens = edital.get('total_itens_match', 0)
        
        if not itens and not total_itens:
            return 0
        
        # Verificar fonte dos itens
        if itens:
            fonte = itens[0].get('fonte', '')
            
            # Itens do JSON (melhor qualidade)
            if fonte == 'itens_json':
                return self.PESO_ITENS  # 20
            
            # Itens parseados do texto
            if fonte in ['texto_parseado', 'texto_separado', 'medicamento']:
                return int(self.PESO_ITENS * 0.75)  # 15
            
            # Item virtual/fallback
            if fonte in ['objeto_virtual', 'objeto_fallback', 'objeto']:
                return int(self.PESO_ITENS * 0.5)  # 10
        
        # Tem itens mas sem fonte identificada
        if total_itens > 0:
            return int(self.PESO_ITENS * 0.5)  # 10
        
        return 0
    
    def _score_fonte(self, edital: Dict) -> int:
        """
        Score baseado na confiabilidade da fonte.
        
        - PNCP/editais_normalizados: 20 pts
        - licitacoes (dados estruturados): 15 pts
        - Outras fontes: 10 pts
        """
        fonte = edital.get('fonte', edital.get('_origem', ''))
        
        # Fonte oficial PNCP
        if any(f in str(fonte).lower() for f in self.FONTES_CONFIAVEIS):
            return self.PESO_FONTE  # 20
        
        # Collection licitacoes (dados estruturados)
        if fonte == 'licitacoes' or edital.get('_origem') == 'licitacoes':
            return int(self.PESO_FONTE * 0.75)  # 15
        
        # Outras fontes
        return int(self.PESO_FONTE * 0.5)  # 10
    
    def calcular_lote(self, editais: List[Dict]) -> List[Dict]:
        """Calcula quality score para uma lista de editais"""
        return [self.calcular_quality_score(e) for e in editais]
    
    def filtrar_por_qualidade(
        self,
        editais: List[Dict],
        incluir_suspeitos: bool = False,
        incluir_planejamento: bool = False,
        limite_minimo: int = None
    ) -> List[Dict]:
        """
        Filtra editais por qualidade.
        
        Args:
            editais: Lista de editais já com quality_score
            incluir_suspeitos: Se True, inclui DATA_SUSPEITA
            incluir_planejamento: Se True, inclui PLANEJAMENTO_LONGO
            limite_minimo: Score mínimo (default: 70)
            
        Returns:
            Lista filtrada
        """
        limite = limite_minimo if limite_minimo is not None else self.LIMITE_FEED_DEFAULT
        
        resultado = []
        for e in editais:
            quality_score = e.get('quality_score', 0)
            audit_status = e.get('audit_status', 'DADOS_VALIDOS')
            
            # Verificar score mínimo
            if quality_score < limite:
                continue
            
            # Verificar DATA_SUSPEITA
            if audit_status == 'DATA_SUSPEITA' and not incluir_suspeitos:
                continue
            
            # Verificar PLANEJAMENTO_LONGO
            if audit_status == 'PLANEJAMENTO_LONGO' and not incluir_planejamento:
                continue
            
            # Verificar DATA_INCONSISTENTE (sempre excluir do default)
            if audit_status == 'DATA_INCONSISTENTE':
                continue
            
            resultado.append(e)
        
        return resultado
    
    def get_estatisticas(self, editais: List[Dict]) -> Dict:
        """
        Retorna estatísticas de qualidade.
        """
        if not editais:
            return {
                "total": 0,
                "alta_qualidade": 0,
                "media_qualidade": 0,
                "baixa_qualidade": 0,
                "qualificam_default": 0,
                "excluidos_default": 0,
                "score_medio": 0
            }
        
        scores = [e.get('quality_score', 0) for e in editais]
        levels = [e.get('quality_level', 'BAIXA') for e in editais]
        qualificam = sum(1 for e in editais if e.get('qualifica_feed_default', False))
        
        return {
            "total": len(editais),
            "alta_qualidade": levels.count('ALTA'),
            "media_qualidade": levels.count('MEDIA'),
            "baixa_qualidade": levels.count('BAIXA'),
            "qualificam_default": qualificam,
            "excluidos_default": len(editais) - qualificam,
            "score_medio": round(sum(scores) / len(scores), 1)
        }


# Singleton
_instance = None

def get_quality_scorer() -> QualityScorer:
    """Retorna instância do scorer"""
    global _instance
    if _instance is None:
        _instance = QualityScorer()
    return _instance
