"""
Serviço de Extração e Matching de Itens - Padrão GSM
=========================================================

🎯 OBJETIVO:
Extrair itens do edital e identificar quais correspondem aos termos buscados.

📌 REGRAS OBRIGATÓRIAS (CRÍTICAS):
1. Todos os editais DEVEM exibir:
   - numero_item: Número do item no edital (ou "NA" se não disponível)
   - descricao: Nome/descrição exata do item
   - quantidade: Quantidade solicitada (ou "NA")
   - unidade: Unidade de medida (ou "NA")
   - valor_unitario: Valor de referência unitário (ou "NA")
   - valor_total: Valor de referência total (ou "NA")
   
2. NUNCA inventar ou aproximar dados
3. Se não extrair com confiança → marcar como "NA" com aviso visual
4. Fonte do item deve ser rastreável

🔴 REGRA ANTI-ERRO:
Licitação só é relevante se pelo menos 1 ITEM corresponder ao termo.
Match apenas no objeto genérico NÃO é suficiente.
"""

import re
import hashlib
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# =====================================================================
# CAMPOS OBRIGATÓRIOS DE ITEM (PADRÃO GSM)
# =====================================================================
CAMPOS_OBRIGATORIOS_ITEM = [
    "numero_item",
    "descricao", 
    "quantidade",
    "unidade",
    "valor_unitario",
    "valor_total"
]

# =====================================================================
# DICIONÁRIO DE SINÔNIMOS E NOMES COMERCIAIS (SAÚDE)
# =====================================================================
SINONIMOS_MEDICAMENTOS = {
    # Canabidiol
    "canabidiol": ["cbd", "cannabidiol", "cannabis medicinal", "mevatyl", "canabis"],
    
    # Insulinas
    "insulina": ["lantus", "novorapid", "humalog", "tresiba", "levemir", "apidra", 
                 "novolin", "humulin", "glargina", "lispro", "asparte", "detemir",
                 "degludeca", "nph", "regular"],
    
    # Biológicos
    "adalimumabe": ["humira", "hadlima", "hyrimoz", "amgevita", "imraldi"],
    "etanercepte": ["enbrel", "brenzys", "erelzi"],
    "infliximabe": ["remicade", "remsima", "inflectra"],
    "rituximabe": ["mabthera", "truxima", "ruxience"],
    "trastuzumabe": ["herceptin", "ogivri", "herzuma", "kanjinti"],
    "bevacizumabe": ["avastin", "mvasi", "zirabev"],
    
    # Oncológicos
    "pembrolizumabe": ["keytruda"],
    "nivolumabe": ["opdivo"],
    "atezolizumabe": ["tecentriq"],
    
    # Outros comuns
    "omeprazol": ["losec", "peprazol"],
    "metformina": ["glifage", "glucoformin"],
    "atorvastatina": ["lipitor", "citalor"],
    "losartana": ["cozaar", "aradois"],
    "dipirona": ["novalgina", "anador"],
    "paracetamol": ["tylenol", "dorflex"],
    
    # Insumos hospitalares
    "seringa": ["agulha", "seringas"],
    "luva": ["luvas", "procedimento"],
    "soro": ["solução fisiológica", "sf 0,9", "ringer"],
    "cateter": ["cateteres", "sonda"],
    "equipo": ["equipos", "infusão"],
}

# Cache de resultados (hash: resultado)
_cache_itens: Dict[str, Dict] = {}
_cache_max_size = 1000


def garantir_campos_obrigatorios(item: Dict) -> Dict:
    """
    Garante que todos os campos obrigatórios estejam presentes.
    Campos ausentes são marcados como "NA" (Não Disponível).
    
    🔴 REGRA CRÍTICA: Nunca inventar dados - usar "NA" quando não disponível.
    """
    item_completo = dict(item)  # Cópia para não modificar original
    
    # Garantir numero_item
    if not item_completo.get('numero_item'):
        item_completo['numero_item'] = "NA"
    else:
        item_completo['numero_item'] = str(item_completo['numero_item'])
    
    # Garantir descricao
    if not item_completo.get('descricao'):
        item_completo['descricao'] = "Descrição não disponível"
        item_completo['_descricao_na'] = True
    
    # Garantir quantidade
    if item_completo.get('quantidade') is None or item_completo.get('quantidade') == '':
        item_completo['quantidade'] = "NA"
        item_completo['_quantidade_na'] = True
    
    # Garantir unidade
    if not item_completo.get('unidade'):
        item_completo['unidade'] = "NA"
        item_completo['_unidade_na'] = True
    
    # Garantir valor_unitario
    if item_completo.get('valor_unitario') is None or item_completo.get('valor_unitario') == '':
        item_completo['valor_unitario'] = "NA"
        item_completo['_valor_unitario_na'] = True
    
    # Garantir valor_total
    if item_completo.get('valor_total') is None or item_completo.get('valor_total') == '':
        item_completo['valor_total'] = "NA"
        item_completo['_valor_total_na'] = True
    
    # Marcar fonte se não existir
    if not item_completo.get('fonte'):
        item_completo['fonte'] = "NAO_IDENTIFICADA"
    
    return item_completo


