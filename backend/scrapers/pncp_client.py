import requests
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import time
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

class PNCPClient:
    """
    Cliente APRIMORADO para buscar licitações REAIS no PNCP
    
    Implementa:
    - Busca hierárquica via API pública
    - Extração completa de metadados (UASG, esfera, datas, itens)
    - Navegação dupla para links diretos de PDF
    - Zero dados mockados
    
    Baseado nas melhores práticas de agregadores profissionais (Portal, eLicitacao)
    """
    
    def __init__(self):
        # ATUALIZADO 2024/2025: Endpoints corretos conforme documentação oficial
        self.base_url_api = 'https://pncp.gov.br/pncp-api/v1'
        self.base_url_app = 'https://pncp.gov.br/app'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'pt-BR,pt;q=0.9',
            'Origin': 'https://pncp.gov.br',
            'Referer': 'https://pncp.gov.br/'
        })
        
        # Expandir lista de CNPJs de órgãos de saúde conhecidos
        self.orgaos_saude_cnpj = [
            '00394544000145',  # Ministério da Saúde
            '26990000000119',  # FIOCRUZ
            '61144955000130',  # FUNASA
            '33530486000109',  # ANVISA
            '00360305000104',  # ANS
            '03426420000118',  # Hospital das Clínicas SP
            '60979457000167',  # INCA
            '00394494000138',  # FUNAI
        ]
    
    def _delay(self, seconds: float = 1.5):
        """Rate limiting para não sobrecarregar o servidor"""
        time.sleep(seconds)
    
    def buscar_licitacoes(self, termo_busca: str = None, apenas_futuras: bool = False, limit: int = 20) -> List[Dict]:
        """
        Busca licitações REAIS no PNCP com metadados completos
        
        Implementa estratégia hierárquica:
        1. Busca via API de pesquisa do PNCP
        2. Para cada resultado, busca detalhes completos via API v1
        3. Extrai link direto para PDF (navegação dupla)
        4. Extrai itens da licitação
        
        Args:
            termo_busca: Termo para buscar (ex: "canabidiol", "insulina")
            apenas_futuras: Se True, filtra apenas licitações com data futura
            limit: Número máximo de resultados
            
        Returns:
            List[Dict]: Lista de licitações com campos expandidos
        """
        resultados = []
        
        try:
            logger.info(f"🔍 [PNCP] Iniciando busca: '{termo_busca or 'geral'}'")
            
            # ETAPA 1: Buscar na API de pesquisa
            licitacoes_encontradas = self._buscar_via_api_search(termo_busca, limit)
            
            if not licitacoes_encontradas:
                logger.info("ℹ️ [PNCP] Nenhum resultado encontrado na busca inicial")
                return []
            
            logger.info(f"✅ [PNCP] Encontradas {len(licitacoes_encontradas)} licitações")
            
            # ETAPA 2: Para cada licitação, buscar detalhes completos
            for idx, lic_basica in enumerate(licitacoes_encontradas[:limit], 1):
                try:
                    logger.info(f"  📄 [{idx}/{min(len(licitacoes_encontradas), limit)}] Processando licitação...")
                    
                    # Buscar detalhes completos via API v1
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
                        logger.info("  ✅ Licitação processada com sucesso")
                    
                    # Rate limiting
                    if idx < len(licitacoes_encontradas):
                        self._delay(0.8)
                        
                except Exception as e:
                    logger.error(f"  ❌ Erro ao processar licitação {idx}: {str(e)}")
                    continue
            
            logger.info(f"🎯 [PNCP] Total processado: {len(resultados)} licitações válidas")
            
        except Exception as e:
            logger.error(f"❌ [PNCP] Erro geral na busca: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return resultados
    
    def _buscar_via_api_search(self, termo_busca: str, limit: int = 20) -> List[Dict]:
        """
        Busca inicial via API do PNCP - ATUALIZADO 2024/2025
        
        Agora usa a API de busca global do portal para encontrar resultados em todo o país.
        """
        logger.info(f"  🔄 Realizando busca global no PNCP para: '{termo_busca}'")
        
        try:
            url_search = "https://pncp.gov.br/api/search/"
            params = {
                'q': termo_busca,
                'tipos_documento': 'edital',
                'ordenacao': '-data',
                'pagina': 1,
                'tam_pagina': limit,
                'status': 'recebendo_proposta'
            }
            
            response = self.session.get(url_search, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                items = data.get('items', [])
                
                licitacoes = []
                for item in items:
                    licitacoes.append({
                        'cnpj': item.get('orgao_cnpj'),
                        'ano': item.get('ano'),
                        'sequencial': item.get('numero_sequencial'),
                        '_raw': item
                    })
                
                return licitacoes
            else:
                logger.error(f"  ❌ Erro na busca global: {response.status_code}")
        except Exception as e:
            logger.error(f"  ❌ Erro ao acessar busca global: {str(e)}")
            
        # Fallback para órgãos conhecidos se a busca global falhar
        return self._buscar_via_orgaos_conhecidos(termo_busca, limit)
    
    def _buscar_via_orgaos_conhecidos(self, termo_busca: str, limit: int = 10) -> List[Dict]:
        """
        Estratégia alternativa: buscar em órgãos de saúde conhecidos
        
        Lista de CNPJs de Secretarias de Saúde estaduais e Ministério da Saúde
        """
        logger.info("  🔄 Tentando estratégia alternativa: órgãos de saúde conhecidos")
        
        # CNPJs de órgãos de saúde relevantes (exemplos)
        orgaos_saude = [
            # Ministério da Saúde
            {'cnpj': '00394544000145', 'nome': 'Ministério da Saúde', 'uf': 'DF'},
            # Secretarias Estaduais (alguns exemplos - expandir conforme necessário)
            {'cnpj': '46374500000194', 'nome': 'Secretaria de Saúde SP', 'uf': 'SP'},
            {'cnpj': '42498600000100', 'nome': 'Secretaria de Saúde RS', 'uf': 'RS'},
        ]
        
        resultados = []
        ano_atual = datetime.now().year
        
        for orgao in orgaos_saude[:5]:  # Aumentado para 5 órgãos
            try:
                # Endpoint correto: /pncp-api/v1/orgaos/{cnpj}/compras/{ano}
                url = f"{self.base_url_api}/orgaos/{orgao['cnpj']}/compras/{ano_atual}"
                
                logger.debug(f"  Consultando: {orgao.get('nome', orgao['cnpj'])}")
                
                response = self.session.get(
                    url, 
                    params={'pagina': 1, 'tamanhoPagina': 10}, 
                    timeout=15
                )
                
                if response.status_code == 200:
                    compras = response.json()
                    
                    for compra in compras.get('data', [])[:3]:
                        # Filtrar por termo de busca no objeto
                        objeto = compra.get('objetoCompra', '').lower()
                        if termo_busca and termo_busca.lower() in objeto:
                            resultados.append({
                                'cnpj': orgao['cnpj'],
                                'ano': ano_atual,
                                'sequencial': compra.get('sequencialCompra'),
                                '_raw': compra
                            })
                
                if len(resultados) >= limit:
                    break
                    
                self._delay(1.0)
                
            except Exception:
                logger.debug(f"  Órgão {orgao['nome']}: não disponível")
                continue
        
        logger.info(f"  ✅ Estratégia alternativa: {len(resultados)} resultados")
        return resultados
    
    def _buscar_detalhes_licitacao(self, lic_basica: Dict) -> Optional[Dict]:
        """
        Busca detalhes completos de uma licitação via API v1
        
        Implementa navegação dupla para extrair:
        - Metadados completos
        - Link direto para PDF
        - Itens da licitação
        """
        try:
            cnpj = lic_basica['cnpj']
            ano = lic_basica['ano']
            sequencial = lic_basica['sequencial']
            
            # ETAPA 1: Buscar dados da compra
            url_compra = f"{self.base_url_api}/orgaos/{cnpj}/compras/{ano}/{sequencial}"
            
            logger.debug(f"    🔍 Buscando detalhes: {url_compra}")
            
            response = self.session.get(url_compra, timeout=12)
            
            if response.status_code != 200:
                logger.warning(f"    ⚠️ Detalhes indisponíveis (status {response.status_code})")
                return None
            
            dados_compra = response.json()
            
            # ETAPA 2: Buscar itens da licitação
            itens = self._buscar_itens_licitacao(cnpj, ano, sequencial)
            
            # ETAPA 3: Buscar link direto para PDF (navegação dupla)
            link_pdf = self._extrair_link_pdf(cnpj, ano, sequencial)
            
            # ETAPA 4: Processar e formatar dados
            return self._processar_dados_completos(dados_compra, itens, link_pdf, cnpj, ano, sequencial)
            
        except requests.exceptions.Timeout:
            logger.warning("    ⏱️ Timeout ao buscar detalhes")
            return None
        except Exception as e:
            logger.error(f"    ❌ Erro ao buscar detalhes: {str(e)}")
            return None
    
    def _buscar_itens_licitacao(self, cnpj: str, ano: int, sequencial: str) -> List[Dict]:
        """
        Busca itens da licitação via API
        
        Retorna array de itens com número, descrição e quantidade
        """
        try:
            url_itens = f"{self.base_url_api}/orgaos/{cnpj}/compras/{ano}/{sequencial}/itens"
            
            response = self.session.get(url_itens, timeout=10)
            
            if response.status_code != 200:
                logger.debug("    ℹ️ Itens não disponíveis")
                return []
            
            itens_raw = response.json()
            itens_processados = []
            
            for item in itens_raw:
                itens_processados.append({
                    'numero': item.get('numeroItem', item.get('numero', 0)),
                    'descricao': item.get('descricao', item.get('itemDescricao', 'Item não especificado')),
                    'quantidade': item.get('quantidade', item.get('quantidadeTotal')),
                    'unidade': item.get('unidade', item.get('unidadeMedida')),
                    'valor_estimado': item.get('valorUnitario', item.get('valorUnitarioEstimado'))
                })
            
            logger.debug(f"    ✅ {len(itens_processados)} itens extraídos")
            return itens_processados
            
        except Exception as e:
            logger.debug(f"    ⚠️ Não foi possível extrair itens: {str(e)}")
            return []
    
    def _extrair_link_pdf(self, cnpj: str, ano: int, sequencial: str) -> Optional[str]:
        """
        NAVEGAÇÃO DUPLA: Extrai link direto para PDF do edital
        
        Estratégia:
        1. Buscar lista de arquivos via API
        2. Identificar arquivo do tipo "edital"
        3. Construir URL direta de download
        """
        try:
            url_arquivos = f"{self.base_url_api}/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos"
            
            response = self.session.get(url_arquivos, timeout=10)
            
            if response.status_code != 200:
                logger.debug("    ℹ️ Lista de arquivos não disponível")
                return None
            
            arquivos = response.json()
            
            # Procurar arquivo do tipo "edital"
            for arquivo in arquivos:
                tipo = arquivo.get('tipo', '').lower()
                nome = arquivo.get('nome', '').lower()
                
                if 'edital' in tipo or 'edital' in nome:
                    # Extrair ID do arquivo
                    arquivo_id = arquivo.get('id') or arquivo.get('sequencial')
                    
                    if arquivo_id:
                        # Construir URL direta de download
                        link_direto = f"{self.base_url_api}/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos/{arquivo_id}"
                        logger.debug("    ✅ Link PDF encontrado")
                        return link_direto
            
            logger.debug("    ℹ️ PDF do edital não encontrado nos arquivos")
            return None
            
        except Exception as e:
            logger.debug(f"    ⚠️ Erro ao buscar PDF: {str(e)}")
            return None
    
    def _processar_dados_completos(self, dados_compra: Dict, itens: List[Dict], 
                                   link_pdf: Optional[str], cnpj: str, ano: int, 
                                   sequencial: str) -> Dict:
        """
        Processa dados completos e retorna no formato expandido do modelo Licitacao
        """
        try:
            # Extrair orgão
            orgao = dados_compra.get('orgaoEntidade', {})
            razao_social = orgao.get('razaoSocial', 'Órgão não identificado')
            uf = orgao.get('uf', 'BR')
            
            # Extrair datas
            data_pub = dados_compra.get('dataPublicacaoPncp')
            data_abertura = dados_compra.get('dataAberturaProposta')
            data_encerramento = dados_compra.get('dataEncerramentoProposta')
            
            # Converter datas
            data_publicacao_dt = self._parse_date(data_pub)
            data_abertura_dt = self._parse_date(data_abertura)
            data_final_dt = self._parse_date(data_encerramento)
            
            # Determinar status
            status = self._determinar_status(data_final_dt, dados_compra.get('situacaoCompra'))
            
            # Extrair modalidade
            modalidade = dados_compra.get('modalidadeNome', dados_compra.get('modalidade', 'Não informada'))
            
            # Extrair objeto
            objeto = dados_compra.get('objetoCompra', 'Objeto não especificado')
            
            # Extrair medicamento do objeto ou itens
            medicamento = self._extrair_medicamento(objeto, itens)
            
            # Número do processo
            numero_processo = dados_compra.get('numeroControlePNCP', f'{ano}/{sequencial}')
            
            # Construir URL de origem (página de detalhes)
            link_origem = f"{self.base_url_app}/editais/{cnpj}/{ano}/{sequencial}"
            
            # Determinar esfera
            esfera = self._determinar_esfera(orgao, uf)
            
            # Gerar ID único para o frontend
            import uuid
            licitacao_id = str(uuid.uuid4())
            
            return {
                'id': licitacao_id,
                'medicamento': medicamento,
                'principio_ativo': None,
                'estado': uf,
                'status': status,
                'orgao_licitante': razao_social,
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
                'fonte_nome': 'PNCP - Portal Nacional de Contratações Públicas',
                'fonte_id': f'pncp-{cnpj}-{ano}-{sequencial}',
                'numero_pregao': numero_processo,
                'uasg': cnpj,
                'esfera': esfera,
                'objeto': objeto,
                
                # Itens
                'itens': itens,
                
                # Metadados
                'tags': self._extrair_tags(objeto),
                'is_mock': False,
                'fonte': 'PNCP'
            }
            
        except Exception as e:
            logger.error(f"    ❌ Erro ao processar dados: {str(e)}")
            return None
    
    def _processar_item_pncp(self, item: Dict) -> Optional[Dict]:
        """
        Processa um item REAL da API PNCP para formato padronizado
        
        Args:
            item: Item retornado pela API do PNCP
            
        Returns:
            Dict com dados padronizados ou None se dados incompletos
        """
        try:
            # Extrair informações principais
            ano_compra = item.get('anoCompra', item.get('ano'))
            sequencial = item.get('sequencialCompra', item.get('sequencial'))
            
            # Validação CRÍTICA: Se não tem ano e sequencial, não podemos criar URL válida
            if not ano_compra or not sequencial:
                logger.warning("⚠️ Item do PNCP sem ano ou sequencial - ignorado")
                return None
            
            # Número do processo completo
            numero_processo_completo = item.get('numeroProcesso', f'{ano_compra}/{sequencial}')
            
            # Orgão
            orgao_entidade = item.get('orgaoEntidade', {})
            razao_social = orgao_entidade.get('razaoSocial', 'Órgão não identificado')
            uf = orgao_entidade.get('uf', 'BR')
            cnpj = orgao_entidade.get('cnpj')
            
            # Validação CRÍTICA: CNPJ é obrigatório para construir URL
            if not cnpj:
                logger.warning("⚠️ Item do PNCP sem CNPJ - ignorado")
                return None
            
            # Datas
            data_publicacao = item.get('dataPublicacaoPncp', item.get('dataPublicacao'))
            data_abertura = item.get('dataAberturaProposta') or data_publicacao
            
            # Modalidade
            modalidade = item.get('modalidadeNome', item.get('modalidade', 'Não informada'))
            
            # Status
            situacao = item.get('situacaoCompra', item.get('situacao', 'Em andamento'))
            
            # Objeto da compra
            objeto = item.get('objetoCompra', item.get('objeto', ''))
            
            # ✅ CONSTRUIR URL DIRETA VÁLIDA (usando dados REAIS)
            # Formato: https://pncp.gov.br/app/editais/{CNPJ}/{ANO}/{SEQUENCIAL}
            link_edital = f'https://pncp.gov.br/app/editais/{cnpj}/{ano_compra}/{sequencial}'
            logger.info(f"✅ PNCP: URL REAL construída: {link_edital}")
            
            # Extrair tags
            tags = self._extrair_tags(objeto)
            
            # Determinar se é futuro
            is_futuro = False
            data_abertura_dt = None
            if data_abertura:
                try:
                    data_abertura_dt = datetime.fromisoformat(data_abertura.replace('Z', ''))
                    is_futuro = data_abertura_dt > datetime.now()
                except (ValueError, AttributeError):
                    pass
            
            data_referencia_dt = None
            if data_publicacao:
                try:
                    data_referencia_dt = datetime.fromisoformat(data_publicacao.replace('Z', ''))
                except (ValueError, AttributeError):
                    data_referencia_dt = datetime.now()
            else:
                data_referencia_dt = datetime.now()
            
            return {
                'medicamento': self._extrair_medicamento(objeto),
                'principio_ativo': None,
                'estado': uf,
                'status': 'FUTURA' if is_futuro else situacao,
                'orgao_licitante': razao_social,
                'modalidade': modalidade,
                'numero_processo': numero_processo_completo,
                'data_referencia': data_referencia_dt,
                'data_abertura': data_abertura_dt,
                'link_origem': link_edital,  # ✅ URL REAL E VÁLIDA
                'link_documento': self._extrair_link_documento(item, cnpj, ano_compra, sequencial),
                'tags': tags,
                'is_mock': False,  # ✅ DADOS REAIS
                'fonte': 'PNCP'
            }
        
        except Exception as e:
            logger.error(f"❌ Erro ao processar item PNCP: {str(e)}")
            return None
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Converte string de data para datetime"""
        if not date_str:
            return None
        try:
            # Remover timezone 'Z' se presente
            clean_str = date_str.replace('Z', '').replace('+00:00', '')
            return datetime.fromisoformat(clean_str)
        except (ValueError, AttributeError):
            return None
    
    def _determinar_status(self, data_final: Optional[datetime], situacao_api: Optional[str]) -> str:
        """Determina status da licitação baseado em data final e situação"""
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
    
    def _determinar_esfera(self, orgao: Dict, uf: str) -> str:
        """Determina esfera administrativa do órgão"""
        razao = orgao.get('razaoSocial', '').lower()
        
        if 'federal' in razao or 'ministério' in razao or 'ministerio' in razao:
            return 'Federal'
        elif 'municipal' in razao or 'prefeitura' in razao or 'município' in razao:
            return 'Municipal'
        elif uf and uf != 'BR':
            return 'Estadual'
        
        return 'Não identificada'
    
    def _extrair_medicamento(self, objeto: str, itens: List[Dict] = None) -> str:
        """Extrai nome do medicamento do objeto ou dos itens"""
        texto = objeto
        """
        Extrai nome do medicamento do objeto da compra
        
        Args:
            texto: Descrição do objeto da licitação
            
        Returns:
            Nome do medicamento identificado ou descrição genérica
        """
        if not texto:
            return 'Medicamento não especificado'
        
        texto_lower = texto.lower()
        
        # Lista expandida de medicamentos comuns
        medicamentos_conhecidos = [
            'adalimumabe', 'pembrolizumabe', 'insulina', 'metformina',
            'omeprazol', 'paracetamol', 'dipirona', 'amoxicilina',
            'losartana', 'atorvastatina', 'sinvastatina', 'ibuprofeno',
            'nimesulida', 'azitromicina', 'dexametasona', 'prednisolona',
            'lenacapavir', 'cabotegravir', 'risperidona', 'quetiapina'
        ]
        
        for med in medicamentos_conhecidos:
            if med in texto_lower:
                return med.capitalize()
        
        # Tentar identificar por palavras-chave médicas
        if 'medicamento' in texto_lower:
            palavras = texto.split()
            idx = -1
            for i, palavra in enumerate(palavras):
                if 'medicamento' in palavra.lower():
                    idx = i
                    break
            if idx >= 0 and idx + 1 < len(palavras):
                # Pegar próxima palavra
                proxima = palavras[idx + 1].strip('.,;:')
                if len(proxima) > 3:
                    return proxima.capitalize()
        
        # Pegar primeira palavra significativa
        palavras = texto.split()
        for palavra in palavras[:15]:
            palavra_limpa = palavra.strip('.,;:()[]')
            if len(palavra_limpa) > 5 and palavra_limpa.lower() not in [
                'aquisicao', 'aquisição', 'compra', 'fornecimento', 'registro', 
                'pregao', 'pregão', 'licitacao', 'licitação'
            ]:
                return palavra_limpa.capitalize()
        
        return 'Medicamento não especificado'
    
    def _extrair_tags(self, texto: str) -> List[str]:
        """Extrai tags do objeto da compra com critérios ESPECÍFICOS"""
        texto_lower = texto.lower()
        tags = []
        
        if any(k in texto_lower for k in ['alto custo', 'especializado', 'ceaf']):
            tags.append('alto_custo')
        
        # IMPORTADO - CRITÉRIOS EXCLUSIVOS E ESPECÍFICOS
        # Só marca como importado se encontrar termos MUITO específicos de importação
        termos_importacao = [
            'aquisição de medicamentos importados',
            'aquisição de produtos importados',
            'núcleo de importação',
            'proforma invoice',
            'regulamento aduaneiro',
            'importacao.ce@saude.ce.gov.br',
            'importacao@saude',
            'sem registro no país',
            'ausência de registro anvisa',
            'sem registro anvisa',
            'rdc 660/2022',
            'rdc 660',
            'rdc 81/2009',
            'rdc 81',
            'portaria anvisa',
            'siscomex',
            'declaração de importação',
            'di - declaração',
            'excepcionalidade',
            'importação em caráter excepcional',
            'importação excepcional',
            'inexigibilidade',  # Forte indicativo de importado
            'dispensa de licitação'  # Forte indicativo
        ]
        
        if any(termo in texto_lower for termo in termos_importacao):
            tags.append('importado')
        
        if any(k in texto_lower for k in ['judicial', 'liminar', 'mandado']):
            tags.append('judicial')
        
        return tags
    
    def _extrair_link_documento(self, item: Dict, cnpj: str, ano: int, sequencial: str) -> Optional[str]:
        """
        Tenta extrair link direto para documento PDF do edital do PNCP
        
        Args:
            item: Item da API
            cnpj: CNPJ do órgão
            ano: Ano da compra
            sequencial: Sequencial da compra
            
        Returns:
            URL do PDF ou None
        """
        try:
            # PRIORIDADE 1: Verificar se há links de anexos/documentos na resposta da API
            anexos = item.get('arquivos', []) or item.get('documentos', []) or item.get('anexos', [])
            
            if anexos and isinstance(anexos, list):
                for anexo in anexos:
                    # Buscar por PDF do edital
                    nome = anexo.get('nome', '').lower()
                    tipo = anexo.get('tipo', '').lower()
                    url = anexo.get('url') or anexo.get('link') or anexo.get('arquivo')
                    
                    if url and (tipo == 'edital' or 'edital' in nome or '.pdf' in url.lower()):
                        # Validar que é URL pública
                        if url.startswith('http'):
                            logger.info(f"✅ PDF encontrado nos metadados: {url[:80]}...")
                            return url
                        elif url.startswith('/'):
                            url_completa = f'https://pncp.gov.br{url}'
                            logger.info(f"✅ PDF encontrado (relativo): {url_completa[:80]}...")
                            return url_completa
            
            # PRIORIDADE 2: Construir URL da API de documentos do PNCP
            # Endpoint: /v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos
            if cnpj and ano and sequencial:
                url_api_docs = f'https://pncp.gov.br/api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{sequencial}/arquivos'
                
                try:
                    resp = self.session.get(url_api_docs, timeout=8)
                    if resp.status_code == 200:
                        docs = resp.json()
                        if isinstance(docs, list):
                            # Buscar edital na lista
                            for doc in docs:
                                tipo_doc = doc.get('tipo', '').lower()
                                nome_doc = doc.get('nome', '').lower()
                                if 'edital' in tipo_doc or 'edital' in nome_doc:
                                    doc_url = doc.get('url') or doc.get('link')
                                    if doc_url and doc_url.startswith('http'):
                                        logger.info(f"✅ PDF encontrado via API: {doc_url[:80]}...")
                                        return doc_url
                except requests.exceptions.Timeout:
                    logger.debug("⏱️ Timeout ao buscar documentos na API")
                except requests.exceptions.RequestException as e:
                    logger.debug(f"⚠️ Erro ao acessar API de documentos: {str(e)}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao extrair link documento: {str(e)}")
        
        # Se não encontrou, retorna None
        # O frontend usará o link_origem (página do edital)
        return None
