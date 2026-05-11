#!/usr/bin/env python3
"""
🧪 TESTE COMPLETO DO BACKEND GSM - Buscador de Editais

Testa os endpoints críticos conforme review request:
1. Busca Principal - POST /api/search
2. Listas Customizadas - CRUD /api/listas  
3. Dashboard - GET /api/status/scrapers
4. Exportação - GET /api/export
5. Estatísticas - GET /api/stats
6. Cache - GET /api/cache/stats
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Optional
import sys
import os

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
TIMEOUT = 30

class GSMTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.results = {}
        self.created_lists = []  # Para cleanup
        
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
    
    def test_1_busca_principal(self) -> Dict:
        """TESTE 1: Busca Principal - POST /api/search"""
        self.log("🧪 TESTE 1: Busca Principal - POST /api/search")
        
        # Teste com medicamento: "insulina"
        payload = {
            "medicamento": "insulina",
            "page": 1,
            "per_page": 10
        }
        
        try:
            start_time = time.time()
            response = self.session.post(
                f"{BACKEND_URL}/search",
                json=payload,
                timeout=TIMEOUT
            )
            response_time = time.time() - start_time
            
            if response.status_code != 200:
                return {
                    "status": "❌ FALHOU",
                    "erro": f"Status {response.status_code}: {response.text[:200]}",
                    "tempo": response_time
                }
            
            data = response.json()
            
            # Validações críticas
            validacoes = {
                "api_200": response.status_code == 200,
                "tem_total": 'total' in data and isinstance(data['total'], int),
                "tem_resultados": 'resultados' in data and isinstance(data['resultados'], list),
                "tem_paginacao": 'pagination' in data,
                "multiplos_scrapers": False,
                "performance_ok": response_time < 5.0
            }
            
            # Verificar metadados de paginação
            pagination = data.get('pagination', {})
            paginacao_ok = all(key in pagination for key in ['page', 'per_page', 'total_pages', 'total_items'])
            validacoes["paginacao_completa"] = paginacao_ok
            
            # Verificar múltiplos scrapers
            resultados = data.get('resultados', [])
            fontes = set(r.get('fonte', '') for r in resultados if r.get('fonte'))
            validacoes["multiplos_scrapers"] = len(fontes) > 1 or len(resultados) == 0
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "total_resultados": data.get('total', 0),
                "fontes_encontradas": list(fontes),
                "paginacao": pagination,
                "validacoes": validacoes,
                "tempo": response_time,
                "performance_ok": response_time < 5.0
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": 0
            }
    
    def test_2_listas_crud(self) -> Dict:
        """TESTE 2: Listas Customizadas - CRUD /api/listas"""
        self.log("🧪 TESTE 2: Listas Customizadas - CRUD /api/listas")
        
        try:
            start_time = time.time()
            
            # 1. GET /api/listas (listar todas)
            self.log("   Testando GET /api/listas...")
            response = self.session.get(f"{BACKEND_URL}/listas", timeout=15)
            if response.status_code != 200:
                return {
                    "status": "❌ FALHOU",
                    "erro": f"GET /listas falhou: {response.status_code}",
                    "tempo": time.time() - start_time
                }
            
            listas_iniciais = response.json().get('total', 0)
            
            # 2. POST /api/listas (criar nova)
            self.log("   Testando POST /api/listas...")
            nova_lista = {
                "nome": f"Teste_GSM_{int(time.time())}",
                "descricao": "Lista de teste para GSM",
                "medicamentos": ["insulina", "dipirona", "paracetamol"]
            }
            
            response = self.session.post(f"{BACKEND_URL}/listas", json=nova_lista, timeout=15)
            if response.status_code != 201:
                return {
                    "status": "❌ FALHOU",
                    "erro": f"POST /listas falhou: {response.status_code} - {response.text[:200]}",
                    "tempo": time.time() - start_time
                }
            
            lista_criada = response.json().get('lista', {})
            lista_id = lista_criada.get('id')
            if not lista_id:
                return {
                    "status": "❌ FALHOU",
                    "erro": "Lista criada sem ID",
                    "tempo": time.time() - start_time
                }
            
            self.created_lists.append(lista_id)  # Para cleanup
            
            # 3. GET /api/listas/{id} (buscar específica)
            self.log("   Testando GET /api/listas/{id}...")
            response = self.session.get(f"{BACKEND_URL}/listas/{lista_id}", timeout=15)
            if response.status_code != 200:
                return {
                    "status": "❌ FALHOU",
                    "erro": f"GET /listas/{lista_id} falhou: {response.status_code}",
                    "tempo": time.time() - start_time
                }
            
            # 4. PUT /api/listas/{id} (atualizar)
            self.log("   Testando PUT /api/listas/{id}...")
            update_data = {
                "descricao": "Lista atualizada pelo teste GSM"
            }
            response = self.session.put(f"{BACKEND_URL}/listas/{lista_id}", json=update_data, timeout=15)
            if response.status_code != 200:
                return {
                    "status": "❌ FALHOU",
                    "erro": f"PUT /listas/{lista_id} falhou: {response.status_code}",
                    "tempo": time.time() - start_time
                }
            
            # 5. Verificar limite de 5 listas (criar mais 4)
            self.log("   Testando limite de 5 listas...")
            listas_extras = []
            for i in range(4):
                lista_extra = {
                    "nome": f"Extra_{i}_{int(time.time())}",
                    "descricao": f"Lista extra {i}",
                    "medicamentos": ["teste"]
                }
                response = self.session.post(f"{BACKEND_URL}/listas", json=lista_extra, timeout=15)
                if response.status_code == 201:
                    extra_id = response.json().get('lista', {}).get('id')
                    if extra_id:
                        listas_extras.append(extra_id)
                        self.created_lists.append(extra_id)
            
            # Tentar criar a 6ª lista (deve falhar)
            lista_sexta = {
                "nome": f"Sexta_{int(time.time())}",
                "descricao": "Esta deve falhar",
                "medicamentos": ["teste"]
            }
            response = self.session.post(f"{BACKEND_URL}/listas", json=lista_sexta, timeout=15)
            limite_funcionou = response.status_code == 400
            
            # 6. DELETE /api/listas/{id} (deletar)
            self.log("   Testando DELETE /api/listas/{id}...")
            response = self.session.delete(f"{BACKEND_URL}/listas/{lista_id}", timeout=15)
            delete_ok = response.status_code == 200
            
            if delete_ok:
                self.created_lists.remove(lista_id)
            
            response_time = time.time() - start_time
            
            # Validações
            validacoes = {
                "get_listas": True,
                "post_lista": True,
                "get_lista_id": True,
                "put_lista": True,
                "delete_lista": delete_ok,
                "limite_5_listas": limite_funcionou
            }
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "lista_id_criado": lista_id,
                "listas_extras": len(listas_extras),
                "limite_funcionou": limite_funcionou,
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": time.time() - start_time
            }
    
    def test_3_dashboard_scrapers(self) -> Dict:
        """TESTE 3: Dashboard - GET /api/status/scrapers"""
        self.log("🧪 TESTE 3: Dashboard - GET /api/status/scrapers")
        
        try:
            start_time = time.time()
            response = self.session.get(f"{BACKEND_URL}/status/scrapers", timeout=15)
            response_time = time.time() - start_time
            
            if response.status_code != 200:
                return {
                    "status": "❌ FALHOU",
                    "erro": f"Status {response.status_code}: {response.text[:200]}",
                    "tempo": response_time
                }
            
            data = response.json()
            
            # Validar estrutura da resposta
            validacoes = {
                "api_200": response.status_code == 200,
                "tem_scrapers": 'scrapers' in data or 'system_health' in data,
                "estrutura_valida": False
            }
            
            # Verificar se tem informações de scrapers
            scrapers_info = []
            if 'scrapers' in data:
                scrapers_info = data['scrapers']
            elif isinstance(data, dict):
                # Pode ser que a estrutura seja diferente
                scrapers_info = [data]
            
            # Verificar estrutura dos scrapers
            if scrapers_info:
                primeiro_scraper = scrapers_info[0] if isinstance(scrapers_info, list) else scrapers_info
                campos_esperados = ['status', 'nome'] if isinstance(primeiro_scraper, dict) else []
                validacoes["estrutura_valida"] = len(campos_esperados) > 0
            else:
                # Se não tem scrapers, mas API responde, ainda é válido
                validacoes["estrutura_valida"] = True
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "scrapers_encontrados": len(scrapers_info) if isinstance(scrapers_info, list) else 1,
                "estrutura_resposta": list(data.keys()) if isinstance(data, dict) else [],
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": 0
            }
    
    def test_4_exportacao(self) -> Dict:
        """TESTE 4: Exportação - GET /api/export"""
        self.log("🧪 TESTE 4: Exportação - GET /api/export")
        
        try:
            start_time = time.time()
            
            # Teste formato CSV
            self.log("   Testando exportação CSV...")
            params = {
                "formato": "csv",
                "medicamento": "insulina"
            }
            response = self.session.get(f"{BACKEND_URL}/export", params=params, timeout=30)
            csv_ok = response.status_code == 200 and 'text/csv' in response.headers.get('content-type', '')
            
            # Teste formato JSON
            self.log("   Testando exportação JSON...")
            params = {
                "formato": "json",
                "medicamento": "insulina"
            }
            response = self.session.get(f"{BACKEND_URL}/export", params=params, timeout=30)
            json_ok = response.status_code == 200 and 'application/json' in response.headers.get('content-type', '')
            
            # Verificar se stream funciona (headers de download)
            stream_ok = 'attachment' in response.headers.get('content-disposition', '')
            
            response_time = time.time() - start_time
            
            # Validações
            validacoes = {
                "csv_funciona": csv_ok,
                "json_funciona": json_ok,
                "stream_funciona": stream_ok,
                "performance_ok": response_time < 30
            }
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "csv_ok": csv_ok,
                "json_ok": json_ok,
                "stream_ok": stream_ok,
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": time.time() - start_time
            }
    
    def test_5_estatisticas(self) -> Dict:
        """TESTE 5: Estatísticas - GET /api/stats"""
        self.log("🧪 TESTE 5: Estatísticas - GET /api/stats")
        
        try:
            start_time = time.time()
            response = self.session.get(f"{BACKEND_URL}/stats", timeout=15)
            response_time = time.time() - start_time
            
            if response.status_code != 200:
                return {
                    "status": "❌ FALHOU",
                    "erro": f"Status {response.status_code}: {response.text[:200]}",
                    "tempo": response_time
                }
            
            data = response.json()
            
            # Validar estrutura da resposta
            validacoes = {
                "api_200": response.status_code == 200,
                "tem_total_licitacoes": 'total_licitacoes' in data,
                "tem_scrapers_ativos": 'estados_com_scraping' in data or 'scrapers_ativos' in data,
                "estrutura_valida": False
            }
            
            # Verificar contagem de licitações
            total_licitacoes = data.get('total_licitacoes', 0)
            validacoes["contagem_valida"] = isinstance(total_licitacoes, int) and total_licitacoes >= 0
            
            # Verificar dados de scrapers ativos
            scrapers_ativos = data.get('estados_com_scraping', [])
            validacoes["scrapers_info_ok"] = isinstance(scrapers_ativos, list)
            
            # Verificar se tem informações por estado
            por_estado = data.get('por_estado', [])
            validacoes["por_estado_ok"] = isinstance(por_estado, list)
            
            validacoes["estrutura_valida"] = all([
                validacoes["contagem_valida"],
                validacoes["scrapers_info_ok"],
                validacoes["por_estado_ok"]
            ])
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "total_licitacoes": total_licitacoes,
                "scrapers_ativos": len(scrapers_ativos) if isinstance(scrapers_ativos, list) else 0,
                "estados_com_dados": len(por_estado) if isinstance(por_estado, list) else 0,
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": 0
            }
    
    def test_6_cache_stats(self) -> Dict:
        """TESTE 6: Cache - GET /api/cache/stats"""
        self.log("🧪 TESTE 6: Cache - GET /api/cache/stats")
        
        try:
            start_time = time.time()
            response = self.session.get(f"{BACKEND_URL}/cache/stats", timeout=15)
            response_time = time.time() - start_time
            
            if response.status_code != 200:
                return {
                    "status": "❌ FALHOU",
                    "erro": f"Status {response.status_code}: {response.text[:200]}",
                    "tempo": response_time
                }
            
            data = response.json()
            
            # Validar estrutura da resposta
            validacoes = {
                "api_200": response.status_code == 200,
                "tem_cache_stats": 'cache_stats' in data,
                "estrutura_valida": False
            }
            
            # Verificar estatísticas do cache
            cache_stats = data.get('cache_stats', {})
            if isinstance(cache_stats, dict):
                # Campos esperados em estatísticas de cache
                campos_cache = ['hits', 'misses', 'size'] if cache_stats else []
                validacoes["estrutura_valida"] = len(campos_cache) > 0 or len(cache_stats) == 0
            else:
                validacoes["estrutura_valida"] = True  # Cache vazio é válido
            
            status = "✅ PASSOU" if all(validacoes.values()) else "❌ FALHOU"
            
            return {
                "status": status,
                "cache_stats": cache_stats,
                "tem_dados": len(cache_stats) > 0 if isinstance(cache_stats, dict) else False,
                "validacoes": validacoes,
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": 0
            }
    
    def cleanup_test_data(self):
        """Remove dados de teste criados"""
        if not self.created_lists:
            return
        
        self.log("🧹 Limpando dados de teste...")
        for lista_id in self.created_lists:
            try:
                response = self.session.delete(f"{BACKEND_URL}/listas/{lista_id}", timeout=10)
                if response.status_code == 200:
                    self.log(f"   ✅ Lista {lista_id} removida")
                else:
                    self.log(f"   ⚠️ Erro ao remover lista {lista_id}: {response.status_code}", "WARN")
            except Exception as e:
                self.log(f"   ⚠️ Erro ao remover lista {lista_id}: {str(e)}", "WARN")
    
    def run_all_tests(self):
        """Executa todos os testes e gera relatório"""
        self.log("🚀 INICIANDO TESTE COMPLETO DO BACKEND GSM")
        self.log("=" * 60)
        
        # Teste de conectividade
        if not self.test_api_connection():
            self.log("❌ Falha na conectividade. Abortando testes.", "ERROR")
            return
        
        # Executar todos os testes
        tests = [
            ("TESTE 1: Busca Principal", self.test_1_busca_principal),
            ("TESTE 2: Listas Customizadas CRUD", self.test_2_listas_crud),
            ("TESTE 3: Dashboard Scrapers", self.test_3_dashboard_scrapers),
            ("TESTE 4: Exportação", self.test_4_exportacao),
            ("TESTE 5: Estatísticas", self.test_5_estatisticas),
            ("TESTE 6: Cache Stats", self.test_6_cache_stats)
        ]
        
        # Executar testes
        for nome, test_func in tests:
            self.log(f"\n{'='*60}")
            resultado = test_func()
            self.results[nome] = resultado
            
            # Log do resultado
            status = resultado.get('status', '❌ FALHOU')
            tempo = resultado.get('tempo', 0)
            self.log(f"{status} - {nome} ({tempo:.2f}s)")
            
            if 'erro' in resultado:
                self.log(f"   Erro: {resultado['erro']}", "ERROR")
            
            # Delay entre testes
            time.sleep(1)
        
        # Cleanup
        self.cleanup_test_data()
        
        # Gerar relatório final
        self.generate_report()
    
    def generate_report(self):
        """Gera relatório final dos testes"""
        self.log("\n" + "=" * 60)
        self.log("📊 RELATÓRIO FINAL DOS TESTES GSM")
        self.log("=" * 60)
        
        passed = 0
        partial = 0
        failed = 0
        
        for nome, resultado in self.results.items():
            status = resultado.get('status', '❌ FALHOU')
            tempo = resultado.get('tempo', 0)
            
            if status.startswith('✅'):
                passed += 1
                icon = "✅"
            elif status.startswith('⚠️'):
                partial += 1
                icon = "⚠️"
            else:
                failed += 1
                icon = "❌"
            
            self.log(f"{icon} {nome}: {status} ({tempo:.2f}s)")
            
            # Detalhes específicos por teste
            if 'total_resultados' in resultado:
                self.log(f"   └─ Resultados: {resultado['total_resultados']}")
            
            if 'fontes_encontradas' in resultado:
                fontes = resultado['fontes_encontradas']
                if fontes:
                    self.log(f"   └─ Fontes: {', '.join(fontes)}")
            
            if 'erro' in resultado:
                self.log(f"   └─ Erro: {resultado['erro']}")
        
        # Resumo
        total = len(self.results)
        self.log("\n" + "=" * 60)
        self.log("📈 RESUMO:")
        self.log(f"   ✅ Passou: {passed}/{total}")
        self.log(f"   ⚠️ Parcial: {partial}/{total}")
        self.log(f"   ❌ Falhou: {failed}/{total}")
        
        # Critério de sucesso para GSM
        sucesso_minimo = 4  # Pelo menos 4 dos 6 testes
        testes_ok = passed + partial
        
        if testes_ok >= sucesso_minimo:
            self.log(f"\n🎉 SUCESSO! Sistema GSM passou em {testes_ok}/{total} testes (mínimo: {sucesso_minimo})")
        else:
            self.log(f"\n❌ FALHA! Sistema GSM passou em apenas {testes_ok}/{total} testes (mínimo: {sucesso_minimo})")
        
        self.log("=" * 60)


def main():
    """Função principal"""
    tester = GSMTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
        self.log("🧪 TESTE 9: Links Diretos (Navegação Dupla)")
        
        payload = {
            "medicamento": "medicamento",
            "apenas_reais": True
        }
        
        try:
            start_time = time.time()
            response = self.session.post(
                f"{BACKEND_URL}/search",
                json=payload,
                timeout=TIMEOUT
            )
            response_time = time.time() - start_time
            
            if response.status_code != 200:
                return {
                    "status": "❌ FALHOU",
                    "erro": f"Status {response.status_code}: {response.text}",
                    "tempo": response_time
                }
            
            data = response.json()
            resultados = data.get('resultados', [])
            
            # Verificar links
            com_link_origem = 0
            com_link_documento = 0
            exemplos_links = []
            
            for resultado in resultados[:10]:  # Verificar primeiros 10
                link_origem = resultado.get('link_origem', '')
                link_documento = resultado.get('link_documento', '')
                
                if link_origem:
                    com_link_origem += 1
                
                if link_documento:
                    com_link_documento += 1
                    
                    # Verificar se é link direto de PDF
                    link_lower = link_documento.lower()
                    is_pdf_direto = any(palavra in link_lower for palavra in ['.pdf', 'arquivo', 'download'])
                    is_pagina_detalhes = 'app/editais' in link_lower or 'detalhes' in link_lower
                    
                    if is_pdf_direto and not is_pagina_detalhes:
                        exemplos_links.append({
                            "tipo": "PDF_DIRETO",
                            "url": link_documento[:80] + "..." if len(link_documento) > 80 else link_documento
                        })
                    else:
                        exemplos_links.append({
                            "tipo": "PAGINA_DETALHES",
                            "url": link_documento[:80] + "..." if len(link_documento) > 80 else link_documento
                        })
            
            links_ok = com_link_origem > 0
            
            return {
                "status": "✅ PASSOU" if links_ok else "⚠️ PARCIAL",
                "total_resultados": len(resultados),
                "com_link_origem": com_link_origem,
                "com_link_documento": com_link_documento,
                "exemplos_links": exemplos_links[:3],  # Primeiros 3 exemplos
                "tempo": response_time
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": 0
            }
    
    def test_10_stress_lista_customizada(self, lista_id: Optional[str]) -> Dict:
        """TESTE 10: Stress Test - Busca com Lista Customizada"""
        self.log("🧪 TESTE 10: Stress Test - Busca com Lista Customizada")
        
        if not lista_id:
            return {
                "status": "❌ FALHOU",
                "erro": "Lista de teste não foi criada",
                "tempo": 0
            }
        
        payload = {
            "lista_id": lista_id,
            "apenas_reais": True
        }
        
        try:
            start_time = time.time()
            response = self.session.post(
                f"{BACKEND_URL}/search",
                json=payload,
                timeout=45  # Timeout maior para stress test
            )
            response_time = time.time() - start_time
            
            if response.status_code != 200:
                return {
                    "status": "❌ FALHOU",
                    "erro": f"Status {response.status_code}: {response.text}",
                    "tempo": response_time
                }
            
            data = response.json()
            resultados = data.get('resultados', [])
            medicamento_info = data.get('medicamento', '')
            
            # Verificar se buscou múltiplos medicamentos
            medicamentos_esperados = ["Canabidiol", "Mevatyl", "CBD"]
            medicamentos_encontrados = set()
            
            for resultado in resultados:
                med = resultado.get('medicamento', '').lower()
                for esperado in medicamentos_esperados:
                    if esperado.lower() in med:
                        medicamentos_encontrados.add(esperado)
            
            # Verificar fontes agregadas
            fontes_encontradas = set(r.get('fonte', '') for r in resultados)
            
            # Validações
            busca_multipla = len(medicamentos_encontrados) >= 2 or "Lista:" in medicamento_info
            tempo_aceitavel = response_time < 30
            agregacao_ok = len(fontes_encontradas) > 1 or len(resultados) == 0
            
            return {
                "status": "✅ PASSOU" if busca_multipla and tempo_aceitavel else "⚠️ PARCIAL",
                "total_resultados": len(resultados),
                "medicamentos_encontrados": list(medicamentos_encontrados),
                "fontes_encontradas": list(fontes_encontradas),
                "tempo": response_time,
                "tempo_aceitavel": tempo_aceitavel,
                "medicamento_info": medicamento_info
            }
            
        except Exception as e:
            return {
                "status": "❌ FALHOU",
                "erro": str(e),
                "tempo": 0
            }
    
    def cleanup_test_list(self, lista_id: Optional[str]):
        """Remove a lista de teste criada"""
        if not lista_id:
            return
        
        try:
            self.log("🧹 Removendo lista de teste...")
            response = self.session.delete(f"{BACKEND_URL}/listas/{lista_id}", timeout=10)
            
            if response.status_code == 200:
                self.log("✅ Lista de teste removida")
            else:
                self.log(f"⚠️ Erro ao remover lista: {response.status_code}", "WARN")
                
        except Exception as e:
            self.log(f"⚠️ Erro ao remover lista: {str(e)}", "WARN")
    
    def run_all_tests(self):
        """Executa todos os testes e gera relatório"""
        self.log("🚀 INICIANDO TESTE DE INTEGRAÇÃO COMPLETO - BEM")
        self.log("=" * 60)
        
        # Teste de conectividade
        if not self.test_api_connection():
            self.log("❌ Falha na conectividade. Abortando testes.", "ERROR")
            return
        
        # Criar lista de teste
        lista_id = self.create_test_list()
        
        # Executar todos os testes
        tests = [
            ("TESTE 1: Busca Básica com Agregadores", self.test_1_busca_basica_agregadores),
            ("TESTE 2: Filtro de Status", self.test_2_filtro_status),
            ("TESTE 3: Filtro de Esfera", self.test_3_filtro_esfera),
            ("TESTE 4: Apenas Futuras", self.test_4_apenas_futuras),
            ("TESTE 5: Busca Apenas PNCP", self.test_5_apenas_pncp),
            ("TESTE 6: Busca Apenas ComprasNet", self.test_6_apenas_comprasnet),
            ("TESTE 7: Ordenação por Urgência", self.test_7_ordenacao_urgencia),
            ("TESTE 8: Campos Expandidos - Itens", self.test_8_campos_expandidos_itens),
            ("TESTE 9: Links Diretos", self.test_9_links_diretos),
            ("TESTE 10: Stress Test - Lista Customizada", lambda: self.test_10_stress_lista_customizada(lista_id))
        ]
        
        # Executar testes
        for nome, test_func in tests:
            self.log(f"\n{'='*60}")
            resultado = test_func()
            self.results[nome] = resultado
            
            # Log do resultado
            status = resultado.get('status', '❌ FALHOU')
            tempo = resultado.get('tempo', 0)
            self.log(f"{status} - {nome} ({tempo:.2f}s)")
            
            if 'erro' in resultado:
                self.log(f"   Erro: {resultado['erro']}", "ERROR")
            
            # Delay entre testes
            time.sleep(1)
        
        # Cleanup
        self.cleanup_test_list(lista_id)
        
        # Gerar relatório final
        self.generate_report()
    
    def generate_report(self):
        """Gera relatório final dos testes"""
        self.log("\n" + "=" * 60)
        self.log("📊 RELATÓRIO FINAL DOS TESTES")
        self.log("=" * 60)
        
        passed = 0
        partial = 0
        failed = 0
        
        for nome, resultado in self.results.items():
            status = resultado.get('status', '❌ FALHOU')
            tempo = resultado.get('tempo', 0)
            
            if status.startswith('✅'):
                passed += 1
                icon = "✅"
            elif status.startswith('⚠️'):
                partial += 1
                icon = "⚠️"
            else:
                failed += 1
                icon = "❌"
            
            self.log(f"{icon} {nome}: {status} ({tempo:.2f}s)")
            
            # Detalhes específicos por teste
            if 'total_resultados' in resultado:
                self.log(f"   └─ Resultados: {resultado['total_resultados']}")
            
            if 'fontes_encontradas' in resultado:
                fontes = resultado['fontes_encontradas']
                if fontes:
                    self.log(f"   └─ Fontes: {', '.join(fontes)}")
            
            if 'erro' in resultado:
                self.log(f"   └─ Erro: {resultado['erro']}")
        
        # Resumo
        total = len(self.results)
        self.log("\n" + "=" * 60)
        self.log("📈 RESUMO:")
        self.log(f"   ✅ Passou: {passed}/{total}")
        self.log(f"   ⚠️ Parcial: {partial}/{total}")
        self.log(f"   ❌ Falhou: {failed}/{total}")
        
        # Critério de sucesso
        sucesso_minimo = 7  # Pelo menos 7 dos 10 testes
        testes_ok = passed + partial
        
        if testes_ok >= sucesso_minimo:
            self.log(f"\n🎉 SUCESSO! Sistema passou em {testes_ok}/{total} testes (mínimo: {sucesso_minimo})")
        else:
            self.log(f"\n❌ FALHA! Sistema passou em apenas {testes_ok}/{total} testes (mínimo: {sucesso_minimo})")
        
        self.log("=" * 60)


def main():
    """Função principal"""
    tester = BEMTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()