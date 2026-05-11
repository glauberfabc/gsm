# Manual de Implementação — API Dados Abertos Compras.gov.br

**Versão baseada na documentação oficial:** Manual do Usuário – API do Compras.gov.br, versão 2.0, Fev/2026.  
**Base oficial da API:** `https://dadosabertos.compras.gov.br`  
**Formato:** REST / HTTP 1.1 com retorno em JSON.  
**Autenticação:** a documentação de dados abertos não indica uso de token obrigatório para as consultas públicas.

---

## 1. Objetivo da integração

Esta documentação serve como guia técnico para integrar a API de Dados Abertos do **Compras.gov.br** em um sistema de radar de licitações, mineração de oportunidades, monitoramento de compras públicas ou base de dados própria.

A API permite consultar dados de:

- Catálogo de Materiais — CATMAT
- Catálogo de Serviços — CATSER
- Pesquisa de preço
- PGC — Planejamento e Gerenciamento de Contratações
- UASG e órgãos
- Licitações do módulo legado
- Pregões
- Compras sem licitação
- RDC
- Contratações PNCP Lei 14.133/2021
- Atas de Registro de Preços — ARP
- Contratos
- Fornecedores
- Dados em padrão OCDS

---

## 2. Base URL

```txt
https://dadosabertos.compras.gov.br
```

Exemplo padrão:

```bash
curl -X GET \
  "https://dadosabertos.compras.gov.br/modulo-contratacoes/1_consultarContratacoes_PNCP_14133?pagina=1&tamanhoPagina=100" \
  -H "accept: application/json"
```

---

## 3. Padrão de comunicação

A documentação informa que o acesso é feito por URLs, usando REST/HTTP 1.1, com dados trafegando em JSON.

### Headers recomendados

```http
Accept: application/json
Content-Type: application/json
User-Agent: SeuSistema/1.0
```

### Resposta padrão mais comum

Grande parte dos endpoints retorna uma estrutura parecida com:

```json
{
  "resultado": [],
  "totalRegistros": 0,
  "totalPaginas": 0,
  "paginasRestantes": 0
}
```

Alguns endpoints também retornam:

```json
{
  "dataHoraConsulta": "2026-01-01T00:00:00.000Z",
  "timeZoneAtual": "America/Sao_Paulo"
}
```

---

## 4. Paginação

A maioria dos endpoints aceita:

| Parâmetro | Tipo | Obrigatório | Descrição |
|---|---:|---:|---|
| `pagina` | inteiro | não | Página atual. Valor padrão geralmente `1`. |
| `tamanhoPagina` | inteiro | não | Quantidade de registros por página. Limite máximo geralmente `500`. |

### Estratégia recomendada

1. Buscar `pagina=1`.
2. Ler `totalPaginas` ou `paginasRestantes`.
3. Iterar até finalizar.
4. Salvar checkpoint por endpoint + filtros + última página.
5. Usar `tamanhoPagina=500` para carga inicial e menor valor para sincronização incremental.

Exemplo:

```txt
GET /modulo-contratacoes/1_consultarContratacoes_PNCP_14133?pagina=1&tamanhoPagina=500
GET /modulo-contratacoes/1_consultarContratacoes_PNCP_14133?pagina=2&tamanhoPagina=500
```

---

## 5. Módulos da API

## 5.1. Módulo Material — CATMAT

Usado para consultar grupos, classes, PDM, itens, natureza da despesa, unidades de fornecimento e características do catálogo de materiais.

### Endpoints

| Serviço | Método | Endpoint |
|---|---|---|
| Grupo de Material | GET | `/modulo-material/1_consultarGrupoMaterial` |
| Classe de Material | GET | `/modulo-material/2_consultarClasseMaterial` |
| PDM de Material | GET | `/modulo-material/3_consultarPdmMaterial` |
| Item de Material | GET | `/modulo-material/4_consultarItemMaterial` |
| Natureza da Despesa | GET | `/modulo-material/5_consultarNaturezaDespesa` |
| Unidade de Fornecimento | GET | `/modulo-material/6_consultarUnidadeFornecimento` |
| Características | GET | `/modulo-material/7_consultarCaracteristicaMaterial` |

