#!/usr/bin/env python3
"""
🧪 TESTES DE MONITORAMENTO - GSM BUSCADOR DE EDITAIS

Testa os endpoints de monitoramento implementados:

1. GET /api/monitoring/dashboard - Dashboard completo
2. GET /api/monitoring/workers - Status dos workers  
3. GET /api/monitoring/fontes - Status das fontes
4. GET /api/monitoring/pipeline - Métricas do pipeline
5. GET /api/monitoring/alertas - Métricas dos alertas
"""

import requests
import json
import time
import sys
from datetime import datetime
from typing import Dict

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

class MonitoringTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
    def log(self, message: str, level: str = "INFO"):
        """Log com timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")

    def test_monitoring_dashboard(self) -> Dict:
        """TESTE: Dashboard de Monitoramento Completo"""
        self.log("🧪 TESTE: Dashboard de Monitoramento Completo")
        
        try:
            start_time = time.time()
            
            # Testar endpoint do dashboard completo
            self.log("   Testando GET /api/monitoring/dashboard...")
            
            response = self.session.get(f"{BACKEND_URL}/monitoring/dashboard", timeout=60)
            response_time = time.time() - start_time
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "tem_timestamp": False,
                "tem_workers": False,
                "tem_fontes": False,
                "tem_pipeline": False,
                "tem_alertas": False,
                "tem_saude_geral": False,
                "tem_tempo_coleta": False
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.2f}s")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = isinstance(data, dict)
                    
                    # Verificar campos obrigatórios
                    timestamp = data.get('timestamp')
                    workers = data.get('workers', {})
                    fontes = data.get('fontes', {})
                    pipeline = data.get('pipeline', {})
                    alertas = data.get('alertas', {})
                    saude_geral = data.get('saude_geral', {})
                    tempo_coleta_ms = data.get('tempo_coleta_ms')
                    
                    validacoes["tem_timestamp"] = timestamp is not None
                    validacoes["tem_workers"] = isinstance(workers, dict)
                    validacoes["tem_fontes"] = isinstance(fontes, dict)
                    validacoes["tem_pipeline"] = isinstance(pipeline, dict)
                    validacoes["tem_alertas"] = isinstance(alertas, dict)
                    validacoes["tem_saude_geral"] = isinstance(saude_geral, dict) and 'score' in saude_geral
                    validacoes["tem_tempo_coleta"] = isinstance(tempo_coleta_ms, (int, float))
                    
                    self.log(f"   ✅ Dashboard completo obtido com sucesso")
                    self.log(f"   Timestamp: {timestamp}")
                    self.log(f"   Tempo de coleta: {tempo_coleta_ms}ms")
                    
                    # Log de saúde geral
                    if saude_geral:
                        score = saude_geral.get('score', 0)
                        status = saude_geral.get('status', 'N/A')
                        emoji = saude_geral.get('emoji', '')
                        detalhes = saude_geral.get('detalhes', [])
                        self.log(f"   Saúde geral: {score} ({status}) {emoji}")
                        if detalhes:
                            self.log(f"   Detalhes: {detalhes}")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro ao obter dashboard: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "saude_geral": saude_geral if 'saude_geral' in locals() else {},
                "tempo_coleta_ms": tempo_coleta_ms if 'tempo_coleta_ms' in locals() else 0,
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": time.time() - start_time
            }

    def test_monitoring_workers(self) -> Dict:
        """TESTE: Status dos Workers"""
        self.log("🧪 TESTE: Status dos Workers")
        
        try:
            start_time = time.time()
            
            # Testar endpoint de workers
            self.log("   Testando GET /api/monitoring/workers...")
            
            response = self.session.get(f"{BACKEND_URL}/monitoring/workers", timeout=30)
            response_time = time.time() - start_time
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "tem_workers": False,
                "tem_resumo": False,
                "workers_com_status": False
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.2f}s")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = isinstance(data, dict)
                    
                    workers = data.get('workers', {})
                    resumo = data.get('resumo', {})
                    
                    validacoes["tem_workers"] = isinstance(workers, dict)
                    validacoes["tem_resumo"] = isinstance(resumo, dict) and 'total' in resumo
                    
                    # Verificar se workers têm status válidos
                    if workers:
                        status_validos = ['OK', 'ERRO', 'ATRASO', 'DESCONHECIDO']
                        workers_validos = all(
                            w.get('status') in status_validos 
                            for w in workers.values() if isinstance(w, dict)
                        )
                        validacoes["workers_com_status"] = workers_validos
                        
                        self.log(f"   ✅ Workers obtidos com sucesso")
                        self.log(f"   Total workers: {len(workers)}")
                        
                        # Log de cada worker
                        for worker_key, worker_data in list(workers.items())[:5]:  # Primeiros 5
                            nome = worker_data.get('nome', 'N/A')
                            status = worker_data.get('status', 'N/A')
                            self.log(f"     {nome}: {status}")
                    else:
                        # Se não há workers, ainda consideramos válido
                        validacoes["workers_com_status"] = True
                        self.log(f"   ℹ️ Nenhum worker encontrado")
                    
                    # Log do resumo
                    if resumo:
                        total = resumo.get('total', 0)
                        ok = resumo.get('ok', 0)
                        erro = resumo.get('erro', 0)
                        atraso = resumo.get('atraso', 0)
                        self.log(f"   Resumo: {total} total, {ok} OK, {erro} ERRO, {atraso} ATRASO")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro ao obter workers: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "workers_count": len(workers) if 'workers' in locals() else 0,
                "resumo": resumo if 'resumo' in locals() else {},
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": time.time() - start_time
            }

    def test_monitoring_fontes(self) -> Dict:
        """TESTE: Status das Fontes"""
        self.log("🧪 TESTE: Status das Fontes")
        
        try:
            start_time = time.time()
            
            # Testar endpoint de fontes
            self.log("   Testando GET /api/monitoring/fontes...")
            
            response = self.session.get(f"{BACKEND_URL}/monitoring/fontes", timeout=30)
            response_time = time.time() - start_time
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "tem_fontes": False,
                "tem_pncp_oficial": False,
                "fontes_com_status": False,
                "fontes_com_metricas": False
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.2f}s")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = isinstance(data, dict)
                    
                    fontes = data.get('fontes', {})
                    
                    validacoes["tem_fontes"] = isinstance(fontes, dict)
                    
                    if fontes:
                        # Verificar se PNCP-OFICIAL está presente
                        pncp_oficial = 'PNCP-OFICIAL' in fontes
                        validacoes["tem_pncp_oficial"] = pncp_oficial
                        
                        # Verificar se fontes têm status e métricas
                        fontes_com_status = all(
                            'status' in f for f in fontes.values() if isinstance(f, dict)
                        )
                        fontes_com_metricas = all(
                            'fonte' in f for f in fontes.values() if isinstance(f, dict)
                        )
                        
                        validacoes["fontes_com_status"] = fontes_com_status
                        validacoes["fontes_com_metricas"] = fontes_com_metricas
                        
                        self.log(f"   ✅ Fontes obtidas com sucesso")
                        self.log(f"   Total fontes: {len(fontes)}")
                        
                        if pncp_oficial:
                            self.log(f"   ✅ PNCP-OFICIAL presente")
                        else:
                            self.log(f"   ❌ PNCP-OFICIAL não encontrado")
                        
                        # Log de algumas fontes
                        for fonte_key, fonte_data in list(fontes.items())[:3]:  # Primeiras 3
                            nome = fonte_data.get('fonte', 'N/A')
                            status = fonte_data.get('status', 'N/A')
                            self.log(f"     {nome}: {status}")
                    else:
                        # Se não há fontes, relaxar critérios
                        validacoes["tem_pncp_oficial"] = True
                        validacoes["fontes_com_status"] = True
                        validacoes["fontes_com_metricas"] = True
                        self.log(f"   ℹ️ Nenhuma fonte encontrada")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro ao obter fontes: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "fontes_count": len(fontes) if 'fontes' in locals() else 0,
                "tem_pncp_oficial": validacoes["tem_pncp_oficial"],
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": time.time() - start_time
            }

    def test_monitoring_pipeline(self) -> Dict:
        """TESTE: Métricas do Pipeline"""
        self.log("🧪 TESTE: Métricas do Pipeline")
        
        try:
            start_time = time.time()
            
            # Testar endpoint de pipeline
            self.log("   Testando GET /api/monitoring/pipeline...")
            
            response = self.session.get(f"{BACKEND_URL}/monitoring/pipeline", timeout=30)
            response_time = time.time() - start_time
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "tem_editais_raw": False,
                "tem_editais_normalizados": False,
                "tem_taxa_normalizacao": False,
                "tem_matches": False,
                "tem_saude": False
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.2f}s")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = isinstance(data, dict)
                    
                    editais_raw = data.get('editais_raw')
                    editais_normalizados = data.get('editais_normalizados')
                    taxa_normalizacao = data.get('taxa_normalizacao')
                    matches = data.get('matches', {})
                    saude = data.get('saude', {})
                    
                    validacoes["tem_editais_raw"] = isinstance(editais_raw, int)
                    validacoes["tem_editais_normalizados"] = isinstance(editais_normalizados, int)
                    validacoes["tem_taxa_normalizacao"] = isinstance(taxa_normalizacao, (int, float))
                    validacoes["tem_matches"] = isinstance(matches, dict) and 'total' in matches
                    validacoes["tem_saude"] = isinstance(saude, dict) and 'total' in saude
                    
                    self.log(f"   ✅ Pipeline metrics obtidas com sucesso")
                    self.log(f"   Editais raw: {editais_raw}")
                    self.log(f"   Editais normalizados: {editais_normalizados}")
                    self.log(f"   Taxa normalização: {taxa_normalizacao}%")
                    
                    if matches:
                        total_matches = matches.get('total', 0)
                        pendentes = matches.get('pendentes', 0)
                        self.log(f"   Matches: {total_matches} total, {pendentes} pendentes")
                    
                    if saude:
                        total_saude = saude.get('total', 0)
                        percentual = saude.get('percentual', 0)
                        self.log(f"   Saúde: {total_saude} total ({percentual}%)")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro ao obter pipeline: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "editais_raw": editais_raw if 'editais_raw' in locals() else 0,
                "editais_normalizados": editais_normalizados if 'editais_normalizados' in locals() else 0,
                "taxa_normalizacao": taxa_normalizacao if 'taxa_normalizacao' in locals() else 0,
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": time.time() - start_time
            }

    def test_monitoring_alertas(self) -> Dict:
        """TESTE: Métricas dos Alertas"""
        self.log("🧪 TESTE: Métricas dos Alertas")
        
        try:
            start_time = time.time()
            
            # Testar endpoint de alertas
            self.log("   Testando GET /api/monitoring/alertas...")
            
            response = self.session.get(f"{BACKEND_URL}/monitoring/alertas", timeout=30)
            response_time = time.time() - start_time
            
            # Validações
            validacoes = {
                "endpoint_funciona": response.status_code == 200,
                "estrutura_valida": False,
                "tem_alertas": False,
                "tem_matches": False,
                "tem_notificacoes": False
            }
            
            self.log(f"   Status da resposta: {response.status_code}")
            self.log(f"   Tempo de resposta: {response_time:.2f}s")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    validacoes["estrutura_valida"] = isinstance(data, dict)
                    
                    alertas = data.get('alertas', {})
                    matches = data.get('matches', {})
                    notificacoes = data.get('notificacoes', {})
                    
                    validacoes["tem_alertas"] = isinstance(alertas, dict) and 'ativos' in alertas
                    validacoes["tem_matches"] = isinstance(matches, dict) and 'disparados' in matches
                    validacoes["tem_notificacoes"] = isinstance(notificacoes, dict)
                    
                    self.log(f"   ✅ Alertas metrics obtidas com sucesso")
                    
                    if alertas:
                        ativos = alertas.get('ativos', 0)
                        inativos = alertas.get('inativos', 0)
                        self.log(f"   Alertas: {ativos} ativos, {inativos} inativos")
                    
                    if matches:
                        disparados = matches.get('disparados', 0)
                        suprimidos = matches.get('suprimidos', 0)
                        score_medio = matches.get('score_medio', 0)
                        self.log(f"   Matches: {disparados} disparados, {suprimidos} suprimidos, score médio {score_medio}")
                    
                    if notificacoes:
                        self.log(f"   Notificações stats presentes")
                        
                except Exception as e:
                    self.log(f"   ❌ Erro ao processar resposta JSON: {str(e)}")
                    validacoes["estrutura_valida"] = False
            else:
                self.log(f"   ❌ Erro ao obter alertas: {response.status_code}")
                self.log(f"   Response: {response.text[:200]}")
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "status_code": response.status_code,
                "alertas": alertas if 'alertas' in locals() else {},
                "matches": matches if 'matches' in locals() else {},
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": time.time() - start_time
            }

    def run_monitoring_tests(self):
        """Executa todos os testes de monitoramento"""
        self.log("🚀 INICIANDO TESTES DE MONITORAMENTO - GSM BUSCADOR DE EDITAIS")
        self.log("=" * 80)
        
        # Lista de testes de monitoramento
        tests = [
            ("Dashboard Completo", self.test_monitoring_dashboard),
            ("Workers Status", self.test_monitoring_workers),
            ("Fontes Status", self.test_monitoring_fontes),
            ("Pipeline Metrics", self.test_monitoring_pipeline),
            ("Alertas Metrics", self.test_monitoring_alertas)
        ]
        
        results = {}
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            self.log(f"\n📋 Executando: {test_name}")
            self.log("-" * 60)
            
            try:
                result = test_func()
                results[test_name] = result
                
                if "✅ PASSOU" in result["status"]:
                    passed += 1
                    self.log(f"✅ {test_name}: PASSOU")
                else:
                    failed += 1
                    self.log(f"❌ {test_name}: FALHOU")
                    if "erro" in result:
                        self.log(f"   Erro: {result['erro']}")
                        
            except Exception as e:
                failed += 1
                self.log(f"❌ {test_name}: ERRO CRÍTICO - {str(e)}")
                results[test_name] = {
                    "status": "❌ FALHOU",
                    "erro": str(e)
                }
        
        # Relatório final
        self.log("\n" + "=" * 80)
        self.log("📊 RELATÓRIO FINAL DOS TESTES DE MONITORAMENTO")
        self.log("=" * 80)
        
        self.log(f"✅ Testes aprovados: {passed}")
        self.log(f"❌ Testes falharam: {failed}")
        self.log(f"📈 Taxa de sucesso: {(passed/(passed+failed)*100):.1f}%")
        
        # Detalhes dos testes
        self.log("\n📋 DETALHES DOS TESTES:")
        for test_name, result in results.items():
            status = result.get("status", "❌ FALHOU")
            tempo = result.get("tempo", 0)
            self.log(f"   {status} - {test_name} ({tempo:.2f}s)")
            
            if "❌ FALHOU" in status and "validacoes" in result:
                validacoes = result["validacoes"]
                falhas = [k for k, v in validacoes.items() if not v]
                if falhas:
                    self.log(f"     Falhas: {', '.join(falhas)}")
        
        return results

if __name__ == "__main__":
    tester = MonitoringTester()
    results = tester.run_monitoring_tests()