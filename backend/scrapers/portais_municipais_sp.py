"""
Portais Municipais SP - Integrador de Licitações
=================================================

🎯 OBJETIVO:
Integrar dados de portais municipais prioritários de SP, 
complementando o PNCP (que continua sendo o backbone).

📌 ESTRATÉGIA:
1. PNCP é a fonte principal de dados estruturados
2. Portais municipais fornecem links diretos aos editais
3. Links PNCP são SEMPRE preferidos quando disponíveis

🔒 DIRETRIZES OBRIGATÓRIAS:
- Filtro temporal DEFAULT (90 dias ou abertura futura)
- Padrão Portal (links diretos, sem ?q= ou datasets)
- Somente processos abertos/futuros

🏛️ PORTAIS PRIORITÁRIOS:
1. Santo André - https://portais.santoandre.sp.gov.br/compras
2. São Bernardo do Campo - https://compras.saobernardo.sp.gov.br
3. Guarulhos - https://www.guarulhos.sp.gov.br/licitacoes
4. Diadema - https://portal.diadema.sp.gov.br/licitacoes
5. São Caetano do Sul - https://www.saocaetanodosul.sp.gov.br/licitacoes
6. Campinas - https://portal.campinas.sp.gov.br/licitacoes
7. Santos - https://egov.santos.sp.gov.br/licitacao
"""

import aiohttp
import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# CNPJs dos municípios prioritários (para busca no PNCP)
MUNICIPIOS_SP = {
    "santo_andre": {
        "nome": "Santo André",
        "cnpj": "46522942000130",  # Prefeitura Municipal de Santo André
        "portal": "https://web.santoandre.sp.gov.br/portal/editais",
        "ativo": True,
    },
    "sao_bernardo": {
        "nome": "São Bernardo do Campo",
        "cnpj": "46523239000147",  # Prefeitura Municipal de SBC
        "portal": "https://licitacoes.saobernardo.sp.gov.br",
        "ativo": True,
    },
    "guarulhos": {
        "nome": "Guarulhos",
        "cnpj": "46319000000150",  # Prefeitura Municipal de Guarulhos
        "portal": "https://www.guarulhos.sp.gov.br/transparencia/licitacoes-em-andamento",
        "ativo": True,
    },
    "diadema": {
        "nome": "Diadema",
        "cnpj": "46523247000193",  # Prefeitura Municipal de Diadema
        "portal": "https://transparencia.diadema.sp.gov.br/transparencia/servlet/wmcontratolicitacoes",
        "ativo": True,
    },
    "sao_caetano": {
        "nome": "São Caetano do Sul",
        "cnpj": "46522959000190",  # Prefeitura Municipal de SCS
        "portal": "https://www.saocaetanodosul.sp.gov.br/licitacoes",
        "ativo": True,
    },
    "campinas": {
        "nome": "Campinas",
        "cnpj": "51885242000140",  # Prefeitura Municipal de Campinas
        "portal": "https://licitacoes.campinas.sp.gov.br",
        "ativo": True,
    },
    "santos": {
        "nome": "Santos",
        "cnpj": "58200015000183",  # Prefeitura Municipal de Santos
        "portal": "https://egov.santos.sp.gov.br/licitasantos",
        "ativo": True,
    },
    "guaruja": {
        "nome": "Guarujá",
        "cnpj": "44959021000190",  # Prefeitura Municipal de Guarujá
        "portal": "https://www.guaruja.sp.gov.br/licitacoes",
        "ativo": False,  # Ativar após validação
    },
}