### Exemplo — Consultar itens de material

```bash
curl -X GET \
  "https://dadosabertos.compras.gov.br/modulo-material/4_consultarItemMaterial?pagina=1&tamanhoPagina=100&codigoItem=123456" \
  -H "accept: application/json"
```

### Uso no seu sistema

Use este módulo para enriquecer itens de licitações com:

- código do item
- descrição padronizada
- grupo
- classe
- PDM
- unidade de fornecimento
- vínculo com Banco de Preços em Saúde, quando disponível

---

## 5.2. Módulo Serviço — CATSER

Usado para consultar a estrutura do catálogo de serviços.

### Endpoints

| Serviço | Método | Endpoint |
|---|---|---|
| Seção | GET | `/modulo-servico/1_consultarSecaoServico` |
| Divisão | GET | `/modulo-servico/2_consultarDivisaoServico` |
| Grupo | GET | `/modulo-servico/3_consultarGrupoServico` |
| Classe | GET | `/modulo-servico/4_consultarClasseServico` |
| Subclasse | GET | `/modulo-servico/5_consultarSubclasseServico` |
| Item de Serviço | GET | `/modulo-servico/6_consultarItemServico` |
| Unidade de Medida | GET | `/modulo-servico/7_consultarUnidadeMedidaServico` |
| Natureza da Despesa | GET | `/modulo-servico/8_consultarNaturezaDespesaServico` |

### Exemplo

```bash
curl -X GET \
  "https://dadosabertos.compras.gov.br/modulo-servico/6_consultarItemServico?pagina=1&tamanhoPagina=100" \
  -H "accept: application/json"
```

---

## 5.3. Módulo Pesquisa de Preço

Usado para consultar histórico de preços praticados em compras públicas.

### Endpoints

| Serviço | Método | Endpoint |
|---|---|---|
| Pesquisa de preço — Material | GET | `/modulo-pesquisa-preco/1_consultarMaterial` |
| Detalhe do Material | GET | `/modulo-pesquisa-preco/2_consultarMaterialDetalhe` |
| Pesquisa de preço — Serviço | GET | `/modulo-pesquisa-preco/3_consultarServico` |
| Detalhe do Serviço | GET | `/modulo-pesquisa-preco/4_consultarServicoDetalhe` |

### Campos úteis no retorno

- `idCompra`
- `idItemCompra`
- `forma`
- `modalidade`
- `criterioJulgamento`
- `descricaoItem`
- `codigoItemCatalogo`
- `quantidade`
- `precoUnitario`
- `niFornecedor`
- `nomeFornecedor`
- `codigoUasg`
- `nomeUasg`
- `municipio`
- `estado`
- `dataCompra`
- `dataResultado`

### Exemplo — Histórico de preço para material

```bash
curl -X GET \
  "https://dadosabertos.compras.gov.br/modulo-pesquisa-preco/1_consultarMaterial?pagina=1&tamanhoPagina=100&descricaoItem=CANABIDIOL" \
  -H "accept: application/json"
```

> Observação: nem todos os endpoints aceitam busca textual da mesma forma. Confirme os filtros reais no Swagger antes de colocar em produção.

### Uso no seu sistema

Use para:

- comparação de preço estimado
- cálculo de média, mediana e menor preço
- alerta de oportunidade acima/abaixo do preço histórico
- enriquecimento da tela de licitação

---

## 5.4. Módulo PGC — Planejamento e Gerenciamento de Contratações

Usado para consultar dados do planejamento anual de contratações.

### Endpoints

| Serviço | Método | Endpoint |
|---|---|---|
| PGC Detalhe | GET | `/modulo-pgc/1_consultarPGCDetalhe` |
| PGC Detalhe Catálogo | GET | `/modulo-pgc/2_consultarPGCDetalheCatalogo` |
| PGC Agregação | GET | `/modulo-pgc/3_consultarPGCAgregacao` |

### Uso no seu sistema

Use para antecipar demandas futuras antes de virarem edital/licitação.

