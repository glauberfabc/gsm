# 🏥 BEM - Buscador Estadual de Medicamentos

## 📋 Visão Geral

O **BEM** é uma plataforma web para busca e monitoramento de licitações de medicamentos em portais estaduais de compras públicas do Brasil. O sistema utiliza **web scraping** para coletar dados de 3 estados principais (CE, ES, SP) e apresenta dados de exemplo para os demais 24 estados.

## 🎯 Características Principais

### ✅ Funcionalidades Implementadas

1. **Busca de Medicamentos**
   - Busca por nome comercial ou princípio ativo
   - Resultados de 27 estados (26 + DF)
   - Sistema híbrido: dados reais + mockados

2. **Web Scraping Real - 3 Estados**
   - ✅ **Ceará (CE)** - Portal Licitaweb
   - ✅ **Espírito Santo (ES)** - e-Compras ES
   - ✅ **São Paulo (SP)** - Compras SP

3. **Filtros Avançados**
   - 💰 Alto Custo
   - 🌍 Importado
   - ⚖️ Judicial
   - 📊 Apenas dados reais (CE, ES, SP)

4. **Informações Exibidas**
   - Nome do medicamento
   - Estado (UF)
   - Status (Em Licitação, Contratado, Judicial, etc)
   - Órgão licitante
   - Modalidade (Pregão Eletrônico, Dispensa, etc)
   - Número do processo
   - Data de referência
   - Link para portal oficial
   - Tags (alto custo, importado, judicial)

5. **Recursos Especiais**
   - 🔄 Refresh manual por estado (CE, ES, SP)
   - 📊 Estatísticas gerais do sistema
   - 🏷️ Indicadores visuais: dados reais vs mockados
   - 🎨 Interface moderna e responsiva

## 🛠️ Tecnologias Utilizadas

### Backend
- **FastAPI** - Framework web assíncrono
- **MongoDB** - Banco de dados NoSQL
- **BeautifulSoup4** - Web scraping
- **Motor** - Driver MongoDB assíncrono
- **Requests** - HTTP client
- **APScheduler** - Agendamento de tarefas

### Frontend
- **React 19** - Biblioteca UI
- **Tailwind CSS** - Framework CSS
- **Axios** - HTTP client
- **Lucide React** - Ícones

## 📁 Estrutura do Projeto

```
/app/
├── backend/
│   ├── server.py                 # API principal
│   ├── models/
│   │   └── licitacao.py         # Modelos de dados
│   ├── scrapers/
│   │   ├── base_scraper.py      # Classe base
│   │   ├── ceara_scraper.py     # Scraper CE
│   │   ├── espirito_santo_scraper.py  # Scraper ES
│   │   └── sao_paulo_scraper.py # Scraper SP
│   ├── services/
│   │   ├── scraper_service.py   # Serviço de scraping
│   │   └── mock_data_service.py # Dados mockados
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── App.js              # Componente principal
│   │   └── App.css             # Estilos
│   └── package.json
│
└── BEM_DOCUMENTACAO.md         # Este arquivo
```

## 🚀 API Endpoints

### 1. **GET /api/**
Informações da API

**Resposta:**
```json
{
  "message": "BEM - Buscador Estadual de Medicamentos API",
  "version": "1.0.0",
  "endpoints": {
    "search": "/api/search",
    "states": "/api/states",
    "refresh": "/api/refresh",
    "stats": "/api/stats"
  }
}
```

### 2. **POST /api/search**
Busca medicamentos

**Request Body:**
```json
{
  "medicamento": "Adalimumabe",
  "estado": null,
  "tags": ["alto_custo", "importado"],
  "apenas_reais": false
}
```

**Resposta:**
```json
{
  "total": 13,
  "medicamento": "Adalimumabe",
  "resultados": [
    {
      "medicamento": "Adalimumabe",
      "principio_ativo": null,
      "estado": "CE",
      "status": "Em Licitação",
      "orgao_licitante": "SESA-CE",
      "modalidade": "Pregão Eletrônico",
      "numero_processo": "PE-2025/001",
      "data_referencia": "2025-12-05T15:00:00",
      "link_origem": "https://...",
      "tags": ["alto_custo"],
      "is_mock": false
    }
  ]
}
```

