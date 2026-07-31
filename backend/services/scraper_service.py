from typing import List, Dict, Optional, Callable, Any, Tuple
from scrapers import CearaScraper, EspiritoSantoScraper, SaoPauloScraper, RioDeJaneiroScraper, RioGrandeDoSulScraper, SantaCatarinaScraper, ParanaCsvImporter, BahiaCsvImporter, PernambucoCsvImporter, SaoPauloTceCsvImporter, MinasGeraisCsvImporter, GoiasCsvImporter, EspiritoSantoCsvImporter, MatoGrossoSulCsvImporter, PNCPApiOficial, AgregadorClient
from scrapers.pncp_client import PNCPClient
from scrapers.comprasnet_client import ComprasNetClient
from scrapers.bec_sp_client import BECSpClient
from scrapers.minas_gerais_scraper import MinasGeraisScraper
import logging
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Pool de threads para scrapers síncronos (PNCP, ComprasNet)
_thread_pool = ThreadPoolExecutor(max_workers=10)

# Limite de browsers Chromium (Playwright) simultâneos.
# Cada instância consome ~300-500MB de RAM; a VPS tem só ~3.6GB no total,
# então rodar os 5 scrapers baseados em browser (BEC/SP, RJ, RS, SC, PR) em
# paralelo sem limite é o principal responsável pelo esgotamento de memória.
_playwright_semaphore = asyncio.Semaphore(2)