---

## 5.5. Módulo UASG

Consulta unidades administrativas e órgãos.

### Endpoints

| Serviço | Método | Endpoint |
|---|---|---|
| UASG | GET | `/modulo-uasg/1_consultarUasg` |
| Órgão | GET | `/modulo-uasg/2_consultarOrgao` |

### Campos úteis

- `codigoUasg`
- `nomeUasg`
- `codigoOrgao`
- `nomeOrgao`
- `municipio`
- `estado`
- `poder`
- `esfera`

### Uso no seu sistema

Crie tabelas auxiliares:

- `orgaos`
- `uasgs`
- `municipios`
- `ufs`

Essas tabelas melhoram filtros e reduzem repetição.

---

## 5.6. Módulo Legado

Este módulo consulta compras do modelo anterior e é importante porque ainda há dados históricos e processos que não estão apenas no novo formato PNCP.

### Endpoints

| Serviço | Método | Endpoint |
|---|---|---|
| Licitação | GET | `/modulo-legado/1_consultarLicitacao` |
| Itens de Licitações | GET | `/modulo-legado/2_consultarItemLicitacao` |
| Pregão | GET | `/modulo-legado/3_consultarPregao` |
| Itens de Pregões | GET | `/modulo-legado/4_consultarItemPregao` |
| Compra sem Licitação | GET | `/modulo-legado/5_consultarCompraSemLicitacao` |
| Itens de Compras sem Licitação | GET | `/modulo-legado/6_consultarItemCompraSemLicitacao` |
| RDC | GET | `/modulo-legado/7_consultarRDC` |

### Endpoint principal para radar

```txt
GET /modulo-legado/1_consultarLicitacao
```

### Exemplo

```bash
curl -X GET \
  "https://dadosabertos.compras.gov.br/modulo-legado/1_consultarLicitacao?pagina=1&tamanhoPagina=100&modalidade=5" \
  -H "accept: application/json"
```

### Campos úteis no retorno de licitação

- `id_compra`
- `identificador`
- `numero_processo`
- `uasg`
- `modalidade`
- `nome_modalidade`
- `numero_aviso`
- `situacao_aviso`
- `numero_itens`
- `valor_estimado_total`
- `valor_homologado_total`
- `objeto`
- `data_abertura_proposta`
- `data_entrega_proposta`
- `data_publicacao`

### Itens de licitação

```txt
GET /modulo-legado/2_consultarItemLicitacao
```

Parâmetros importantes:

- `pagina`
- `tamanhoPagina`
- `uasg`
- `numero_aviso`
- `modalidade`
- `codigo_item_material`
- `codigo_item_servico`
- `cnpj_fornecedor`
- `cpfVencedor`

---

## 5.7. Módulo Contratações — Lei 14.133/2021 / PNCP

Este é o módulo mais importante para um radar moderno de licitações.

### Endpoints

| Serviço | Método | Endpoint |
|---|---|---|
| Contratações PNCP 14133 | GET | `/modulo-contratacoes/1_consultarContratacoes_PNCP_14133` |
| Itens das Contratações PNCP 14133 | GET | `/modulo-contratacoes/2_consultarItensContratacoes_PNCP_14133` |
| Resultado dos Itens das Contratações PNCP 14133 | GET | `/modulo-contratacoes/3_consultarResultadoItensContratacoes_PNCP_14133` |

### Endpoint principal

```txt
GET /modulo-contratacoes/1_consultarContratacoes_PNCP_14133
```

### Exemplo básico

```bash
curl -X GET \
  "https://dadosabertos.compras.gov.br/modulo-contratacoes/1_consultarContratacoes_PNCP_14133?pagina=1&tamanhoPagina=100" \
  -H "accept: application/json"
```

### Campos úteis no retorno