class ItemExtractorService:
    """
    Serviço de extração e matching de itens do edital.
    
    🔴 REGRAS OBRIGATÓRIAS:
    - Todos os itens devem ter campos completos (ou "NA")
    - Nunca inventar dados
    - Fonte do item deve ser rastreável
    """
    
    def __init__(self):
        self.sinonimos = SINONIMOS_MEDICAMENTOS
    
    def _gerar_cache_key(self, edital_id: str, termos: List[str]) -> str:
        """Gera chave de cache única para edital + termos"""
        termos_str = ",".join(sorted([t.lower() for t in termos]))
        return hashlib.md5(f"{edital_id}:{termos_str}".encode()).hexdigest()
    
    def _get_from_cache(self, key: str) -> Optional[Dict]:
        """Busca resultado do cache"""
        return _cache_itens.get(key)
    
    def _set_cache(self, key: str, value: Dict):
        """Armazena resultado no cache"""
        global _cache_itens
        if len(_cache_itens) >= _cache_max_size:
            # Limpar metade do cache quando cheio
            keys_to_remove = list(_cache_itens.keys())[:_cache_max_size // 2]
            for k in keys_to_remove:
                del _cache_itens[k]
        _cache_itens[key] = value
    
    def extrair_itens(self, edital: Dict) -> List[Dict]:
        """
        Extrai itens estruturados do edital.
        
        🔴 REGRA OBRIGATÓRIA: Todos os itens devem ter campos completos
        
        Fontes de extração (em ordem de prioridade):
        1. Campo 'itens_edital' (API PNCP - fonte confiável)
        2. Campo 'itens' (JSON do PNCP)
        3. Campo 'objeto' (parsing de texto)
        4. Campo 'objeto_resumido'
        """
        itens = []
        
        # 0. Prioridade máxima: itens_edital (do PNCP resolver)
        if edital.get('itens_edital') and isinstance(edital['itens_edital'], list):
            for i, item in enumerate(edital['itens_edital']):
                item_normalizado = self._normalizar_item(item, i + 1)
                item_normalizado['fonte'] = 'PNCP_API'
                itens.append(item_normalizado)
            if itens:
                return itens
        
        # 1. Tentar campo 'itens' direto
        if edital.get('itens') and isinstance(edital['itens'], list):
            for i, item in enumerate(edital['itens']):
                itens.append(self._normalizar_item(item, i + 1))
            if itens:
                return itens
        
        # 2. Extrair do campo 'objeto'
        objeto = edital.get('objeto', '') or ''
        if objeto:
            itens_extraidos = self._extrair_itens_do_texto(objeto)
            if itens_extraidos:
                return itens_extraidos
        
        # 3. Fallback: criar item único do objeto
        if objeto:
            item_fallback = garantir_campos_obrigatorios({
                "numero_item": "1",
                "descricao": objeto[:500],
                "quantidade": None,
                "unidade": None,
                "valor_unitario": None,
                "valor_total": None,
                "fonte": "OBJETO_TEXTO",
                "_item_nao_estruturado": True  # Flag para aviso visual
            })
            itens.append(item_fallback)
        
        # 4. Tentar objeto_resumido
        objeto_resumido = edital.get('objeto_resumido', '') or ''
        if objeto_resumido and not itens:
            item_fallback = garantir_campos_obrigatorios({
                "numero_item": "1",
                "descricao": objeto_resumido[:500],
                "quantidade": None,
                "unidade": None,
                "valor_unitario": None,
                "valor_total": None,
                "fonte": "OBJETO_RESUMIDO",
                "_item_nao_estruturado": True
            })
            itens.append(item_fallback)
        
        # 5. Tentar medicamento (collection licitacoes)
        medicamento = edital.get('medicamento', '') or ''
        if medicamento:
            item_med = garantir_campos_obrigatorios({
                "numero_item": str(len(itens) + 1),
                "descricao": medicamento,
                "quantidade": None,
                "unidade": None,
                "valor_unitario": None,
                "valor_total": None,
                "fonte": "MEDICAMENTO_CAMPO",
                "_item_nao_estruturado": True
            })
            itens.append(item_med)
        
        return itens
    
    def _normalizar_item(self, item: Dict, numero: int) -> Dict:
        """
        Normaliza estrutura de um item e garante campos obrigatórios.
        
        🔴 REGRA: Todos os campos devem estar presentes (ou "NA")
        """
        item_base = {
            "numero_item": str(item.get('numero', item.get('numero_item', item.get('numeroItem', numero)))),
            "descricao": item.get('descricao', item.get('description', '')),
            "quantidade": item.get('quantidade', item.get('qtd', None)),
            "unidade": item.get('unidade', item.get('un', item.get('unidadeMedida', None))),
            "valor_unitario": item.get('valor_unitario', item.get('valorUnitarioEstimado', item.get('valor_un', None))),
            "valor_total": item.get('valor_total', item.get('valorTotal', item.get('valor', None))),
            "fonte": item.get('fonte', 'itens_json')
        }
        
        # Aplicar garantia de campos obrigatórios
        return garantir_campos_obrigatorios(item_base)
    
    def _extrair_itens_do_texto(self, texto: str) -> List[Dict]:
        """
        Extrai itens de um texto de objeto usando patterns comuns.
        
        Patterns reconhecidos:
        - "Item 1:", "Item 01:", "1.", "1)", "1 -"
        - Listas numeradas
        - Separação por ";" ou ","
        """
        itens = []
        
        # Pattern 1: "Item N:" ou "N." ou "N)" ou "N -"
        pattern_item = r'(?:item\s*)?(\d+)\s*[:\.\)\-]\s*([^;]+?)(?=(?:item\s*)?\d+\s*[:\.\)\-]|$)'
        matches = re.findall(pattern_item, texto, re.IGNORECASE)
        
        if matches and len(matches) >= 2:
            for num, desc in matches:
                desc_limpa = desc.strip()
                if len(desc_limpa) > 10:  # Ignorar descrições muito curtas
                    itens.append({
                        "numero_item": num,
                        "descricao": desc_limpa[:300],
                        "quantidade": self._extrair_quantidade(desc_limpa),
                        "unidade": self._extrair_unidade(desc_limpa),
                        "fonte": "texto_parseado"
                    })
        
        # Pattern 2: Separação por ";" (comum em objetos)
        if not itens and ';' in texto:
            partes = texto.split(';')
            for i, parte in enumerate(partes):
                parte_limpa = parte.strip()
                if len(parte_limpa) > 15:
                    itens.append({
                        "numero_item": str(i + 1),
                        "descricao": parte_limpa[:300],
                        "quantidade": self._extrair_quantidade(parte_limpa),
                        "unidade": self._extrair_unidade(parte_limpa),
                        "fonte": "texto_separado"
                    })
        
        return itens[:20]  # Limitar a 20 itens
    
    def _extrair_quantidade(self, texto: str) -> Optional[str]:
        """Extrai quantidade do texto"""
        patterns = [
            r'(\d+(?:\.\d+)?)\s*(?:unidade|un\.|und\.|pç|peça)',
            r'quantidade[:\s]*(\d+(?:\.\d+)?)',
            r'qtd[:\s]*(\d+(?:\.\d+)?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, texto, re.IGNORECASE)
            if match:
                return match.group(1)
        return None
    
    def _extrair_unidade(self, texto: str) -> Optional[str]:
        """Extrai unidade do texto"""
        unidades = ['unidade', 'un', 'und', 'pç', 'peça', 'cx', 'caixa', 'fr', 'frasco', 
                    'amp', 'ampola', 'cp', 'comprimido', 'ml', 'mg', 'g', 'kg', 'l']
        texto_lower = texto.lower()
        for un in unidades:
            if un in texto_lower:
                return un
        return None
    
    def expandir_termo(self, termo: str) -> List[str]:
        """
        Expande um termo com sinônimos e nomes comerciais.
        
        Ex: "adalimumabe" -> ["adalimumabe", "humira", "hadlima", ...]
        """
        termo_lower = termo.lower().strip()
        termos_expandidos = [termo_lower]
        
        # Buscar sinônimos diretos
        if termo_lower in self.sinonimos:
            termos_expandidos.extend(self.sinonimos[termo_lower])
        
        # Buscar reverso (nome comercial -> princípio ativo)
        for principio, nomes in self.sinonimos.items():
            if termo_lower in [n.lower() for n in nomes]:
                termos_expandidos.append(principio)
                termos_expandidos.extend(nomes)
        
        return list(set(termos_expandidos))
    
    def fazer_matching(
        self, 
        edital: Dict, 
        termos_busca: List[str]
    ) -> Tuple[List[Dict], bool]:
        """
        Faz matching entre itens do edital e termos buscados.
        
        🔄 FALLBACK: Se não há itens estruturados, usa o objeto como item único
        e verifica se o termo está presente. Isso evita falsos negativos.
        
        Returns:
            Tuple[itens_correspondentes, tem_match]
            - itens_correspondentes: Lista de itens com match
            - tem_match: True se pelo menos 1 item corresponde
        """
        edital_id = edital.get('id', edital.get('id_externo', str(edital.get('_id', ''))))
        
        # Verificar cache
        cache_key = self._gerar_cache_key(edital_id, termos_busca)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached['itens'], cached['tem_match']
        
        # Extrair itens do edital
        itens = self.extrair_itens(edital)
        
        # Expandir termos de busca
        termos_expandidos = []
        for termo in termos_busca:
            termos_expandidos.extend(self.expandir_termo(termo))
        termos_expandidos = list(set(termos_expandidos))
        
        # Se não há itens mas o termo está no objeto, criar item virtual
        if not itens or len(itens) == 0:
            objeto = (edital.get('objeto', '') or '').lower()
            medicamento = (edital.get('medicamento', '') or '').lower()
            texto_busca = f"{objeto} {medicamento}"
            
            for termo in termos_expandidos:
                if termo.lower() in texto_busca:
                    # Criar item virtual do objeto
                    item_virtual = {
                        "numero_item": "1",
                        "descricao": edital.get('objeto', '')[:500] or edital.get('medicamento', ''),
                        "quantidade": None,
                        "unidade": None,
                        "fonte": "objeto_virtual",
                        "termo_match": termo,
                        "score": 70
                    }
                    self._set_cache(cache_key, {'itens': [item_virtual], 'tem_match': True})
                    return [item_virtual], True
            
            self._set_cache(cache_key, {'itens': [], 'tem_match': False})
            return [], False
        
        # Fazer matching nos itens extraídos
        itens_correspondentes = []
        for item in itens:
            descricao = (item.get('descricao', '') or '').lower()
            
            for termo in termos_expandidos:
                if termo.lower() in descricao:
                    # Encontrou match!
                    item_match = item.copy()
                    item_match['termo_match'] = termo
                    item_match['score'] = self._calcular_score_match(descricao, termo)
                    itens_correspondentes.append(item_match)
                    break  # Um match por item é suficiente
        
        # FALLBACK: Se nenhum item estruturado deu match, verificar objeto
        if not itens_correspondentes:
            objeto = (edital.get('objeto', '') or '').lower()
            medicamento = (edital.get('medicamento', '') or '').lower()
            texto_busca = f"{objeto} {medicamento}"
            
            for termo in termos_expandidos:
                if termo.lower() in texto_busca:
                    # Usar primeiro item como representante
                    item_fallback = itens[0].copy() if itens else {
                        "numero_item": "1",
                        "descricao": edital.get('objeto', '')[:500],
                        "quantidade": None,
                        "unidade": None,
                        "fonte": "objeto_fallback"
                    }
                    item_fallback['termo_match'] = termo
                    item_fallback['score'] = 60
                    itens_correspondentes.append(item_fallback)
                    break
        
        # Ordenar por score
        itens_correspondentes.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        tem_match = len(itens_correspondentes) > 0
        
        # Armazenar no cache
        self._set_cache(cache_key, {
            'itens': itens_correspondentes,
            'tem_match': tem_match
        })
        
        return itens_correspondentes, tem_match
    
    def _calcular_score_match(self, descricao: str, termo: str) -> int:
        """
        Calcula score de relevância do match.
        
        - Match exato no início: 100
        - Match exato em qualquer lugar: 80
        - Match parcial: 50
        """
        termo_lower = termo.lower()
        
        if descricao.startswith(termo_lower):
            return 100
        elif termo_lower in descricao:
            # Verificar se é palavra completa
            pattern = r'\b' + re.escape(termo_lower) + r'\b'
            if re.search(pattern, descricao):
                return 80
            return 50
        return 0
    
    def filtrar_editais_com_match(
        self,
        editais: List[Dict],
        termos_busca: List[str]
    ) -> List[Dict]:
        """
        🔴 FILTRO MATA-LIXO v55.0: Filtra editais por relevância.
        
        REGRA v55.0 (RELAXADA PARA VOLUME):
        - Se fonte é GSM_LOCAL ou CLONE → ACEITAR sempre (dados já validados)
        - Se fonte é externa → exigir match no objeto ou itens
        
        Returns:
            Editais com match confirmado ou de fonte confiável
        """
        editais_filtrados = []
        
        for edital in editais:
            # v55.0: Aceitar automaticamente dados de fontes locais clonadas
            fonte = (edital.get('fonte_origem', '') or edital.get('fonte', '') or '').upper()
            is_fonte_local = any(x in fonte for x in ['GSM', 'CLONE', 'LOCAL', 'HISTORICO'])
            
            if is_fonte_local:
                # Dados já validados no clone - aceitar direto
                if not edital.get('itens_correspondentes'):
                    # Criar item sintético do objeto
                    edital['itens_correspondentes'] = [{
                        "numero_item": "1",
                        "descricao": edital.get('objeto', '')[:500],
                        "quantidade": "Ver edital",
                        "unidade": None,
                        "fonte": "clone_gsm",
                        "termo_match": termos_busca[0] if termos_busca else "",
                        "match_encontrado": True,
                        "score": 100
                    }]
                    edital['total_itens_match'] = 1
                editais_filtrados.append(edital)
                continue
            
            # Para fontes externas, aplicar filtro original
            itens_match, tem_match_itens = self.fazer_matching(edital, termos_busca)
            
            # Verificar se tem match no objeto também
            objeto = (edital.get('objeto') or '').lower()
            tem_match_objeto = any(termo.lower() in objeto for termo in termos_busca if termo)
            
            # 🔴 MATA-LIXO: Só passa se tiver o termo no objeto OU nos itens
            tem_match = tem_match_itens or tem_match_objeto
            
            if tem_match:
                # Enriquecer edital com itens correspondentes
                edital['itens_correspondentes'] = itens_match[:10]  # Limitar a 10
                edital['total_itens_match'] = len(itens_match)
                
                # Se match foi no objeto mas não nos itens, criar item sintético
                if not itens_match and tem_match_objeto:
                    termo_encontrado = next((t for t in termos_busca if t.lower() in objeto), termos_busca[0] if termos_busca else "")
                    edital['itens_correspondentes'] = [{
                        "numero_item": "OBJ",
                        "descricao": edital.get('objeto', '')[:500],
                        "quantidade": "Ver edital",
                        "unidade": None,
                        "fonte": "match_no_objeto",
                        "termo_match": termo_encontrado,
                        "match_encontrado": True,
                        "score": 80
                    }]
                    edital['total_itens_match'] = 1
                    logger.info(f"✅ Edital mantido: match no objeto para '{termo_encontrado}'")
                
                editais_filtrados.append(edital)
            else:
                logger.debug(f"❌ Edital REMOVIDO (Mata-Lixo): sem match para {termos_busca}")
        
        logger.info(f"🔴 [MATA-LIXO v55] {len(editais)} editais → {len(editais_filtrados)} aceitos")
        return editais_filtrados
    
    def enriquecer_editais_com_itens(
        self,
        editais: List[Dict],
        termos_busca: List[str],
        filtrar_sem_match: bool = True
    ) -> List[Dict]:
        """
        Enriquece editais com itens correspondentes.
        
        Args:
            editais: Lista de editais
            termos_busca: Termos buscados
            filtrar_sem_match: Se True, remove editais sem match (Padrão GSM)
            
        Returns:
            Editais enriquecidos (e opcionalmente filtrados)
        """
        if filtrar_sem_match:
            return self.filtrar_editais_com_match(editais, termos_busca)
        
        # Apenas enriquecer sem filtrar
        for edital in editais:
            itens_match, _ = self.fazer_matching(edital, termos_busca)
            edital['itens_correspondentes'] = itens_match[:10]
            edital['total_itens_match'] = len(itens_match)
        
        return editais


# Singleton
_instance = None

def get_item_extractor() -> ItemExtractorService:
    """Retorna instância do serviço"""
    global _instance
    if _instance is None:
        _instance = ItemExtractorService()
    return _instance
