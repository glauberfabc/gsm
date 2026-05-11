# 🚀 BEM v3.0 - PLANO DE DESENVOLVIMENTO
## Roadmap de Expansão e Otimização

**Versão:** 3.0  
**Data de Criação:** 08/12/2024  
**Status:** PLANEJAMENTO  
**Pré-requisito:** Deploy bem-sucedido da v2.0  

---

## 📋 ÍNDICE
1. [Visão Geral](#visão-geral)
2. [Prioridades e Cronograma](#prioridades-e-cronograma)
3. [P1: Implementação BEC SP Real](#p1-implementação-bec-sp-real)
4. [P2: Expansão Scrapers Estaduais](#p2-expansão-scrapers-estaduais)
5. [P3: Dashboard de Saúde do Sistema](#p3-dashboard-de-saúde-do-sistema)
6. [P4: Exportação de Resultados](#p4-exportação-de-resultados)
7. [P5: Features Futuras](#p5-features-futuras)
8. [Estimativas de Tempo](#estimativas-de-tempo)
9. [Critérios de Aceitação](#critérios-de-aceitação)

---

## 🎯 VISÃO GERAL

### Objetivo da v3.0
Transformar o BEM de uma **estrutura hierárquica funcional (v2.0)** para um **agregador completo com cobertura real de dados (v3.0)**.

**Meta Principal:** Passar de "Estrutura Implementada" para "Cobertura Real Funcionando"

**Pilares da v3.0:**
- ✅ Cobertura real de São Paulo (BEC SP com Playwright)
- ✅ Scrapers estaduais funcionais com links diretos (navegação dupla)
- ✅ Monitoramento de saúde do sistema (dashboard operacional)
- ✅ Exportação de dados para análise (CSV/JSON)

### Estado Atual (v2.0 - Deployment Ready)
- ✅ Arquitetura hierárquica implementada e testada
- ✅ PNCP + ComprasNet integrados (APIs públicas com limitações de acesso)
- ✅ BEC SP estruturado (retorna vazio - aguardando implementação real)
- ✅ Interface v2.0 com 7 filtros avançados
- ✅ Listas customizadas funcionais (CRUD completo)
- ✅ Modelo de dados expandido (23+ campos)
- ✅ Ordenação por urgência implementada
- ✅ Testes E2E: 8/10 passou (backend 9/10)

### Limitações a Resolver na v3.0
1. 🔴 **CRÍTICO:** BEC SP retorna vazio (scraping de SPA complexo pendente)
2. 🔴 **CRÍTICO:** Scrapers estaduais não extraem links diretos para PDFs
3. 🟡 **IMPORTANTE:** Sem visibilidade de saúde do sistema (não sabemos se scrapers estão UP/DOWN)
4. 🟡 **IMPORTANTE:** Impossível exportar resultados para análise externa
5. 🟢 **DESEJÁVEL:** Apenas 3 estados (CE, ES, SP) - expandir para 27

---

## 📊 PRIORIDADES E CRONOGRAMA

| Prioridade | Feature | Tempo Estimado | Impacto | Status |
|------------|---------|----------------|---------|--------|
| **P1** | BEC SP Real | 2-3 horas | 🔥 ALTO | Planejado |
| **P2** | Scrapers Estaduais | 3-4 horas | 🔥 ALTO | Planejado |
| **P3** | Dashboard Status | 1-2 horas | 🟡 MÉDIO | Planejado |
| **P4** | Exportação Dados | 1 hora | 🟡 MÉDIO | Planejado |
| **P5** | Features Futuras | Variável | 🟢 BAIXO | Backlog |

**Tempo Total Estimado:** 7-10 horas de desenvolvimento

---

## 🔥 P1: IMPLEMENTAÇÃO BEC SP REAL

### 1.1 Contexto
O cliente BEC SP (`bec_sp_client.py`) está estruturado mas retorna vazio porque o portal BEC é um sistema complexo (SPA com JavaScript) que requer navegação avançada.

### 1.2 Opções Técnicas

#### **OPÇÃO A: Selenium/Playwright** (Recomendada)
**Vantagens:**
- ✅ Simula navegação real do usuário
- ✅ Lida com JavaScript automaticamente
- ✅ Pode capturar dados dinâmicos
- ✅ Não requer autenticação/credenciais

**Desvantagens:**
- ❌ Mais lento (2-5 segundos por página)
- ❌ Requer browser headless (Chrome/Firefox)
- ❌ Pode quebrar se o portal mudar layout

**Arquitetura:**
```python
# /app/backend/scrapers/bec_sp_client_real.py

from playwright.sync_api import sync_playwright
import logging

class BECSpClientReal:
    def __init__(self):
        self.base_url = 'https://www.bec.sp.gov.br'
        self.playwright = None
        self.browser = None
        
    def _init_browser(self):
        """Inicia browser headless"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        
    def buscar_licitacoes(self, termo: str, limit: int = 15):
        """Busca com navegação real"""
        try:
            page = self.browser.new_page()
            
            # PASSO 1: Acessar portal de consulta
            page.goto(f'{self.base_url}/BECSP/Consultas/Edital/Consultar_Edital.aspx')
            
            # PASSO 2: Preencher formulário de busca
            page.fill('#txtPalavraChave', termo)
            page.select_option('#ddlSituacao', 'Aberto')
            
            # PASSO 3: Submeter busca
            page.click('#btnBuscar')
            page.wait_for_load_state('networkidle')
            
            # PASSO 4: Extrair resultados
            resultados = []
            rows = page.query_selector_all('.grid-row')
            
            for row in rows[:limit]:
                # Extrair dados de cada linha
                numero = row.query_selector('.numero').inner_text()
                orgao = row.query_selector('.orgao').inner_text()
                
                # PASSO 5: Navegar para página de detalhes
                link_detalhes = row.query_selector('a.detalhes')
                detail_url = link_detalhes.get_attribute('href')
                
                # Abrir nova aba para detalhes
                detail_page = self.browser.new_page()
                detail_page.goto(detail_url)
                
                # PASSO 6: Extrair link direto do PDF (NAVEGAÇÃO DUPLA)
                pdf_link = detail_page.query_selector('a.download-edital')
                link_documento = pdf_link.get_attribute('href') if pdf_link else None
                
                # Extrair itens
                itens = self._extrair_itens(detail_page)
                
                detail_page.close()
                
                # Montar estrutura de dados
                resultados.append({
                    'medicamento': termo,
                    'estado': 'SP',
                    'orgao_licitante': orgao,
                    'numero_processo': numero,
                    'link_origem': detail_url,
                    'link_documento': link_documento,  # PDF DIRETO
                    'itens': itens,
                    'fonte': 'BEC-SP',
                    'esfera': 'Estadual',
                    # ... demais campos
                })
            
            page.close()
            return resultados
            
        except Exception as e:
            logging.error(f"Erro BEC SP: {str(e)}")
            return []
    
    def _extrair_itens(self, page):
        """Extrai itens da tabela de detalhes"""
        itens = []
        rows = page.query_selector_all('.tabela-itens tr')
        for row in rows[1:]:  # Skip header
            cols = row.query_selector_all('td')
            if len(cols) >= 3:
                itens.append({
                    'numero': int(cols[0].inner_text()),
                    'descricao': cols[1].inner_text(),
                    'quantidade': float(cols[2].inner_text())
                })
        return itens
    
    def __del__(self):
        """Cleanup"""
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
```

**Dependências:**
```bash
pip install playwright
playwright install chromium
```

**Tempo Estimado:** 2-3 horas (desenvolvimento + testes)

---

#### **OPÇÃO B: Web Service SOAP**
**Vantagens:**
- ✅ Mais rápido (requisições diretas)
- ✅ Mais estável (API oficial)
- ✅ Documentado pelo governo

**Desvantagens:**
- ❌ Requer autenticação/credenciais
- ❌ SOAP é mais complexo que REST
- ❌ Precisa de biblioteca específica (zeep)

**Arquitetura:**
```python
# /app/backend/scrapers/bec_sp_soap_client.py

from zeep import Client
from zeep.wsse.username import UsernameToken

class BECSpSOAPClient:
    def __init__(self):
        self.wsdl = 'https://www.bec.sp.gov.br/BecWS/WSConsulta.asmx?WSDL'
        self.username = os.getenv('BEC_SP_USERNAME')
        self.password = os.getenv('BEC_SP_PASSWORD')
        
    def buscar_licitacoes(self, termo: str, limit: int = 15):
        client = Client(
            self.wsdl,
            wsse=UsernameToken(self.username, self.password)
        )
        
        # Chamar método do Web Service
        resultado = client.service.ConsultarEditais(
            palavraChave=termo,
            situacao='Aberto',
            dataInicio='2024-01-01',
            dataFim='2025-12-31'
        )
        
        # Processar XML retornado
        # ...
```

**Dependências:**
```bash
pip install zeep
```

**Tempo Estimado:** 3-4 horas (requer credenciais + aprender SOAP)

---

### 1.3 Recomendação

**Implementar OPÇÃO A (Playwright)** porque:
1. ✅ Não requer credenciais (público)
2. ✅ Mais flexível para adaptações futuras
3. ✅ Equipe já tem experiência com scraping
4. ✅ Pode ser reutilizado para outros portais

**Plano de Implementação:**
```
Dia 1 (1h):
- Instalar Playwright
- Analisar estrutura HTML do portal BEC
- Identificar seletores CSS dos elementos

Dia 2 (1-2h):
- Implementar navegação e extração
- Testar com diferentes medicamentos
- Validar estrutura de dados

Dia 3 (30min):
- Integrar no scraper_service.py
- Testes E2E
- Deploy
```

---

## 🗺️ P2: EXPANSÃO SCRAPERS ESTADUAIS

### 2.1 Objetivo
Transformar os 3 scrapers básicos (CE, ES, SP) em scrapers **completos com navegação dupla** e expandir para mais estados.

### 2.2 Template Reutilizável

Criar um **BaseEstadualScraper** que todos os estados herdam:

```python
# /app/backend/scrapers/base_estadual_scraper.py

from abc import ABC, abstractmethod
from typing import List, Dict
import requests
from bs4 import BeautifulSoup

class BaseEstadualScraper(ABC):
    """
    Template base para scrapers estaduais.
    
    Implementa navegação dupla automaticamente.
    Cada estado precisa apenas definir os seletores CSS.
    """
    
    def __init__(self):
        self.estado = None  # Definir na subclasse
        self.base_url = None
        self.session = requests.Session()
    
    @abstractmethod
    def get_search_url(self, termo: str) -> str:
        """Retorna URL de busca com o termo"""
        pass
    
    @abstractmethod
    def get_selectors(self) -> Dict:
        """
        Retorna dicionário com seletores CSS.
        
        Exemplo:
        {
            'result_row': '.licitacao-row',
            'numero': '.numero-processo',
            'orgao': '.orgao-nome',
            'link_detalhes': 'a.ver-detalhes',
            'link_pdf': 'a.download-edital',
            'tabela_itens': '.itens-licitacao tr'
        }
        """
        pass
    
    def buscar_medicamento(self, termo: str, limit: int = 10) -> List[Dict]:
        """
        Método principal de busca.
        Implementa navegação dupla automaticamente.
        """
        resultados = []
        
        # ETAPA 1: Buscar na listagem
        search_url = self.get_search_url(termo)
        response = self.session.get(search_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        selectors = self.get_selectors()
        rows = soup.select(selectors['result_row'])
        
        for row in rows[:limit]:
            try:
                # Extrair dados básicos
                numero = row.select_one(selectors['numero']).text.strip()
                orgao = row.select_one(selectors['orgao']).text.strip()
                link_detalhes_elem = row.select_one(selectors['link_detalhes'])
                link_detalhes = link_detalhes_elem['href']
                
                # ETAPA 2: Navegar para detalhes (NAVEGAÇÃO DUPLA)
                detail_response = self.session.get(link_detalhes)
                detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
                
                # ETAPA 3: Extrair link direto do PDF
                pdf_elem = detail_soup.select_one(selectors['link_pdf'])
                link_documento = pdf_elem['href'] if pdf_elem else None
                
                # ETAPA 4: Extrair itens
                itens = self._extrair_itens(detail_soup, selectors)
                
                # Montar estrutura
                resultados.append({
                    'medicamento': termo,
                    'estado': self.estado,
                    'orgao_licitante': orgao,
                    'numero_processo': numero,
                    'link_origem': link_detalhes,
                    'link_documento': link_documento,  # PDF DIRETO
                    'itens': itens,
                    'fonte': 'estadual',
                    'esfera': 'Estadual',
                    # ... demais campos padrão
                })
                
            except Exception as e:
                logging.warning(f"Erro ao processar linha: {str(e)}")
                continue
        
        return resultados
    
    def _extrair_itens(self, soup, selectors) -> List[Dict]:
        """Extrai itens da tabela"""
        itens = []
        rows = soup.select(selectors['tabela_itens'])
        for row in rows[1:]:  # Skip header
            cols = row.find_all('td')
            if len(cols) >= 3:
                itens.append({
                    'numero': int(cols[0].text.strip()),
                    'descricao': cols[1].text.strip(),
                    'quantidade': self._parse_number(cols[2].text)
                })
        return itens
    
    @staticmethod
    def _parse_number(text: str) -> float:
        """Converte texto para número"""
        try:
            return float(text.replace('.', '').replace(',', '.'))
        except:
            return 0.0
```

**Exemplo de Implementação por Estado:**

```python
# /app/backend/scrapers/estados/ceara_scraper.py

from scrapers.base_estadual_scraper import BaseEstadualScraper

class CearaScraper(BaseEstadualScraper):
    def __init__(self):
        super().__init__()
        self.estado = 'CE'
        self.base_url = 'https://licitacoes.seplag.ce.gov.br'
    
    def get_search_url(self, termo: str) -> str:
        return f'{self.base_url}/busca?q={termo}&tipo=medicamento'
    
    def get_selectors(self) -> Dict:
        return {
            'result_row': '.resultado-licitacao',
            'numero': '.num-processo',
            'orgao': '.orgao',
            'link_detalhes': 'a.btn-detalhes',
            'link_pdf': 'a.btn-download-edital',
            'tabela_itens': 'table.itens tbody tr'
        }
```

### 2.3 Estados Prioritários

**Fase 1 (Imediato):**
- ✅ CE - Ceará (melhorar existente)
- ✅ ES - Espírito Santo (melhorar existente)
- ✅ SP - São Paulo (melhorar existente)

**Fase 2 (Médio prazo):**
- 🆕 RJ - Rio de Janeiro (alto volume)
- 🆕 MG - Minas Gerais (alto volume)
- 🆕 BA - Bahia (alto volume)
- 🆕 PR - Paraná (alto volume)

**Fase 3 (Longo prazo):**
- Demais 20 estados

**Tempo Estimado:**
- Fase 1: 3-4 horas (melhorar 3 existentes + template)
- Fase 2: 1h por estado (4 horas total)
- Fase 3: 30min por estado (10 horas total)

---

## 📊 P3: DASHBOARD DE SAÚDE DO SISTEMA

### 3.1 Objetivo
Criar visibilidade sobre o **status de funcionamento** de cada agregador e scraper.

### 3.2 Backend: Endpoint de Status

```python
# /app/backend/server.py

from datetime import datetime, timedelta
from typing import Dict

# Cache de status em memória (ou Redis)
status_cache = {
    'pncp': {'status': 'UNKNOWN', 'last_check': None, 'last_success': None},
    'comprasnet': {'status': 'UNKNOWN', 'last_check': None, 'last_success': None},
    'bec_sp': {'status': 'UNKNOWN', 'last_check': None, 'last_success': None},
    'estados': {}
}

@api_router.get("/status/scrapers")
async def get_scrapers_status():
    """
    Retorna status de saúde de todos os scrapers.
    
    Status possíveis:
    - UP: Funcionando (última busca < 1h com sucesso)
    - DOWN: Offline (última tentativa falhou)
    - DEGRADED: Parcial (funcionando mas lento)
    - UNKNOWN: Sem dados (nunca testado)
    """
    
    # Verificar cada fonte
    status_response = {}
    
    # PNCP
    pncp_status = await _check_scraper_health(
        'pncp',
        scraper_service.buscar_apenas_pncp,
        'insulina'
    )
    status_response['pncp'] = pncp_status
    
    # ComprasNet
    comprasnet_status = await _check_scraper_health(
        'comprasnet',
        scraper_service.buscar_apenas_comprasnet,
        'insulina'
    )
    status_response['comprasnet'] = comprasnet_status
    
    # BEC SP
    bec_status = await _check_scraper_health(
        'bec_sp',
        scraper_service.buscar_apenas_bec_sp,
        'insulina'
    )
    status_response['bec_sp'] = bec_status
    
    # Estados
    estados_status = {}
    for estado in ['CE', 'ES', 'SP']:
        estado_status = await _check_scraper_health(
            f'estado_{estado}',
            lambda: scraper_service.refresh_estado(estado, 'insulina'),
            'insulina'
        )
        estados_status[estado] = estado_status
    
    status_response['estados'] = estados_status
    
    # Estatísticas gerais
    stats = await db.licitacoes.aggregate([
        {
            '$match': {
                'created_at': {'$gte': datetime.now() - timedelta(hours=24)}
            }
        },
        {
            '$group': {
                '_id': '$fonte',
                'count': {'$sum': 1}
            }
        }
    ]).to_list(100)
    
    status_response['stats_24h'] = {
        item['_id']: item['count'] for item in stats
    }
    
    return status_response

async def _check_scraper_health(name: str, scraper_func, test_term: str) -> Dict:
    """
    Testa saúde de um scraper específico.
    """
    try:
        start_time = datetime.now()
        
        # Tentar busca de teste
        resultados = await scraper_func(test_term, limit=1)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Determinar status
        if len(resultados) > 0:
            status = 'UP'
        elif elapsed > 10:
            status = 'DEGRADED'
        else:
            status = 'DOWN'
        
        # Atualizar cache
        status_cache[name] = {
            'status': status,
            'last_check': datetime.now(),
            'last_success': datetime.now() if status == 'UP' else status_cache[name].get('last_success'),
            'response_time': elapsed,
            'results_count': len(resultados)
        }
        
        return status_cache[name]
        
    except Exception as e:
        status_cache[name] = {
            'status': 'DOWN',
            'last_check': datetime.now(),
            'last_error': str(e)
        }
        return status_cache[name]
```

### 3.3 Frontend: Página de Status

```javascript
// /app/frontend/src/pages/SystemStatus.js

import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function SystemStatus() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 60000); // Atualizar a cada 1min
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/status/scrapers`);
      setStatus(response.data);
      setLoading(false);
    } catch (error) {
      console.error('Erro ao buscar status:', error);
    }
  };

  const getStatusColor = (st) => {
    const colors = {
      'UP': 'bg-green-100 text-green-800 border-green-300',
      'DOWN': 'bg-red-100 text-red-800 border-red-300',
      'DEGRADED': 'bg-yellow-100 text-yellow-800 border-yellow-300',
      'UNKNOWN': 'bg-gray-100 text-gray-800 border-gray-300'
    };
    return colors[st] || colors['UNKNOWN'];
  };

  if (loading) return <div>Carregando status...</div>;

  return (
    <div className="max-w-7xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Status do Sistema</h1>
      
      {/* Agregadores Nacionais */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4">Agregadores Nacionais</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          
          {/* PNCP */}
          <div className={`border-2 rounded-lg p-4 ${getStatusColor(status.pncp.status)}`}>
            <h3 className="font-bold mb-2">PNCP</h3>
            <div className="text-sm space-y-1">
              <p>Status: <span className="font-semibold">{status.pncp.status}</span></p>
              {status.pncp.response_time && (
                <p>Tempo: {status.pncp.response_time.toFixed(2)}s</p>
              )}
              {status.pncp.last_success && (
                <p className="text-xs text-gray-600">
                  Último sucesso: {new Date(status.pncp.last_success).toLocaleString('pt-BR')}
                </p>
              )}
            </div>
          </div>
          
          {/* ComprasNet */}
          <div className={`border-2 rounded-lg p-4 ${getStatusColor(status.comprasnet.status)}`}>
            <h3 className="font-bold mb-2">ComprasNet/SIASG</h3>
            <div className="text-sm space-y-1">
              <p>Status: <span className="font-semibold">{status.comprasnet.status}</span></p>
              {status.comprasnet.response_time && (
                <p>Tempo: {status.comprasnet.response_time.toFixed(2)}s</p>
              )}
            </div>
          </div>
          
          {/* BEC SP */}
          <div className={`border-2 rounded-lg p-4 ${getStatusColor(status.bec_sp.status)}`}>
            <h3 className="font-bold mb-2">BEC SP</h3>
            <div className="text-sm space-y-1">
              <p>Status: <span className="font-semibold">{status.bec_sp.status}</span></p>
              {status.bec_sp.response_time && (
                <p>Tempo: {status.bec_sp.response_time.toFixed(2)}s</p>
              )}
            </div>
          </div>
          
        </div>
      </div>
      
      {/* Scrapers Estaduais */}
      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <h2 className="text-xl font-semibold mb-4">Scrapers Estaduais</h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {Object.entries(status.estados).map(([uf, data]) => (
            <div key={uf} className={`border-2 rounded-lg p-3 text-center ${getStatusColor(data.status)}`}>
              <p className="font-bold">{uf}</p>
              <p className="text-xs mt-1">{data.status}</p>
            </div>
          ))}
        </div>
      </div>
      
      {/* Estatísticas 24h */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4">Resultados (Últimas 24h)</h2>
        <div className="space-y-2">
          {Object.entries(status.stats_24h || {}).map(([fonte, count]) => (
            <div key={fonte} className="flex justify-between items-center">
              <span className="font-medium">{fonte}</span>
              <span className="bg-blue-100 text-blue-800 px-3 py-1 rounded-full">
                {count} resultados
              </span>
            </div>
          ))}
        </div>
      </div>
      
    </div>
  );
}
```

**Adicionar rota no App.js:**
```javascript
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import SystemStatus from './pages/SystemStatus';

// No return:
<Router>
  <Routes>
    <Route path="/" element={<App />} />
    <Route path="/status" element={<SystemStatus />} />
  </Routes>
</Router>
```

**Tempo Estimado:** 1-2 horas

---

## 📥 P4: EXPORTAÇÃO DE RESULTADOS

### 4.1 Backend: Endpoint de Exportação

```python
# /app/backend/server.py

import csv
import io
from fastapi.responses import StreamingResponse

@api_router.post("/export")
async def exportar_resultados(query: SearchQuery, formato: str = 'csv'):
    """
    Exporta resultados de busca em CSV ou JSON.
    
    Aceita os mesmos parâmetros da busca normal.
    """
    try:
        # Executar busca (reutilizar lógica existente)
        # ... (código de busca igual ao /search)
        
        if formato == 'csv':
            return _export_csv(resultados)
        elif formato == 'json':
            return _export_json(resultados)
        else:
            raise HTTPException(status_code=400, detail="Formato inválido")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _export_csv(resultados: List[Dict]) -> StreamingResponse:
    """Exporta para CSV"""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        'medicamento', 'estado', 'status', 'orgao_licitante',
        'modalidade', 'numero_processo', 'data_final',
        'fonte', 'esfera', 'link_origem', 'link_documento'
    ])
    
    writer.writeheader()
    for r in resultados:
        # Flatten dados
        row = {
            'medicamento': r.get('medicamento'),
            'estado': r.get('estado'),
            'status': r.get('status'),
            'orgao_licitante': r.get('orgao_licitante'),
            'modalidade': r.get('modalidade'),
            'numero_processo': r.get('numero_processo'),
            'data_final': r.get('data_final').isoformat() if r.get('data_final') else '',
            'fonte': r.get('fonte'),
            'esfera': r.get('esfera'),
            'link_origem': r.get('link_origem'),
            'link_documento': r.get('link_documento', '')
        }
        writer.writerow(row)
    
    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=bem_resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        }
    )

def _export_json(resultados: List[Dict]) -> StreamingResponse:
    """Exporta para JSON"""
    import json
    
    # Converter datetime para string
    def serialize(obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj
    
    json_data = json.dumps(resultados, default=serialize, ensure_ascii=False, indent=2)
    
    return StreamingResponse(
        iter([json_data]),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=bem_resultados_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        }
    )
```

### 4.2 Frontend: Botão de Exportação

```javascript
// No App.js, adicionar na seção de resultados:

const handleExportar = async (formato) => {
  try {
    const payload = {
      medicamento: medicamento.trim() || null,
      tags: tagsFiltro.length > 0 ? tagsFiltro : null,
      apenas_reais: apenasReais,
      apenas_futuras: apenasFuturas,
      lista_id: listaSelecionada?.id || null,
      status_filtro: statusFiltro !== 'Todas' ? statusFiltro : null,
      modalidade_filtro: modalidadeFiltro.length > 0 ? modalidadeFiltro : null,
      esfera_filtro: esferaFiltro || null
    };

    const response = await axios.post(
      `${API}/export?formato=${formato}`,
      payload,
      { responseType: 'blob' }
    );

    // Download do arquivo
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `bem_resultados.${formato}`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    
    alert(`Arquivo ${formato.toUpperCase()} baixado com sucesso!`);
  } catch (error) {
    console.error('Erro ao exportar:', error);
    alert('Erro ao exportar resultados.');
  }
};

// No JSX, após os resultados:
{!loading && resultados.length > 0 && (
  <div className="flex gap-3 mt-6">
    <button
      onClick={() => handleExportar('csv')}
      className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium"
    >
      📊 Exportar CSV
    </button>
    <button
      onClick={() => handleExportar('json')}
      className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors font-medium"
    >
      📄 Exportar JSON
    </button>
  </div>
)}
```

**Tempo Estimado:** 1 hora

---

## 🔮 P5: FEATURES FUTURAS (Backlog)

### 5.1 Notificações de Novas Licitações
- Email/SMS quando nova licitação de medicamento da lista customizada aparecer
- Webhook para integração com outros sistemas
**Tempo:** 2-3 horas

### 5.2 Histórico de Preços
- Armazenar valores de licitações antigas
- Gráfico de evolução de preços por medicamento
**Tempo:** 3-4 horas

### 5.3 API Pública
- Endpoint REST público para terceiros consultarem
- Rate limiting e autenticação por API key
**Tempo:** 2-3 horas

### 5.4 App Mobile
- React Native para iOS/Android
- Notificações push
**Tempo:** 20-30 horas

### 5.5 Integração com Diário Oficial
- Buscar em diários oficiais estaduais
- Fonte adicional de dados
**Tempo:** 5-8 horas

---

## ⏱️ ESTIMATIVAS DE TEMPO

### Cronograma Realista

| Semana | Prioridade | Features | Horas | Acumulado |
|--------|------------|----------|-------|-----------|
| 1 | P1 | BEC SP Real (Playwright) | 2-3h | 2-3h |
| 2 | P2 | Template Base + Melhorar 3 estados | 3-4h | 5-7h |
| 3 | P3 | Dashboard Status | 1-2h | 6-9h |
| 4 | P4 | Exportação CSV/JSON | 1h | 7-10h |

**Total V3.0 Core:** 7-10 horas

### Cronograma Extenso (com Fase 2 de P2)

| Semana | Features | Horas | Acumulado |
|--------|----------|-------|-----------|
| 5-6 | 4 novos estados (RJ, MG, BA, PR) | 4h | 11-14h |

**Total V3.0 Completo:** 11-14 horas

---

## ✅ CRITÉRIOS DE ACEITAÇÃO

### P1 (BEC SP Real)
- [ ] Cliente BEC SP retorna pelo menos 1 resultado real para "insulina"
- [ ] Links diretos para PDF funcionam (não quebram)
- [ ] Itens da licitação são extraídos corretamente
- [ ] Tempo de resposta < 10 segundos por busca
- [ ] Integrado no fluxo de busca hierárquica

### P2 (Scrapers Estaduais)
- [ ] Template base implementado e funcional
- [ ] 3 estados (CE, ES, SP) extraem links diretos de PDF
- [ ] Itens da licitação extraídos em todos os estados
- [ ] Testes E2E passam para os 3 estados

### P3 (Dashboard Status)
- [ ] Endpoint `/status/scrapers` retorna JSON correto
- [ ] Página de status acessível em `/status`
- [ ] Atualização automática a cada 1 minuto
- [ ] Cores corretas para cada status (UP/DOWN/DEGRADED)

### P4 (Exportação)
- [ ] Exportação CSV funciona e arquivo abre no Excel
- [ ] Exportação JSON válida (valida no jsonlint.com)
- [ ] Botões visíveis na interface
- [ ] Filename com timestamp

---

## 🎯 PRÓXIMOS PASSOS

### Após Deploy da v2.0:

1. **Coletar Feedback (1-2 semanas)**
   - Usuários reais testam o sistema
   - Identificar prioridades reais vs planejadas
   - Ajustar roadmap baseado em uso

2. **Priorizar P1**
   - Se BEC SP for crítico → Começar imediatamente
   - Se scrapers estaduais mais importantes → Ajustar ordem

3. **Executar em Sprints**
   - Sprint 1 (1 semana): P1
   - Sprint 2 (1 semana): P2 Fase 1
   - Sprint 3 (1 semana): P3 + P4
   - Sprint 4 (2 semanas): P2 Fase 2

4. **Deploy Incremental**
   - Deploy de cada P assim que completada
   - Não esperar v3.0 completa para fazer deploy

---

## 📞 CONTATO E SUPORTE

Para dúvidas sobre este roadmap:
- Revisar este documento
- Consultar código existente em `/app/backend` e `/app/frontend`
- Testar localmente antes de fazer deploy

---

**Documento criado em:** 08/12/2024  
**Versão:** 1.0  
**Status:** PRONTO PARA EXECUÇÃO  

**Próxima atualização:** Após deploy da v2.0 e coleta de feedback

---

## 🎉 CONCLUSÃO

O BEM v3.0 transformará o sistema de uma **estrutura hierárquica funcional** em um **agregador completo e robusto de licitações de medicamentos** com cobertura nacional real.

As prioridades estão claras, as estimativas são realistas e a arquitetura está preparada para expansão.

**O próximo passo é:** Deploy da v2.0 → Feedback → Executar v3.0!

Boa sorte! 🚀