- `idCompra`
- `numeroControlePNCP`
- `orgaoEntidadeCnpj`
- `orgaoEntidadeRazaoSocial`
- `unidadeOrgaoUfSigla`
- `unidadeOrgaoMunicipioNome`
- `numeroCompra`
- `modalidadeIdPncp`
- `codigoModalidade`
- `modalidadeNome`
- `srp`
- `codigoModoDisputa`
- `amparoLegalNome`
- `processo`
- `objetoCompra`
- `valorTotalEstimado`
- `valorTotalHomologado`
- `dataPublicacaoPncp`
- `dataAberturaPropostaPncp`
- `dataEncerramentoPropostaPncp`
- `situacaoCompraNomePncp`

### Exemplo para sincronização incremental

```bash
curl -X GET \
  "https://dadosabertos.compras.gov.br/modulo-contratacoes/1_consultarContratacoes_PNCP_14133?pagina=1&tamanhoPagina=500&dataPublicacaoPncpInicial=2026-04-20&dataPublicacaoPncpFinal=2026-04-30" \
  -H "accept: application/json"
```

> Confirme os nomes exatos dos filtros de data no Swagger. A documentação mostra os campos de retorno e parâmetros do módulo, mas o Swagger é a fonte mais prática para validar os nomes aceitos em produção.

### Itens da contratação

```bash
curl -X GET \
  "https://dadosabertos.compras.gov.br/modulo-contratacoes/2_consultarItensContratacoes_PNCP_14133?pagina=1&tamanhoPagina=100&idCompra=ID_DA_COMPRA" \
  -H "accept: application/json"
```

### Resultado dos itens

```bash
curl -X GET \
  "https://dadosabertos.compras.gov.br/modulo-contratacoes/3_consultarResultadoItensContratacoes_PNCP_14133?pagina=1&tamanhoPagina=100&idCompra=ID_DA_COMPRA" \
  -H "accept: application/json"
```

---

## 5.8. Módulo ARP — Ata de Registro de Preços

Usado para consultar atas de registro de preços e dados relacionados.

### Endpoints

| Serviço | Método | Endpoint |
|---|---|---|
| ARP | GET | `/modulo-arp/1_consultarARP` |
| Itens da ARP | GET | `/modulo-arp/2_consultarItensARP` |
| Consultar Unidades do Item | GET | `/modulo-arp/3_consultarUnidadesItemARP` |
| Consultar Empenhos e Saldo do Item | GET | `/modulo-arp/4_consultarEmpenhosSaldoItemARP` |
| Consultar Adesões do Item | GET | `/modulo-arp/5_consultarAdesoesItemARP` |

### Exemplo

```bash
curl -X GET \
  "https://dadosabertos.compras.gov.br/modulo-arp/1_consultarARP?pagina=1&tamanhoPagina=100" \
  -H "accept: application/json"
```

### Uso no sistema

Use ARP para:

- identificar oportunidades de adesão
- monitorar atas vigentes
- acompanhar itens e fornecedores vencedores
- cruzar preços registrados com novas licitações

---

## 5.9. Módulo Contratos

Consulta contratos e itens de contratos.

### Endpoints

| Serviço | Método | Endpoint |
|---|---|---|
| Contratos | GET | `/modulo-contratos/1_consultarContratos` |
| Itens de contrato | GET | `/modulo-contratos/2_consultarItensContrato` |

### Exemplo

```bash
curl -X GET \
  "https://dadosabertos.compras.gov.br/modulo-contratos/1_consultarContratos?pagina=1&tamanhoPagina=100" \
  -H "accept: application/json"
```

### Parâmetros comuns

- `codigoOrgao`
- `codigoUnidadeGestora`
- `codigoUnidadeGestoraOrigemContrato`
- `codigoUnidadeRealizadoraCompra`
- `numeroContrato`
- `codigoModalidadeCompra`
- filtros de vigência/publicação conforme Swagger

### Uso no sistema

Use contratos para:

- identificar fornecedores ativos
- analisar histórico de contratos por órgão
- calcular recorrência de compra
- encontrar oportunidades futuras por vencimento contratual

---

## 5.10. Módulo Fornecedor

Consulta dados cadastrais de fornecedores registrados.

### Endpoint

```txt
GET /modulo-fornecedor/1_consultarFornecedor
```

### Exemplo

