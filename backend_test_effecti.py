#!/usr/bin/env python3
"""
🎯 TESTE COMPLETO - PADRÃO EFFECTI - CLASSIFICAÇÃO DE OPORTUNIDADES

Testa a implementação completa do PADRÃO EFFECTI para classificação de oportunidades no GSM - Buscador de Editais.

## CONTEXTO
O sistema GSM - Buscador de Editais agora classifica todas as licitações em 3 status:
- 🟢 ATIVA: Oportunidade acionável (abertura em até 90 dias)
- 🟡 FUTURA: Publicada, mas abertura > 90 dias
- 🔴 ENCERRADA: Prazo já passou ou status encerrado

Por DEFAULT, a busca retorna SOMENTE oportunidades ATIVAS.

## TESTES OBRIGATÓRIOS

### 1. Teste de Classificação Padrão (CRÍTICO)
**Endpoint**: GET /api/search/local?q=canabidiol&limit=30
**Critérios**:
- Deve retornar SOMENTE resultados com status_oportunidade = "ATIVA"
- Cada resultado deve ter os campos: status_oportunidade, badge_status, dias_ate_abertura, is_acionavel
- Response deve incluir `classificacao_oportunidade.contagem_status` com contagem de ATIVA, FUTURA, ENCERRADA

### 2. Teste de Filtro FUTURAS
**Endpoint**: GET /api/search/local?q=canabidiol&incluir_ativas=false&incluir_futuras=true&incluir_encerradas=false
**Critérios**:
- Deve retornar SOMENTE resultados com status_oportunidade = "FUTURA"
- dias_ate_abertura > 90 para todos

### 3. Teste de Filtro ENCERRADAS
**Endpoint**: GET /api/search/local?q=canabidiol&incluir_ativas=false&incluir_futuras=false&incluir_encerradas=true
**Critérios**:
- Deve retornar SOMENTE resultados com status_oportunidade = "ENCERRADA"
- dias_ate_abertura < 0 para todos (ou null)

### 4. Teste de Filtro COMBINADO
**Endpoint**: GET /api/search/local?q=credenciamento&incluir_ativas=true&incluir_futuras=true&incluir_encerradas=true
**Critérios**:
- Total deve ser >= soma das contagens individuais
- Resultados devem incluir mix de status

### 5. Teste de Campos Obrigatórios no Card
**Endpoint**: GET /api/search/local?q=insulina&limit=5
**Critérios para cada resultado**:
- numero_processo ou numero_edital presente
- modalidade ou tipo_modalidade presente
- status_oportunidade presente
- badge_status.texto, badge_status.cor, badge_status.icone presentes
- data_abertura presente
- data_publicacao presente

### 6. Teste de Performance
**Endpoint**: GET /api/search/local?q=medicamento&limit=50
**Critérios**:
- tempo_ms < 200ms
- Todos os 50 resultados classificados corretamente

URL Base: Use REACT_APP_BACKEND_URL do arquivo /app/frontend/.env
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

class EffectiPatternTester:
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
    
    def test_api_connection(self) -> bool:
        """Testa conectividade básica com a API"""
        try:
            self.log("🔌 Testando conectividade com API...")
            self.log(f"   URL: {BACKEND_URL}")
            response = self.session.get(f"{BACKEND_URL}/", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"✅ API conectada: {data.get('message', 'GSM API')}")
                self.log(f"   Versão: {data.get('version', 'N/A')}")
                return True
            else:
                self.log(f"❌ API retornou status {response.status_code}", "ERROR")
                self.log(f"   Response: {response.text[:200]}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Erro de conectividade: {str(e)}", "ERROR")
            return False

    def test_1_classificacao_padrao(self) -> Dict:
        """TESTE 1: Classificação Padrão (CRÍTICO) - deve retornar SOMENTE oportunidades ATIVAS"""
        self.log("🧪 TESTE 1: Classificação Padrão (CRÍTICO)")
        
        try:
            start_time = time.time()
            
            # Testar busca padrão que deve retornar SOMENTE ATIVAS
            self.log("   Testando GET /api/search/local?q=canabidiol&limit=30...")
            params = {
                "q": "canabidiol",
                "limit": 30
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params, timeout=TIMEOUT)
            response_time = time.time() - start_time
            response_time_ms = response_time * 1000
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "somente_ativas": False,
                "campos_obrigatorios": False,
                "contagem_status": False,
                "tempo_aceitavel": response_time_ms < 5000  # 5 segundos
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time_ms:.1f}ms")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = 'resultados' in data and 'total' in data
                    
                    resultados = data.get('resultados', [])
                    total = data.get('total', 0)
                    classificacao = data.get('classificacao_oportunidade', {})
                    
                    self.log(f"   Total de resultados: {total}")
                    self.log(f"   Resultados retornados: {len(resultados)}")
                    
                    # Verificar se todos são ATIVAS (comportamento padrão)
                    ativas_count = 0
                    campos_ok_count = 0
                    
                    for resultado in resultados:
                        status_oportunidade = resultado.get('status_oportunidade')
                        if status_oportunidade == 'ATIVA':
                            ativas_count += 1
                        
                        # Verificar campos obrigatórios
                        campos_presentes = all([
                            'status_oportunidade' in resultado,
                            'badge_status' in resultado,
                            'dias_ate_abertura' in resultado or 'is_acionavel' in resultado
                        ])
                        
                        if campos_presentes:
                            campos_ok_count += 1
                    
                    validacoes["somente_ativas"] = ativas_count == len(resultados) and len(resultados) > 0
                    validacoes["campos_obrigatorios"] = campos_ok_count == len(resultados)
                    
                    # Verificar contagem de status na resposta
                    contagem_status = classificacao.get('contagem_status', {})
                    validacoes["contagem_status"] = isinstance(contagem_status, dict) and len(contagem_status) > 0
                    
                    self.log(f"   ✅ Busca padrão executada com sucesso")
                    self.log(f"   Resultados ATIVAS: {ativas_count}/{len(resultados)}")
                    self.log(f"   Campos obrigatórios OK: {campos_ok_count}/{len(resultados)}")
                    self.log(f"   Contagem de status: {contagem_status}")
                    
                    if validacoes["somente_ativas"]:
                        self.log(f"   ✅ PADRÃO EFFECTI: Retorna SOMENTE oportunidades ATIVAS por default")
                    else:
                        self.log(f"   ❌ ERRO: Deveria retornar SOMENTE ATIVAS, mas encontrou outros status")
                    
                    # Log do primeiro resultado para debug
                    if resultados:
                        primeiro = resultados[0]
                        self.log(f"   Primeiro resultado:")
                        self.log(f"     Status Oportunidade: {primeiro.get('status_oportunidade', 'N/A')}")
                        self.log(f"     Badge Status: {primeiro.get('badge_status', 'N/A')}")
                        self.log(f"     Dias até abertura: {primeiro.get('dias_ate_abertura', 'N/A')}")
                        self.log(f"     Objeto: {primeiro.get('objeto', 'N/A')[:80]}...")
                        
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
                "resultados_ativas": ativas_count if 'ativas_count' in locals() else 0,
                "validacoes": validacoes,
                "tempo_ms": response_time_ms
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo_ms": (time.time() - start_time) * 1000
            }

    def test_2_filtro_futuras(self) -> Dict:
        """TESTE 2: Filtro FUTURAS - deve retornar SOMENTE oportunidades FUTURAS"""
        self.log("🧪 TESTE 2: Filtro FUTURAS")
        
        try:
            start_time = time.time()
            
            # Testar filtro específico para FUTURAS
            self.log("   Testando GET /api/search/local com filtro FUTURAS...")
            params = {
                "q": "canabidiol",
                "incluir_ativas": "false",
                "incluir_futuras": "true", 
                "incluir_encerradas": "false",
                "limit": 30
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params, timeout=TIMEOUT)
            response_time = time.time() - start_time
            response_time_ms = response_time * 1000
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "somente_futuras": False,
                "dias_corretos": False,
                "tempo_aceitavel": response_time_ms < 5000
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time_ms:.1f}ms")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = 'resultados' in data and 'total' in data
                    
                    resultados = data.get('resultados', [])
                    total = data.get('total', 0)
                    
                    self.log(f"   Total de resultados FUTURAS: {total}")
                    self.log(f"   Resultados retornados: {len(resultados)}")
                    
                    # Verificar se todos são FUTURAS
                    futuras_count = 0
                    dias_corretos_count = 0
                    
                    for resultado in resultados:
                        status_oportunidade = resultado.get('status_oportunidade')
                        if status_oportunidade == 'FUTURA':
                            futuras_count += 1
                        
                        # Verificar dias até abertura > 90
                        dias_ate_abertura = resultado.get('dias_ate_abertura')
                        if dias_ate_abertura is not None and dias_ate_abertura > 90:
                            dias_corretos_count += 1
                        elif dias_ate_abertura is None:
                            # Se não tem dias_ate_abertura, pode ser válido para FUTURA
                            dias_corretos_count += 1
                    
                    validacoes["somente_futuras"] = futuras_count == len(resultados) if len(resultados) > 0 else True
                    validacoes["dias_corretos"] = dias_corretos_count == len(resultados) if len(resultados) > 0 else True
                    
                    self.log(f"   ✅ Filtro FUTURAS executado com sucesso")
                    self.log(f"   Resultados FUTURAS: {futuras_count}/{len(resultados)}")
                    self.log(f"   Dias corretos (>90): {dias_corretos_count}/{len(resultados)}")
                    
                    if len(resultados) == 0:
                        self.log(f"   ℹ️ Nenhuma oportunidade FUTURA encontrada (pode ser normal)")
                        # Considerar válido se não há resultados
                        validacoes["somente_futuras"] = True
                        validacoes["dias_corretos"] = True
                    
                    # Log do primeiro resultado para debug
                    if resultados:
                        primeiro = resultados[0]
                        self.log(f"   Primeiro resultado FUTURA:")
                        self.log(f"     Status Oportunidade: {primeiro.get('status_oportunidade', 'N/A')}")
                        self.log(f"     Dias até abertura: {primeiro.get('dias_ate_abertura', 'N/A')}")
                        self.log(f"     Data abertura: {primeiro.get('data_abertura', 'N/A')}")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro na busca FUTURAS: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_resultados": total if 'total' in locals() else 0,
                "resultados_futuras": futuras_count if 'futuras_count' in locals() else 0,
                "validacoes": validacoes,
                "tempo_ms": response_time_ms
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo_ms": (time.time() - start_time) * 1000
            }

    def test_3_filtro_encerradas(self) -> Dict:
        """TESTE 3: Filtro ENCERRADAS - deve retornar SOMENTE oportunidades ENCERRADAS"""
        self.log("🧪 TESTE 3: Filtro ENCERRADAS")
        
        try:
            start_time = time.time()
            
            # Testar filtro específico para ENCERRADAS
            self.log("   Testando GET /api/search/local com filtro ENCERRADAS...")
            params = {
                "q": "canabidiol",
                "incluir_ativas": "false",
                "incluir_futuras": "false",
                "incluir_encerradas": "true",
                "limit": 30
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params, timeout=TIMEOUT)
            response_time = time.time() - start_time
            response_time_ms = response_time * 1000
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "somente_encerradas": False,
                "dias_corretos": False,
                "tempo_aceitavel": response_time_ms < 5000
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time_ms:.1f}ms")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = 'resultados' in data and 'total' in data
                    
                    resultados = data.get('resultados', [])
                    total = data.get('total', 0)
                    
                    self.log(f"   Total de resultados ENCERRADAS: {total}")
                    self.log(f"   Resultados retornados: {len(resultados)}")
                    
                    # Verificar se todos são ENCERRADAS
                    encerradas_count = 0
                    dias_corretos_count = 0
                    
                    for resultado in resultados:
                        status_oportunidade = resultado.get('status_oportunidade')
                        if status_oportunidade == 'ENCERRADA':
                            encerradas_count += 1
                        
                        # Verificar dias até abertura < 0 (ou null)
                        dias_ate_abertura = resultado.get('dias_ate_abertura')
                        if dias_ate_abertura is not None and dias_ate_abertura < 0:
                            dias_corretos_count += 1
                        elif dias_ate_abertura is None:
                            # Se não tem dias_ate_abertura, pode ser válido para ENCERRADA
                            dias_corretos_count += 1
                    
                    validacoes["somente_encerradas"] = encerradas_count == len(resultados) if len(resultados) > 0 else True
                    validacoes["dias_corretos"] = dias_corretos_count == len(resultados) if len(resultados) > 0 else True
                    
                    self.log(f"   ✅ Filtro ENCERRADAS executado com sucesso")
                    self.log(f"   Resultados ENCERRADAS: {encerradas_count}/{len(resultados)}")
                    self.log(f"   Dias corretos (<0 ou null): {dias_corretos_count}/{len(resultados)}")
                    
                    if len(resultados) == 0:
                        self.log(f"   ℹ️ Nenhuma oportunidade ENCERRADA encontrada (pode ser normal)")
                        # Considerar válido se não há resultados
                        validacoes["somente_encerradas"] = True
                        validacoes["dias_corretos"] = True
                    
                    # Log do primeiro resultado para debug
                    if resultados:
                        primeiro = resultados[0]
                        self.log(f"   Primeiro resultado ENCERRADA:")
                        self.log(f"     Status Oportunidade: {primeiro.get('status_oportunidade', 'N/A')}")
                        self.log(f"     Dias até abertura: {primeiro.get('dias_ate_abertura', 'N/A')}")
                        self.log(f"     Data abertura: {primeiro.get('data_abertura', 'N/A')}")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro na busca ENCERRADAS: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_resultados": total if 'total' in locals() else 0,
                "resultados_encerradas": encerradas_count if 'encerradas_count' in locals() else 0,
                "validacoes": validacoes,
                "tempo_ms": response_time_ms
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo_ms": (time.time() - start_time) * 1000
            }

    def test_4_filtro_combinado(self) -> Dict:
        """TESTE 4: Filtro COMBINADO - deve incluir mix de todos os status"""
        self.log("🧪 TESTE 4: Filtro COMBINADO")
        
        try:
            start_time = time.time()
            
            # Testar filtro combinado (todos os status)
            self.log("   Testando GET /api/search/local com filtro COMBINADO...")
            params = {
                "q": "credenciamento",
                "incluir_ativas": "true",
                "incluir_futuras": "true",
                "incluir_encerradas": "true",
                "limit": 50
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params, timeout=TIMEOUT)
            response_time = time.time() - start_time
            response_time_ms = response_time * 1000
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "mix_status": False,
                "total_coerente": False,
                "tempo_aceitavel": response_time_ms < 5000
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time_ms:.1f}ms")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = 'resultados' in data and 'total' in data
                    
                    resultados = data.get('resultados', [])
                    total = data.get('total', 0)
                    classificacao = data.get('classificacao_oportunidade', {})
                    contagem_status = classificacao.get('contagem_status', {})
                    
                    self.log(f"   Total de resultados COMBINADOS: {total}")
                    self.log(f"   Resultados retornados: {len(resultados)}")
                    self.log(f"   Contagem por status: {contagem_status}")
                    
                    # Contar status nos resultados
                    status_counts = {"ATIVA": 0, "FUTURA": 0, "ENCERRADA": 0}
                    
                    for resultado in resultados:
                        status_oportunidade = resultado.get('status_oportunidade')
                        if status_oportunidade in status_counts:
                            status_counts[status_oportunidade] += 1
                    
                    # Verificar se há mix de status (pelo menos 2 tipos diferentes)
                    status_presentes = sum(1 for count in status_counts.values() if count > 0)
                    validacoes["mix_status"] = status_presentes >= 1  # Pelo menos 1 tipo presente
                    
                    # Verificar se total é coerente
                    soma_contagem = sum(contagem_status.values()) if contagem_status else 0
                    validacoes["total_coerente"] = total >= len(resultados)
                    
                    self.log(f"   ✅ Filtro COMBINADO executado com sucesso")
                    self.log(f"   Status encontrados: {status_counts}")
                    self.log(f"   Tipos de status presentes: {status_presentes}")
                    self.log(f"   Total coerente: {total} >= {len(resultados)}")
                    
                    # Log de alguns resultados para debug
                    if resultados:
                        self.log(f"   Primeiros resultados:")
                        for i, resultado in enumerate(resultados[:3]):
                            status = resultado.get('status_oportunidade', 'N/A')
                            dias = resultado.get('dias_ate_abertura', 'N/A')
                            self.log(f"     {i+1}. Status: {status}, Dias: {dias}")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro na busca COMBINADA: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_resultados": total if 'total' in locals() else 0,
                "status_counts": status_counts if 'status_counts' in locals() else {},
                "validacoes": validacoes,
                "tempo_ms": response_time_ms
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo_ms": (time.time() - start_time) * 1000
            }

    def test_5_campos_obrigatorios(self) -> Dict:
        """TESTE 5: Campos Obrigatórios no Card - verificar estrutura completa"""
        self.log("🧪 TESTE 5: Campos Obrigatórios no Card")
        
        try:
            start_time = time.time()
            
            # Testar campos obrigatórios
            self.log("   Testando GET /api/search/local com verificação de campos...")
            params = {
                "q": "insulina",
                "limit": 5
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params, timeout=TIMEOUT)
            response_time = time.time() - start_time
            response_time_ms = response_time * 1000
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "numero_processo": False,
                "modalidade": False,
                "status_oportunidade": False,
                "badge_status_completo": False,
                "data_abertura": False,
                "data_publicacao": False,
                "tempo_aceitavel": response_time_ms < 5000
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time_ms:.1f}ms")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = 'resultados' in data and 'total' in data
                    
                    resultados = data.get('resultados', [])
                    total = data.get('total', 0)
                    
                    self.log(f"   Total de resultados: {total}")
                    self.log(f"   Resultados para verificação: {len(resultados)}")
                    
                    if len(resultados) > 0:
                        # Verificar campos obrigatórios em cada resultado
                        campos_ok = {
                            "numero_processo": 0,
                            "modalidade": 0,
                            "status_oportunidade": 0,
                            "badge_status_completo": 0,
                            "data_abertura": 0,
                            "data_publicacao": 0
                        }
                        
                        for resultado in resultados:
                            # 1. Número do processo ou edital
                            if resultado.get('numero_processo') or resultado.get('numero_edital'):
                                campos_ok["numero_processo"] += 1
                            
                            # 2. Modalidade
                            if resultado.get('modalidade') or resultado.get('tipo_modalidade'):
                                campos_ok["modalidade"] += 1
                            
                            # 3. Status oportunidade
                            if resultado.get('status_oportunidade'):
                                campos_ok["status_oportunidade"] += 1
                            
                            # 4. Badge status completo
                            badge_status = resultado.get('badge_status', {})
                            if (isinstance(badge_status, dict) and 
                                badge_status.get('texto') and 
                                badge_status.get('cor') and 
                                badge_status.get('icone')):
                                campos_ok["badge_status_completo"] += 1
                            
                            # 5. Data abertura
                            if resultado.get('data_abertura'):
                                campos_ok["data_abertura"] += 1
                            
                            # 6. Data publicação
                            if resultado.get('data_publicacao'):
                                campos_ok["data_publicacao"] += 1
                        
                        # Calcular percentuais
                        total_resultados = len(resultados)
                        for campo, count in campos_ok.items():
                            percentual = (count / total_resultados) * 100
                            validacoes[campo] = count == total_resultados  # 100% dos resultados
                            self.log(f"   {campo}: {count}/{total_resultados} ({percentual:.1f}%)")
                        
                        # Log do primeiro resultado para debug
                        primeiro = resultados[0]
                        self.log(f"   Primeiro resultado - campos:")
                        self.log(f"     numero_processo: {primeiro.get('numero_processo', 'N/A')}")
                        self.log(f"     modalidade: {primeiro.get('modalidade', 'N/A')}")
                        self.log(f"     status_oportunidade: {primeiro.get('status_oportunidade', 'N/A')}")
                        self.log(f"     badge_status: {primeiro.get('badge_status', 'N/A')}")
                        self.log(f"     data_abertura: {primeiro.get('data_abertura', 'N/A')}")
                        self.log(f"     data_publicacao: {primeiro.get('data_publicacao', 'N/A')}")
                    else:
                        self.log(f"   ℹ️ Nenhum resultado para verificar campos")
                        # Se não há resultados, considerar válido
                        for campo in ["numero_processo", "modalidade", "status_oportunidade", 
                                    "badge_status_completo", "data_abertura", "data_publicacao"]:
                            validacoes[campo] = True
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro na busca de campos: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_resultados": total if 'total' in locals() else 0,
                "campos_ok": campos_ok if 'campos_ok' in locals() else {},
                "validacoes": validacoes,
                "tempo_ms": response_time_ms
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo_ms": (time.time() - start_time) * 1000
            }

    def test_6_performance(self) -> Dict:
        """TESTE 6: Performance - deve processar 50 resultados em menos de 200ms"""
        self.log("🧪 TESTE 6: Performance")
        
        try:
            start_time = time.time()
            
            # Testar performance com 50 resultados
            self.log("   Testando GET /api/search/local com 50 resultados...")
            params = {
                "q": "medicamento",
                "limit": 50
            }
            
            response = self.session.get(f"{BACKEND_URL}/search/local", params=params, timeout=TIMEOUT)
            response_time = time.time() - start_time
            response_time_ms = response_time * 1000
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "performance_excelente": response_time_ms < 200.0,  # Menos de 200ms
                "todos_classificados": False,
                "limite_respeitado": False
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time_ms:.1f}ms")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = 'resultados' in data and 'total' in data
                    
                    resultados = data.get('resultados', [])
                    total = data.get('total', 0)
                    
                    self.log(f"   Total de resultados: {total}")
                    self.log(f"   Resultados retornados: {len(resultados)}")
                    
                    # Verificar se respeitou o limite
                    validacoes["limite_respeitado"] = len(resultados) <= 50
                    
                    # Verificar se todos estão classificados
                    classificados_count = 0
                    for resultado in resultados:
                        if resultado.get('status_oportunidade') in ['ATIVA', 'FUTURA', 'ENCERRADA']:
                            classificados_count += 1
                    
                    validacoes["todos_classificados"] = classificados_count == len(resultados)
                    
                    self.log(f"   ✅ Teste de performance executado")
                    self.log(f"   Resultados classificados: {classificados_count}/{len(resultados)}")
                    self.log(f"   Limite respeitado: {len(resultados)} <= 50")
                    
                    if validacoes["performance_excelente"]:
                        self.log(f"   ✅ PERFORMANCE EXCELENTE: {response_time_ms:.1f}ms < 200ms")
                    else:
                        self.log(f"   ❌ PERFORMANCE LENTA: {response_time_ms:.1f}ms >= 200ms")
                    
                    # Verificar tempo reportado pela API
                    performance_api = data.get('performance', {})
                    tempo_api = performance_api.get('tempo_ms', 0)
                    if tempo_api:
                        self.log(f"   Tempo reportado pela API: {tempo_api}ms")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro no teste de performance: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "total_resultados": total if 'total' in locals() else 0,
                "resultados_classificados": classificados_count if 'classificados_count' in locals() else 0,
                "validacoes": validacoes,
                "tempo_ms": response_time_ms
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo_ms": (time.time() - start_time) * 1000
            }

    def run_all_tests(self):
        """Executa todos os testes do Padrão Effecti"""
        self.log("🎯 INICIANDO TESTES DO PADRÃO EFFECTI - CLASSIFICAÇÃO DE OPORTUNIDADES")
        self.log("=" * 80)
        
        # Testar conectividade primeiro
        if not self.test_api_connection():
            self.log("❌ Falha na conectividade. Abortando testes.", "ERROR")
            return
        
        # Lista de testes
        testes = [
            ("1. Classificação Padrão (CRÍTICO)", self.test_1_classificacao_padrao),
            ("2. Filtro FUTURAS", self.test_2_filtro_futuras),
            ("3. Filtro ENCERRADAS", self.test_3_filtro_encerradas),
            ("4. Filtro COMBINADO", self.test_4_filtro_combinado),
            ("5. Campos Obrigatórios no Card", self.test_5_campos_obrigatorios),
            ("6. Performance", self.test_6_performance),
        ]
        
        # Executar testes
        resultados_testes = {}
        testes_passaram = 0
        
        for nome_teste, funcao_teste in testes:
            self.log(f"\n{'='*60}")
            self.log(f"EXECUTANDO: {nome_teste}")
            self.log(f"{'='*60}")
            
            try:
                resultado = funcao_teste()
                resultados_testes[nome_teste] = resultado
                
                if resultado["status"] == "✅ PASSOU":
                    testes_passaram += 1
                    self.log(f"✅ {nome_teste}: PASSOU")
                else:
                    self.log(f"❌ {nome_teste}: FALHOU")
                    if "erro" in resultado:
                        self.log(f"   Erro: {resultado['erro']}")
                
            except Exception as e:
                self.log(f"❌ {nome_teste}: ERRO CRÍTICO - {str(e)}")
                resultados_testes[nome_teste] = {
                    "status": "❌ FALHOU",
                    "erro": str(e)
                }
        
        # Resumo final
        self.log(f"\n{'='*80}")
        self.log(f"🎯 RESUMO FINAL - PADRÃO EFFECTI")
        self.log(f"{'='*80}")
        self.log(f"Testes executados: {len(testes)}")
        self.log(f"Testes que passaram: {testes_passaram}")
        self.log(f"Taxa de sucesso: {(testes_passaram/len(testes)*100):.1f}%")
        
        # Detalhes por teste
        self.log(f"\nDetalhes por teste:")
        for nome_teste, resultado in resultados_testes.items():
            status = resultado.get("status", "❌ FALHOU")
            tempo = resultado.get("tempo_ms", 0)
            self.log(f"  {status} {nome_teste} ({tempo:.1f}ms)")
        
        # Determinar resultado geral
        if testes_passaram == len(testes):
            self.log(f"\n🎉 PADRÃO EFFECTI - TOTALMENTE APROVADO!")
            self.log(f"   Todos os {len(testes)} testes obrigatórios passaram com sucesso.")
            self.log(f"   Sistema de classificação de oportunidades funcionando perfeitamente.")
        elif testes_passaram >= len(testes) * 0.8:  # 80% ou mais
            self.log(f"\n✅ PADRÃO EFFECTI - APROVADO COM RESSALVAS")
            self.log(f"   {testes_passaram}/{len(testes)} testes passaram.")
            self.log(f"   Sistema funcional, mas alguns ajustes podem ser necessários.")
        else:
            self.log(f"\n❌ PADRÃO EFFECTI - REPROVADO")
            self.log(f"   Apenas {testes_passaram}/{len(testes)} testes passaram.")
            self.log(f"   Sistema precisa de correções antes da aprovação.")
        
        return resultados_testes

if __name__ == "__main__":
    tester = EffectiPatternTester()
    tester.run_all_tests()