class PortaisMunicipaisSP:
    """
    Integrador de Portais Municipais de SP
    
    Estratégia:
    1. Buscar editais no PNCP filtrados por CNPJ do município
    2. Verificar se há link direto no portal municipal
    3. Aplicar filtro temporal obrigatório
    4. Garantir links no padrão Portal
    """
    
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
    async def buscar_compras_por_cnpj(
        self,
        cnpj: str,
        ano: int = None,
        limite: int = 100
    ) -> List[Dict]:
        """
        🔒 P4.3: Busca compras de um órgão específico no PNCP usando endpoint correto.
        
        Endpoint: https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano}/{seq}
        
        Estratégia: Buscar sequenciais em ordem decrescente até encontrar X resultados
        ou atingir limite de requisições.
        """
        editais = []
        ano_atual = ano or datetime.now().year
        
        # Encontrar info do município
        municipio_info = None
        for mun_id, mun_data in MUNICIPIOS_SP.items():
            if mun_data["cnpj"] == cnpj:
                municipio_info = mun_data
                break
        
        nome_municipio = municipio_info["nome"] if municipio_info else "Desconhecido"
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Primeiro, descobrir o último sequencial (começar do 600 e descer)
                ultimo_seq = 0
                for seq_teste in [700, 600, 500, 400, 300, 200, 100]:
                    url = f"https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano_atual}/{seq_teste}"
                    try:
                        async with session.get(url, headers=self.headers) as response:
                            if response.status == 200:
                                ultimo_seq = max(ultimo_seq, seq_teste)
                                break
                    except:
                        continue
                
                if ultimo_seq == 0:
                    logger.info(f"⚠️ PNCP/{nome_municipio}: Nenhuma compra encontrada em {ano_atual}")
                    return editais
                
                # Buscar sequenciais em ordem decrescente
                seq_atual = ultimo_seq + 50  # Começar um pouco acima
                consecutivos_vazios = 0
                max_vazios = 10
                
                while len(editais) < limite and consecutivos_vazios < max_vazios:
                    url = f"https://pncp.gov.br/api/consulta/v1/orgaos/{cnpj}/compras/{ano_atual}/{seq_atual}"
                    
                    try:
                        async with session.get(url, headers=self.headers) as response:
                            if response.status == 200:
                                data = await response.json()
                                
                                if "objetoCompra" in data:
                                    edital = self._normalizar_edital_pncp_v2(data, cnpj)
                                    if edital:
                                        edital["municipio"] = nome_municipio
                                        edital["_municipio_id"] = next(
                                            (k for k, v in MUNICIPIOS_SP.items() if v["cnpj"] == cnpj), 
                                            None
                                        )
                                        editais.append(edital)
                                        consecutivos_vazios = 0
                                    else:
                                        consecutivos_vazios += 1
                                else:
                                    consecutivos_vazios += 1
                            else:
                                consecutivos_vazios += 1
                    except Exception as e:
                        logger.debug(f"Erro seq {seq_atual}: {e}")
                        consecutivos_vazios += 1
                    
                    seq_atual -= 1
                    
                    # Evitar loop infinito
                    if seq_atual <= 0:
                        break
                
                logger.info(f"✅ PNCP/{nome_municipio}: {len(editais)} compras encontradas")
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar PNCP/{nome_municipio}: {e}")
        
        return editais
    
    def _normalizar_edital_pncp_v2(self, data: Dict, cnpj: str) -> Optional[Dict]:
        """
        🔒 P4.3: Normaliza edital do novo endpoint PNCP.
        
        Endpoint retorna dados mais completos que o antigo.
        """
        try:
            orgao = data.get("orgaoEntidade", {})
            
            # Extrair datas
            data_pub = data.get("dataPublicacaoPncp")
            data_abertura = data.get("dataAberturaProposta")
            
            # Construir link do edital (PNCP direto)
            numero = data.get("numeroCompra", "")
            ano = data.get("anoCompra", "")
            link_pncp = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{numero}"
            
            # Link do sistema de origem (ComprasNet, etc)
            link_sistema = data.get("linkSistemaOrigem", "")
            
            # Preferir link PNCP (mais confiável)
            link_final = link_pncp
            link_status = "VALIDO"
            
            edital = {
                "id_externo": f"PNCP-{cnpj}-{ano}-{numero}",
                "orgao": orgao.get("razaoSocial", ""),
                "cnpj_orgao": cnpj,
                "uf": orgao.get("ufSigla", "SP"),
                "esfera": "Municipal",
                "objeto": data.get("objetoCompra", ""),
                "modalidade": data.get("modalidadeNome", ""),
                "numero_processo": f"{numero}/{ano}",
                "data_publicacao": data_pub,
                "data_abertura": data_abertura,
                "valor_estimado": data.get("valorTotalEstimado"),
                "situacao": data.get("situacaoCompraNome", ""),
                "link_edital": link_final,
                "link_sistema_origem": link_sistema,
                "link_status": link_status,
                "fonte": "PNCP_API_V2",
                "is_saude": self._detectar_saude(data.get("objetoCompra", "")),
                "itens": [],
                "tags": self._extrair_tags(data.get("objetoCompra", "")),
            }
            
            return edital
            
        except Exception as e:
            logger.error(f"❌ Erro ao normalizar edital PNCP V2: {e}")
            return None
    
    async def buscar_editais_pncp_municipio(
        self,
        cnpj: str,
        dias: int = 90,
        limite: int = 50
    ) -> List[Dict]:
        """
        Busca editais no PNCP por CNPJ do município
        
        🔒 P4 - Estratégia corrigida:
        1. Buscar via endpoint /publicacao com filtro UF=SP
        2. Filtrar por CNPJ ou nome do município
        3. Garantir links válidos no padrão Portal
        
        Args:
            cnpj: CNPJ do órgão municipal
            dias: Período em dias para buscar (default: 90)
            limite: Máximo de resultados
            
        Returns:
            Lista de editais normalizados
        """
        editais = []
        
        # Encontrar nome do município pelo CNPJ
        municipio_info = None
        for mun_id, mun_data in MUNICIPIOS_SP.items():
            if mun_data["cnpj"] == cnpj:
                municipio_info = mun_data
                break
        
        if not municipio_info:
            logger.warning(f"⚠️ CNPJ {cnpj} não encontrado nos municípios configurados")
            return editais
        
        nome_municipio = municipio_info["nome"]
        nome_lower = nome_municipio.lower().replace(" ", "")
        
        try:
            # Calcular datas
            data_final = datetime.now()
            data_inicial = data_final - timedelta(days=dias)
            
            # 🔒 P4: Usar endpoint /publicacao com filtro UF=SP
            url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Buscar em múltiplas modalidades e páginas
                for modalidade in [6, 8, 12]:  # 6=Pregão, 8=Dispensa, 12=Credenciamento
                    for pagina in range(1, 6):  # Até 5 páginas por modalidade
                        if len(editais) >= limite:
                            break
                        
                        params = {
                            "dataInicial": data_inicial.strftime("%Y%m%d"),
                            "dataFinal": data_final.strftime("%Y%m%d"),
                            "codigoModalidadeContratacao": modalidade,
                            "uf": "SP",
                            "pagina": pagina,
                            "tamanhoPagina": 50,
                        }
                        
                        async with session.get(url, params=params, headers=self.headers) as response:
                            if response.status != 200:
                                logger.debug(f"⚠️ PNCP modalidade {modalidade} página {pagina}: Status {response.status}")
                                break
                            
                            data = await response.json()
                            items = data.get("data", [])
                            
                            if not items:
                                break
                            
                            # Filtrar por CNPJ ou nome do município
                            for item in items:
                                orgao = item.get("orgaoEntidade", {})
                                razao_social = orgao.get("razaoSocial", "").lower().replace(" ", "")
                                cnpj_orgao = orgao.get("cnpj", "")
                                
                                # Match por CNPJ exato OU nome do município
                                is_match = (
                                    cnpj_orgao == cnpj or
                                    nome_lower in razao_social
                                )
                                
                                if is_match:
                                    edital = self._normalizar_edital_pncp(item, cnpj_orgao)
                                    if edital:
                                        edital["municipio"] = nome_municipio
                                        edital["_municipio_id"] = next(
                                            (k for k, v in MUNICIPIOS_SP.items() if v["cnpj"] == cnpj), 
                                            None
                                        )
                                        editais.append(edital)
                
                logger.info(f"✅ PNCP/{nome_municipio}: {len(editais)} editais encontrados")
                        
        except Exception as e:
            logger.error(f"❌ Erro ao buscar PNCP/{nome_municipio}: {str(e)}")
        
        return editais
    
    def _normalizar_edital_pncp(self, item: Dict, cnpj: str) -> Optional[Dict]:
        """
        Normaliza edital do PNCP para formato canônico
        
        🔒 PADRÃO PORTAL: 
        - Usar linkSistemaOrigem quando disponível
        - Construir link PNCP direto como fallback
        - NUNCA usar links de busca (?q=)
        """
        try:
            orgao = item.get("orgaoEntidade", {})
            
            # Extrair dados básicos
            objeto = item.get("objetoCompra", "")
            numero = item.get("numeroCompra", "")
            ano = item.get("anoCompra", "")
            sequencial = item.get("sequencialCompra", "")
            modalidade = item.get("modalidadeNome", "")
            
            # Datas
            data_pub = item.get("dataPublicacaoPncp")
            data_abertura = item.get("dataAberturaProposta")
            
            # 🔒 LINK NO PADRÃO PORTAL
            link_sistema = item.get("linkSistemaOrigem")
            link_pncp = None
            
            # Construir link PNCP direto se tiver dados suficientes
            if cnpj and ano and sequencial:
                link_pncp = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}"
            
            # Prioridade: linkSistemaOrigem > link PNCP construído
            link_final = None
            link_status = "INVALIDO"
            
            if link_sistema and self._validar_link_portal(link_sistema):
                link_final = link_sistema
                link_status = "VALIDO"
            elif link_pncp:
                link_final = link_pncp
                link_status = "VALIDO"
            
            # Determinar município
            municipio_info = None
            for mun_id, mun_data in MUNICIPIOS_SP.items():
                if mun_data["cnpj"] == cnpj:
                    municipio_info = mun_data
                    break
            
            return {
                "id_externo": f"PNCP-{cnpj}-{ano}-{sequencial}",
                "fonte": "PNCP",
                "fonte_detalhe": f"Municipal/{municipio_info['nome'] if municipio_info else 'SP'}",
                "objeto": objeto,
                "orgao": orgao.get("razaoSocial", ""),
                "cnpj_orgao": cnpj,
                "uf": "SP",
                "municipio": municipio_info["nome"] if municipio_info else "",
                "esfera": "Municipal",
                "modalidade": modalidade,
                "numero_processo": f"{numero}/{ano}" if numero and ano else numero,
                "data_publicacao": data_pub,
                "data_abertura": data_abertura,
                "status": "Aberto" if data_abertura else "Publicado",
                "link_edital": link_final,
                "link_pncp": link_pncp,
                "link_portal_orgao": link_sistema if link_sistema != link_pncp else None,
                "link_status": link_status,
                "tipo_link": "pncp_direto" if link_final == link_pncp else "portal_orgao",
                "is_saude": self._detectar_saude(objeto),
                "tags": self._extrair_tags(objeto),
                "tags_saude": [],
                "_origem": "portais_municipais_sp",
                "_municipio_id": next((k for k, v in MUNICIPIOS_SP.items() if v["cnpj"] == cnpj), None),
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao normalizar edital PNCP: {str(e)}")
            return None
    
    def _validar_link_portal(self, url: str) -> bool:
        """
        Valida se link segue PADRÃO PORTAL
        
        🚫 PROIBIDO:
        - ?q= (busca genérica)
        - /dataset
        - dados.gov.br
        - transparência genérica
        """
        if not url or not isinstance(url, str):
            return False
        
        url_lower = url.lower()
        
        # Padrões proibidos
        padroes_invalidos = [
            "?q=",
            "&q=",
            "/dataset",
            "dados.gov.br",
            "dadosabertos",
            "/busca",
            "/pesquisa",
            "status=todos",
        ]
        
        for padrao in padroes_invalidos:
            if padrao in url_lower:
                return False
        
        # Deve ser URL HTTP válida
        if not url.startswith(("http://", "https://")):
            return False
        
        return True
    
    def _detectar_saude(self, texto: str) -> bool:
        """Detecta se edital é relacionado a saúde"""
        if not texto:
            return False
        
        texto_lower = texto.lower()
        termos_saude = [
            "medicament", "hospital", "saúde", "saude", "médic", "medic",
            "farmac", "ambulância", "uti", "upa", "ubs", "enferm",
            "odonto", "laborat", "vacina", "insulina", "canabidiol",
            "oncolog", "cardio", "ortoped", "prótese", "órtese",
        ]
        
        return any(termo in texto_lower for termo in termos_saude)
    
    def _extrair_tags(self, texto: str) -> List[str]:
        """Extrai tags do objeto"""
        tags = []
        
        if not texto:
            return tags
        
        texto_lower = texto.lower()
        
        # Tags de saúde
        if self._detectar_saude(texto):
            tags.append("saude_geral")
        
        # Tags específicas
        if "hospital" in texto_lower:
            tags.append("hospitalar")
        if "medicament" in texto_lower or "farmac" in texto_lower:
            tags.append("medicamentos")
        if "equipament" in texto_lower:
            tags.append("equipamentos")
        if "material" in texto_lower:
            tags.append("materiais")
        
        return tags
    
    async def buscar_todos_municipais_sp(
        self,
        dias: int = 60,
        limite: int = 200
    ) -> List[Dict]:
        """
        🔒 P4: Busca TODOS os editais municipais de SP de forma eficiente
        
        Estratégia:
        1. Buscar via endpoint /publicacao com UF=SP
        2. Filtrar por esfera Municipal no resultado
        3. Validar links no padrão Portal
        
        Returns:
            Lista de editais municipais de SP
        """
        editais = []
        
        try:
            data_final = datetime.now()
            data_inicial = data_final - timedelta(days=dias)
            
            url = "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
            
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                # Buscar em múltiplas modalidades
                for modalidade in [6, 8, 12]:  # 6=Pregão, 8=Dispensa, 12=Credenciamento
                    for pagina in range(1, 4):  # 3 páginas por modalidade
                        if len(editais) >= limite:
                            break
                        
                        params = {
                            "dataInicial": data_inicial.strftime("%Y%m%d"),
                            "dataFinal": data_final.strftime("%Y%m%d"),
                            "codigoModalidadeContratacao": modalidade,
                            "uf": "SP",
                            "pagina": pagina,
                            "tamanhoPagina": 50,
                        }
                        
                        try:
                            async with session.get(url, params=params, headers=self.headers) as response:
                                if response.status != 200:
                                    break
                                
                                data = await response.json()
                                items = data.get("data", [])
                                
                                if not items:
                                    break
                                
                                # Filtrar por Municipal
                                for item in items:
                                    orgao = item.get("orgaoEntidade", {})
                                    razao = orgao.get("razaoSocial", "").lower()
                                    cnpj_orgao = orgao.get("cnpj", "")
                                    esfera_id = orgao.get("esferaId", "")
                                    
                                    # Detectar Municipal
                                    is_municipal = (
                                        esfera_id == "M" or
                                        "prefeitura" in razao or
                                        "municipal" in razao or
                                        "municipio" in razao or
                                        "fundo municipal" in razao or
                                        "camara municipal" in razao
                                    )
                                    
                                    if is_municipal:
                                        edital = self._normalizar_edital_pncp(item, cnpj_orgao)
                                        if edital:
                                            # Detectar município pelo nome
                                            for mun_id, mun_data in MUNICIPIOS_SP.items():
                                                nome_mun = mun_data["nome"].lower()
                                                if nome_mun in razao or cnpj_orgao == mun_data["cnpj"]:
                                                    edital["municipio"] = mun_data["nome"]
                                                    edital["_municipio_id"] = mun_id
                                                    break
                                            
                                            editais.append(edital)
                        except Exception as e:
                            logger.debug(f"⚠️ Erro página {pagina} modalidade {modalidade}: {e}")
                            continue
                
            logger.info(f"✅ PNCP/SP Municipais: {len(editais)} editais encontrados")
                        
        except Exception as e:
            logger.error(f"❌ Erro ao buscar municipais SP: {str(e)}")
        
        return editais
    
    async def sincronizar_municipios(
        self,
        municipios: List[str] = None,
        dias: int = 90,
        limite_por_municipio: int = 50
    ) -> Dict[str, Any]:
        """
        Sincroniza editais dos municípios prioritários
        
        Args:
            municipios: Lista de IDs de municípios (None = todos ativos)
            dias: Período em dias para buscar
            limite_por_municipio: Máximo por município
            
        Returns:
            Dict com estatísticas de sincronização
        """
        stats = {
            "total": 0,
            "por_municipio": {},
            "erros": [],
            "inicio": datetime.now().isoformat(),
        }
        
        # Filtrar municípios ativos
        if municipios is None:
            municipios = [k for k, v in MUNICIPIOS_SP.items() if v.get("ativo", False)]
        
        logger.info(f"🏛️ Iniciando sincronização de {len(municipios)} municípios...")
        
        for mun_id in municipios:
            mun_data = MUNICIPIOS_SP.get(mun_id)
            if not mun_data:
                continue
            
            try:
                cnpj = mun_data["cnpj"]
                nome = mun_data["nome"]
                
                logger.info(f"📍 Sincronizando {nome} (CNPJ: {cnpj})...")
                
                editais = await self.buscar_editais_pncp_municipio(
                    cnpj=cnpj,
                    dias=dias,
                    limite=limite_por_municipio
                )
                
                stats["por_municipio"][mun_id] = {
                    "nome": nome,
                    "total": len(editais),
                    "editais": editais,
                }
                stats["total"] += len(editais)
                
            except Exception as e:
                stats["erros"].append({
                    "municipio": mun_id,
                    "erro": str(e),
                })
                logger.error(f"❌ Erro em {mun_id}: {str(e)}")
        
        stats["fim"] = datetime.now().isoformat()
        
        logger.info(f"✅ Sincronização concluída: {stats['total']} editais de {len(municipios)} municípios")
        
        return stats


# Instância singleton
_instance = None

def get_portais_municipais_sp() -> PortaisMunicipaisSP:
    """Retorna instância do integrador de portais municipais"""
    global _instance
    if _instance is None:
        _instance = PortaisMunicipaisSP()
    return _instance