```bash
curl -X GET \
  "https://dadosabertos.compras.gov.br/modulo-fornecedor/1_consultarFornecedor?pagina=1&tamanhoPagina=100&cnpj=00000000000100" \
  -H "accept: application/json"
```

### Parâmetros

- `pagina`
- `tamanhoPagina`
- `cnpj`
- `cpf`
- `naturezaJuridicaId`
- `porteEmpresaId`
- `codigoCnae`
- `ativo`

### Campos úteis

- `ativo`
- `cnpj`
- `codigoCnae`
- `municipio`
- `naturezaJuridicaId`
- `naturezaJuridica`
- `porteEmpresaId`
- `porteEmpresaNome`
- `nomeRazaoSocialFornecedor`

---

## 5.11. Módulo OCDS

OCDS significa **Open Contracting Data Standard**, padrão internacional para dados de contratações públicas.

### Endpoint

```txt
GET /modulo-ocds/1_releases
```

### Exemplo

```bash
curl -X GET \
  "https://dadosabertos.compras.gov.br/modulo-ocds/1_releases?page=1&offset=100&buyerID=00000000000100&releaseStartDate=2026-04-20&releaseEndDate=2026-04-30" \
  -H "accept: application/json"
```

### Parâmetros

| Parâmetro | Obrigatório | Descrição |
|---|---:|---|
| `page` | não | Página |
| `offset` | não | Quantidade por página, limite geralmente 500 |
| `buyerID` | sim | Identificador do comprador |
| `releaseStartDate` | sim | Data inicial de publicação |
| `releaseEndDate` | sim | Data final de publicação |

---

# 6. Arquitetura recomendada para radar de licitações

## 6.1. Fluxo geral

```txt
Compras.gov.br API
        ↓
Ingestor / Worker
        ↓
Normalização
        ↓
Banco de dados
        ↓
Indexação de busca
        ↓
Alertas por palavra-chave
        ↓
WhatsApp / Email / Dashboard
```

## 6.2. Fontes prioritárias

Para um sistema estilo Effecti, priorize nesta ordem:

1. `modulo-contratacoes/1_consultarContratacoes_PNCP_14133`
2. `modulo-contratacoes/2_consultarItensContratacoes_PNCP_14133`
3. `modulo-legado/1_consultarLicitacao`
4. `modulo-legado/2_consultarItemLicitacao`
5. `modulo-pesquisa-preco/1_consultarMaterial`
6. `modulo-pesquisa-preco/3_consultarServico`
7. `modulo-arp/1_consultarARP`
8. `modulo-contratos/1_consultarContratos`

---

# 7. Modelo de banco de dados recomendado

## 7.1. Tabela `licitacoes`

```sql
CREATE TABLE licitacoes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fonte TEXT NOT NULL DEFAULT 'comprasgov',
  modulo TEXT,
  endpoint TEXT,

  id_compra TEXT,
  numero_controle_pncp TEXT UNIQUE,
  numero_compra TEXT,
  numero_processo TEXT,

  orgao_cnpj TEXT,
  orgao_nome TEXT,
  uasg_codigo TEXT,
  uasg_nome TEXT,

  uf TEXT,
  municipio TEXT,
  codigo_ibge INTEGER,

  modalidade_codigo TEXT,
  modalidade_nome TEXT,
  modo_disputa_codigo TEXT,
  modo_disputa_nome TEXT,

  objeto TEXT,
  informacao_complementar TEXT,

  valor_estimado NUMERIC,
  valor_homologado NUMERIC,

  data_publicacao TIMESTAMP,
  data_abertura_proposta TIMESTAMP,
  data_encerramento_proposta TIMESTAMP,
  data_atualizacao TIMESTAMP,

  situacao TEXT,
  srp BOOLEAN,

  link_origem TEXT,
  raw JSONB NOT NULL,

  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);
```

## 7.2. Tabela `licitacao_itens`