### 3. **GET /api/states**
Lista todos os estados

**Resposta:**
```json
{
  "estados": [
    {
      "uf": "CE",
      "nome": "Ceará",
      "has_scraping": true,
      "is_mock": false
    }
  ]
}
```

### 4. **POST /api/refresh/{estado}?medicamento=X**
Força refresh de um estado específico

**Exemplo:** `POST /api/refresh/CE?medicamento=Adalimumabe`

### 5. **GET /api/stats**
Estatísticas do sistema

**Resposta:**
```json
{
  "total_licitacoes": 26,
  "licitacoes_reais": 6,
  "licitacoes_mock": 20,
  "por_estado": [
    {"estado": "CE", "total": 2}
  ],
  "estados_com_scraping": ["CE", "ES", "SP"]
}
```

## 🔍 Como Usar

### Busca Básica
1. Digite o nome do medicamento no campo de busca
2. Clique em "Buscar"
3. Visualize os resultados em cards

### Filtros
- **Alto Custo**: Medicamentos de alto custo ou CEAF
- **Importado**: Medicamentos importados
- **Judicial**: Fornecimento via judicial
- **Apenas dados reais**: Mostra somente CE, ES, SP

### Refresh Manual
- Clique no ícone 🔄 no card de um estado real (CE, ES, SP)
- Força nova busca no portal estadual
- Útil para obter dados mais recentes

## 📊 Modelo de Dados

### Estrutura no MongoDB

```javascript
{
  "id": "uuid",
  "medicamento": "Nome do medicamento",
  "principio_ativo": "Princípio ativo",
  "estado": "UF",
  "status": "Status da licitação",
  "orgao_licitante": "Nome do órgão",
  "modalidade": "Tipo de licitação",
  "numero_processo": "Número do processo",
  "data_referencia": "2025-12-05T15:00:00",
  "link_origem": "URL do portal",
  "tags": ["alto_custo", "importado", "judicial"],
  "is_mock": false,
  "created_at": "2025-12-05T15:00:00",
  "updated_at": "2025-12-05T15:00:00"
}
```

## 🎨 Design e UX

### Cores
- **Azul primário**: #2563EB (blue-600)
- **Verde**: #10B981 (green-500) - Dados reais
- **Cinza**: #6B7280 (gray-500) - Dados mockados

### Cards de Resultados
- **Borda verde (esquerda)**: Dados reais
- **Borda cinza (esquerda)**: Dados mockados
- **Badge "Real"**: Com checkmark verde
- **Badge "Exemplo"**: Cinza

### Badges de Status
- **Em Licitação**: Azul
- **Contratado**: Verde
- **Fornecimento Judicial**: Roxo
- **Em Análise**: Amarelo
- **Suspenso**: Vermelho

## 🔧 Configuração Técnica

### Backend
```bash
# Porta: 8001
# URL: http://localhost:8001
```

### Frontend
```bash
# Porta: 3000
# URL: https://dama-legal-1.preview.emergentagent.com
```

### MongoDB
- Collection: `licitacoes`
- Database: Configurado via .env

## 📝 Notas Importantes

1. **Web Scraping**: Os scrapers podem precisar de ajustes se os portais mudarem estrutura
2. **Rate Limiting**: Implementado delays entre requisições (1-3 segundos)
3. **Dados Mockados**: 24 estados apresentam dados de exemplo
4. **Cache**: Dados armazenados no MongoDB para performance
5. **Timestamps**: Todas as datas em UTC

## 🚧 Melhorias Futuras

- [ ] Implementar scrapers para todos os 27 estados
- [ ] Sistema de cache com TTL automático
- [ ] Agendamento automático de scraping (a cada 12h)
- [ ] Notificações de novas licitações
- [ ] Export de dados (CSV, Excel)
- [ ] Histórico de preços
- [ ] Análise de tendências
- [ ] Dashboard administrativo
- [ ] Sistema de alertas por email

## 📞 Suporte

Para dúvidas ou problemas:
- Verifique os logs: `/var/log/supervisor/backend.*.log`
- Teste as APIs diretamente: `curl http://localhost:8001/api/`

## 📄 Licença

Projeto desenvolvido para demonstração de capacidades técnicas.

---

**Desenvolvido com ❤️ usando FastAPI + React + MongoDB**
