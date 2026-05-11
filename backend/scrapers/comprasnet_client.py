import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import time
import re

logger = logging.getLogger(__name__)


class ComprasNetClient:
    """
    Cliente para buscar licitações no ComprasNet/SIASG (Portal de Compras do Governo Federal)
    
    Implementa:
    - Busca via API pública de dados abertos
    - Extração completa de metadados (UASG obrigatório)
    - Navegação dupla para links diretos de PDF
    - Extração de itens da licitação
    - Filtros por modalidade (Pregão Eletrônico, etc)
    
    Baseado na documentação oficial:
    https://dadosabertos.compras.gov.br/swagger-ui/index.html
    """
    
    def __init__(self):
        self.base_url = 'https://dadosabertos.compras.gov.br'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'pt-BR,pt;q=0.9'
        })
        
        # Códigos de modalidade (conforme API ComprasNet)
        self.MODALIDADE_PREGAO_ELETRONICO = 14
        self.MODALIDADE_CONCORRENCIA = 1
        self.MODALIDADE_TOMADA_PRECOS = 2
        self.MODALIDADE_CONVITE = 3
        
        # UASGs de órgãos de saúde relevantes (principais)
        self.uasgs_saude = [
            {'uasg': '250001', 'nome': 'Ministério da Saúde', 'uf': 'DF'},
            {'uasg': '153153', 'nome': 'Fiocruz', 'uf': 'RJ'},
            {'uasg': '989915', 'nome': 'Hospital das Clínicas - SP', 'uf': 'SP'},
        ]
    
    def _delay(self, seconds: float = 1.0):
        """Rate limiting"""
        time.sleep(seconds)
    
    def buscar_licitacoes(self, termo_busca: str = None, apenas_futuras: bool = False, 
                         limit: int = 20) -> List[Dict]:
        """
        Busca licitações de medicamentos no ComprasNet
        
        Estratégia:
        1. Buscar licitações em órgãos de saúde conhecidos
        2. Filtrar por termo de busca no objeto
        3. Buscar detalhes completos de cada licitação
        4. Extrair itens e links
        
        Args:
            termo_busca: Termo para filtrar (ex: "canabidiol", "insulina")
            apenas_futuras: Se True, filtra apenas licitações com data futura
            limit: Número máximo de resultados
            
        Returns:
            List[Dict]: Lista de licitações com campos expandidos
        """
        resultados = []
        
        try:
            logger.info(f"🔍 [ComprasNet] Iniciando busca: '{termo_busca or 'medicamentos'}'")
            
            # ETAPA 1: Buscar licitações em UASGs de saúde
            licitacoes_encontradas = self._buscar_em_uasgs(termo_busca, limit)
            
            if not licitacoes_encontradas:
                logger.info("ℹ️ [ComprasNet] Nenhum resultado encontrado")
                return []
            
            logger.info(f"✅ [ComprasNet] Encontradas {len(licitacoes_encontradas)} licitações")
            
            # ETAPA 2: Para cada licitação, buscar detalhes completos
            for idx, lic_basica in enumerate(licitacoes_encontradas[:limit], 1):
                try:
                    logger.info(f"  📄 [{idx}/{min(len(licitacoes_encontradas), limit)}] Processando...")
                    
                    # Buscar detalhes completos
                    lic_completa = self._buscar_detalhes_licitacao(lic_basica)
                    
                    if lic_completa:
                        # Filtrar por data futura se solicitado
                        if apenas_futuras:
                            data_final = lic_completa.get('data_final')
                            if data_final and isinstance(data_final, datetime):
                                if data_final < datetime.now():
                                    logger.debug("  ⏭️ Pulando licitação encerrada")
                                    continue
                        
                        resultados.append(lic_completa)
                        logger.info("  ✅ Licitação processada")
                    
                    # Rate limiting
                    if idx < len(licitacoes_encontradas):
                        self._delay(0.8)
                        
                except Exception as e:
                    logger.error(f"  ❌ Erro ao processar licitação {idx}: {str(e)}")
                    continue
            
            logger.info(f"🎯 [ComprasNet] Total processado: {len(resultados)} licitações válidas")
            
        except Exception as e:
            logger.error(f"❌ [ComprasNet] Erro geral na busca: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return resultados
    
    def _buscar_em_uasgs(self, termo_busca: str, limit: int) -> List[Dict]:
        """
        Busca licitações em UASGs de órgãos de saúde conhecidos
        
        Retorna lista básica para busca detalhada posterior
        """
        resultados = []
        ano_atual = datetime.now().year
        
        try:
            for uasg_info in self.uasgs_saude:
                if len(resultados) >= limit:
                    break
                
                uasg = uasg_info['uasg']
                logger.info(f"  🏥 Consultando UASG {uasg} ({uasg_info['nome']})")
                
                # Endpoint: /modulo-compras/1_consultarCompras
                url = f"{self.base_url}/modulo-compras/1_consultarCompras"
                
                params = {
                    'ano': ano_atual,
                    'uasg': uasg,
                    'modalidade': self.MODALIDADE_PREGAO_ELETRONICO,
                    'tipoCompra': 1,  # 1 = Licitação
                    'pagina': 1
                }
                
                response = self.session.get(url, params=params, timeout=15)
                
                if response.status_code != 200:
                    logger.warning(f"    ⚠️ UASG {uasg}: status {response.status_code}")
                    continue
                
                data = response.json()
                compras = data.get('compras', []) or data.get('_embedded', {}).get('compras', [])
                
                for compra in compras:
                    # Filtrar por termo de busca
                    objeto = compra.get('objeto', '').lower()
                    
                    if termo_busca:
                        if termo_busca.lower() not in objeto:
                            continue
                    else:
                        # Se não tem termo, buscar apenas medicamentos
                        if not any(palavra in objeto for palavra in ['medicamento', 'farmac', 'droga', 'remedio']):
                            continue
                    
                    # Adicionar à lista com metadados básicos
                    resultados.append({
                        'uasg': uasg,
                        'uasg_nome': uasg_info['nome'],
                        'uasg_uf': uasg_info['uf'],
                        'ano': compra.get('ano', ano_atual),
                        'sequencial': compra.get('sequencial') or compra.get('numeroCompra'),
                        'modalidade': compra.get('modalidade'),
                        'objeto': compra.get('objeto'),
                        '_raw': compra
                    })
                
                logger.info(f"    ✅ UASG {uasg}: {len([r for r in resultados if r['uasg'] == uasg])} resultados")
                
                self._delay(1.2)
            
            logger.info(f"  ✅ Total de licitações encontradas: {len(resultados)}")
            return resultados
            
        except Exception as e:
            logger.error(f"  ❌ Erro ao buscar em UASGs: {str(e)}")
            return resultados
    
    def _buscar_detalhes_licitacao(self, lic_basica: Dict) -> Optional[Dict]:
        """
        Busca detalhes completos de uma licitação
        
        Implementa navegação dupla para extrair:
        - Metadados completos
        - Link direto para PDF do edital
        - Itens da licitação
        """
        try:
            uasg = lic_basica['uasg']
            ano = lic_basica['ano']
            sequencial = lic_basica['sequencial']
            
            # ETAPA 1: Buscar detalhes da compra
            # Endpoint: /modulo-compras/2_consultarDetalheCompra
            url_detalhes = f"{self.base_url}/modulo-compras/2_consultarDetalheCompra"
            
            params = {
                'ano': ano,
                'uasg': uasg,
                'sequencial': sequencial
            }
            
            logger.debug(f"    🔍 Buscando detalhes: UASG {uasg}/{ano}/{sequencial}")
            
            response = self.session.get(url_detalhes, params=params, timeout=12)
            
            if response.status_code != 200:
                logger.warning(f"    ⚠️ Detalhes indisponíveis (status {response.status_code})")
                return None
            
            dados_compra = response.json()
            
            # ETAPA 2: Buscar itens da licitação
            itens = self._buscar_itens_licitacao(uasg, ano, sequencial)
            
            # ETAPA 3: Extrair link direto para PDF do edital
            link_pdf = self._extrair_link_edital(dados_compra, uasg, ano, sequencial)
            
            # ETAPA 4: Processar e formatar dados
            return self._processar_dados_completos(dados_compra, lic_basica, itens, link_pdf)
            
        except requests.exceptions.Timeout:
            logger.warning("    ⏱️ Timeout ao buscar detalhes")
            return None
        except Exception as e:
            logger.error(f"    ❌ Erro ao buscar detalhes: {str(e)}")
            return None
    
    def _buscar_itens_licitacao(self, uasg: str, ano: int, sequencial: str) -> List[Dict]:
        """
        Busca itens da licitação
        
        Retorna array de itens com número, descrição, quantidade
        """
        try:
            # Os itens podem vir junto com os detalhes da compra
            # ou em endpoint separado (dependendo da modalidade)
            
            # Por enquanto, retornar vazio (será preenchido se vier nos detalhes)
            # TODO: Implementar endpoint específico se disponível
            logger.debug("    ℹ️ Itens serão extraídos dos detalhes da compra")
            return []
            
        except Exception as e:
            logger.debug(f"    ⚠️ Erro ao buscar itens: {str(e)}")
            return []
    
    def _extrair_link_edital(self, dados_compra: Dict, uasg: str, ano: int, 
                            sequencial: str) -> Optional[str]:
        """
        NAVEGAÇÃO DUPLA: Extrai link direto para PDF do edital
        
        Estratégia:
        1. Verificar se há campo 'linkEdital' ou similar nos dados
        2. Construir URL do edital no ComprasNet
        3. Se possível, obter link direto de download
        """
        try:
            # Verificar se há link direto nos dados
            link_direto = dados_compra.get('linkEdital') or dados_compra.get('urlEdital')
            
            if link_direto:
                logger.debug("    ✅ Link do edital encontrado nos metadados")
                return link_direto
            
            # Construir URL padrão do edital no ComprasNet
            # Formato: https://www.comprasnet.gov.br/livre/Pregao/ata0.asp?prgCod=XXX
            # ou https://www2.comprasnet.gov.br/siasgnet-atasrp/public/visualizarAtaSRP.do?
            
            # Link para página de detalhes (melhor que nada)
            link_portal = f"https://www.comprasnet.gov.br/ConsultaLicitacoes/ConsLicitacao_Filtro.asp?f=2023&numprp={sequencial}&f_UasgCod={uasg}"
            
            logger.debug("    ℹ️ Construído link para portal")
            return link_portal
            
        except Exception as e:
            logger.debug(f"    ⚠️ Erro ao extrair link: {str(e)}")
            return None
    
    def _processar_dados_completos(self, dados_compra: Dict, lic_basica: Dict,
                                   itens: List[Dict], link_pdf: Optional[str]) -> Dict:
        """
        Processa dados completos e retorna no formato expandido
        """
        try:
            # Extrair datas
            data_pub = dados_compra.get('dataPublicacao') or dados_compra.get('dataPublicacaoPncp')
            data_abertura = dados_compra.get('dataAberturaProposta')
            data_encerramento = dados_compra.get('dataEncerramentoProposta') or dados_compra.get('dataLimiteRecebimentoProposta')
            
            # Converter datas
            data_publicacao_dt = self._parse_date(data_pub)
            data_abertura_dt = self._parse_date(data_abertura)
            data_final_dt = self._parse_date(data_encerramento)
            
            # Determinar status
            status = self._determinar_status(data_final_dt, dados_compra.get('situacao'))
            
            # Extrair modalidade
            modalidade = dados_compra.get('modalidadeNome', dados_compra.get('descricaoModalidade', 'Pregão Eletrônico'))
            
            # Extrair objeto
            objeto = dados_compra.get('objeto', lic_basica.get('objeto', 'Objeto não especificado'))
            
            # Extrair medicamento
            medicamento = self._extrair_medicamento(objeto, itens)
            
            # Número do processo
            numero_processo = dados_compra.get('numeroProcesso', f"{lic_basica['ano']}/{lic_basica['sequencial']}")
            
            # Extrair itens se vieram nos detalhes
            if not itens and 'itens' in dados_compra:
                itens = self._processar_itens(dados_compra['itens'])
            
            # UASG
            uasg = lic_basica['uasg']
            orgao_nome = lic_basica.get('uasg_nome', dados_compra.get('nomeOrgao', 'Órgão não identificado'))
            uf = lic_basica.get('uasg_uf', 'BR')
            
            # Link de origem
            link_origem = link_pdf or "https://www.comprasnet.gov.br"
            
            # Gerar ID único para o frontend
            import uuid
            licitacao_id = str(uuid.uuid4())
            
            return {
                'id': licitacao_id,
                'medicamento': medicamento,
                'principio_ativo': None,
                'estado': uf,
                'status': status,
                'orgao_licitante': orgao_nome,
                'modalidade': modalidade,
                'numero_processo': numero_processo,
                
                # Datas expandidas
                'data_referencia': data_publicacao_dt or datetime.now(),
                'data_abertura': data_abertura_dt,
                'data_inicial': data_abertura_dt,
                'data_final': data_final_dt,
                'data_publicacao': data_publicacao_dt,
                
                # Links
                'link_origem': link_origem,
                'link_documento': link_pdf,
                
                # Metadados expandidos
                'fonte_nome': 'ComprasNet/SIASG - Portal de Compras do Governo Federal',
                'fonte_id': f'comprasnet-{uasg}-{lic_basica["ano"]}-{lic_basica["sequencial"]}',
                'numero_pregao': numero_processo,
                'uasg': uasg,
                'esfera': 'Federal',
                'objeto': objeto,
                
                # Itens
                'itens': itens,
                
                # Metadados
                'tags': self._extrair_tags(objeto, itens),
                'is_mock': False,
                'fonte': 'ComprasNet'
            }
            
        except Exception as e:
            logger.error(f"    ❌ Erro ao processar dados: {str(e)}")
            return None
    
    def _processar_itens(self, itens_raw: List[Dict]) -> List[Dict]:
        """Processa array de itens da API"""
        itens_processados = []
        
        for item in itens_raw:
            itens_processados.append({
                'numero': item.get('numeroItem', item.get('numero', 0)),
                'descricao': item.get('descricao', item.get('descricaoDetalhada', 'Item não especificado')),
                'quantidade': item.get('quantidade', item.get('quantidadeTotal')),
                'unidade': item.get('unidade', item.get('unidadeMedida')),
                'valor_estimado': item.get('valorUnitario', item.get('valorUnitarioEstimado'))
            })
        
        return itens_processados
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Converte string de data para datetime"""
        if not date_str:
            return None
        try:
            # Tentar vários formatos comuns
            for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            # Fallback: ISO format
            return datetime.fromisoformat(date_str.replace('Z', ''))
        except (ValueError, AttributeError):
            return None
    
    def _determinar_status(self, data_final: Optional[datetime], situacao_api: Optional[str]) -> str:
        """Determina status da licitação"""
        if data_final:
            if data_final > datetime.now():
                return 'Ativa'
            else:
                return 'Encerrada'
        
        if situacao_api:
            situacao_lower = situacao_api.lower()
            if 'encerrada' in situacao_lower or 'finalizada' in situacao_lower:
                return 'Encerrada'
            elif 'ativa' in situacao_lower or 'aberta' in situacao_lower:
                return 'Ativa'
        
        return 'Em Licitação'
    
    def _extrair_medicamento(self, objeto: str, itens: List[Dict] = None) -> str:
        """Extrai nome do medicamento do objeto ou dos itens"""
        # Lista de medicamentos comuns
        medicamentos_conhecidos = [
            'adalimumabe', 'pembrolizumabe', 'insulina', 'metformina',
            'omeprazol', 'paracetamol', 'dipirona', 'amoxicilina',
            'losartana', 'atorvastatina', 'sinvastatina', 'ibuprofeno',
            'nimesulida', 'azitromicina', 'dexametasona', 'prednisolona',
            'lenacapavir', 'cabotegravir', 'risperidona', 'quetiapina',
            'canabidiol'
        ]
        
        texto_lower = objeto.lower()
        
        for med in medicamentos_conhecidos:
            if med in texto_lower:
                return med.capitalize()
        
        # Tentar extrair dos itens
        if itens and len(itens) > 0:
            primeiro_item = itens[0].get('descricao', '')
            for med in medicamentos_conhecidos:
                if med in primeiro_item.lower():
                    return med.capitalize()
        
        # Pegar primeira palavra significativa
        palavras = objeto.split()
        for palavra in palavras[:15]:
            palavra_limpa = palavra.strip('.,;:()[]').lower()
            if len(palavra_limpa) > 5 and palavra_limpa not in [
                'aquisicao', 'aquisição', 'compra', 'fornecimento', 'registro', 
                'pregao', 'pregão', 'licitacao', 'licitação'
            ]:
                return palavra_limpa.capitalize()
        
        return 'Medicamento não especificado'
    
    def _extrair_tags(self, objeto: str, itens: List[Dict] = None) -> List[str]:
        """Extrai tags (alto_custo, importado, judicial)"""
        tags = []
        texto_lower = objeto.lower()
        
        # Alto custo
        if any(k in texto_lower for k in ['alto custo', 'oncolog', 'imunobiolog', 'biotecnolog']):
            tags.append('alto_custo')
        
        # Importado
        termos_importacao = [
            'importad', 'proforma invoice', 'sem registro no país',
            'rdc 660', 'inexigibilidade', 'importação excepcional'
        ]
        if any(termo in texto_lower for termo in termos_importacao):
            tags.append('importado')
        
        # Judicial
        if any(k in texto_lower for k in ['judicial', 'liminar', 'mandado']):
            tags.append('judicial')
        
        return tags
