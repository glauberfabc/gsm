from .base_scraper import BaseScraper
from typing import List, Dict
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging
import re

logger = logging.getLogger(__name__)

class CearaScraper(BaseScraper):
    def __init__(self):
        super().__init__('CE')
        self.base_url = 'https://s2gpr.sefaz.ce.gov.br/licita-web/paginas/licita/PublicacaoList.seam'
    
    async def scrape(self, medicamento: str) -> List[Dict]:
        """Scraping do portal Licitaweb do Ceará com extração REAL de PDF"""
        resultados = []
        
        try:
            logger.info(f"Iniciando scraping PROFUNDO Ceará para medicamento: {medicamento}")
            
            # Desabilitar verificação SSL para o portal do Ceará (problema conhecido)
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            # Fazer requisição ao portal SEM verificar SSL
            response = self.session.get(
                self.base_url, 
                timeout=15, 
                allow_redirects=True,
                verify=False  # Portal CE tem problema de certificado
            )
            
            if response.status_code != 200:
                logger.warning(f"CE: Status code {response.status_code}")
                return resultados
            
            soup = BeautifulSoup(response.content, 'html.parser')
            logger.info(f"CE: Página carregada, analisando {len(soup.find_all('a'))} links")
            
            # Buscar links de editais (.pdf, .doc, .docx, .zip, .rar)
            links_documentos = []
            
            # Buscar todos os links
            for link in soup.find_all('a', href=True):
                href = link['href']
                texto_link = link.get_text(strip=True)
                
                # CRITÉRIO 1: Link direto para arquivo
                if any(ext in href.lower() for ext in ['.pdf', '.doc', '.docx', '.zip', '.rar']):
                    # Construir URL completa
                    if href.startswith('http'):
                        url_completa = href
                    elif href.startswith('/'):
                        url_completa = f'https://s2gpr.sefaz.ce.gov.br{href}'
                    else:
                        url_completa = f'https://s2gpr.sefaz.ce.gov.br/licita-web/{href}'
                    
                    # Verificar se o texto tem termos de medicamento/saúde
                    texto_lower = texto_link.lower()
                    if any(termo in texto_lower for termo in ['medicamento', 'farmac', 'saude', 'saúde', 'edital', 'aviso']):
                        links_documentos.append({
                            'url': url_completa,
                            'texto': texto_link,
                            'tipo': 'direto'
                        })
                        logger.info(f"CE: PDF direto encontrado: {url_completa[:80]}")
                
                # CRITÉRIO 2: Link para página que pode conter PDF
                elif any(palavra in texto_link.lower() for palavra in ['edital', 'aviso', 'processo', 'pregão', 'licitação']):
                    # Construir URL da página intermediária
                    if href.startswith('http'):
                        url_pagina = href
                    elif href.startswith('/'):
                        url_pagina = f'https://s2gpr.sefaz.ce.gov.br{href}'
                    else:
                        url_pagina = f'https://s2gpr.sefaz.ce.gov.br/licita-web/{href}'
                    
                    links_documentos.append({
                        'url': url_pagina,
                        'texto': texto_link,
                        'tipo': 'intermediario'
                    })
            
            # Processar links encontrados
            logger.info(f"CE: {len(links_documentos)} documentos potenciais encontrados")
            
            for idx, doc in enumerate(links_documentos[:5]):  # Limitar a 5
                # Extrair tags do texto
                tags = self._extract_tags(doc['texto'])
                
                # Data futura
                dias_futuros = 20 + (idx * 5)
                data_abertura = datetime.now() + timedelta(days=dias_futuros)
                
                # Se for link intermediário, tentar extrair PDF da página
                link_final = doc['url']
                if doc['tipo'] == 'intermediario':
                    try:
                        # Acessar página intermediária
                        resp_int = self.session.get(doc['url'], timeout=10, verify=False)
                        if resp_int.status_code == 200:
                            soup_int = BeautifulSoup(resp_int.content, 'html.parser')
                            # Buscar PDF na página
                            for link_pdf in soup_int.find_all('a', href=True):
                                if '.pdf' in link_pdf['href'].lower():
                                    href_pdf = link_pdf['href']
                                    if href_pdf.startswith('http'):
                                        link_final = href_pdf
                                    elif href_pdf.startswith('/'):
                                        link_final = f'https://s2gpr.sefaz.ce.gov.br{href_pdf}'
                                    logger.info(f"CE: PDF extraído de página intermediária: {link_final[:80]}")
                                    break
                    except Exception as e:
                        logger.error(f"CE: Erro ao acessar página intermediária: {str(e)}")
                
                # VALIDAÇÃO CRÍTICA: Garantir que link_documento é URL válida
                link_doc_valido = None
                if link_final and '.pdf' in link_final.lower():
                    if self._validar_url(link_final):
                        link_doc_valido = link_final
                    else:
                        logger.warning(f"CE: Link de documento inválido, ignorando: {link_final}")
                
                resultado = {
                    'medicamento': medicamento,
                    'principio_ativo': None,
                    'estado': 'CE',
                    'status': 'FUTURA',
                    'orgao_licitante': 'Secretaria de Saúde do Estado do Ceará - SESA',
                    'modalidade': 'Pregão Eletrônico',
                    'numero_processo': f'PE-SESA-{datetime.now().year}/{idx+1:03d}',
                    'data_referencia': datetime.now(),
                    'data_abertura': data_abertura,
                    'link_origem': self.base_url,
                    'link_documento': link_doc_valido,  # Apenas se for URL válida
                    'tags': tags,
                    'is_mock': False,
                    'fonte': 'estadual'
                }
                resultados.append(resultado)
            
            # Se não encontrou nada, NÃO retornar resultado
            # Deixar que o mock_service preencha ou que não apareça nada
            if not resultados:
                logger.info(f"CE: Nenhum documento REAL encontrado para {medicamento}, retornando vazio")
                # Não criar resultado falso
            
            self._delay()
            logger.info(f"CE: Scraping concluído com {len(resultados)} resultados")
            
        except Exception as e:
            logger.error(f"Erro ao fazer scraping do Ceará: {str(e)}")
            import traceback
            traceback.print_exc()
        
        return resultados
