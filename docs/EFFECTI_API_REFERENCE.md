# Effecti API Reference (Engenharia Reversa - Dezembro 2025)

## Estatísticas
- **Total de avisos no sistema:** 6.900+
- **Portais integrados:** 22

## Base URL
```
https://mdw.minha.effecti.com.br
```

## Autenticação

### POST /users/login
```json
// Request
{
  "username": "email@example.com",
  "password": "senha"
}

// Response
{
  "status": "success",
  "message": "...",
  "token": "JWT_TOKEN",
  "refreshToken": "REFRESH_TOKEN",
  "daysRemaining": 30,
  "effectiUser": true
}
```

---

## 🎯 ENDPOINT PRINCIPAL DE AVISOS

### POST /aviso/minhas
**Este é o endpoint mais importante para buscar avisos de licitação!**

```json
// Request
{
  "pagina": 0,
  "interesse": true,
  "favorito": false,
  "orgaoFavorito": false,
  "distribuidores": false,
  "id": "",
  "deserto": false,
  "ordem": [
    {"orderBy": "dataEnvioEmail"},
    {"order": "desc"}
  ],
  "tipo": [],
  "dataPublicacao": {
    // Filtros de data
  }
}

// Response
{
  "recordsTotal": 1500,
  "recordsFiltered": 15,
  "data": [...],
  "filterKeywords": [...]
}
```

### Estrutura de cada Aviso (data[0])
```json
{
  "id": 7153660,
  "refer": "vzxkI5sBLT6bu1pHy5hI",
  "isAnexo": null,
  "isGroup": null,
  "objeto": "AQUISIÇÃO PARA DETERMINAÇÃO JUDICIAL",
  "portal": 8,
  "portalNome": "ComprasNet Bahia",
  "perfil": "Perfil Padrão",
  "pregao": "19.180.2025.0310",
  "uasgNome": "FUNDO ESTADUAL DE SAUDE - SAFTEC",
  "url": "https://...",
  "item": [...],
  "anexo": [...],
  "dataEnvioEmail": "2025-12-15T16:02:41",
  "dataInicial": "2025-12-20T00:00:00",
  "dataFinal": "2025-12-27T23:59:59",
  "dataPublicacao": "2025-12-15T00:00:00",
  "modificado": false,
  "favorito": false,
  "uasg": "123456",
  "orgao": "Secretaria de Saúde",
  "uf": "BA",
  "tipo": "Pregão Eletrônico",
  "isSrp": true,
  "iminencia": 5
}
```

### Campos Críticos para Prospecção Futura:
| Campo | Descrição | Uso para Prospecção |
|-------|-----------|---------------------|
| `dataInicial` | Data de abertura das propostas | **FILTRO PRINCIPAL** >= hoje |
| `dataFinal` | Data limite para propostas | Verificar se não passou |
| `dataPublicacao` | Data de publicação | Para ordenação |
| `iminencia` | Dias até o prazo | **Priorização de urgência** |
| `tipo` | Modalidade da licitação | Filtro |
| `uf` | Estado | Filtro geográfico |
| `isSrp` | Se é Sistema de Registro de Preços | Filtro |

---

## Endpoints de Configuração

### GET /aviso/configurar
Retorna configurações do usuário para avisos.

```json
{
  "portals": [...],
  "groups": [...],
  "perfils": [...],
  "relationRole": [...],
  "relationList": [...],
  "description": "...",
  "company": {...},
  "perfil": {...},
  "esferas": ["Federal", "Estadual", "Municipal"]
}
```

### GET /accesses/portals
Lista de portais disponíveis (22 portais).

```json
[
  {
    "id": 1,
    "name": "ComprasNet",
    "proposal": true,
    "monitor": true,
    "dispute": true,
    "availableEveryone": true
  },
  ...
]
```

### POST /aviso/configurar/estados
Busca configurações por estado.

```json
// Request
{
  "states": ["SP", "RJ", "MG"]
}
```

---

## Endpoints de Monitoramento

### GET /monitor/users/alerts/continuous
```json
{
  "continuousAlert": true,
  "soundAlerts": false,
  "biggestAlert": 5
}
```

---

## Endpoints de Dados Gerais

### GET /general/data
Dados do usuário e empresa.

```json
{
  "user": {
    "id": 12345,
    "name": "Nome",
    "email": "email@example.com"
  },
  "company": {
    "id": 67890,
    "name": "Empresa LTDA"
  },
  "menuVisibility": {...},
  "modules": ["encontrar", "monitorar", "disputar"],
  "logout": false
}
```

---

## Parâmetros de Filtro Identificados

### Filtros para POST /aviso/minhas
```javascript
const filtros = {
  pagina: 0,              // Paginação (zero-indexed)
  interesse: true,        // Filtro de interesse
  favorito: false,        // Apenas favoritos
  orgaoFavorito: false,   // Apenas órgãos favoritos
  distribuidores: false,  // Filtro de distribuidores
  deserto: false,         // Incluir licitações desertas
  tipo: [],               // Array de modalidades
  ordem: [
    {orderBy: "dataEnvioEmail"},  // Campo de ordenação
    {order: "desc"}               // asc ou desc
  ],
  dataPublicacao: {
    // Filtros de data (a investigar formato exato)
  }
}
```

### Campos de Ordenação Disponíveis
- `dataEnvioEmail` - Data de envio do e-mail (recebimento)
- `dataInicial` - Data de abertura das propostas
- `dataFinal` - Data limite
- `dataPublicacao` - Data de publicação

