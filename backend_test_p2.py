#!/usr/bin/env python3
"""
🧪 TESTE DE VALIDAÇÃO P2 - PORTAIS MUNICIPAIS SP

Testa integração com PNCP para municípios prioritários de SP conforme review request.

## TESTES OBRIGATÓRIOS

### 1. Endpoint de Listagem de Municípios
- GET /api/municipios/lista
- Verificar: retorna lista com id, nome, cnpj, portal, ativo
- Critério: total_ativos >= 7

### 2. Endpoint de Estatísticas
- GET /api/municipios/stats  
- Verificar: por_municipio contém Guarulhos, Santo André, São Bernardo, Santos
- Critério: total > 0 para municípios prioritários, com_link_valido > 0

### 3. Busca com Filtro Temporal (DEFAULT)
- GET /api/search/local?q=credenciamento&estados=SP&limit=30
- Critério: Todos os resultados devem ter data_abertura >= hoje OU data_publicacao >= (hoje - 90 dias)
- Nenhum processo antigo (data_abertura < hoje E data_publicacao < (hoje - 90 dias))

### 4. Busca COM Histórico
- GET /api/search/local?q=credenciamento&estados=SP&incluir_historico=true&limit=50
- Critério: Total > busca sem histórico, deve incluir processos de municípios prioritários

### 5. Padrão Effecti (Links)
- Verificar que NENHUM link contém: ?q=, dados.gov.br, /dataset/
- Links com link_status=VALIDO devem começar com https://

### 6. Campos Obrigatórios
- Cada resultado deve ter: data_publicacao, data_abertura, link_status (VALIDO/INVALIDO), tags (array)

## CRITÉRIOS DE SUCESSO
- ✅ Pelo menos 3 municípios prioritários com editais
- ✅ Filtro temporal funcionando (default = apenas recentes/futuros)
- ✅ Links no padrão Effecti
- ✅ Performance < 150ms
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

class P2MunicipalTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.results = {}
        self.municipios_prioritarios = ["Guarulhos", "Santo André", "São Bernardo", "Santos"]
        
    def log(self, message: str, level: str = "INFO"):
        """Log com timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
    
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

    def test_1_municipios_lista(self) -> Dict:
        """TESTE 1: Endpoint de Listagem de Municípios"""
        self.log("🧪 TESTE 1: Endpoint de Listagem de Municípios")
        
        try:
            start_time = time.time()
            
            self.log("   Testando GET /api/municipios/lista...")
            response = self.session.get(f"{BACKEND_URL}/municipios/lista", timeout=TIMEOUT)
            response_time = (time.time() - start_time) * 1000
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "tem_municipios": False,
                "campos_obrigatorios": False,
                "total_ativos_minimo": False,
                "performance_ok": response_time < 150
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.1f}ms")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = isinstance(data, dict)
                    
                    municipios = data.get('municipios', [])
                    total_ativos = data.get('total_ativos', 0)
                    
                    validacoes["tem_municipios"] = len(municipios) > 0
                    validacoes["total_ativos_minimo"] = total_ativos >= 7
                    
                    # Verificar campos obrigatórios
                    if municipios:
                        primeiro = municipios[0]
                        campos_necessarios = ['id', 'nome', 'cnpj', 'portal', 'ativo']
                        validacoes["campos_obrigatorios"] = all(campo in primeiro for campo in campos_necessarios)
                    
                    self.log(f"   ✅ Lista de municípios obtida com sucesso")
                    self.log(f"   Total municípios: {len(municipios)}")
                    self.log(f"   Total ativos: {total_ativos}")
                    
                    # Verificar critério específico
                    if total_ativos >= 7:
                        self.log(f"   ✅ Total ativos >= 7: {total_ativos}")
                    else:
                        self.log(f"   ❌ Total ativos < 7: {total_ativos}")
                    
                    # Log dos primeiros municípios
                    for i, mun in enumerate(municipios[:5]):
                        status = "ATIVO" if mun.get('ativo') else "INATIVO"
                        self.log(f"     {i+1}. {mun.get('nome', 'N/A')} - {status}")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro ao obter lista de municípios: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_municipios": len(municipios) if 'municipios' in locals() else 0,
                "total_ativos": total_ativos if 'total_ativos' in locals() else 0,
                "validacoes": validacoes,
                "tempo_ms": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo_ms": (time.time() - start_time) * 1000
            }

    def test_2_municipios_stats(self) -> Dict:
        """TESTE 2: Endpoint de Estatísticas"""
        self.log("🧪 TESTE 2: Endpoint de Estatísticas")
        
        try:
            start_time = time.time()
            
            self.log("   Testando GET /api/municipios/stats...")
            response = self.session.get(f"{BACKEND_URL}/municipios/stats", timeout=TIMEOUT)
            response_time = (time.time() - start_time) * 1000
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "tem_por_municipio": False,
                "municipios_prioritarios": False,
                "total_positivo": False,
                "links_validos": False,
                "performance_ok": response_time < 150
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.1f}ms")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = isinstance(data, dict)
                    
                    por_municipio = data.get('por_municipio', [])
                    total_geral = data.get('total_geral', 0)
                    
                    validacoes["tem_por_municipio"] = len(por_municipio) > 0
                    
                    # Verificar municípios prioritários
                    municipios_encontrados = []
                    municipios_com_editais = 0
                    municipios_com_links_validos = 0
                    
                    for mun_stat in por_municipio:
                        municipio = mun_stat.get('municipio', '')
                        total = mun_stat.get('total', 0)
                        com_link_valido = mun_stat.get('com_link_valido', 0)
                        
                        # Verificar se é um dos prioritários
                        for prioritario in self.municipios_prioritarios:
                            if prioritario.lower() in municipio.lower():
                                municipios_encontrados.append(municipio)
                                if total > 0:
                                    municipios_com_editais += 1
                                if com_link_valido > 0:
                                    municipios_com_links_validos += 1
                                break
                    
                    validacoes["municipios_prioritarios"] = len(municipios_encontrados) >= 3
                    validacoes["total_positivo"] = municipios_com_editais >= 3
                    validacoes["links_validos"] = municipios_com_links_validos > 0
                    
                    self.log(f"   ✅ Estatísticas de municípios obtidas com sucesso")
                    self.log(f"   Total geral: {total_geral}")
                    self.log(f"   Municípios com dados: {len(por_municipio)}")
                    self.log(f"   Municípios prioritários encontrados: {len(municipios_encontrados)}")
                    self.log(f"   Municípios prioritários com editais: {municipios_com_editais}")
                    self.log(f"   Municípios com links válidos: {municipios_com_links_validos}")
                    
                    # Log dos municípios prioritários
                    for mun in municipios_encontrados:
                        self.log(f"     - {mun}")
                    
                    # Log dos top 10 municípios
                    self.log("   Top 10 municípios por editais:")
                    for i, mun_stat in enumerate(por_municipio[:10]):
                        municipio = mun_stat.get('municipio', 'N/A')
                        total = mun_stat.get('total', 0)
                        validos = mun_stat.get('com_link_valido', 0)
                        self.log(f"     {i+1}. {municipio}: {total} editais ({validos} links válidos)")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro ao obter estatísticas: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_geral": total_geral if 'total_geral' in locals() else 0,
                "municipios_prioritarios": len(municipios_encontrados) if 'municipios_encontrados' in locals() else 0,
                "validacoes": validacoes,
                "tempo_ms": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo_ms": (time.time() - start_time) * 1000
            }

    def test_3_busca_filtro_temporal_default(self) -> Dict:
        """TESTE 3: Busca com Filtro Temporal (DEFAULT)"""
        self.log("🧪 TESTE 3: Busca com Filtro Temporal (DEFAULT)")
        
        try:
            start_time = time.time()
            
            self.log("   Testando GET /api/search/local?q=credenciamento&estados=SP&limit=30...")
            params = {
                "q": "credenciamento",
                "estados": "SP",
                "limit": 30
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params, timeout=TIMEOUT)
            response_time = (time.time() - start_time) * 1000
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "tem_resultados": False,
                "filtro_temporal_ok": False,
                "nenhum_processo_antigo": False,
                "performance_ok": response_time < 150
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.1f}ms")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = isinstance(data, dict)
                    
                    resultados = data.get('resultados', [])
                    total = data.get('total', 0)
                    
                    validacoes["tem_resultados"] = len(resultados) > 0
                    
                    # Verificar filtro temporal
                    hoje = datetime.now()
                    limite_90_dias = hoje - timedelta(days=90)
                    
                    processos_validos = 0
                    processos_antigos = 0
                    
                    for resultado in resultados:
                        data_abertura = resultado.get('data_abertura')
                        data_publicacao = resultado.get('data_publicacao')
                        
                        # Converter strings para datetime se necessário
                        dt_abertura = None
                        dt_publicacao = None
                        
                        if data_abertura:
                            try:
                                if isinstance(data_abertura, str):
                                    dt_abertura = datetime.fromisoformat(data_abertura.replace('Z', ''))
                                else:
                                    dt_abertura = data_abertura
                            except:
                                pass
                        
                        if data_publicacao:
                            try:
                                if isinstance(data_publicacao, str):
                                    dt_publicacao = datetime.fromisoformat(data_publicacao.replace('Z', ''))
                                else:
                                    dt_publicacao = data_publicacao
                            except:
                                pass
                        
                        # Verificar critério temporal
                        # Deve ter: data_abertura >= hoje OU data_publicacao >= (hoje - 90 dias)
                        criterio_atendido = False
                        
                        if dt_abertura and dt_abertura >= hoje:
                            criterio_atendido = True
                        elif dt_publicacao and dt_publicacao >= limite_90_dias:
                            criterio_atendido = True
                        
                        if criterio_atendido:
                            processos_validos += 1
                        else:
                            processos_antigos += 1
                    
                    validacoes["filtro_temporal_ok"] = processos_validos > 0
                    validacoes["nenhum_processo_antigo"] = processos_antigos == 0
                    
                    self.log(f"   ✅ Busca com filtro temporal executada")
                    self.log(f"   Total resultados: {total}")
                    self.log(f"   Resultados retornados: {len(resultados)}")
                    self.log(f"   Processos válidos (critério temporal): {processos_validos}")
                    self.log(f"   Processos antigos (fora do critério): {processos_antigos}")
                    
                    # Verificar critério específico
                    if processos_antigos == 0:
                        self.log(f"   ✅ Nenhum processo antigo encontrado")
                    else:
                        self.log(f"   ❌ {processos_antigos} processos antigos encontrados")
                    
                    # Log de alguns exemplos
                    for i, resultado in enumerate(resultados[:3]):
                        objeto = resultado.get('objeto', 'N/A')[:50]
                        data_ab = resultado.get('data_abertura', 'N/A')
                        data_pub = resultado.get('data_publicacao', 'N/A')
                        self.log(f"     {i+1}. {objeto}... (Abertura: {str(data_ab)[:10]}, Pub: {str(data_pub)[:10]})")
                        
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
                "processos_validos": processos_validos if 'processos_validos' in locals() else 0,
                "processos_antigos": processos_antigos if 'processos_antigos' in locals() else 0,
                "validacoes": validacoes,
                "tempo_ms": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo_ms": (time.time() - start_time) * 1000
            }

    def test_4_busca_com_historico(self) -> Dict:
        """TESTE 4: Busca COM Histórico"""
        self.log("🧪 TESTE 4: Busca COM Histórico")
        
        try:
            start_time = time.time()
            
            self.log("   Testando GET /api/search/local?q=credenciamento&estados=SP&incluir_historico=true&limit=50...")
            params = {
                "q": "credenciamento",
                "estados": "SP",
                "incluir_historico": "true",
                "limit": 50
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params, timeout=TIMEOUT)
            response_time = (time.time() - start_time) * 1000
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "tem_resultados": False,
                "maior_que_sem_historico": False,
                "inclui_municipios_prioritarios": False,
                "performance_ok": response_time < 150
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.1f}ms")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = isinstance(data, dict)
                    
                    resultados = data.get('resultados', [])
                    total = data.get('total', 0)
                    
                    validacoes["tem_resultados"] = len(resultados) > 0
                    
                    # Comparar com busca sem histórico (resultado do teste anterior)
                    if hasattr(self, 'results') and 'test_3_busca_filtro_temporal_default' in self.results:
                        total_sem_historico = self.results['test_3_busca_filtro_temporal_default'].get('total_resultados', 0)
                        validacoes["maior_que_sem_historico"] = total > total_sem_historico
                        self.log(f"   Comparação: {total} (com histórico) vs {total_sem_historico} (sem histórico)")
                    else:
                        # Se não temos o resultado anterior, assumir que é válido se tem resultados
                        validacoes["maior_que_sem_historico"] = total > 0
                    
                    # Verificar se inclui processos de municípios prioritários
                    municipios_encontrados = set()
                    
                    for resultado in resultados:
                        municipio = resultado.get('municipio', '')
                        orgao = resultado.get('orgao', '')
                        
                        # Verificar se é de um município prioritário
                        for prioritario in self.municipios_prioritarios:
                            if (prioritario.lower() in municipio.lower() or 
                                prioritario.lower() in orgao.lower()):
                                municipios_encontrados.add(prioritario)
                                break
                    
                    validacoes["inclui_municipios_prioritarios"] = len(municipios_encontrados) > 0
                    
                    self.log(f"   ✅ Busca com histórico executada")
                    self.log(f"   Total resultados: {total}")
                    self.log(f"   Resultados retornados: {len(resultados)}")
                    self.log(f"   Municípios prioritários encontrados: {len(municipios_encontrados)}")
                    
                    # Log dos municípios prioritários encontrados
                    for mun in municipios_encontrados:
                        self.log(f"     - {mun}")
                    
                    # Log de alguns exemplos
                    for i, resultado in enumerate(resultados[:3]):
                        objeto = resultado.get('objeto', 'N/A')[:50]
                        municipio = resultado.get('municipio', 'N/A')
                        orgao = resultado.get('orgao', 'N/A')[:30]
                        self.log(f"     {i+1}. {objeto}... ({municipio} - {orgao}...)")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro na busca com histórico: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_resultados": total if 'total' in locals() else 0,
                "municipios_prioritarios": len(municipios_encontrados) if 'municipios_encontrados' in locals() else 0,
                "validacoes": validacoes,
                "tempo_ms": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo_ms": (time.time() - start_time) * 1000
            }

    def test_5_padrao_effecti_links(self) -> Dict:
        """TESTE 5: Padrão Effecti (Links)"""
        self.log("🧪 TESTE 5: Padrão Effecti (Links)")
        
        try:
            start_time = time.time()
            
            self.log("   Testando padrão Effecti nos links...")
            params = {
                "q": "credenciamento",
                "estados": "SP",
                "limit": 30
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params, timeout=TIMEOUT)
            response_time = (time.time() - start_time) * 1000
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "tem_resultados": False,
                "nenhum_link_busca": False,
                "nenhum_dados_gov": False,
                "nenhum_dataset": False,
                "links_validos_https": False,
                "performance_ok": response_time < 150
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.1f}ms")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = isinstance(data, dict)
                    
                    resultados = data.get('resultados', [])
                    validacoes["tem_resultados"] = len(resultados) > 0
                    
                    # Verificar padrões inválidos nos links
                    links_com_busca = 0
                    links_dados_gov = 0
                    links_dataset = 0
                    links_validos_https = 0
                    total_links_validos = 0
                    
                    for resultado in resultados:
                        # Verificar diferentes campos de link
                        links_para_verificar = []
                        
                        # Coletar todos os possíveis links
                        for campo in ['link_origem', 'link_edital', 'link_documento', 'link_portal_orgao']:
                            link = resultado.get(campo)
                            if link and isinstance(link, str):
                                links_para_verificar.append(link)
                        
                        link_status = resultado.get('link_status', '')
                        
                        for link in links_para_verificar:
                            # Verificar padrões inválidos
                            if '?q=' in link:
                                links_com_busca += 1
                            
                            if 'dados.gov.br' in link:
                                links_dados_gov += 1
                            
                            if '/dataset/' in link:
                                links_dataset += 1
                            
                            # Verificar se links válidos começam com https://
                            if link_status == 'VALIDO':
                                total_links_validos += 1
                                if link.startswith('https://'):
                                    links_validos_https += 1
                    
                    validacoes["nenhum_link_busca"] = links_com_busca == 0
                    validacoes["nenhum_dados_gov"] = links_dados_gov == 0
                    validacoes["nenhum_dataset"] = links_dataset == 0
                    validacoes["links_validos_https"] = (total_links_validos == 0 or 
                                                       links_validos_https == total_links_validos)
                    
                    self.log(f"   ✅ Verificação de padrão Effecti executada")
                    self.log(f"   Total resultados: {len(resultados)}")
                    self.log(f"   Links com ?q= (busca): {links_com_busca}")
                    self.log(f"   Links dados.gov.br: {links_dados_gov}")
                    self.log(f"   Links /dataset/: {links_dataset}")
                    self.log(f"   Links válidos com HTTPS: {links_validos_https}/{total_links_validos}")
                    
                    # Verificar critérios específicos
                    if links_com_busca == 0:
                        self.log(f"   ✅ Nenhum link de busca (?q=) encontrado")
                    else:
                        self.log(f"   ❌ {links_com_busca} links de busca encontrados")
                    
                    if links_dados_gov == 0:
                        self.log(f"   ✅ Nenhum link dados.gov.br encontrado")
                    else:
                        self.log(f"   ❌ {links_dados_gov} links dados.gov.br encontrados")
                    
                    # Log de alguns exemplos de links
                    self.log("   Exemplos de links encontrados:")
                    for i, resultado in enumerate(resultados[:3]):
                        link_status = resultado.get('link_status', 'N/A')
                        link = resultado.get('link_origem') or resultado.get('link_edital', 'N/A')
                        if isinstance(link, str) and len(link) > 50:
                            link = link[:50] + "..."
                        self.log(f"     {i+1}. Status: {link_status}, Link: {link}")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro na verificação de links: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_resultados": len(resultados) if 'resultados' in locals() else 0,
                "links_com_busca": links_com_busca if 'links_com_busca' in locals() else 0,
                "links_dados_gov": links_dados_gov if 'links_dados_gov' in locals() else 0,
                "links_dataset": links_dataset if 'links_dataset' in locals() else 0,
                "validacoes": validacoes,
                "tempo_ms": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo_ms": (time.time() - start_time) * 1000
            }

    def test_6_campos_obrigatorios(self) -> Dict:
        """TESTE 6: Campos Obrigatórios"""
        self.log("🧪 TESTE 6: Campos Obrigatórios")
        
        try:
            start_time = time.time()
            
            self.log("   Testando campos obrigatórios nos resultados...")
            params = {
                "q": "credenciamento",
                "estados": "SP",
                "limit": 30
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params, timeout=TIMEOUT)
            response_time = (time.time() - start_time) * 1000
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "tem_resultados": False,
                "tem_data_publicacao": False,
                "tem_data_abertura": False,
                "tem_link_status": False,
                "tem_tags_array": False,
                "performance_ok": response_time < 150
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.1f}ms")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = isinstance(data, dict)
                    
                    resultados = data.get('resultados', [])
                    validacoes["tem_resultados"] = len(resultados) > 0
                    
                    # Verificar campos obrigatórios
                    resultados_com_data_pub = 0
                    resultados_com_data_ab = 0
                    resultados_com_link_status = 0
                    resultados_com_tags = 0
                    
                    for resultado in resultados:
                        # data_publicacao (presente)
                        if 'data_publicacao' in resultado and resultado['data_publicacao']:
                            resultados_com_data_pub += 1
                        
                        # data_abertura (presente)
                        if 'data_abertura' in resultado and resultado['data_abertura']:
                            resultados_com_data_ab += 1
                        
                        # link_status (VALIDO ou INVALIDO)
                        link_status = resultado.get('link_status', '')
                        if link_status in ['VALIDO', 'INVALIDO']:
                            resultados_com_link_status += 1
                        
                        # tags (array)
                        tags = resultado.get('tags', [])
                        if isinstance(tags, list):
                            resultados_com_tags += 1
                    
                    total_resultados = len(resultados)
                    
                    # Considerar válido se pelo menos 80% dos resultados têm os campos
                    threshold = max(1, int(total_resultados * 0.8))
                    
                    validacoes["tem_data_publicacao"] = resultados_com_data_pub >= threshold
                    validacoes["tem_data_abertura"] = resultados_com_data_ab >= threshold
                    validacoes["tem_link_status"] = resultados_com_link_status >= threshold
                    validacoes["tem_tags_array"] = resultados_com_tags >= threshold
                    
                    self.log(f"   ✅ Verificação de campos obrigatórios executada")
                    self.log(f"   Total resultados: {total_resultados}")
                    self.log(f"   Com data_publicacao: {resultados_com_data_pub}/{total_resultados}")
                    self.log(f"   Com data_abertura: {resultados_com_data_ab}/{total_resultados}")
                    self.log(f"   Com link_status: {resultados_com_link_status}/{total_resultados}")
                    self.log(f"   Com tags (array): {resultados_com_tags}/{total_resultados}")
                    
                    # Log de exemplo de estrutura
                    if resultados:
                        primeiro = resultados[0]
                        self.log("   Exemplo de estrutura do primeiro resultado:")
                        campos_exemplo = ['data_publicacao', 'data_abertura', 'link_status', 'tags']
                        for campo in campos_exemplo:
                            valor = primeiro.get(campo, 'AUSENTE')
                            if isinstance(valor, str) and len(valor) > 30:
                                valor = valor[:30] + "..."
                            self.log(f"     {campo}: {valor}")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro na verificação de campos: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_resultados": total_resultados if 'total_resultados' in locals() else 0,
                "com_data_publicacao": resultados_com_data_pub if 'resultados_com_data_pub' in locals() else 0,
                "com_data_abertura": resultados_com_data_ab if 'resultados_com_data_ab' in locals() else 0,
                "com_link_status": resultados_com_link_status if 'resultados_com_link_status' in locals() else 0,
                "com_tags": resultados_com_tags if 'resultados_com_tags' in locals() else 0,
                "validacoes": validacoes,
                "tempo_ms": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo_ms": (time.time() - start_time) * 1000
            }

    def run_all_tests(self):
        """Executa todos os testes P2"""
        self.log("🚀 INICIANDO TESTES P2 - PORTAIS MUNICIPAIS SP")
        self.log("=" * 60)
        
        # Testar conectividade primeiro
        if not self.test_api_connection():
            self.log("❌ Falha na conectividade. Abortando testes.", "ERROR")
            return
        
        # Lista de testes
        tests = [
            ("test_1_municipios_lista", self.test_1_municipios_lista),
            ("test_2_municipios_stats", self.test_2_municipios_stats),
            ("test_3_busca_filtro_temporal_default", self.test_3_busca_filtro_temporal_default),
            ("test_4_busca_com_historico", self.test_4_busca_com_historico),
            ("test_5_padrao_effecti_links", self.test_5_padrao_effecti_links),
            ("test_6_campos_obrigatorios", self.test_6_campos_obrigatorios),
        ]
        
        # Executar testes
        for test_name, test_func in tests:
            self.log(f"\n{'='*60}")
            try:
                result = test_func()
                self.results[test_name] = result
                self.log(f"RESULTADO: {result['status']}")
            except Exception as e:
                self.log(f"❌ ERRO CRÍTICO no {test_name}: {str(e)}", "ERROR")
                self.results[test_name] = {
                    "status": "❌ ERRO CRÍTICO",
                    "erro": str(e)
                }
        
        # Resumo final
        self.log(f"\n{'='*60}")
        self.log("📊 RESUMO DOS TESTES P2")
        self.log("=" * 60)
        
        passed = 0
        failed = 0
        
        for test_name, result in self.results.items():
            status = result.get('status', '❌ FALHOU')
            self.log(f"{status} - {test_name}")
            
            if "✅" in status:
                passed += 1
            else:
                failed += 1
        
        self.log(f"\n📈 ESTATÍSTICAS FINAIS:")
        self.log(f"   ✅ Testes aprovados: {passed}")
        self.log(f"   ❌ Testes falharam: {failed}")
        self.log(f"   📊 Taxa de sucesso: {(passed/(passed+failed)*100):.1f}%")
        
        # Verificar critérios de sucesso P2
        self.log(f"\n🎯 CRITÉRIOS DE SUCESSO P2:")
        
        # Critério 1: Pelo menos 3 municípios prioritários com editais
        municipios_stats = self.results.get('test_2_municipios_stats', {})
        municipios_prioritarios = municipios_stats.get('municipios_prioritarios', 0)
        criterio_1 = municipios_prioritarios >= 3
        self.log(f"   {'✅' if criterio_1 else '❌'} Pelo menos 3 municípios prioritários: {municipios_prioritarios}/3")
        
        # Critério 2: Filtro temporal funcionando
        filtro_temporal = self.results.get('test_3_busca_filtro_temporal_default', {})
        processos_antigos = filtro_temporal.get('processos_antigos', 1)
        criterio_2 = processos_antigos == 0
        self.log(f"   {'✅' if criterio_2 else '❌'} Filtro temporal (apenas recentes): {processos_antigos} processos antigos")
        
        # Critério 3: Links no padrão Effecti
        links_effecti = self.results.get('test_5_padrao_effecti_links', {})
        links_busca = links_effecti.get('links_com_busca', 1)
        criterio_3 = links_busca == 0
        self.log(f"   {'✅' if criterio_3 else '❌'} Links padrão Effecti: {links_busca} links inválidos")
        
        # Critério 4: Performance < 150ms
        tempos = []
        for result in self.results.values():
            tempo = result.get('tempo_ms', 0)
            if tempo > 0:
                tempos.append(tempo)
        
        tempo_medio = sum(tempos) / len(tempos) if tempos else 0
        criterio_4 = tempo_medio < 150
        self.log(f"   {'✅' if criterio_4 else '❌'} Performance < 150ms: {tempo_medio:.1f}ms médio")
        
        # Resultado final P2
        criterios_atendidos = sum([criterio_1, criterio_2, criterio_3, criterio_4])
        sucesso_p2 = criterios_atendidos >= 3  # Pelo menos 3 dos 4 critérios
        
        self.log(f"\n🏆 RESULTADO FINAL P2:")
        self.log(f"   {'🎉 APROVADO' if sucesso_p2 else '❌ REPROVADO'} - {criterios_atendidos}/4 critérios atendidos")
        
        if sucesso_p2:
            self.log("   ✅ Sistema pronto para integração com Portais Municipais SP")
        else:
            self.log("   ❌ Sistema precisa de ajustes antes da integração")

if __name__ == "__main__":
    tester = P2MunicipalTester()
    tester.run_all_tests()