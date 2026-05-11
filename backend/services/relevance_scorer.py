"""
Serviço de Ranking de Relevância - P2
======================================

🎯 OBJETIVO:
Ordenar resultados de forma inteligente, destacando oportunidades mais relevantes.

📊 CRITÉRIOS DE SCORE (0-100):
1. Quantidade de itens compatíveis (até 30 pts)
2. Tipo de match - exato > sinônimo > parcial (até 25 pts)
3. Proximidade da abertura (até 20 pts)
4. Modalidade - Pregão > Credenciamento (até 15 pts)
5. Qualidade do dado - link válido + itens estruturados (até 10 pts)

🔒 REGRAS:
- NÃO altera lógica de datas, status ou classificação
- NÃO modifica regras de matching ou extração
- Apenas ordena resultados já retornados
"""

import logging
from typing import Dict, List, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class RelevanceScorer:
    """
    Calcula score de relevância (0-100) para cada resultado.
    
    Categorias:
    - 🔥 Alta Relevância: 70-100
    - ⚡ Média Relevância: 40-69
    - 📋 Baixa Relevância: 0-39
    """
    
    # Pesos dos critérios (total = 100)
    PESO_ITENS = 30          # Quantidade de itens compatíveis
    PESO_TIPO_MATCH = 25     # Tipo de match (exato > sinônimo > parcial)
    PESO_PROXIMIDADE = 20    # Proximidade da abertura
    PESO_MODALIDADE = 15     # Tipo de modalidade
    PESO_QUALIDADE = 10      # Qualidade do dado
    
    # Modalidades competitivas (maior score)
    MODALIDADES_PREMIUM = [
        "pregão", "pregao", "pregão eletrônico", "pregao eletronico",
        "concorrência", "concorrencia", "dispensa", "dispensa eletrônica",
        "cotação", "cotacao", "rdc"
    ]
    
    def __init__(self):
        pass
    
    def calcular_score(self, resultado: Dict, termos_busca: List[str]) -> Dict:
        """
        Calcula score de relevância para um resultado.
        
        Args:
            resultado: Edital/licitação com itens_correspondentes
            termos_busca: Termos originais da busca
            
        Returns:
            resultado enriquecido com relevance_score e relevance_level
        """
        scores = {
            'itens': self._score_itens(resultado),
            'tipo_match': self._score_tipo_match(resultado, termos_busca),
            'proximidade': self._score_proximidade(resultado),
            'modalidade': self._score_modalidade(resultado),
            'qualidade': self._score_qualidade(resultado)
        }
        
        # Score total (0-100)
        total = sum(scores.values())
        total = min(100, max(0, total))  # Garantir 0-100
        
        # Nível de relevância
        if total >= 70:
            level = "ALTA"
            emoji = "🔥"
        elif total >= 40:
            level = "MEDIA"
            emoji = "⚡"
        else:
            level = "BAIXA"
            emoji = "📋"
        
        # Enriquecer resultado
        resultado['relevance_score'] = round(total)
        resultado['relevance_level'] = level
        resultado['relevance_emoji'] = emoji
        resultado['relevance_breakdown'] = scores
        
        return resultado
    
    def _score_itens(self, resultado: Dict) -> int:
        """
        Score baseado em quantidade de itens compatíveis.
        
        - 1 item: 10 pts
        - 2-3 itens: 20 pts
        - 4+ itens: 30 pts
        """
        total_itens = resultado.get('total_itens_match', 0)
        itens = resultado.get('itens_correspondentes', [])
        
        if not total_itens:
            total_itens = len(itens)
        
        if total_itens >= 4:
            return self.PESO_ITENS  # 30
        elif total_itens >= 2:
            return int(self.PESO_ITENS * 0.67)  # 20
        elif total_itens >= 1:
            return int(self.PESO_ITENS * 0.33)  # 10
        return 0
    
    def _score_tipo_match(self, resultado: Dict, termos_busca: List[str]) -> int:
        """
        Score baseado no tipo de match.
        
        - Match exato no termo original: 25 pts
        - Match em sinônimo: 15 pts
        - Match parcial: 10 pts
        """
        itens = resultado.get('itens_correspondentes', [])
        if not itens:
            return 0
        
        termos_lower = [t.lower() for t in termos_busca]
        melhor_score = 0
        
        for item in itens:
            termo_match = (item.get('termo_match', '') or '').lower()
            descricao = (item.get('descricao', '') or '').lower()
            
            # Match exato no termo original
            if termo_match in termos_lower:
                # Verificar se é match exato na descrição
                for termo in termos_lower:
                    if termo in descricao:
                        # É o termo original E está na descrição
                        melhor_score = max(melhor_score, self.PESO_TIPO_MATCH)  # 25
                        break
            
            # Match em sinônimo (termo_match diferente do original)
            elif termo_match:
                melhor_score = max(melhor_score, int(self.PESO_TIPO_MATCH * 0.6))  # 15
            
            # Match parcial
            else:
                melhor_score = max(melhor_score, int(self.PESO_TIPO_MATCH * 0.4))  # 10
        
        return melhor_score
    
    def _score_proximidade(self, resultado: Dict) -> int:
        """
        Score baseado na proximidade da abertura.
        
        - Hoje ou amanhã: 20 pts
        - 2-7 dias: 18 pts
        - 8-30 dias: 15 pts
        - 31-60 dias: 10 pts
        - 61-90 dias: 5 pts
        - >90 dias ou sem data: 0 pts
        """
        dias = resultado.get('dias_ate_abertura')
        
        if dias is None:
            # Sem data - verificar se é credenciamento vigente
            if resultado.get('is_credenciamento'):
                return int(self.PESO_PROXIMIDADE * 0.5)  # 10 pts para credenciamento
            return 0
        
        if dias < 0:
            return 0  # Já passou
        elif dias <= 1:
            return self.PESO_PROXIMIDADE  # 20
        elif dias <= 7:
            return int(self.PESO_PROXIMIDADE * 0.9)  # 18
        elif dias <= 30:
            return int(self.PESO_PROXIMIDADE * 0.75)  # 15
        elif dias <= 60:
            return int(self.PESO_PROXIMIDADE * 0.5)  # 10
        elif dias <= 90:
            return int(self.PESO_PROXIMIDADE * 0.25)  # 5
        else:
            return 0
    
    def _score_modalidade(self, resultado: Dict) -> int:
        """
        Score baseado na modalidade.
        
        - Pregão/Concorrência: 15 pts
        - Dispensa/RDC: 12 pts
        - Credenciamento: 8 pts
        - Outros: 5 pts
        """
        modalidade = (resultado.get('modalidade') or resultado.get('tipo_modalidade') or '').lower()
        
        # Modalidades premium
        for mod in self.MODALIDADES_PREMIUM:
            if mod in modalidade:
                if "pregão" in modalidade or "pregao" in modalidade:
                    return self.PESO_MODALIDADE  # 15
                elif "concorrência" in modalidade or "concorrencia" in modalidade:
                    return self.PESO_MODALIDADE  # 15
                else:
                    return int(self.PESO_MODALIDADE * 0.8)  # 12
        
        # Credenciamento
        if "credenciamento" in modalidade or "chamamento" in modalidade:
            return int(self.PESO_MODALIDADE * 0.53)  # 8
        
        # Outros
        return int(self.PESO_MODALIDADE * 0.33)  # 5
    
    def _score_qualidade(self, resultado: Dict) -> int:
        """
        Score baseado na qualidade do dado.
        
        - Link direto válido: 5 pts
        - Itens estruturados (não fallback): 3 pts
        - Dados completos (datas, órgão): 2 pts
        """
        score = 0
        
        # Link válido
        link_status = resultado.get('link_status', '')
        if link_status == 'VALIDO':
            score += 5
        elif resultado.get('link_edital') or resultado.get('link_pncp'):
            score += 3
        
        # Itens estruturados
        itens = resultado.get('itens_correspondentes', [])
        if itens:
            fonte_item = itens[0].get('fonte', '')
            if fonte_item in ['itens_json', 'texto_parseado']:
                score += 3
            elif fonte_item not in ['objeto_fallback', 'objeto_virtual']:
                score += 2
        
        # Dados completos
        if resultado.get('data_abertura') and resultado.get('data_publicacao'):
            score += 1
        if resultado.get('orgao') or resultado.get('orgao_licitante'):
            score += 1
        
        return min(self.PESO_QUALIDADE, score)  # Max 10
    
    def ordenar_por_relevancia(
        self, 
        resultados: List[Dict], 
        termos_busca: List[str]
    ) -> List[Dict]:
        """
        Calcula score e ordena resultados por relevância (decrescente).
        
        Args:
            resultados: Lista de editais já filtrados
            termos_busca: Termos originais da busca
            
        Returns:
            Lista ordenada por relevance_score (maior primeiro)
        """
        # Calcular score para cada resultado
        for resultado in resultados:
            self.calcular_score(resultado, termos_busca)
        
        # Ordenar por score decrescente
        resultados_ordenados = sorted(
            resultados,
            key=lambda x: x.get('relevance_score', 0),
            reverse=True
        )
        
        # Adicionar posição no ranking
        for i, resultado in enumerate(resultados_ordenados):
            resultado['ranking_position'] = i + 1
        
        return resultados_ordenados
    
    def get_estatisticas(self, resultados: List[Dict]) -> Dict:
        """
        Retorna estatísticas de relevância do resultado.
        """
        if not resultados:
            return {
                'total': 0,
                'alta': 0,
                'media': 0,
                'baixa': 0,
                'score_medio': 0,
                'score_max': 0,
                'score_min': 0
            }
        
        scores = [r.get('relevance_score', 0) for r in resultados]
        levels = [r.get('relevance_level', 'BAIXA') for r in resultados]
        
        return {
            'total': len(resultados),
            'alta': levels.count('ALTA'),
            'media': levels.count('MEDIA'),
            'baixa': levels.count('BAIXA'),
            'score_medio': round(sum(scores) / len(scores), 1),
            'score_max': max(scores),
            'score_min': min(scores)
        }


# Singleton
_instance = None

def get_relevance_scorer() -> RelevanceScorer:
    """Retorna instância do scorer"""
    global _instance
    if _instance is None:
        _instance = RelevanceScorer()
    return _instance
