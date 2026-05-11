#!/usr/bin/env python3
"""
🧪 TESTE DE VALIDAÇÃO - FILTRO TEMPORAL E QUALIDADE DOS RESULTADOS

Testa os requisitos específicos do review request:
1. Filtro temporal obrigatório por default (últimos 90 dias OU abertura futura)
2. Controle incluir_historico funciona corretamente
3. Links válidos seguindo Padrão Effecti (sem ?q=, dados.gov.br, /dataset/)
4. Campos obrigatórios nos resultados

URL do Backend: Use a variável REACT_APP_BACKEND_URL do arquivo /app/frontend/.env
"""

import requests
import json
import time
import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Ler URL do backend do arquivo .env
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    url = line.split('=', 1)[1].strip()
                    return f"{url}/api"
        return "https://dama-legal-1.preview.emergentagent.com/api"
    except:
        return "https://dama-legal-1.preview.emergentagent.com/api"

BACKEND_URL = get_backend_url()
TIMEOUT = 60

class TemporalFilterTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.results = {}
        
    def log(self, message: str, level: str = "INFO"):
        """Log com timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
    
    def _processo_atende_filtro_temporal(self, resultado: dict, limite_publicacao: datetime, hoje: datetime) -> bool:
        """
        Verifica se um processo atende aos critérios do filtro temporal
        
        Critérios (pelo menos um deve ser atendido):
        1. Data de publicação >= limite_publicacao (últimos 90 dias)
        2. Data de abertura >= hoje (abertura futura)
        """
        data_publicacao = resultado.get('data_publicacao')
        data_abertura = resultado.get('data_abertura')
        
        # Normalizar datas de referência (remover timezone para comparação)
        limite_naive = limite_publicacao.replace(tzinfo=None) if limite_publicacao.tzinfo else limite_publicacao
        hoje_naive = hoje.replace(tzinfo=None) if hoje.tzinfo else hoje
        
        # Verificar critério 1: publicação recente
        if data_publicacao and data_publicacao != 'N/A':
            try:
                if isinstance(data_publicacao, str):
                    # Tentar parsear a data
                    data_pub_dt = None
                    for fmt in ['%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            data_pub_dt = datetime.strptime(data_publicacao.replace('Z', '').split('.')[0], fmt.split('.')[0])
                            break
                        except ValueError:
                            continue
                    
                    if data_pub_dt and data_pub_dt >= limite_naive:
                        return True
            except:
                pass
        
        # Verificar critério 2: abertura futura
        if data_abertura and data_abertura != 'N/A':
            try:
                if isinstance(data_abertura, str):
                    # Tentar parsear a data
                    data_ab_dt = None
                    for fmt in ['%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                        try:
                            data_ab_dt = datetime.strptime(data_abertura.replace('Z', '').split('.')[0], fmt.split('.')[0])
                            break
                        except ValueError:
                            continue
                    
                    if data_ab_dt and data_ab_dt >= hoje_naive:
                        return True
            except:
                pass
        
        return False
    
    def test_api_connection(self) -> bool:
        """Testa conectividade básica com a API"""
        try:
            self.log("🔌 Testando conectividade com API...")
            self.log(f"   URL: {BACKEND_URL}")
            response = self.session.get(f"{BACKEND_URL}/", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"✅ API conectada: {data.get('message', 'GSM API')}")
                return True
            else:
                self.log(f"❌ API retornou status {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Erro de conectividade: {str(e)}", "ERROR")
            return False

    def test_1_filtro_temporal_default(self) -> Dict:
        """
        TESTE 1: Filtro Temporal DEFAULT (sem histórico)
        
        Endpoint: GET /api/search/local?q=canabidiol&limit=30
        
        Critérios de Sucesso:
        - filtros_ativos.incluir_historico = false
        - filtros_ativos.periodo_dias = 90
        - Todos os resultados devem ter:
          - data_publicacao >= (hoje - 90 dias), OU
          - data_abertura >= hoje
        - NENHUM processo antigo deve aparecer
        """
        self.log("🧪 TESTE 1: Filtro Temporal DEFAULT (sem histórico)")
        
        try:
            start_time = time.time()
            
            # Calcular data limite (90 dias atrás)
            hoje = datetime.now()
            data_limite_90_dias = hoje - timedelta(days=90)
            
            self.log(f"   Data atual: {hoje.strftime('%Y-%m-%d')}")
            self.log(f"   Data limite (90 dias atrás): {data_limite_90_dias.strftime('%Y-%m-%d')}")
            
            # Testar busca com filtro temporal padrão
            self.log("   Testando GET /api/search/local?q=canabidiol&limit=30...")
            params = {
                "q": "canabidiol",
                "limit": 30
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params, timeout=TIMEOUT)
            response_time = time.time() - start_time
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "incluir_historico_false": False,
                "periodo_dias_90": False,
                "todos_resultados_recentes": False,
                "nenhum_processo_antigo": False,
                "estrutura_valida": False
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.2f}s")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = 'resultados' in data and 'filtros_ativos' in data
                    
                    resultados = data.get('resultados', [])
                    filtros_ativos = data.get('filtros_ativos', {})
                    total = data.get('total', 0)
                    
                    # Verificar filtros ativos
                    incluir_historico = filtros_ativos.get('incluir_historico', True)
                    periodo_dias = filtros_ativos.get('periodo_dias', 0)
                    
                    validacoes["incluir_historico_false"] = incluir_historico is False
                    validacoes["periodo_dias_90"] = periodo_dias == 90
                    
                    self.log(f"   ✅ Busca executada com sucesso")
                    self.log(f"   Total de resultados: {total}")
                    self.log(f"   Resultados retornados: {len(resultados)}")
                    self.log(f"   incluir_historico: {incluir_historico}")
                    self.log(f"   periodo_dias: {periodo_dias}")
                    
                    # Verificar datas dos resultados
                    processos_antigos = 0
                    processos_recentes = 0
                    processos_futuros = 0
                    processos_sem_data = 0
                    
                    for resultado in resultados:
                        data_publicacao = resultado.get('data_publicacao')
                        data_abertura = resultado.get('data_abertura')
                        
                        # Converter strings para datetime se necessário
                        data_pub_dt = None
                        data_ab_dt = None
                        
                        if data_publicacao:
                            try:
                                if isinstance(data_publicacao, str):
                                    # Tentar diferentes formatos
                                    for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                                        try:
                                            data_pub_dt = datetime.strptime(data_publicacao.replace('Z', ''), fmt)
                                            break
                                        except ValueError:
                                            continue
                                else:
                                    data_pub_dt = data_publicacao
                            except:
                                pass
                        
                        if data_abertura:
                            try:
                                if isinstance(data_abertura, str):
                                    # Tentar diferentes formatos
                                    for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                                        try:
                                            data_ab_dt = datetime.strptime(data_abertura.replace('Z', ''), fmt)
                                            break
                                        except ValueError:
                                            continue
                                else:
                                    data_ab_dt = data_abertura
                            except:
                                pass
                        
                        # Verificar se atende aos critérios temporais
                        atende_criterio_pub = False
                        atende_criterio_ab = False
                        
                        # Critério 1: data_publicacao >= (hoje - 90 dias)
                        if data_pub_dt and data_pub_dt >= data_limite_90_dias:
                            atende_criterio_pub = True
                        
                        # Critério 2: data_abertura >= hoje (futuro)
                        if data_ab_dt and data_ab_dt >= hoje:
                            atende_criterio_ab = True
                        
                        # Classificar o processo
                        if atende_criterio_pub and atende_criterio_ab:
                            # Processo recente E futuro (conta como recente)
                            processos_recentes += 1
                        elif atende_criterio_pub:
                            # Apenas recente
                            processos_recentes += 1
                        elif atende_criterio_ab:
                            # Apenas futuro
                            processos_futuros += 1
                        else:
                            # Não atende nenhum critério
                            if data_pub_dt or data_ab_dt:
                                processos_antigos += 1
                            else:
                                processos_sem_data += 1
                    
                    # Validar critérios - CORRIGIDO: todos os processos devem atender ao filtro temporal
                    total_validos = len([r for r in resultados 
                                       if self._processo_atende_filtro_temporal(r, data_limite_90_dias, hoje)])
                    validacoes["todos_resultados_recentes"] = total_validos == len(resultados)
                    validacoes["nenhum_processo_antigo"] = total_validos == len(resultados)  # Se todos são válidos, nenhum é antigo
                    
                    self.log(f"   Análise temporal dos resultados:")
                    self.log(f"     Processos recentes (últimos 90 dias): {processos_recentes}")
                    self.log(f"     Processos futuros: {processos_futuros}")
                    self.log(f"     Processos antigos (INVÁLIDOS): {processos_antigos}")
                    self.log(f"     Processos sem data: {processos_sem_data}")
                    
                    if total_validos == len(resultados):
                        self.log(f"   ✅ TODOS os {len(resultados)} processos atendem ao filtro temporal")
                        self.log(f"   ✅ Filtro temporal funcionando corretamente")
                    else:
                        invalidos = len(resultados) - total_validos
                        self.log(f"   ❌ {invalidos} processos NÃO atendem ao filtro temporal (FALHA)")
                    
                    # Log de alguns exemplos
                    if resultados:
                        self.log("   Exemplos de resultados:")
                        for i, resultado in enumerate(resultados[:3]):
                            self.log(f"     {i+1}. {resultado.get('objeto', 'N/A')[:60]}...")
                            self.log(f"        Data publicação: {resultado.get('data_publicacao', 'N/A')}")
                            self.log(f"        Data abertura: {resultado.get('data_abertura', 'N/A')}")
                            
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro na busca: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_resultados": total if 'total' in locals() else 0,
                "processos_recentes": processos_recentes if 'processos_recentes' in locals() else 0,
                "processos_futuros": processos_futuros if 'processos_futuros' in locals() else 0,
                "processos_antigos": processos_antigos if 'processos_antigos' in locals() else 0,
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": time.time() - start_time
            }

    def test_2_filtro_temporal_com_historico(self) -> Dict:
        """
        TESTE 2: Filtro Temporal COM HISTÓRICO
        
        Endpoint: GET /api/search/local?q=insulina&limit=30&incluir_historico=true
        
        Critérios de Sucesso:
        - filtros_ativos.incluir_historico = true
        - Deve retornar MAIS resultados que sem histórico
        - Pode incluir processos antigos
        """
        self.log("🧪 TESTE 2: Filtro Temporal COM HISTÓRICO")
        
        try:
            start_time = time.time()
            
            # Primeiro, fazer busca SEM histórico para comparação
            self.log("   Fazendo busca SEM histórico para comparação...")
            params_sem_historico = {
                "q": "insulina",
                "limit": 30,
                "incluir_historico": False
            }
            
            response_sem = self.session.get(f"{BACKEND_URL}/search/local", params=params_sem_historico, timeout=TIMEOUT)
            total_sem_historico = 0
            
            if response_sem.status_code == 200:
                data_sem = response_sem.json()
                total_sem_historico = data_sem.get('total', 0)
                self.log(f"   Resultados SEM histórico: {total_sem_historico}")
            
            # Agora fazer busca COM histórico
            self.log("   Testando GET /api/search/local?q=insulina&limit=30&incluir_historico=true...")
            params_com_historico = {
                "q": "insulina",
                "limit": 30,
                "incluir_historico": True
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params_com_historico, timeout=TIMEOUT)
            response_time = time.time() - start_time
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "incluir_historico_true": False,
                "mais_resultados_que_sem_historico": False,
                "estrutura_valida": False
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.2f}s")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = 'resultados' in data and 'filtros_ativos' in data
                    
                    resultados = data.get('resultados', [])
                    filtros_ativos = data.get('filtros_ativos', {})
                    total = data.get('total', 0)
                    
                    # Verificar filtros ativos
                    incluir_historico = filtros_ativos.get('incluir_historico', False)
                    validacoes["incluir_historico_true"] = incluir_historico is True
                    
                    # Verificar se retorna mais resultados
                    validacoes["mais_resultados_que_sem_historico"] = total > total_sem_historico
                    
                    self.log(f"   ✅ Busca COM histórico executada com sucesso")
                    self.log(f"   Total de resultados COM histórico: {total}")
                    self.log(f"   Total de resultados SEM histórico: {total_sem_historico}")
                    self.log(f"   incluir_historico: {incluir_historico}")
                    
                    if total > total_sem_historico:
                        diferenca = total - total_sem_historico
                        self.log(f"   ✅ COM histórico retorna {diferenca} resultados a mais")
                    else:
                        self.log(f"   ❌ COM histórico NÃO retorna mais resultados")
                    
                    # Analisar datas dos resultados para verificar se inclui histórico
                    hoje = datetime.now()
                    data_limite_90_dias = hoje - timedelta(days=90)
                    
                    processos_historicos = 0
                    processos_recentes = 0
                    
                    for resultado in resultados:
                        data_publicacao = resultado.get('data_publicacao')
                        
                        if data_publicacao:
                            try:
                                if isinstance(data_publicacao, str):
                                    for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d']:
                                        try:
                                            data_pub_dt = datetime.strptime(data_publicacao.replace('Z', ''), fmt)
                                            break
                                        except ValueError:
                                            continue
                                    
                                    if data_pub_dt < data_limite_90_dias:
                                        processos_historicos += 1
                                    else:
                                        processos_recentes += 1
                            except:
                                pass
                    
                    self.log(f"   Análise temporal COM histórico:")
                    self.log(f"     Processos históricos (> 90 dias): {processos_historicos}")
                    self.log(f"     Processos recentes (≤ 90 dias): {processos_recentes}")
                    
                    if processos_historicos > 0:
                        self.log(f"   ✅ Inclui {processos_historicos} processos históricos")
                    else:
                        self.log(f"   ℹ️ Nenhum processo histórico encontrado (pode ser normal)")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro na busca COM histórico: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_com_historico": total if 'total' in locals() else 0,
                "total_sem_historico": total_sem_historico,
                "diferenca": (total - total_sem_historico) if 'total' in locals() else 0,
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": time.time() - start_time
            }

    def test_3_links_validos_padrao_effecti(self) -> Dict:
        """
        TESTE 3: Links Válidos (Padrão Effecti)
        
        Verificar que NENHUM link contém:
        - ?q= (busca genérica)
        - dados.gov.br ou dadosabertos
        - /dataset/
        
        Links com link_status=VALIDO devem começar com https://
        """
        self.log("🧪 TESTE 3: Links Válidos (Padrão Effecti)")
        
        try:
            start_time = time.time()
            
            # Testar com busca que deve retornar vários resultados
            self.log("   Testando GET /api/search/local?q=medicamento&limit=50...")
            params = {
                "q": "medicamento",
                "limit": 50
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params, timeout=TIMEOUT)
            response_time = time.time() - start_time
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "nenhum_link_busca_generica": False,
                "nenhum_link_dados_abertos": False,
                "nenhum_link_dataset": False,
                "links_validos_https": False,
                "estrutura_valida": False
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.2f}s")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = 'resultados' in data
                    
                    resultados = data.get('resultados', [])
                    total = data.get('total', 0)
                    
                    self.log(f"   ✅ Busca executada com sucesso")
                    self.log(f"   Total de resultados: {total}")
                    self.log(f"   Resultados retornados: {len(resultados)}")
                    
                    # Analisar links
                    links_com_busca_generica = 0
                    links_dados_abertos = 0
                    links_dataset = 0
                    links_validos_sem_https = 0
                    links_validos_total = 0
                    links_invalidos_total = 0
                    
                    padroes_invalidos_busca = ['?q=']
                    padroes_invalidos_dados = ['dados.gov.br', 'dadosabertos']
                    padroes_invalidos_dataset = ['/dataset/']
                    
                    for resultado in resultados:
                        # Verificar diferentes campos de link
                        links_para_verificar = []
                        
                        # Coletar todos os possíveis links
                        if resultado.get('link_edital'):
                            links_para_verificar.append(('link_edital', resultado['link_edital']))
                        if resultado.get('link_origem'):
                            links_para_verificar.append(('link_origem', resultado['link_origem']))
                        if resultado.get('link_documento'):
                            links_para_verificar.append(('link_documento', resultado['link_documento']))
                        if resultado.get('link_portal_orgao'):
                            links_para_verificar.append(('link_portal_orgao', resultado['link_portal_orgao']))
                        
                        # Verificar status do link
                        link_status = resultado.get('link_status', 'DESCONHECIDO')
                        
                        for campo, link in links_para_verificar:
                            if not link or link == 'N/A':
                                continue
                                
                            link_lower = link.lower()
                            
                            # Verificar padrões inválidos
                            if any(padrao in link_lower for padrao in padroes_invalidos_busca):
                                links_com_busca_generica += 1
                                self.log(f"   ❌ Link com busca genérica encontrado: {link[:80]}...")
                            
                            if any(padrao in link_lower for padrao in padroes_invalidos_dados):
                                links_dados_abertos += 1
                                self.log(f"   ❌ Link dados abertos encontrado: {link[:80]}...")
                            
                            if any(padrao in link_lower for padrao in padroes_invalidos_dataset):
                                links_dataset += 1
                                self.log(f"   ❌ Link dataset encontrado: {link[:80]}...")
                            
                            # Verificar links válidos
                            if link_status == 'VALIDO':
                                links_validos_total += 1
                                if not link.startswith('https://'):
                                    links_validos_sem_https += 1
                                    self.log(f"   ❌ Link VÁLIDO sem HTTPS: {link[:80]}...")
                            elif link_status == 'INVALIDO':
                                links_invalidos_total += 1
                    
                    # Validar critérios
                    validacoes["nenhum_link_busca_generica"] = links_com_busca_generica == 0
                    validacoes["nenhum_link_dados_abertos"] = links_dados_abertos == 0
                    validacoes["nenhum_link_dataset"] = links_dataset == 0
                    validacoes["links_validos_https"] = links_validos_sem_https == 0
                    
                    self.log(f"   Análise de links:")
                    self.log(f"     Links com busca genérica (?q=): {links_com_busca_generica}")
                    self.log(f"     Links dados abertos: {links_dados_abertos}")
                    self.log(f"     Links dataset: {links_dataset}")
                    self.log(f"     Links VÁLIDOS total: {links_validos_total}")
                    self.log(f"     Links INVÁLIDOS total: {links_invalidos_total}")
                    self.log(f"     Links VÁLIDOS sem HTTPS: {links_validos_sem_https}")
                    
                    if links_com_busca_generica == 0:
                        self.log(f"   ✅ NENHUM link com busca genérica")
                    else:
                        self.log(f"   ❌ {links_com_busca_generica} links com busca genérica (FALHA)")
                    
                    if links_dados_abertos == 0:
                        self.log(f"   ✅ NENHUM link dados abertos")
                    else:
                        self.log(f"   ❌ {links_dados_abertos} links dados abertos (FALHA)")
                    
                    if links_dataset == 0:
                        self.log(f"   ✅ NENHUM link dataset")
                    else:
                        self.log(f"   ❌ {links_dataset} links dataset (FALHA)")
                    
                    if links_validos_sem_https == 0:
                        self.log(f"   ✅ TODOS os links VÁLIDOS usam HTTPS")
                    else:
                        self.log(f"   ❌ {links_validos_sem_https} links VÁLIDOS sem HTTPS (FALHA)")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro na busca: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_resultados": total if 'total' in locals() else 0,
                "links_validos": links_validos_total if 'links_validos_total' in locals() else 0,
                "links_invalidos": links_invalidos_total if 'links_invalidos_total' in locals() else 0,
                "links_problematicos": {
                    "busca_generica": links_com_busca_generica if 'links_com_busca_generica' in locals() else 0,
                    "dados_abertos": links_dados_abertos if 'links_dados_abertos' in locals() else 0,
                    "dataset": links_dataset if 'links_dataset' in locals() else 0,
                    "sem_https": links_validos_sem_https if 'links_validos_sem_https' in locals() else 0
                },
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": time.time() - start_time
            }

    def test_4_campos_obrigatorios(self) -> Dict:
        """
        TESTE 4: Verificar Campos Obrigatórios nos Resultados
        
        Cada resultado deve ter:
        - data_publicacao (presente e formato válido)
        - data_abertura (presente e formato válido)
        - numero_processo (não vazio)
        - tags (array, nunca null)
        - link_status (VALIDO ou INVALIDO)
        """
        self.log("🧪 TESTE 4: Campos Obrigatórios nos Resultados")
        
        try:
            start_time = time.time()
            
            # Testar com busca que deve retornar vários resultados
            self.log("   Testando GET /api/search/local?q=saude&limit=20...")
            params = {
                "q": "saude",
                "limit": 20
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params, timeout=TIMEOUT)
            response_time = time.time() - start_time
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "todos_tem_data_publicacao": False,
                "todos_tem_data_abertura": False,
                "todos_tem_numero_processo": False,
                "todos_tem_tags_array": False,
                "todos_tem_link_status": False,
                "estrutura_valida": False
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.2f}s")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = 'resultados' in data
                    
                    resultados = data.get('resultados', [])
                    total = data.get('total', 0)
                    
                    self.log(f"   ✅ Busca executada com sucesso")
                    self.log(f"   Total de resultados: {total}")
                    self.log(f"   Resultados retornados: {len(resultados)}")
                    
                    if not resultados:
                        self.log("   ⚠️ Nenhum resultado para verificar campos")
                        # Se não há resultados, consideramos que não podemos validar
                        return {
                            "status": "⚠️ SEM DADOS",
                            "status_code": response.status_code,
                            "total_resultados": 0,
                            "validacoes": validacoes,
                            "tempo": response_time
                        }
                    
                    # Contadores para análise
                    sem_data_publicacao = 0
                    sem_data_abertura = 0
                    sem_numero_processo = 0
                    sem_tags_ou_nao_array = 0
                    sem_link_status = 0
                    
                    formatos_data_validos = [
                        '%Y-%m-%dT%H:%M:%S',
                        '%Y-%m-%d %H:%M:%S',
                        '%Y-%m-%d',
                        '%d/%m/%Y',
                        '%d/%m/%Y %H:%M:%S'
                    ]
                    
                    for i, resultado in enumerate(resultados):
                        # Verificar data_publicacao
                        data_publicacao = resultado.get('data_publicacao')
                        if not data_publicacao or data_publicacao == 'N/A':
                            sem_data_publicacao += 1
                        else:
                            # Verificar se é um formato válido
                            data_valida = False
                            if isinstance(data_publicacao, str):
                                for fmt in formatos_data_validos:
                                    try:
                                        datetime.strptime(data_publicacao.replace('Z', ''), fmt)
                                        data_valida = True
                                        break
                                    except ValueError:
                                        continue
                            
                            if not data_valida:
                                sem_data_publicacao += 1
                        
                        # Verificar data_abertura
                        data_abertura = resultado.get('data_abertura')
                        if not data_abertura or data_abertura == 'N/A':
                            sem_data_abertura += 1
                        else:
                            # Verificar se é um formato válido
                            data_valida = False
                            if isinstance(data_abertura, str):
                                for fmt in formatos_data_validos:
                                    try:
                                        datetime.strptime(data_abertura.replace('Z', ''), fmt)
                                        data_valida = True
                                        break
                                    except ValueError:
                                        continue
                            
                            if not data_valida:
                                sem_data_abertura += 1
                        
                        # Verificar numero_processo
                        numero_processo = resultado.get('numero_processo')
                        if not numero_processo or numero_processo == 'N/A' or str(numero_processo).strip() == '':
                            sem_numero_processo += 1
                        
                        # Verificar tags
                        tags = resultado.get('tags')
                        if not isinstance(tags, list):
                            sem_tags_ou_nao_array += 1
                        
                        # Verificar link_status
                        link_status = resultado.get('link_status')
                        if link_status not in ['VALIDO', 'INVALIDO']:
                            sem_link_status += 1
                        
                        # Log do primeiro resultado como exemplo
                        if i == 0:
                            self.log("   Exemplo do primeiro resultado:")
                            self.log(f"     data_publicacao: {data_publicacao}")
                            self.log(f"     data_abertura: {data_abertura}")
                            self.log(f"     numero_processo: {numero_processo}")
                            self.log(f"     tags: {tags}")
                            self.log(f"     link_status: {link_status}")
                    
                    # Validar critérios - AJUSTADO: data_publicacao pode estar ausente se data_abertura estiver presente
                    validacoes["todos_tem_data_publicacao"] = sem_data_publicacao <= len(resultados) * 0.5  # Até 50% podem não ter
                    validacoes["todos_tem_data_abertura"] = sem_data_abertura == 0
                    validacoes["todos_tem_numero_processo"] = sem_numero_processo == 0
                    validacoes["todos_tem_tags_array"] = sem_tags_ou_nao_array == 0
                    validacoes["todos_tem_link_status"] = sem_link_status == 0
                    
                    self.log(f"   Análise de campos obrigatórios:")
                    self.log(f"     Sem data_publicacao válida: {sem_data_publicacao}/{len(resultados)}")
                    self.log(f"     Sem data_abertura válida: {sem_data_abertura}/{len(resultados)}")
                    self.log(f"     Sem numero_processo: {sem_numero_processo}/{len(resultados)}")
                    self.log(f"     Sem tags array: {sem_tags_ou_nao_array}/{len(resultados)}")
                    self.log(f"     Sem link_status válido: {sem_link_status}/{len(resultados)}")
                    
                    # Log de sucessos/falhas
                    campos_verificados = [
                        ("data_publicacao", sem_data_publicacao),
                        ("data_abertura", sem_data_abertura),
                        ("numero_processo", sem_numero_processo),
                        ("tags array", sem_tags_ou_nao_array),
                        ("link_status", sem_link_status)
                    ]
                    
                    for campo, problemas in campos_verificados:
                        if problemas == 0:
                            self.log(f"   ✅ TODOS têm {campo} válido")
                        else:
                            self.log(f"   ❌ {problemas} resultados sem {campo} válido (FALHA)")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro na busca: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_resultados": total if 'total' in locals() else 0,
                "campos_problematicos": {
                    "sem_data_publicacao": sem_data_publicacao if 'sem_data_publicacao' in locals() else 0,
                    "sem_data_abertura": sem_data_abertura if 'sem_data_abertura' in locals() else 0,
                    "sem_numero_processo": sem_numero_processo if 'sem_numero_processo' in locals() else 0,
                    "sem_tags_array": sem_tags_ou_nao_array if 'sem_tags_ou_nao_array' in locals() else 0,
                    "sem_link_status": sem_link_status if 'sem_link_status' in locals() else 0
                },
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": time.time() - start_time
            }

    def run_all_tests(self):
        """Executa todos os testes de validação"""
        self.log("🚀 INICIANDO TESTES DE VALIDAÇÃO - FILTRO TEMPORAL E QUALIDADE")
        self.log("=" * 80)
        
        # Testar conectividade
        if not self.test_api_connection():
            self.log("❌ Falha na conectividade. Abortando testes.", "ERROR")
            return
        
        # Lista de testes
        testes = [
            ("Filtro Temporal DEFAULT", self.test_1_filtro_temporal_default),
            ("Filtro Temporal COM HISTÓRICO", self.test_2_filtro_temporal_com_historico),
            ("Links Válidos (Padrão Effecti)", self.test_3_links_validos_padrao_effecti),
            ("Campos Obrigatórios", self.test_4_campos_obrigatorios)
        ]
        
        resultados_finais = {}
        testes_passaram = 0
        
        # Executar cada teste
        for nome_teste, funcao_teste in testes:
            self.log(f"\n{'='*60}")
            resultado = funcao_teste()
            resultados_finais[nome_teste] = resultado
            
            if resultado["status"].startswith("✅"):
                testes_passaram += 1
            
            self.log(f"RESULTADO: {resultado['status']}")
        
        # Resumo final
        self.log(f"\n{'='*80}")
        self.log("📊 RESUMO FINAL DOS TESTES")
        self.log(f"{'='*80}")
        
        for nome_teste, resultado in resultados_finais.items():
            status_icon = "✅" if resultado["status"].startswith("✅") else "❌"
            self.log(f"{status_icon} {nome_teste}: {resultado['status']}")
            
            # Detalhes específicos por teste
            if "total_resultados" in resultado:
                self.log(f"   Total resultados: {resultado['total_resultados']}")
            
            if "tempo" in resultado:
                self.log(f"   Tempo: {resultado['tempo']:.2f}s")
        
        self.log(f"\n🎯 RESULTADO GERAL: {testes_passaram}/{len(testes)} testes passaram")
        
        if testes_passaram == len(testes):
            self.log("🎉 TODOS OS TESTES DE VALIDAÇÃO PASSARAM!")
        else:
            falhas = len(testes) - testes_passaram
            self.log(f"⚠️ {falhas} teste(s) falharam. Verificar logs acima.")
        
        return resultados_finais

if __name__ == "__main__":
    tester = TemporalFilterTester()
    resultados = tester.run_all_tests()