```sql
CREATE TABLE licitacao_itens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  licitacao_id UUID REFERENCES licitacoes(id) ON DELETE CASCADE,

  id_compra TEXT,
  id_item_compra TEXT,
  numero_item INTEGER,

  tipo_item TEXT,
  codigo_item TEXT,
  descricao_item TEXT,

  quantidade NUMERIC,
  unidade TEXT,
  valor_estimado NUMERIC,
  valor_unitario NUMERIC,
  valor_total NUMERIC,

  fornecedor_documento TEXT,
  fornecedor_nome TEXT,

  raw JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT now()
);
```

## 7.3. Tabela `sync_jobs`

```sql
CREATE TABLE sync_jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  fonte TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  filtros JSONB,
  pagina_atual INTEGER DEFAULT 1,
  status TEXT DEFAULT 'pending',
  total_paginas INTEGER,
  total_registros INTEGER,
  started_at TIMESTAMP,
  finished_at TIMESTAMP,
  error TEXT
);
```

---

# 8. Serviço de integração — Node.js / TypeScript

## 8.1. Cliente HTTP

```ts
// src/integrations/comprasgov/client.ts
import axios from "axios";

export const comprasGovClient = axios.create({
  baseURL: "https://dadosabertos.compras.gov.br",
  timeout: 30000,
  headers: {
    Accept: "application/json",
    "User-Agent": "RadarLicitacoes/1.0"
  }
});
```

## 8.2. Função genérica paginada

```ts
// src/integrations/comprasgov/paginate.ts
import { comprasGovClient } from "./client";

type FetchOptions = {
  endpoint: string;
  params?: Record<string, any>;
  tamanhoPagina?: number;
  maxPages?: number;
};

export async function fetchPaginated<T>({
  endpoint,
  params = {},
  tamanhoPagina = 500,
  maxPages = 9999
}: FetchOptions): Promise<T[]> {
  const all: T[] = [];
  let pagina = 1;
  let totalPaginas = 1;

  do {
    const response = await comprasGovClient.get(endpoint, {
      params: {
        ...params,
        pagina,
        tamanhoPagina
      }
    });

    const body = response.data;
    const results = body.resultado ?? body.data ?? [];

    all.push(...results);

    totalPaginas = body.totalPaginas ?? pagina;
    const paginasRestantes = body.paginasRestantes ?? 0;

    if (paginasRestantes <= 0 && pagina >= totalPaginas) break;

    pagina++;
    await new Promise(resolve => setTimeout(resolve, 300));
  } while (pagina <= totalPaginas && pagina <= maxPages);

  return all;
}
```

## 8.3. Buscar contratações PNCP

```ts
// src/integrations/comprasgov/contratacoes.ts
import { fetchPaginated } from "./paginate";

export type ContratacaoComprasGov = {
  idCompra?: string;
  numeroControlePNCP?: string;
  orgaoEntidadeCnpj?: string;
  orgaoEntidadeRazaoSocial?: string;
  unidadeOrgaoUfSigla?: string;
  unidadeOrgaoMunicipioNome?: string;
  numeroCompra?: string;
  modalidadeNome?: string;
  processo?: string;
  objetoCompra?: string;
  valorTotalEstimado?: number;
  valorTotalHomologado?: number;
  dataPublicacaoPncp?: string;
  dataAberturaPropostaPncp?: string;
  dataEncerramentoPropostaPncp?: string;
  situacaoCompraNomePncp?: string;
};

export async function fetchContratacoesPNCP(params: Record<string, any> = {}) {
  return fetchPaginated<ContratacaoComprasGov>({
    endpoint: "/modulo-contratacoes/1_consultarContratacoes_PNCP_14133",
    params
  });
}
```

## 8.4. Normalizador

