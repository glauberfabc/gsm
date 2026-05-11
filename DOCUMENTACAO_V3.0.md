# 📚 GSM V3.0 - Documentação Completa

## Buscador de Editais - Documentação Técnica e de Usuário

---

## 📖 ÍNDICE

1. [Visão Geral](#visão-geral)
2. [Novidades V3.0](#novidades-v30)
3. [Guia do Usuário](#guia-do-usuário)
4. [Documentação Técnica](#documentação-técnica)
5. [API Reference](#api-reference)
6. [Troubleshooting](#troubleshooting)

---

## 🎯 VISÃO GERAL

O **GSM - Buscador de Editais** é um agregador nacional de licitações públicas que consolida dados de múltiplas fontes governamentais em uma única interface.

### Cobertura

- **Nacional**: PNCP (Portal Nacional de Contratações Públicas)
- **Federal**: ComprasNet/SIASG
- **Estadual**: Scrapers específicos (CE, ES, SP)
- **27 Estados**: Cobertura completa via PNCP

### Principais Recursos

✅ **Busca Hierárquica**: Prioriza fontes mais confiáveis
✅ **Filtros Avançados**: Status, Modalidade, Esfera, Estado
✅ **Listas Customizadas**: Até 5 listas de termos de busca
✅ **Exportação de Dados**: CSV e JSON
✅ **Dashboard de Saúde**: Monitoramento em tempo real
✅ **Interface Responsiva**: Desktop e mobile

---

## 🆕 NOVIDADES V3.0

### 1. Cobertura Nacional Consolidada

**ANTES (V2.0):**
- Scrapers estaduais individuais
- Cobertura limitada a 3 estados

**AGORA (V3.0):**
- PNCP como fonte principal
- Cobertura de todos os 27 estados
- Dados federais, estaduais e municipais

### 2. Nova API Federal (Compras.gov.br)

**Funcionalidade:**
- Integração direta com a API de Dados Abertos do Governo Federal.
- **Sincronização Local**: Backup automático de contratações no MongoDB (`comprasgov_v3`).
- **Busca por Modalidade**: Filtros obrigatórios para Pregão, Dispensa e Inexigibilidade.
- **Independência de Scrapers**: Redução de falhas por mudanças de layout no portal.

**Benefício:** Dados mais precisos, rápidos e disponíveis mesmo offline (via banco local).

---

### 3. Dashboard de Saúde dos Scrapers

**Localização:** `/api/status/scrapers`

**O que monitora:**
- Status de cada fonte (UP/DEGRADED/DOWN)
- Taxa de sucesso (últimas 24h)
- Total de execuções
- Tempo médio de resposta
- Última execução bem-sucedida
- Mensagens de erro

**Benefício:** Operação pode identificar problemas rapidamente

**Como usar:**
```bash
# Via API
curl https://seu-dominio.com/api/status/scrapers

# Via Dashboard (futuro)
Acesse: https://seu-dominio.com/dashboard
```

---

### 3. Exportação de Dados

**Formatos Suportados:**
- ✅ **CSV**: Excel, Google Sheets, análise
- ✅ **JSON**: Integração com outros sistemas

**Filtros Disponíveis:**
- Medicamento/termo de busca
- Estado (UF)
- Status (Ativa, Encerrada, etc.)
- Modalidade (Pregão, Concorrência, etc.)
- Esfera (Federal, Estadual, Municipal)
- Lista customizada

**Como usar:**

**Via Interface:**
1. Faça sua busca com os filtros desejados
2. Clique em "Exportar CSV" ou "Exportar JSON"
3. Arquivo será baixado automaticamente

**Via API:**
```bash
# Exportar CSV
curl "https://seu-dominio.com/api/export?formato=csv&medicamento=insulina&estado=SP"

# Exportar JSON
curl "https://seu-dominio.com/api/export?formato=json&medicamento=canabidiol"
```

**Limite:** 10.000 resultados por exportação

---

### 4. Listas Customizadas de Medicamentos

**Funcionalidade:**
- Criar até 5 listas de termos de busca
- Cada lista pode ter múltiplos medicamentos
- Usar lista como filtro de busca

**Como usar:**

1. Clique em "Minhas Listas" (botão verde no topo)
2. Clique em "Nova Lista"
3. Nomeie sua lista (ex: "Alto Custo")
4. Adicione medicamentos (um por linha)
5. Salve

**Para buscar:**
1. Selecione a lista no dropdown
2. Clique em "Buscar"
3. Sistema busca todos os medicamentos da lista

**Casos de uso:**
- Lista de medicamentos de alto custo
- Produtos específicos de interesse
- Monitoramento de mercado

---

## 👥 GUIA DO USUÁRIO

### Busca Básica

1. **Acesse** o sistema
2. **Digite** o nome do medicamento
3. **Clique** em "Buscar"
4. **Aguarde** os resultados (5-10 segundos)

### Busca Avançada

1. **Clique** em "Filtros Avançados"
2. **Selecione** os filtros desejados:
   - Status (Todas, Ativa, Encerrada, etc.)
   - Modalidade (Pregão, Concorrência, etc.)
   - Esfera (Federal, Estadual, Municipal)
3. **Opções adicionais:**
   - ☑ Apenas Dados Reais (remove dados mockados)
   - ☑ Apenas Licitações Futuras (data final > hoje)
4. **Clique** em "Buscar"

### Entendendo os Resultados

Cada card de resultado contém:

**Informações Principais:**
- 🏥 Medicamento
- 📍 Estado/Município
- 🏛️ Órgão Licitante
- 📋 Modalidade
- 📅 Datas (abertura e encerramento)

**Status:**
- 🟢 Verde: Ativa/Aberta
- 🟡 Amarelo: Suspensa/Em análise
- 🔴 Vermelho: Encerrada/Cancelada

**Ações:**
- 🔗 Ver no Portal de Origem (abre página oficial)
- 📄 Download do Edital (quando disponível)

### Exportando Resultados

**Para análise no Excel:**
1. Configure seus filtros
2. Execute a busca
3. Clique em "Exportar CSV"
4. Abra o arquivo no Excel

**Para integração com sistemas:**
1. Configure seus filtros
2. Execute a busca
3. Clique em "Exportar JSON"
4. Use o arquivo em seu sistema

---

## 🔧 DOCUMENTAÇÃO TÉCNICA

### Arquitetura do Sistema

```
┌─────────────────────────────────────────────┐
│           FRONTEND (React)                  │
│  - Interface de busca                       │
│  - Filtros avançados                        │
│  - Gerenciamento de listas                  │
│  - Exportação de dados                      │
└────────────────┬────────────────────────────┘
                 │
                 │ HTTPS/REST API
                 │
┌────────────────▼────────────────────────────┐
│           BACKEND (FastAPI)                 │
│  - Endpoint de busca (/api/search)          │
│  - Endpoint de exportação (/api/export)     │
│  - Endpoint de status (/api/status)         │
│  - Gerenciamento de listas                  │
└────────────────┬────────────────────────────┘
                 │
        ┌────────┼────────┐
        │        │        │
┌───────▼──┐ ┌──▼─────┐ ┌▼──────────┐
│  PNCP    │ │ComprasN│ │ Scrapers  │
│ (Nacional│ │et      │ │ Estaduais │
│ Priorida │ │(Federal│ │(CE,ES,SP) │
│ de 1)    │ │Prior.2)│ │(Prior. 3) │
└──────────┘ └────────┘ └───────────┘
        │        │        │
        └────────┼────────┘
                 │
        ┌────────▼────────┐
        │   MongoDB       │
        │  - Licitações   │
        │  - Listas       │
        │  - Health Logs  │
        └─────────────────┘
```

### Stack Tecnológico

**Backend:**
- Python 3.11
- FastAPI 0.104+
- Motor (MongoDB async driver)
- Playwright (web scraping)
- Requests + BeautifulSoup4

**Frontend:**
- React 18
- Axios (HTTP client)
- TailwindCSS (styling)
- Lucide Icons

**Database:**
- MongoDB 5.0+

**Infraestrutura:**
- Docker containers
- Kubernetes deployment
- Nginx reverse proxy

### Variáveis de Ambiente

**Backend (`.env`):**
```bash
MONGO_URL=mongodb://localhost:27017
DB_NAME=bem_db
```

**Frontend (`.env`):**
```bash
REACT_APP_BACKEND_URL=https://seu-dominio.com
```

### Collections MongoDB

**1. `licitacoes`**
```javascript
{
  "_id": ObjectId,
  "id": "uuid-string",
  "medicamento": "string",
  "estado": "UF",
  "status": "string",
  "orgao_licitante": "string",
  "modalidade": "string",
  "numero_processo": "string",
  "data_abertura": Date,
  "data_final": Date,
  "link_origem": "url",
  "link_documento": "url",
  "fonte": "PNCP|ComprasNet|...",
  "esfera": "Federal|Estadual|Municipal",
  "objeto": "string",
  "itens": [
    {
      "numero": "int",
      "descricao": "string",
      "quantidade": "int"
    }
  ],
  "is_mock": Boolean
}
```

**2. `listas_medicamentos`**
```javascript
{
  "_id": ObjectId,
  "id": "uuid-string",
  "nome": "string",
  "medicamentos": ["string"],
  "user_id": "string",
  "created_at": Date,
  "updated_at": Date
}
```

**3. `scraper_executions`**
```javascript
{
  "_id": ObjectId,
  "fonte": "PNCP|ComprasNet|BEC/SP",
  "timestamp": Date,
  "status": "success|error|timeout",
  "resultados_count": int,
  "termo_busca": "string",
  "tempo_execucao_ms": int,
  "erro_mensagem": "string"
}
```

---

## 📡 API REFERENCE

### Base URL
```
https://seu-dominio.com/api
```

### Endpoints

#### 1. Buscar Licitações
```http
POST /api/search
Content-Type: application/json

{
  "medicamento": "insulina",
  "tags": null,
  "apenas_reais": false,
  "apenas_futuras": false,
  "lista_id": null,
  "status_filtro": "Ativa",
  "modalidade_filtro": ["Pregão Eletrônico"],
  "esfera_filtro": "Estadual"
}

Response 200:
{
  "total": 45,
  "resultados": [
    {
      "id": "uuid",
      "medicamento": "Insulina",
      "estado": "SP",
      ...
    }
  ]
}
```

#### 2. Exportar Dados
```http
GET /api/export?formato=csv&medicamento=insulina&estado=SP

Response 200:
Content-Type: text/csv
Content-Disposition: attachment; filename="licitacoes_export_20241210_201500.csv"

id,medicamento,estado,...
uuid-1,Insulina,SP,...
```

#### 3. Status dos Scrapers
```http
GET /api/status/scrapers

Response 200:
{
  "timestamp": "2024-12-10T20:15:00",
  "status_geral": "HEALTHY",
  "total_fontes": 3,
  "fontes_up": 3,
  "fontes_down": 0,
  "fontes_degraded": 0,
  "scrapers": [
    {
      "fonte": "PNCP",
      "status": "UP",
      "total_execucoes_24h": 150,
      "taxa_sucesso_24h": 95.3,
      ...
    }
  ]
}
```

#### 4. API Compras.gov.br (Federal)

**Pesquisa de Preços:**
```http
GET /api/compras-gov/search?q=insulina&dias=30
```

**Sincronização Manual:**
```http
POST /api/compras-gov/sync?dias=7
```

**Detalhes de Itens:**
```http
GET /api/compras-gov/items/{id_compra}
```

#### 5. Gerenciar Listas

**Listar:**
```http
GET /api/listas

Response 200:
{
  "total": 2,
  "listas": [...]
}
```

**Criar:**
```http
POST /api/listas
Content-Type: application/json

{
  "nome": "Alto Custo",
  "medicamentos": ["Adalimumabe", "Pembrolizumabe"]
}

Response 201:
{
  "message": "Lista criada com sucesso",
  "lista": {...}
}
```

**Deletar:**
```http
DELETE /api/listas/{lista_id}

Response 200:
{
  "message": "Lista deletada com sucesso"
}
```

---

## 🔍 TROUBLESHOOTING

### Problema: Busca retorna 0 resultados

**Possíveis causas:**
1. APIs externas indisponíveis
2. Termo de busca muito específico
3. Filtros muito restritivos

**Soluções:**
1. Tente novamente em alguns minutos
2. Use termo mais genérico (ex: "insulina" em vez de "insulina glargina 100ui")
3. Remova alguns filtros
4. Desmarque "Apenas Dados Reais" temporariamente

---

### Problema: Exportação não funciona

**Possíveis causas:**
1. Popup blocker do navegador
2. Muitos resultados (>10k)
3. Filtros incompatíveis

**Soluções:**
1. Permita popups do site
2. Adicione mais filtros para reduzir resultados
3. Verifique se formato está correto (csv ou json)

---

### Problema: Dashboard de saúde mostra DEGRADED

**Interpretação:**
- Taxa de sucesso entre 50-90%
- Sistema funcional mas com problemas

**Ação:**
- Aguarde algumas horas
- APIs externas podem estar lentas
- Sistema continuará funcionando

---

## 📞 SUPORTE

Para dúvidas ou problemas:

1. Consulte esta documentação
2. Verifique o dashboard de saúde (`/api/status/scrapers`)
3. Entre em contato com o suporte técnico

---

## 📝 CHANGELOG

### V3.0 (Dezembro 2024)
- ✅ Cobertura nacional via PNCP
- ✅ Dashboard de saúde dos scrapers
- ✅ Exportação de dados (CSV/JSON)
- ✅ Listas customizadas (até 5)
- ✅ Filtros avançados aprimorados

### V2.0 (Novembro 2024)
- ✅ Busca hierárquica
- ✅ Integração PNCP e ComprasNet
- ✅ Filtros por status, modalidade, esfera
- ✅ Interface redesenhada

### V1.0 (Outubro 2024)
- ✅ Busca básica
- ✅ Scrapers estaduais (CE, ES, SP)
- ✅ Interface inicial

---

**Última atualização:** Dezembro 2024
**Versão:** 3.0.0
