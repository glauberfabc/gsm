#!/usr/bin/env python3
"""
🧪 GSM V3.0 - SMOKE TESTS PARA PRODUÇÃO

Executa bateria rápida de testes críticos após deploy.
Valida funcionalidades essenciais em ~5 minutos.

Uso:
    python3 smoke_tests_producao.py https://seu-app.emergentagent.com
"""

import requests
import json
import time
import sys
from datetime import datetime
from typing import Dict, List


class ProductionSmokeTests:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api"
        self.results = {}
        self.start_time = None
        
    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        symbols = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "ERROR": "❌",
            "WARNING": "⚠️",
            "TEST": "🧪"
        }
        symbol = symbols.get(level, "•")
        print(f"[{timestamp}] {symbol} {message}")
    
    def test_health_check(self) -> bool:
        """Teste 1: Health Check - API está respondendo?"""
        self.log("Teste 1: Health Check da API", "TEST")
        
        try:
            response = requests.get(f"{self.api_url}/", timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                self.log(f"API respondendo: {data.get('message', 'OK')}", "SUCCESS")
                return True
            else:
                self.log(f"API retornou status {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Erro ao conectar na API: {str(e)}", "ERROR")
            return False
    
    def test_busca_simples(self) -> bool:
        """Teste 2: Busca Simples - Funcionalidade principal"""
        self.log("Teste 2: Busca Simples (insulina)", "TEST")
        
        try:
            payload = {"medicamento": "insulina"}
            response = requests.post(
                f"{self.api_url}/search",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('total', 0)
                self.log(f"Busca funcionando: {total} resultados encontrados", "SUCCESS")
                
                # Validar estrutura dos resultados
                if 'resultados' in data and isinstance(data['resultados'], list):
                    self.log("Estrutura de dados válida", "SUCCESS")
                    return True
                else:
                    self.log("Estrutura de dados inválida", "WARNING")
                    return False
            else:
                self.log(f"Busca retornou status {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Erro na busca: {str(e)}", "ERROR")
            return False
    
    def test_filtros_avancados(self) -> bool:
        """Teste 3: Filtros Avançados"""
        self.log("Teste 3: Filtros Avançados", "TEST")
        
        try:
            payload = {
                "medicamento": "medicamento",
                "status_filtro": "Ativa",
                "esfera_filtro": "Federal"
            }
            response = requests.post(
                f"{self.api_url}/search",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                self.log("Filtros avançados funcionando", "SUCCESS")
                return True
            else:
                self.log(f"Filtros retornaram status {response.status_code}", "WARNING")
                return False
                
        except Exception as e:
            self.log(f"Erro nos filtros: {str(e)}", "ERROR")
            return False
    
    def test_exportacao_json(self) -> bool:
        """Teste 4: Exportação JSON"""
        self.log("Teste 4: Exportação JSON", "TEST")
        
        try:
            response = requests.get(
                f"{self.api_url}/export",
                params={"formato": "json", "medicamento": "teste"},
                timeout=10
            )
            
            # 200 (dados) ou 404 (sem dados) são aceitáveis
            if response.status_code in [200, 404]:
                self.log("Exportação JSON funcionando", "SUCCESS")
                return True
            else:
                self.log(f"Exportação retornou status {response.status_code}", "WARNING")
                return False
                
        except Exception as e:
            self.log(f"Erro na exportação: {str(e)}", "ERROR")
            return False
    
    def test_exportacao_csv(self) -> bool:
        """Teste 5: Exportação CSV"""
        self.log("Teste 5: Exportação CSV", "TEST")
        
        try:
            response = requests.get(
                f"{self.api_url}/export",
                params={"formato": "csv", "medicamento": "teste"},
                timeout=10
            )
            
            # 200 (dados) ou 404 (sem dados) são aceitáveis
            if response.status_code in [200, 404]:
                self.log("Exportação CSV funcionando", "SUCCESS")
                return True
            else:
                self.log(f"Exportação CSV retornou status {response.status_code}", "WARNING")
                return False
                
        except Exception as e:
            self.log(f"Erro na exportação CSV: {str(e)}", "ERROR")
            return False
    
    def test_dashboard_saude(self) -> bool:
        """Teste 6: Dashboard de Saúde"""
        self.log("Teste 6: Dashboard de Saúde", "TEST")
        
        try:
            response = requests.get(
                f"{self.api_url}/status/scrapers",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                status_geral = data.get('status_geral', 'UNKNOWN')
                total_fontes = data.get('total_fontes', 0)
                self.log(f"Dashboard ativo: {status_geral}, {total_fontes} fontes", "SUCCESS")
                return True
            else:
                self.log(f"Dashboard retornou status {response.status_code}", "WARNING")
                return False
                
        except Exception as e:
            self.log(f"Erro no dashboard: {str(e)}", "ERROR")
            return False
    
    def test_gerenciamento_listas(self) -> bool:
        """Teste 7: Gerenciamento de Listas"""
        self.log("Teste 7: Gerenciamento de Listas", "TEST")
        
        try:
            # Listar listas existentes
            response = requests.get(
                f"{self.api_url}/listas",
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('total', 0)
                self.log(f"Listas acessíveis: {total} lista(s)", "SUCCESS")
                return True
            else:
                self.log(f"Listas retornaram status {response.status_code}", "WARNING")
                return False
                
        except Exception as e:
            self.log(f"Erro nas listas: {str(e)}", "ERROR")
            return False
    
    def test_frontend_carregamento(self) -> bool:
        """Teste 8: Frontend Carrega"""
        self.log("Teste 8: Frontend Carregamento", "TEST")
        
        try:
            response = requests.get(self.base_url, timeout=10)
            
            if response.status_code == 200:
                html = response.text
                
                # Verificar elementos críticos
                checks = {
                    'React': 'root' in html or 'react' in html.lower(),
                    'Título': 'GSM' in html or 'Buscador' in html,
                    'Assets': '.js' in html or '.css' in html
                }
                
                if all(checks.values()):
                    self.log("Frontend carregando corretamente", "SUCCESS")
                    return True
                else:
                    failed = [k for k, v in checks.items() if not v]
                    self.log(f"Frontend com problemas: {', '.join(failed)}", "WARNING")
                    return False
            else:
                self.log(f"Frontend retornou status {response.status_code}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Erro ao carregar frontend: {str(e)}", "ERROR")
            return False
    
    def test_performance(self) -> bool:
        """Teste 9: Performance da Busca"""
        self.log("Teste 9: Performance (<15s)", "TEST")
        
        try:
            start = time.time()
            
            payload = {"medicamento": "teste"}
            response = requests.post(
                f"{self.api_url}/search",
                json=payload,
                timeout=20
            )
            
            elapsed = time.time() - start
            
            if response.status_code == 200 and elapsed < 15:
                self.log(f"Performance OK: {elapsed:.2f}s (meta: <15s)", "SUCCESS")
                return True
            elif elapsed >= 15:
                self.log(f"Performance degradada: {elapsed:.2f}s", "WARNING")
                return False
            else:
                self.log(f"Erro no teste de performance", "WARNING")
                return False
                
        except Exception as e:
            self.log(f"Erro no teste de performance: {str(e)}", "ERROR")
            return False
    
    def test_endpoints_auxiliares(self) -> bool:
        """Teste 10: Endpoints Auxiliares"""
        self.log("Teste 10: Endpoints Auxiliares", "TEST")
        
        try:
            # Testar /api/states
            response_states = requests.get(f"{self.api_url}/states", timeout=10)
            states_ok = response_states.status_code == 200
            
            # Testar /api/stats
            response_stats = requests.get(f"{self.api_url}/stats", timeout=10)
            stats_ok = response_stats.status_code == 200
            
            if states_ok and stats_ok:
                self.log("Endpoints auxiliares funcionando", "SUCCESS")
                return True
            else:
                self.log("Alguns endpoints auxiliares com problemas", "WARNING")
                return False
                
        except Exception as e:
            self.log(f"Erro nos endpoints auxiliares: {str(e)}", "ERROR")
            return False
    
    def run_all_tests(self) -> Dict:
        """Executa todos os smoke tests"""
        self.log("=" * 70)
        self.log("🚀 INICIANDO SMOKE TESTS DE PRODUÇÃO - GSM V3.0")
        self.log(f"🌐 URL: {self.base_url}")
        self.log("=" * 70)
        
        self.start_time = time.time()
        
        # Executar testes
        tests = [
            ("Health Check", self.test_health_check),
            ("Busca Simples", self.test_busca_simples),
            ("Filtros Avançados", self.test_filtros_avancados),
            ("Exportação JSON", self.test_exportacao_json),
            ("Exportação CSV", self.test_exportacao_csv),
            ("Dashboard Saúde", self.test_dashboard_saude),
            ("Gerenciamento Listas", self.test_gerenciamento_listas),
            ("Frontend", self.test_frontend_carregamento),
            ("Performance", self.test_performance),
            ("Endpoints Auxiliares", self.test_endpoints_auxiliares)
        ]
        
        results = {}
        for name, test_func in tests:
            try:
                results[name] = test_func()
            except Exception as e:
                self.log(f"Erro crítico no teste '{name}': {str(e)}", "ERROR")
                results[name] = False
            
            time.sleep(0.5)  # Pequeno delay entre testes
        
        # Relatório Final
        elapsed = time.time() - self.start_time
        
        self.log("")
        self.log("=" * 70)
        self.log("📊 RELATÓRIO FINAL DOS SMOKE TESTS")
        self.log("=" * 70)
        
        passed = sum(1 for v in results.values() if v)
        failed = len(results) - passed
        success_rate = (passed / len(results)) * 100 if results else 0
        
        for test_name, result in results.items():
            status = "✅ PASSOU" if result else "❌ FALHOU"
            self.log(f"  {status} - {test_name}")
        
        self.log("")
        self.log(f"📈 RESUMO:")
        self.log(f"  ✅ Passou: {passed}/{len(results)} ({success_rate:.1f}%)")
        self.log(f"  ❌ Falhou: {failed}/{len(results)}")
        self.log(f"  ⏱️  Tempo Total: {elapsed:.2f}s")
        
        # Critério de aprovação
        if success_rate >= 80:
            self.log("")
            self.log("🎉 DEPLOY VALIDADO COM SUCESSO!", "SUCCESS")
            self.log(f"  Sistema em produção está operacional ({success_rate:.1f}%)")
            approval = "APROVADO"
        elif success_rate >= 60:
            self.log("")
            self.log("⚠️  DEPLOY PARCIALMENTE FUNCIONAL", "WARNING")
            self.log(f"  Alguns componentes precisam de atenção")
            approval = "PARCIAL"
        else:
            self.log("")
            self.log("❌ DEPLOY COM PROBLEMAS CRÍTICOS", "ERROR")
            self.log(f"  Recomenda-se investigação imediata")
            approval = "REPROVADO"
        
        self.log("=" * 70)
        
        return {
            "results": results,
            "passed": passed,
            "failed": failed,
            "success_rate": success_rate,
            "elapsed_time": elapsed,
            "approval": approval
        }


def main():
    if len(sys.argv) < 2:
        print("❌ Uso: python3 smoke_tests_producao.py <URL_PRODUCAO>")
        print("   Exemplo: python3 smoke_tests_producao.py https://gsm.emergentagent.com")
        sys.exit(1)
    
    production_url = sys.argv[1]
    
    tester = ProductionSmokeTests(production_url)
    report = tester.run_all_tests()
    
    # Exit code baseado no resultado
    if report['approval'] == 'APROVADO':
        sys.exit(0)
    elif report['approval'] == 'PARCIAL':
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