```ts
// src/integrations/comprasgov/normalize.ts
import { ContratacaoComprasGov } from "./contratacoes";

export function normalizeContratacao(row: ContratacaoComprasGov) {
  return {
    fonte: "comprasgov",
    modulo: "contratacoes",
    endpoint: "1_consultarContratacoes_PNCP_14133",

    id_compra: row.idCompra ?? null,
    numero_controle_pncp: row.numeroControlePNCP ?? null,
    numero_compra: row.numeroCompra ?? null,
    numero_processo: row.processo ?? null,

    orgao_cnpj: row.orgaoEntidadeCnpj ?? null,
    orgao_nome: row.orgaoEntidadeRazaoSocial ?? null,

    uf: row.unidadeOrgaoUfSigla ?? null,
    municipio: row.unidadeOrgaoMunicipioNome ?? null,

    modalidade_nome: row.modalidadeNome ?? null,
    objeto: row.objetoCompra ?? null,

    valor_estimado: row.valorTotalEstimado ?? null,
    valor_homologado: row.valorTotalHomologado ?? null,

    data_publicacao: row.dataPublicacaoPncp ?? null,
    data_abertura_proposta: row.dataAberturaPropostaPncp ?? null,
    data_encerramento_proposta: row.dataEncerramentoPropostaPncp ?? null,

    situacao: row.situacaoCompraNomePncp ?? null,

    raw: row
  };
}
```

## 8.5. Job de sincronização

```ts
// src/jobs/syncComprasGov.ts
import { fetchContratacoesPNCP } from "../integrations/comprasgov/contratacoes";
import { normalizeContratacao } from "../integrations/comprasgov/normalize";
// import { supabaseAdmin } from "../lib/supabase";

export async function syncComprasGovContratacoes() {
  const rows = await fetchContratacoesPNCP({
    // Ajustar filtros conforme Swagger
    // dataPublicacaoPncpInicial: "2026-04-20",
    // dataPublicacaoPncpFinal: "2026-04-30"
  });

  const normalized = rows.map(normalizeContratacao);

  // Exemplo Supabase:
  // const { error } = await supabaseAdmin
  //   .from("licitacoes")
  //   .upsert(normalized, { onConflict: "numero_controle_pncp" });
  //
  // if (error) throw error;

  return {
    total: normalized.length
  };
}
```

---

# 9. Busca por palavra-chave

A API pode não oferecer busca textual ideal em todos os módulos. Para radar de licitações, recomendo:

1. Ingerir dados por data/publicação.
2. Salvar no banco.
3. Criar índice de texto no seu banco.
4. Buscar no seu sistema.

## 9.1. PostgreSQL Full Text Search

```sql
ALTER TABLE licitacoes
ADD COLUMN search_vector tsvector
GENERATED ALWAYS AS (
  to_tsvector(
    'portuguese',
    coalesce(objeto, '') || ' ' ||
    coalesce(informacao_complementar, '') || ' ' ||
    coalesce(orgao_nome, '') || ' ' ||
    coalesce(modalidade_nome, '')
  )
) STORED;

CREATE INDEX licitacoes_search_idx
ON licitacoes USING GIN(search_vector);
```

## 9.2. Exemplo de busca

```sql
SELECT *
FROM licitacoes
WHERE search_vector @@ plainto_tsquery('portuguese', 'canabidiol')
ORDER BY data_publicacao DESC;
```

---

# 10. Estratégia para encontrar “canabidiol” entre 20/04 e 30/04

## Caminho recomendado

1. Buscar contratações publicadas no período.
2. Salvar no banco.
3. Buscar por palavra-chave no campo `objeto`.
4. Buscar itens relacionados nos endpoints de itens.
5. Enriquecer com preço histórico.

## Pseudofluxo

```txt
GET /modulo-contratacoes/1_consultarContratacoes_PNCP_14133
  filtros: dataPublicacao inicial/final

para cada contratação:
  salvar raw
  normalizar
  se objeto contém "canabidiol":
    buscar itens
    salvar oportunidade
```

## Busca local

```sql
SELECT *
FROM licitacoes
WHERE data_publicacao::date BETWEEN '2026-04-20' AND '2026-04-30'
AND (
  objeto ILIKE '%canabidiol%'
  OR informacao_complementar ILIKE '%canabidiol%'
);
```

---

# 11. Tratamento de erros

## Recomendações

- Timeout: 30 segundos
- Retry: 3 tentativas
- Delay entre páginas: 300ms a 1000ms
- Backoff exponencial para erro 429/500
- Gravar `raw` sempre que possível
- Não apagar registros antigos; marcar como atualizado/excluído

