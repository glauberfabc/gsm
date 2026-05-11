"""
Serviço de Enriquecimento de Dados - GSM Buscador de Editais
============================================================

Este módulo implementa a inteligência de negócios da Smart Medical,
transformando dados brutos de qualquer fonte (PNCP, Agregador, Scrapers)
em registros enriquecidos com:

1. Cálculo de Iminência (dias/horas até a abertura)
2. Tags Inteligentes de Saúde (categorização automática)
3. Score de Relevância (priorização automática)
4. Normalização de dados (formatos padronizados)

Este módulo substitui a necessidade de usar o Agregador como
"processador de dados", tornando o sistema GSM completamente autossuficiente.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import logging
import re

logger = logging.getLogger(__name__)


# =============================================================================
# CONSTANTES DE NEGÓCIO - SMART MEDICAL
# =============================================================================

# Tags de Saúde organizadas por categoria (Core Business)
TAGS_SAUDE = {
    "🏥 Hospitalar": [
        "hospital", "hospitalar", "ambulatório", "ambulatorial", "uti", 
        "upa", "ubs", "samu", "pronto-socorro", "pronto socorro",
        "enfermaria", "centro cirúrgico", "bloco cirúrgico"
    ],
    "💊 Medicamentos": [
        "medicament", "fármaco", "farmacêutico", "remédio", "droga",
        "comprimido", "cápsula", "ampola", "injetável", "solução oral",
        "antibiótico", "analgésico", "anti-inflamatório", "antiviral"
    ],
    "🩺 Equipamentos Médicos": [
        "equipamento médico", "aparelho", "monitor", "desfibrilador",
        "ventilador", "respirador", "eletrocardiógrafo", "ultrassom",
        "raio-x", "tomógrafo", "ressonância", "endoscópio", "bisturi"
    ],
    "🧪 Laboratório": [
        "laborat", "exame", "teste", "reagente", "kit diagnóstico",
        "hemograma", "bioquímica", "microscópio", "centrífuga"
    ],
    "💉 Insumos Médicos": [
        "seringa", "agulha", "cateter", "sonda", "gaze", "algodão",
        "luva", "máscara", "avental", "touca", "propé", "epi",
        "curativo", "bandagem", "esparadrapo", "compressa"
    ],
    "🦷 Odontologia": [
        "odontológic", "dentário", "dental", "dentista",
        "ortodontia", "prótese dentária", "implante dental"
    ],
    "👁️ Oftalmologia": [
        "oftalmológic", "óculos", "lente", "colírio", "oftalmoscópio"
    ],
    "🩻 Oncologia": [
        "oncológic", "quimioterapia", "quimioterápic", "radioterapia",
        "câncer", "tumor", "neoplasia"
    ],
    "🫀 Cardiologia": [
        "cardiológic", "cardíaco", "marca-passo", "stent", "cateterismo"
    ],
    "🧬 Especialidades": [
        "insulina", "vacina", "imunização", "hemodiálise", "diálise",
        "transplante", "ortopédic", "protese", "órtese"
    ],
    "👨‍⚕️ Serviços de Saúde": [
        "serviço médico", "serviços médicos", "atendimento médico", "consulta médica",
        "fisioterapia", "fonoaudiologia", "nutrição clínica",
        "psicologia", "terapia ocupacional", "assistência à saúde",
        "prestação de serviços médicos", "credenciamento médico",
        "contratação de médicos", "profissionais de saúde"
    ],
    "🩹 Saúde Geral": [
        "saúde", "saude", "sus ", "sus,", "sistema único de saúde",
        "secretaria de saúde", "fundo de saúde", "fundo municipal de saúde",
        "consórcio de saúde", "consorcio de saude"
    ]
}

# Palavras-chave de urgência
KEYWORDS_URGENCIA = [
    "urgente", "urgência", "emergencial", "emergência", 
    "imediata", "imediato", "caráter urgente", "prazo exíguo",
    "covid", "pandemia", "epidemia", "calamidade"
]

# Palavras-chave de exclusão (não são de saúde)
KEYWORDS_EXCLUSAO = [
    "obra", "construção civil", "pavimentação", "asfalto",
    "mobiliário urbano", "praça", "iluminação pública",
    "veículo automotor", "combustível", "gasolina", "diesel",
    "limpeza urbana", "coleta de lixo"
]

# Mapa de UFs por nome
UF_MAP = {
    'acre': 'AC', 'alagoas': 'AL', 'amapá': 'AP', 'amazonas': 'AM',
    'bahia': 'BA', 'ceará': 'CE', 'distrito federal': 'DF', 'espírito santo': 'ES',
    'goiás': 'GO', 'maranhão': 'MA', 'mato grosso': 'MT', 'mato grosso do sul': 'MS',
    'minas gerais': 'MG', 'pará': 'PA', 'paraíba': 'PB', 'paraná': 'PR',
    'pernambuco': 'PE', 'piauí': 'PI', 'rio de janeiro': 'RJ', 'rio grande do norte': 'RN',
    'rio grande do sul': 'RS', 'rondônia': 'RO', 'roraima': 'RR', 'santa catarina': 'SC',
    'são paulo': 'SP', 'sergipe': 'SE', 'tocantins': 'TO'
}


class DataEnrichmentService:
    """
    Serviço de enriquecimento de dados de licitações.
    
    Transforma dados brutos em registros enriquecidos com:
    - Iminência calculada
    - Tags de saúde categorizadas
    - Score de relevância
    - Dados normalizados
    """
    
    def __init__(self):
        self.tags_saude = TAGS_SAUDE
        self.keywords_urgencia = KEYWORDS_URGENCIA
        self.keywords_exclusao = KEYWORDS_EXCLUSAO
    
    # =========================================================================
    # MÉTODOS PÚBLICOS
    # =========================================================================
    
    def enriquecer_licitacao(self, licitacao: Dict) -> Dict:
        """
        Enriquece uma licitação individual com dados calculados.
        
        Args:
            licitacao: Dicionário com dados da licitação
            
        Returns:
            Licitação enriquecida
        """
        # Extrair texto para análise
        objeto = (licitacao.get('objeto') or licitacao.get('objetoCompra') or '').lower()
        orgao = (licitacao.get('orgao_licitante') or licitacao.get('orgaoNome') or '').lower()
        texto_completo = f"{objeto} {orgao}"
        
        # 1. Calcular iminência
        data_limite = self._extrair_data_limite(licitacao)
        iminencia_info = self._calcular_iminencia(data_limite)
        
        # 2. Extrair tags de saúde
        tags_saude = self._extrair_tags_saude(texto_completo)
        
        # 3. Verificar urgência
        is_urgente = self._verificar_urgencia(texto_completo, iminencia_info['dias'])
        if is_urgente:
            tags_saude.insert(0, "🚨 URGENTE")
        
        # 4. Calcular score de relevância
        score = self._calcular_score_relevancia(
            tags_saude=tags_saude,
            iminencia_dias=iminencia_info['dias'],
            is_urgente=is_urgente,
            objeto=objeto
        )
        
        # 5. Normalizar UF
        uf = self._normalizar_uf(licitacao.get('estado') or licitacao.get('uf'))
        
        # 6. Determinar esfera
        esfera = self._determinar_esfera(orgao)
        
        # 7. Verificar se é de saúde
        is_saude = len(tags_saude) > 0 or self._e_de_saude(texto_completo)
        
        # Retornar licitação enriquecida
        licitacao_enriquecida = {
            **licitacao,
            # Campos calculados
            'iminencia': iminencia_info['dias'],
            'iminencia_display': iminencia_info['display'],
            'iminencia_badge': iminencia_info['badge'],
            'tags_saude': tags_saude,
            'tags_display': ', '.join(tags_saude) if tags_saude else 'Geral',
            'score_relevancia': score,
            'is_urgente': is_urgente,
            'is_saude': is_saude,
            'is_futuro': iminencia_info['dias'] >= 0 if iminencia_info['dias'] is not None else True,
            # Campos normalizados
            'estado': uf,
            'esfera': esfera,
            'data_limite_formatada': data_limite.strftime('%d/%m/%Y %H:%M') if data_limite else 'N/D',
            # Timestamp de enriquecimento
            'enriched_at': datetime.now().isoformat()
        }
        
        return licitacao_enriquecida
    
    def enriquecer_lote(self, licitacoes: List[Dict]) -> List[Dict]:
        """
        Enriquece um lote de licitações.
        
        Args:
            licitacoes: Lista de licitações brutas
            
        Returns:
            Lista de licitações enriquecidas e ordenadas por relevância
        """
        logger.info(f"🔬 [ENRICHMENT] Processando {len(licitacoes)} licitações...")
        
        enriquecidas = []
        for lic in licitacoes:
            try:
                enriquecida = self.enriquecer_licitacao(lic)
                enriquecidas.append(enriquecida)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao enriquecer licitação: {e}")
                enriquecidas.append(lic)  # Manter original em caso de erro
        
        # Ordenar por score de relevância (maior primeiro)
        enriquecidas.sort(key=lambda x: x.get('score_relevancia', 0), reverse=True)
        
        # Estatísticas
        saude_count = sum(1 for l in enriquecidas if l.get('is_saude'))
        urgente_count = sum(1 for l in enriquecidas if l.get('is_urgente'))
        
        logger.info(f"✅ [ENRICHMENT] Concluído: {len(enriquecidas)} processadas, {saude_count} de saúde, {urgente_count} urgentes")
        
        return enriquecidas
    
    def filtrar_saude(self, licitacoes: List[Dict]) -> List[Dict]:
        """Filtra apenas licitações de saúde."""
        return [l for l in licitacoes if l.get('is_saude', False)]
    
    def filtrar_urgentes(self, licitacoes: List[Dict]) -> List[Dict]:
        """Filtra apenas licitações urgentes."""
        return [l for l in licitacoes if l.get('is_urgente', False)]
    
    def filtrar_futuras(self, licitacoes: List[Dict]) -> List[Dict]:
        """Filtra apenas licitações futuras."""
        return [l for l in licitacoes if l.get('is_futuro', True)]
    
    # =========================================================================
    # MÉTODOS PRIVADOS - CÁLCULOS
    # =========================================================================
    
    def _extrair_data_limite(self, licitacao: Dict) -> Optional[datetime]:
        """Extrai a data limite da licitação de vários campos possíveis."""
        campos_data = [
            'data_final', 'data_limite', 'data_abertura',
            'dataEncerramentoProposta', 'dataAberturaProposta',
            'dataHoraProposta', 'dataFinal', 'dataInicial'
        ]
        
        for campo in campos_data:
            valor = licitacao.get(campo)
            if valor:
                data = self._parse_data(valor)
                if data:
                    return data
        
        return None
    
    def _parse_data(self, valor) -> Optional[datetime]:
        """Converte vários formatos de data para datetime."""
        if not valor:
            return None
        
        if isinstance(valor, datetime):
            return valor
        
        valor_str = str(valor).strip()
        
        # Formatos comuns
        formatos = [
            '%Y-%m-%dT%H:%M:%S',      # ISO com T
            '%Y-%m-%d %H:%M:%S',       # ISO com espaço
            '%Y-%m-%dT%H:%M:%S.%f',    # ISO com microsegundos
            '%Y-%m-%d',                # Apenas data
            '%d/%m/%Y %H:%M:%S',       # BR completo
            '%d/%m/%Y %H:%M',          # BR sem segundos
            '%d/%m/%Y',                # BR apenas data
        ]
        
        for fmt in formatos:
            try:
                return datetime.strptime(valor_str[:len(fmt)+5], fmt)
            except:
                continue
        
        return None
    
    def _calcular_iminencia(self, data_limite: Optional[datetime]) -> Dict:
        """
        Calcula a iminência (tempo até a abertura).
        
        Returns:
            Dict com 'dias', 'display' e 'badge'
        """
        if not data_limite:
            return {
                'dias': None,
                'display': 'Data não informada',
                'badge': '⚪'
            }
        
        agora = datetime.now()
        delta = data_limite - agora
        dias = delta.days
        horas = delta.total_seconds() / 3600
        
        # Já passou
        if horas < 0:
            return {
                'dias': dias,
                'display': f"Encerrado em {data_limite.strftime('%d/%m')}",
                'badge': '❌'
            }
        
        # HOJE (menos de 24h)
        if dias == 0:
            return {
                'dias': 0,
                'display': f"🔴 HOJE! ({int(horas)}h restantes)",
                'badge': '🔴'
            }
        
        # Muito urgente (1-3 dias)
        if dias <= 3:
            return {
                'dias': dias,
                'display': f"🟠 {dias} dia{'s' if dias > 1 else ''} (URGENTE)",
                'badge': '🟠'
            }
        
        # Urgente (4-7 dias)
        if dias <= 7:
            return {
                'dias': dias,
                'display': f"🟡 {dias} dias",
                'badge': '🟡'
            }
        
        # Normal (8-30 dias)
        if dias <= 30:
            return {
                'dias': dias,
                'display': f"🟢 {dias} dias",
                'badge': '🟢'
            }
        
        # Longo prazo (31+ dias)
        return {
            'dias': dias,
            'display': f"🔵 {dias} dias (Longo Prazo)",
            'badge': '🔵'
        }
    
    def _extrair_tags_saude(self, texto: str) -> List[str]:
        """Extrai tags de saúde do texto."""
        tags = []
        texto_lower = texto.lower()
        
        # Verificar exclusões primeiro
        for exclusao in self.keywords_exclusao:
            if exclusao in texto_lower:
                return []  # Não é de saúde
        
        # Buscar tags por categoria
        for categoria, keywords in self.tags_saude.items():
            for keyword in keywords:
                if keyword in texto_lower:
                    if categoria not in tags:
                        tags.append(categoria)
                    break  # Uma keyword por categoria é suficiente
        
        return tags
    
    def _verificar_urgencia(self, texto: str, dias: Optional[int]) -> bool:
        """Verifica se a licitação é urgente."""
        texto_lower = texto.lower()
        
        # Urgência por palavras-chave
        for keyword in self.keywords_urgencia:
            if keyword in texto_lower:
                return True
        
        # Urgência por prazo
        if dias is not None and 0 <= dias <= 3:
            return True
        
        return False
    
    def _calcular_score_relevancia(
        self,
        tags_saude: List[str],
        iminencia_dias: Optional[int],
        is_urgente: bool,
        objeto: str
    ) -> int:
        """
        Calcula um score de relevância para priorização.
        
        Score maior = mais relevante para Smart Medical
        """
        score = 0
        
        # Base: tags de saúde (+20 cada)
        score += len(tags_saude) * 20
        
        # Bônus por urgência (+50)
        if is_urgente:
            score += 50
        
        # Bônus por iminência
        if iminencia_dias is not None:
            if iminencia_dias == 0:  # HOJE
                score += 100
            elif iminencia_dias <= 3:  # 1-3 dias
                score += 80
            elif iminencia_dias <= 7:  # 4-7 dias
                score += 60
            elif iminencia_dias <= 30:  # 8-30 dias
                score += 40
            else:
                score += 10  # Longo prazo
        
        # Bônus por palavras-chave específicas de alto valor
        palavras_alto_valor = [
            'medicament', 'insulina', 'vacina', 'equipamento médico',
            'hospital', 'quimioterapia', 'cirúrgico', 'uti'
        ]
        for palavra in palavras_alto_valor:
            if palavra in objeto:
                score += 30
                break
        
        return score
    
    def _normalizar_uf(self, uf: str) -> str:
        """Normaliza o nome do estado para sigla UF."""
        if not uf:
            return ''
        
        uf_str = str(uf).strip()
        
        # Já é sigla de 2 letras
        if len(uf_str) == 2:
            return uf_str.upper()
        
        # Buscar no mapa
        uf_lower = uf_str.lower()
        return UF_MAP.get(uf_lower, uf_str[:2].upper())
    
    def _determinar_esfera(self, orgao: str) -> str:
        """Determina a esfera administrativa."""
        orgao_lower = orgao.lower()
        
        palavras_federal = ['federal', 'união', 'ministério', 'brasil']
        palavras_municipal = ['municipal', 'prefeitura', 'câmara municipal']
        
        for palavra in palavras_federal:
            if palavra in orgao_lower:
                return 'Federal'
        
        for palavra in palavras_municipal:
            if palavra in orgao_lower:
                return 'Municipal'
        
        return 'Estadual'
    
    def _e_de_saude(self, texto: str) -> bool:
        """Verifica se o texto indica área de saúde."""
        texto_lower = texto.lower()
        
        # Verificar exclusões
        for exclusao in self.keywords_exclusao:
            if exclusao in texto_lower:
                return False
        
        # Verificar inclusões
        for categoria, keywords in self.tags_saude.items():
            for keyword in keywords:
                if keyword in texto_lower:
                    return True
        
        return False


# Instância singleton
data_enrichment_service = DataEnrichmentService()


# =============================================================================
# FUNÇÕES DE CONVENIÊNCIA
# =============================================================================

def enriquecer_licitacao(licitacao: Dict) -> Dict:
    """Função de conveniência para enriquecer uma licitação."""
    return data_enrichment_service.enriquecer_licitacao(licitacao)

def enriquecer_lote(licitacoes: List[Dict]) -> List[Dict]:
    """Função de conveniência para enriquecer um lote."""
    return data_enrichment_service.enriquecer_lote(licitacoes)


# =============================================================================
# TESTE
# =============================================================================

if __name__ == "__main__":
    # Teste com dados simulados
    licitacoes_teste = [
        {
            "objeto": "Aquisição de MEDICAMENTOS para uso hospitalar - insulina e antibióticos",
            "orgao_licitante": "Hospital Municipal de São Paulo",
            "data_final": (datetime.now() + timedelta(days=2)).isoformat(),
            "estado": "SP"
        },
        {
            "objeto": "Contratação de serviços de limpeza predial",
            "orgao_licitante": "Prefeitura de Osasco",
            "data_final": (datetime.now() + timedelta(days=30)).isoformat(),
            "estado": "SP"
        },
        {
            "objeto": "Compra de EQUIPAMENTOS MÉDICOS para UTI - ventiladores e monitores",
            "orgao_licitante": "Ministério da Saúde",
            "data_final": (datetime.now() + timedelta(hours=12)).isoformat(),
            "estado": "DF"
        }
    ]
    
    print("=" * 60)
    print("🔬 TESTE DE ENRIQUECIMENTO DE DADOS")
    print("=" * 60)
    
    enriquecidas = enriquecer_lote(licitacoes_teste)
    
    for lic in enriquecidas:
        print(f"\n📋 {lic['objeto'][:50]}...")
        print(f"   🏷️ Tags: {lic['tags_display']}")
        print(f"   ⏰ Iminência: {lic['iminencia_display']}")
        print(f"   📊 Score: {lic['score_relevancia']}")
        print(f"   🏥 É Saúde: {lic['is_saude']}")
        print(f"   🚨 Urgente: {lic['is_urgente']}")