---

## Stack Tecnológica Identificada

| Componente | Tecnologia |
|------------|------------|
| Frontend | Vue.js |
| Autenticação | JWT |
| API Style | REST |
| Paginação | Zero-indexed |
| Headers | Bearer Token |

---

## Rotas do Frontend Identificadas

```
#/avisos-cartoes     - Lista de avisos (cartões)
#/aviso-dashboard    - Dashboard de avisos
#/avisos-configuracoes - Configurações
#/proposta-minhas    - Minhas propostas
#/aviso-anexos       - Anexos dos avisos
#/proposta-impressao - Impressão de propostas
#/analisar/relatorio - Relatórios de análise
#/customer-panel     - Painel do cliente
#/accesses/list-new  - Lista de acessos
```

---

## Como Usar para Nosso Sistema GSM

### 1. Endpoint Equivalente
Criar endpoint `POST /api/search` com parâmetros similares:

```python
@router.post("/api/search")
async def search_licitacoes(
    pagina: int = 0,
    apenas_futuras: bool = True,  # Equivalente ao filtro de interesse
    favoritos: bool = False,
    estados: List[str] = [],
    modalidades: List[str] = [],
    ordem: str = "dataAbertura",
    direcao: str = "desc"
):
    ...
```

### 2. Campos a Implementar/Melhorar
- [x] `data_abertura` (dataInicial)
- [x] `data_final` (dataFinal)
- [x] `data_publicacao` (dataPublicacao)
- [ ] `iminencia` (dias até o prazo) - **NOVO**
- [x] `is_srp` (registro de preços)
- [x] `uf` (estado)
- [x] `modalidade` (tipo)

### 3. Filtros de Prospecção (baseado no Effecti)
```python
# Filtros proativos para processos FUTUROS
filtros_prospeccao = {
    "dataInicial": {"$gte": datetime.now()},  # Abertura no futuro
    "dataFinal": {"$gte": datetime.now()},    # Ainda não encerrou
    # OU usar iminencia > 0
}
```

---

## Observações

1. **O Effecti agrupa 22 portais diferentes** - nós temos 14 ativos
2. **Usa paginação zero-indexed** - diferente da nossa que é 1-indexed
3. **Tem campo `iminencia`** - calculado automaticamente, ótimo para priorização
4. **Filtro `interesse`** - parece ser o equivalente ao nosso `apenas_futuras`

---

## Comparação com Nosso Sistema GSM

### Fontes de Dados: Effecti vs GSM

| Portal | Effecti | GSM | Status GSM |
|--------|---------|-----|------------|
| ComprasNet (Federal) | ✅ | ✅ | ATIVO |
| PNCP (Federal) | ✅ | ✅ | ATIVO (API Oficial) |
| ComprasNet Bahia | ✅ | ✅ | ATIVO |
| BEC/SP | ✅ | ❌ | BLOQUEADO (CAPTCHA) |
| TCE-SP | ❌ | ✅ | ATIVO |
| Ceará | ✅ | ✅ | ATIVO |
| Rio de Janeiro | ✅ | ✅ | ATIVO |
| Rio Grande do Sul | ✅ | ✅ | ATIVO |
| Santa Catarina | ✅ | ✅ | ATIVO |
| Paraná | ✅ | ✅ | ATIVO |
| Pernambuco | ✅ | ✅ | ATIVO |
| Minas Gerais | ✅ | ✅ | ATIVO |
| Goiás | ✅ | ✅ | ATIVO |
| Espírito Santo | ✅ | ✅ | ATIVO |
| Licitações-e (BB) | ✅ | ❌ | BLOQUEADO (Cloudflare) |
| Mato Grosso do Sul | ✅ | ⚠️ | VIA PNCP |

### Funcionalidades: Effecti vs GSM

| Funcionalidade | Effecti | GSM |
|----------------|---------|-----|
| Prospecção Futura | ✅ | ✅ |
| Cálculo de Iminência | ✅ | ✅ |
| Filtro por Estado | ✅ | ✅ |
| Filtro por Modalidade | ✅ | ✅ |
| Filtro por SRP | ✅ | ✅ |
| Dashboard de Saúde | ❌ | ✅ |
| API Aberta | ❌ (Proprietário) | ✅ |

### Vantagens Competitivas do GSM

1. **Dashboard de Saúde** - Monitoramento em tempo real das fontes
2. **API Aberta** - Permite integrações externas
3. **TCE-SP** - Cobertura alternativa para São Paulo (evita CAPTCHA)
4. **Código Aberto** - Flexibilidade para customizações

### Oportunidades de Melhoria

1. **BEC/SP** - Investigar alternativas ao CAPTCHA
2. **Licitações-e** - Aguardar ou usar API intermediária
3. **Mais Estados** - TCE-PB, e-Compras DF em investigação

---

## Status da Engenharia Reversa

**Última Atualização:** Dezembro 2025

- [x] Autenticação documentada
- [x] Endpoint principal de busca documentado
- [x] Estrutura de resposta mapeada
- [x] Filtros identificados
- [x] Comparação com GSM realizada
- [x] Stack tecnológica identificada

**Conclusão:** A engenharia reversa do Effecti está **FINALIZADA**. Os insights foram utilizados para implementar funcionalidades equivalentes no GSM (iminência, prospecção futura). O sistema GSM já possui paridade funcional com o Effecti nas principais features de prospecção.