## Exemplo

```ts
async function retry<T>(fn: () => Promise<T>, attempts = 3): Promise<T> {
  let lastError: unknown;

  for (let i = 0; i < attempts; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)));
    }
  }

  throw lastError;
}
```

---

# 12. Checklist de implementação

## Primeira entrega

- [ ] Criar cliente HTTP Compras.gov.br
- [ ] Criar função paginada
- [ ] Integrar contratações PNCP
- [ ] Integrar itens das contratações
- [ ] Criar tabelas `licitacoes` e `licitacao_itens`
- [ ] Criar normalizador
- [ ] Criar busca por palavra-chave
- [ ] Criar job agendado diário/horário
- [ ] Criar tela de resultados

## Segunda entrega

- [ ] Integrar módulo legado
- [ ] Integrar pesquisa de preço
- [ ] Integrar ARP
- [ ] Integrar contratos
- [ ] Criar alertas por WhatsApp/E-mail
- [ ] Criar histórico de alterações
- [ ] Criar score de oportunidade

---

# 13. Estrutura de pastas sugerida

```txt
src/
  integrations/
    comprasgov/
      client.ts
      paginate.ts
      contratacoes.ts
      itensContratacoes.ts
      legado.ts
      pesquisaPreco.ts
      arp.ts
      contratos.ts
      fornecedores.ts
      normalize.ts
  jobs/
    syncComprasGov.ts
  lib/
    supabase.ts
  modules/
    licitacoes/
      repository.ts
      search.ts
      alerts.ts
```

---

# 14. Observações importantes

1. Para dados de licitações modernas, priorize **Módulo Contratações PNCP 14133**.
2. Para dados históricos, use **Módulo Legado**.
3. Para preço de referência, use **Pesquisa de Preço**.
4. Para contratos vigentes, use **Contratos**.
5. Para atas, use **ARP**.
6. Para interoperabilidade internacional, use **OCDS**.
7. Sempre salve o retorno bruto em `raw JSONB`.
8. Valide filtros exatos no Swagger antes de subir em produção.
9. Para busca por palavras-chave, prefira indexação local em PostgreSQL/Meilisearch/Elasticsearch.

---

# 15. Prompt para Claude Code / Cursor implementar

```txt
Você é um engenheiro backend sênior especialista em integrações governamentais e dados abertos.

Crie uma integração completa com a API de Dados Abertos do Compras.gov.br.

Requisitos:

1. Criar cliente HTTP base:
   - baseURL: https://dadosabertos.compras.gov.br
   - timeout 30s
   - headers Accept application/json

2. Criar função genérica de paginação:
   - suporta pagina
   - suporta tamanhoPagina
   - lê resultado, totalPaginas e paginasRestantes
   - retry com backoff
   - delay entre páginas

3. Criar conectores:
   - modulo-contratacoes/1_consultarContratacoes_PNCP_14133
   - modulo-contratacoes/2_consultarItensContratacoes_PNCP_14133
   - modulo-contratacoes/3_consultarResultadoItensContratacoes_PNCP_14133
   - modulo-legado/1_consultarLicitacao
   - modulo-legado/2_consultarItemLicitacao
   - modulo-pesquisa-preco/1_consultarMaterial
   - modulo-pesquisa-preco/3_consultarServico
   - modulo-arp/1_consultarARP
   - modulo-contratos/1_consultarContratos
   - modulo-fornecedor/1_consultarFornecedor

4. Criar normalizadores:
   - licitacoes
   - itens
   - fornecedores
   - contratos
   - atas

5. Criar schema SQL para Supabase:
   - licitacoes
   - licitacao_itens
   - contratos
   - atas_registro_preco
   - fornecedores
   - sync_jobs

6. Criar busca textual:
   - PostgreSQL full text search
   - filtro por UF, município, modalidade, data, valor e palavra-chave

7. Criar job:
   - sincronização incremental diária
   - sincronização manual por intervalo de datas

8. Criar logs:
   - total importado
   - páginas lidas
   - erros
   - tempo de execução

Entregar código TypeScript limpo, modular e documentado.
```