class ScraperService:
    """
    Serviço de agregação de scrapers
    
    Implementa busca hierárquica:
    1. PNCP (nacional - estadual/municipal)
    2. ComprasNet/SIASG (federal)
    3. BEC/e-NEGÓCIOS SP (regional - alto volume)
    4. RJ (regional - Portal SIGA RJ)
    5. RS (regional - Compras Eletrônicas RS)
    6. SC (regional - Portal de Compras SC)
    7. PR (regional - Portal Transparência CSV)
    8. BA (regional - Dados Abertos CSV)
    9. PE (regional - Dados Abertos TCE CSV)
    10. SP-TCE (regional - Portal TCE-SP CSV - todos municípios paulistas)
    11. MG (regional - Dados Abertos MG CSV - todos órgãos estaduais)
    12. GO (regional - Dados Abertos GO CSV - todos órgãos estaduais)
    13. ES (regional - Dados Abertos ES CSV - todos órgãos estaduais)
    14. MS (regional - Dados Abertos MS CSV - todos órgãos estaduais)
    15. Scrapers estaduais (CE)
    """
    def __init__(self, health_monitor=None):
        """
        Inicializa o serviço de scrapers
        
        Args:
            health_monitor: Instância do HealthMonitorService para registrar execuções (opcional)
        """
        # Health Monitor para registrar execuções
        self.health_monitor = health_monitor
        
        # Scrapers estaduais
        self.scrapers = {
            'CE': CearaScraper(),
            'ES': EspiritoSantoScraper(),
            'SP': SaoPauloScraper(),
            'MG': None,  # Será atribuído abaixo (CSV)
            'RJ': None,  # Será atribuído abaixo
            'RS': None,  # Rio Grande do Sul
            'SC': None,  # Santa Catarina
            'PR': None,  # Paraná (CSV)
            'BA': None,  # Bahia (CSV)
            'PE': None,  # Pernambuco (CSV)
            'SP-TCE': None,  # São Paulo TCE (CSV)
            'MG-CSV': None  # NOVO: Minas Gerais CSV (Dados Abertos)
        }
        
        # Agregadores (PRIORIDADE)
        self.pncp_client = PNCPClient()
        self.pncp_api_oficial = PNCPApiOficial()  # NOVO: API oficial de dados abertos
        self.comprasnet_client = ComprasNetClient()
        self.bec_sp_client = BECSpClient()  # Agregador regional SP
        self.agregador_client = AgregadorClient()  # Agregador (22 portais incluindo Licitações-e)
        
        # Scrapers estaduais individuais
        self.mg_scraper = MinasGeraisScraper()  # Minas Gerais Playwright (backup)
        self.mg_csv_importer = MinasGeraisCsvImporter()  # Minas Gerais CSV
        self.rj_scraper = RioDeJaneiroScraper()  # Rio de Janeiro
        self.rs_scraper = RioGrandeDoSulScraper()  # Rio Grande do Sul
        self.sc_scraper = SantaCatarinaScraper()  # Santa Catarina
        self.pr_importer = ParanaCsvImporter()  # Paraná (CSV)
        self.ba_importer = BahiaCsvImporter()  # Bahia (CSV)
        self.pe_importer = PernambucoCsvImporter()  # Pernambuco (CSV)
        self.sp_tce_importer = SaoPauloTceCsvImporter()  # São Paulo TCE (CSV)
        self.go_importer = GoiasCsvImporter()  # Goiás (CSV)
        self.es_csv_importer = EspiritoSantoCsvImporter()  # NOVO: Espírito Santo (CSV)
        
        self.scrapers['MG'] = self.mg_csv_importer  # Usar CSV como padrão
        self.scrapers['RJ'] = self.rj_scraper
        self.scrapers['RS'] = self.rs_scraper
        self.scrapers['SC'] = self.sc_scraper
        self.scrapers['PR'] = self.pr_importer
        self.scrapers['BA'] = self.ba_importer
        self.scrapers['PE'] = self.pe_importer
        self.scrapers['SP-TCE'] = self.sp_tce_importer
        self.scrapers['GO'] = self.go_importer
        self.scrapers['ES-CSV'] = self.es_csv_importer  # NOVO
    
    async def _registrar_execucao(
        self,
        fonte: str,
        status: str,
        resultados_count: int = 0,
        termo_busca: str = None,
        tempo_execucao_ms: int = None,
        erro_mensagem: str = None
    ):
        """
        Registra execução no Health Monitor se disponível
        """
        if self.health_monitor:
            try:
                await self.health_monitor.registrar_execucao(
                    fonte=fonte,
                    status=status,
                    resultados_count=resultados_count,
                    termo_busca=termo_busca,
                    tempo_execucao_ms=tempo_execucao_ms,
                    erro_mensagem=erro_mensagem
                )
            except Exception as e:
                logger.debug(f"Erro ao registrar execução no health monitor: {str(e)}")
    
    async def _executar_scraper_async(
        self,
        nome_fonte: str,
        coro_or_func: Any,
        medicamento: str,
        is_sync: bool = False,
        timeout_seconds: int = 30,
        usa_browser: bool = False,
        **kwargs
    ) -> Tuple[str, List[Dict], int, Optional[str]]:
        """
        Executa um scraper individual com TIMEOUT e retorna resultado padronizado.

        Args:
            nome_fonte: Nome da fonte para logging
            coro_or_func: Coroutine ou função síncrona a executar
            medicamento: Termo de busca
            is_sync: Se True, executa em thread pool
            timeout_seconds: Timeout em segundos (padrão: 30s)
            usa_browser: Se True, limita concorrência via _playwright_semaphore
                (scraper abre um Chromium e consome bastante RAM)
            **kwargs: Argumentos adicionais para o scraper

        Returns:
            Tuple[nome_fonte, resultados, tempo_ms, erro_msg]
        """
        inicio = time.time()
        try:
            if is_sync:
                # Executar função síncrona no thread pool com timeout
                loop = asyncio.get_event_loop()
                dados = await asyncio.wait_for(
                    loop.run_in_executor(_thread_pool, coro_or_func),
                    timeout=timeout_seconds
                )
            elif usa_browser:
                # Aguarda vaga no semáforo (sem contar no timeout do scraper)
                # e só então executa a coroutine com o timeout normal.
                async with _playwright_semaphore:
                    dados = await asyncio.wait_for(coro_or_func, timeout=timeout_seconds)
            else:
                # Executar coroutine com timeout
                dados = await asyncio.wait_for(coro_or_func, timeout=timeout_seconds)
            
            tempo_ms = int((time.time() - inicio) * 1000)
            resultados = dados if dados else []
            
            if resultados:
                logger.info(f"  ✅ {nome_fonte}: {len(resultados)} resultados ({tempo_ms}ms)")
            else:
                logger.info(f"  ℹ️ {nome_fonte}: 0 resultados ({tempo_ms}ms)")
            
            return (nome_fonte, resultados, tempo_ms, None)
        
        except asyncio.TimeoutError:
            tempo_ms = int((time.time() - inicio) * 1000)
            logger.warning(f"  ⏰ TIMEOUT no {nome_fonte} após {timeout_seconds}s")
            return (nome_fonte, [], tempo_ms, f"Timeout após {timeout_seconds}s")
            
        except Exception as e:
            tempo_ms = int((time.time() - inicio) * 1000)
            logger.error(f"  ❌ Erro no {nome_fonte}: {str(e)}")
            return (nome_fonte, [], tempo_ms, str(e))

    async def buscar_medicamento(
        self, 
        medicamento: str, 
        estados: List[str] = None, 
        incluir_agregadores: bool = True,
        apenas_futuras: bool = False,
        limit_por_fonte: int = 10
    ) -> List[Dict]:
        """
        Busca medicamento com estratégia PARALELA otimizada.
        
        OTIMIZAÇÃO P0: Todos os scrapers são executados em paralelo usando asyncio.gather(),
        reduzindo o tempo total de execução de ~90-120s para ~10-15s.
        
        Args:
            medicamento: Nome do medicamento
            estados: Lista de estados específicos (opcional)
            incluir_agregadores: Se True, busca em PNCP e ComprasNet
            apenas_futuras: Se True, filtra apenas licitações com data futura
            limit_por_fonte: Limite de resultados por fonte
            
        Returns:
            List[Dict]: Lista agregada de licitações
        """
        inicio_total = time.time()
        logger.info(f"🚀 Iniciando busca PARALELA para: '{medicamento}'")
        
        # ========== FASE 1: PNCP-OFICIAL (executar ANTES do paralelo) ==========
        # A API PNCP é a fonte mais rica para propostas abertas, executamos isoladamente
        resultados_pncp = []
        if incluir_agregadores and apenas_futuras:
            try:
                logger.info("  🎯 [FASE 1] Buscando PNCP-OFICIAL (propostas abertas)...")
                inicio_pncp = time.time()
                resultados_pncp = await self.pncp_api_oficial.buscar_licitacoes(
                    termo_busca=medicamento,
                    apenas_futuras=apenas_futuras,
                    apenas_saude=True,
                    limit=limit_por_fonte
                )
                tempo_pncp = int((time.time() - inicio_pncp) * 1000)
                logger.info(f"  ✅ PNCP-OFICIAL: {len(resultados_pncp)} resultados ({tempo_pncp}ms)")
                await self._registrar_execucao('PNCP-OFICIAL', 'success', len(resultados_pncp), medicamento, tempo_pncp)
            except Exception as e:
                logger.error(f"  ❌ Erro no PNCP-OFICIAL: {str(e)}")
                await self._registrar_execucao('PNCP-OFICIAL', 'error', 0, medicamento, 0, str(e))
        
        # ========== FASE 2: Outros scrapers em paralelo ==========
        # Preparar lista de tasks para execução paralela
        tasks = []
        
        if incluir_agregadores:
            # Agregador (22 portais) - precisa login
            tasks.append(self._executar_scraper_async(
                'AGREGADOR',
                self.agregador_client.buscar_licitacoes(
                    termo_busca=medicamento,
                    apenas_futuras=apenas_futuras,
                    limit=limit_por_fonte
                ),
                medicamento,
                timeout_seconds=25
            ))
            
            # PNCP (síncrono - usar thread pool)
            tasks.append(self._executar_scraper_async(
                'PNCP',
                lambda: self.pncp_client.buscar_licitacoes(medicamento, apenas_futuras, limit_por_fonte),
                medicamento,
                is_sync=True,
                timeout_seconds=20
            ))
            
            # ComprasNet (síncrono - usar thread pool)
            tasks.append(self._executar_scraper_async(
                'ComprasNet',
                lambda: self.comprasnet_client.buscar_licitacoes(medicamento, apenas_futuras, limit_por_fonte),
                medicamento,
                is_sync=True,
                timeout_seconds=20
            ))
            
            # BEC/SP - scraper web mais lento
            tasks.append(self._executar_scraper_async(
                'BEC/SP',
                self.bec_sp_client.buscar_licitacoes(
                    termo_busca=medicamento,
                    apenas_futuras=apenas_futuras,
                    limit=limit_por_fonte
                ),
                medicamento,
                timeout_seconds=40,
                usa_browser=True
            ))

            # RJ (SIGA) - scraper web
            tasks.append(self._executar_scraper_async(
                'RJ',
                self.rj_scraper.buscar_licitacoes(
                    termo_busca=medicamento,
                    apenas_futuras=apenas_futuras,
                    limit=limit_por_fonte
                ),
                medicamento,
                timeout_seconds=25,
                usa_browser=True
            ))

            # RS (CELIC) - scraper web
            tasks.append(self._executar_scraper_async(
                'RS',
                self.rs_scraper.buscar_licitacoes(
                    termo_busca=medicamento,
                    apenas_futuras=apenas_futuras,
                    limit=limit_por_fonte
                ),
                medicamento,
                timeout_seconds=25,
                usa_browser=True
            ))

            # SC (CIASC) - scraper web
            tasks.append(self._executar_scraper_async(
                'SC',
                self.sc_scraper.buscar_licitacoes(
                    termo_busca=medicamento,
                    apenas_futuras=apenas_futuras,
                    limit=limit_por_fonte
                ),
                medicamento,
                timeout_seconds=25,
                usa_browser=True
            ))

            # PR (CSV) - arquivo ~1MB
            tasks.append(self._executar_scraper_async(
                'PR',
                self.pr_importer.buscar_licitacoes(
                    termo_busca=medicamento,
                    apenas_saude=True,
                    limit=limit_por_fonte
                ),
                medicamento,
                timeout_seconds=40,
                usa_browser=True
            ))
            
            # BA (CSV) - arquivo grande ~120MB
            tasks.append(self._executar_scraper_async(
                'BA',
                self.ba_importer.buscar_licitacoes(
                    termo_busca=medicamento,
                    apenas_saude=True,
                    limit=limit_por_fonte
                ),
                medicamento,
                timeout_seconds=40
            ))
            
            # PE (CSV) - arquivo ~10MB
            tasks.append(self._executar_scraper_async(
                'PE',
                self.pe_importer.buscar_licitacoes(
                    termo_busca=medicamento,
                    apenas_saude=True,
                    limit=limit_por_fonte
                ),
                medicamento,
                timeout_seconds=40
            ))
            
            # SP-TCE (CSV) - arquivo grande ~50MB
            tasks.append(self._executar_scraper_async(
                'SP-TCE',
                self.sp_tce_importer.buscar_licitacoes(
                    termo_busca=medicamento,
                    apenas_saude=True,
                    limit=limit_por_fonte
                ),
                medicamento,
                timeout_seconds=40
            ))
            
            # MG (CSV) - arquivo ~25MB
            tasks.append(self._executar_scraper_async(
                'MG',
                self.mg_csv_importer.buscar_licitacoes(
                    termo_busca=medicamento,
                    apenas_saude=True,
                    apenas_futuras=apenas_futuras,
                    limit=limit_por_fonte
                ),
                medicamento,
                timeout_seconds=40
            ))
            
            # GO (CSV) - arquivos múltiplos
            tasks.append(self._executar_scraper_async(
                'GO',
                self.go_importer.buscar_licitacoes(
                    termo_busca=medicamento,
                    apenas_saude=True,
                    apenas_futuras=apenas_futuras,
                    limit=limit_por_fonte
                ),
                medicamento,
                timeout_seconds=40
            ))
            
            # ES (CSV) - arquivo ~2.5MB
            tasks.append(self._executar_scraper_async(
                'ES-CSV',
                self.es_csv_importer.buscar_licitacoes(
                    termo_busca=medicamento,
                    apenas_saude=True,
                    apenas_futuras=apenas_futuras,
                    limit=limit_por_fonte
                ),
                medicamento,
                timeout_seconds=40
            ))
        
        # Scrapers estaduais (CE, SP)
        if not estados:
            estados = ['CE', 'SP']
        
        for estado in estados:
            if estado in self.scrapers and self.scrapers[estado]:
                tasks.append(self._executar_scraper_async(
                    f'SCRAPER-{estado}',
                    self.scrapers[estado].scrape(medicamento),
                    medicamento
                ))
        
        # ========== EXECUÇÃO PARALELA ==========
        logger.info(f"  ⚡ Executando {len(tasks)} scrapers em PARALELO...")
        
        # Executar todas as tasks em paralelo com asyncio.gather
        # Cada task tem seu próprio timeout individual, não precisamos de timeout global
        # return_exceptions=True garante que erros não param a execução
        resultados_paralelos = await asyncio.gather(*tasks, return_exceptions=True)
        
        # ========== PROCESSAR RESULTADOS ==========
        resultados = []
        sucessos = 0
        erros = 0
        
        for resultado in resultados_paralelos:
            if isinstance(resultado, Exception):
                # Erro não capturado no wrapper
                logger.error(f"  ❌ Erro não capturado: {str(resultado)}")
                erros += 1
            elif isinstance(resultado, tuple) and len(resultado) == 4:
                nome_fonte, dados, tempo_ms, erro_msg = resultado
                
                # Registrar execução no health monitor
                if erro_msg:
                    await self._registrar_execucao(nome_fonte, 'error', 0, medicamento, tempo_ms, erro_msg)
                    erros += 1
                else:
                    await self._registrar_execucao(nome_fonte, 'success', len(dados), medicamento, tempo_ms)
                    sucessos += 1
                    resultados.extend(dados)
        
        # ========== ADICIONAR RESULTADOS PNCP-OFICIAL (FASE 1) ==========
        if resultados_pncp:
            resultados.extend(resultados_pncp)
            logger.info(f"  📊 Adicionados {len(resultados_pncp)} do PNCP-OFICIAL (Fase 1)")
        
        # ========== RELATÓRIO FINAL ==========
        tempo_total = time.time() - inicio_total
        logger.info(f"⚡ Busca concluída em {tempo_total:.2f}s")
        logger.info(f"   📊 Fontes paralelas: {sucessos} sucesso / {erros} erro")
        logger.info(f"   📊 PNCP-OFICIAL: {len(resultados_pncp)} resultados")
        logger.info(f"🎯 Total agregado: {len(resultados)} licitações")
        
        return resultados
    
    async def buscar_apenas_pncp(self, medicamento: str = None, apenas_futuras: bool = False, limit: int = 20) -> List[Dict]:
        """Busca apenas no PNCP"""
        try:
            logger.info(f"Buscando apenas no PNCP: {medicamento}")
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None, 
                self.pncp_client.buscar_licitacoes, 
                medicamento,
                apenas_futuras,
                limit
            )
        except Exception as e:
            logger.error(f"Erro ao buscar no PNCP: {str(e)}")
            return []
    
    async def buscar_apenas_comprasnet(self, medicamento: str = None, apenas_futuras: bool = False, limit: int = 20) -> List[Dict]:
        """Busca apenas no ComprasNet/SIASG"""
        try:
            logger.info(f"Buscando apenas no ComprasNet: {medicamento}")
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self.comprasnet_client.buscar_licitacoes,
                medicamento,
                apenas_futuras,
                limit
            )
        except Exception as e:
            logger.error(f"Erro ao buscar no ComprasNet: {str(e)}")
            return []
    
    async def buscar_apenas_bec_sp(self, medicamento: str = None, apenas_futuras: bool = False, limit: int = 20) -> List[Dict]:
        """Busca apenas no BEC/e-NEGÓCIOS SP"""
        try:
            logger.info(f"Buscando apenas no BEC SP: {medicamento}")
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self.bec_sp_client.buscar_licitacoes,
                medicamento,
                apenas_futuras,
                limit
            )
        except Exception as e:
            logger.error(f"Erro ao buscar no BEC SP: {str(e)}")
            return []
    
    async def buscar_apenas_rj(self, medicamento: str = None, apenas_futuras: bool = False, limit: int = 20) -> List[Dict]:
        """Busca apenas no Portal SIGA RJ"""
        try:
            logger.info(f"Buscando apenas no RJ (SIGA): {medicamento}")
            return await self.rj_scraper.buscar_licitacoes(
                termo_busca=medicamento,
                apenas_futuras=apenas_futuras,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Erro ao buscar no RJ (SIGA): {str(e)}")
            return []
    
    async def buscar_apenas_rs(self, medicamento: str = None, apenas_futuras: bool = False, limit: int = 20) -> List[Dict]:
        """Busca apenas no Portal Compras RS (CELIC)"""
        try:
            logger.info(f"Buscando apenas no RS (CELIC): {medicamento}")
            return await self.rs_scraper.buscar_licitacoes(
                termo_busca=medicamento,
                apenas_futuras=apenas_futuras,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Erro ao buscar no RS (CELIC): {str(e)}")
            return []
    
    async def buscar_apenas_sc(self, medicamento: str = None, apenas_futuras: bool = False, limit: int = 20) -> List[Dict]:
        """Busca apenas no Portal de Compras SC (CIASC)"""
        try:
            logger.info(f"Buscando apenas no SC (CIASC): {medicamento}")
            return await self.sc_scraper.buscar_licitacoes(
                termo_busca=medicamento,
                apenas_futuras=apenas_futuras,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Erro ao buscar no SC (CIASC): {str(e)}")
            return []
    
    async def buscar_apenas_pr(self, medicamento: str = None, apenas_saude: bool = True, limit: int = 20) -> List[Dict]:
        """Busca apenas no Portal Transparência PR (CSV)"""
        try:
            logger.info(f"Buscando apenas no PR (CSV): {medicamento}")
            return await self.pr_importer.buscar_licitacoes(
                termo_busca=medicamento,
                apenas_saude=apenas_saude,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Erro ao buscar no PR (CSV): {str(e)}")
            return []
    
    async def buscar_apenas_ba(self, medicamento: str = None, apenas_saude: bool = True, limit: int = 20) -> List[Dict]:
        """Busca apenas no Portal Dados Abertos BA (CSV)"""
        try:
            logger.info(f"Buscando apenas no BA (CSV): {medicamento}")
            return await self.ba_importer.buscar_licitacoes(
                termo_busca=medicamento,
                apenas_saude=apenas_saude,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Erro ao buscar no BA (CSV): {str(e)}")
            return []
    
    async def buscar_apenas_pe(self, medicamento: str = None, apenas_saude: bool = True, limit: int = 20) -> List[Dict]:
        """Busca apenas no Portal Dados Abertos PE (CSV)"""
        try:
            logger.info(f"Buscando apenas no PE (CSV): {medicamento}")
            return await self.pe_importer.buscar_licitacoes(
                termo_busca=medicamento,
                apenas_saude=apenas_saude,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Erro ao buscar no PE (CSV): {str(e)}")
            return []
    
    async def buscar_apenas_sp_tce(self, medicamento: str = None, apenas_saude: bool = True, limit: int = 20) -> List[Dict]:
        """Busca apenas no Portal TCE-SP (CSV - todos municípios paulistas)"""
        try:
            logger.info(f"Buscando apenas no SP-TCE (CSV): {medicamento}")
            return await self.sp_tce_importer.buscar_licitacoes(
                termo_busca=medicamento,
                apenas_saude=apenas_saude,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Erro ao buscar no SP-TCE (CSV): {str(e)}")
            return []
    
    async def buscar_apenas_mg(self, medicamento: str = None, apenas_saude: bool = True, limit: int = 20) -> List[Dict]:
        """Busca apenas no Portal Dados Abertos MG (CSV - todos órgãos estaduais)"""
        try:
            logger.info(f"Buscando apenas no MG (CSV): {medicamento}")
            return await self.mg_csv_importer.buscar_licitacoes(
                termo_busca=medicamento,
                apenas_saude=apenas_saude,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Erro ao buscar no MG (CSV): {str(e)}")
            return []
    
    async def buscar_apenas_go(self, medicamento: str = None, apenas_saude: bool = True, limit: int = 20) -> List[Dict]:
        """Busca apenas no Portal Dados Abertos GO (CSV - todos órgãos estaduais)"""
        try:
            logger.info(f"Buscando apenas no GO (CSV): {medicamento}")
            return await self.go_importer.buscar_licitacoes(
                termo_busca=medicamento,
                apenas_saude=apenas_saude,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Erro ao buscar no GO (CSV): {str(e)}")
            return []
    
    async def buscar_apenas_es(self, medicamento: str = None, apenas_saude: bool = True, limit: int = 20) -> List[Dict]:
        """Busca apenas no Portal Dados Abertos ES (CSV - todos órgãos estaduais)"""
        try:
            logger.info(f"Buscando apenas no ES (CSV): {medicamento}")
            return await self.es_csv_importer.buscar_licitacoes(
                termo_busca=medicamento,
                apenas_saude=apenas_saude,
                limit=limit
            )
        except Exception as e:
            logger.error(f"Erro ao buscar no ES (CSV): {str(e)}")
            return []
    
    async def refresh_estado(self, estado: str, medicamento: str) -> List[Dict]:
        """Força refresh de um estado específico"""
        if estado in self.scrapers:
            logger.info(f"Refresh do estado {estado}")
            return await self.scrapers[estado].scrape(medicamento)
        return []
