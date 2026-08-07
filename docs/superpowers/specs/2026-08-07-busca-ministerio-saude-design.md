# Busca "Ministério da Saúde" (multi-UASG) — Design

## Contexto

O usuário pediu um botão dedicado, no mesmo padrão visual dos "Radares de Atalho"
já existentes, para restringir a busca de licitações/editais aos órgãos do
portfólio federal de saúde (Ministério da Saúde e suas unidades — DLOG, Fiocruz,
INCA, hospitais federais, DSEIs/SESAI etc.), reaproveitando a mesma lista de
resultados que a busca normal já usa.

O pedido chegou via uma conversa com o Gemini (compartilhada pelo usuário), que
propôs código pronto. Antes de aceitar essa proposta, ela foi verificada contra
o código real do GSM e contra as APIs públicas mencionadas:

- **O botão "atalho" real não é hardcoded.** Em `SearchTab.jsx`, os atalhos
  (`radaresAtalho`) vêm das 5 primeiras Listas salvas do usuário, cada uma
  virando uma pílula que preenche um termo fixo. O HTML que o Gemini gerou
  (com nomes "HUDSON", "CLAUDIO" etc. hardcoded) nunca foi confrontado com o
  código real — não pode ser copiado como está.
- **`comprasnet_search_service.py` já tem um esqueleto para isso, mas está
  morto.** Existe uma lista `uasgs_saude` (9 entradas, incluindo uma prefeitura
  misturada por engano) e um método `_buscar_em_uasgs_saude()` que varre por
  UASG — mas `busca_service_v2.py` só importa o serviço, nunca chama.
- **A ideia central do Gemini (filtrar pelo CNPJ raiz do Ministério da Saúde na
  API oficial do PNCP) foi testada ao vivo e não funciona**: o parâmetro
  (`orgaoEntidadeCnpj` e `cnpjOrgao`) é ignorado pela API — os resultados
  voltaram de um DER estadual e prefeituras aleatórias, não do Ministério.
  Isso também seria insuficiente mesmo se funcionasse: Fiocruz e INCA são
  entidades com **CNPJ próprio**, diferente do CNPJ raiz do Ministério, então
  um filtro por CNPJ único nunca cobriria essas unidades.
- **A URL que o Gemini sugeriu para listar todas as UASGs**
  (`compras.dados.gov.br/unidades/v1/unidades.json`) retorna **404** — não
  existe / mudou de endereço.
- A página oficial `gov.br/saude/.../pregoes/2026` foi conferida e confirma
  pelo menos duas UASGs reais: **DLOG = 250005** e **DSEI Alto Rio Solimões
  (SESAI) = 257025**.

Conclusão: a única abordagem confiável é manter uma **lista curada** de
órgãos/UASGs do portfólio saúde, com validação manual, em vez de um único
filtro mágico por CNPJ.

## Objetivo

Adicionar um filtro de escopo "Ministério da Saúde" à busca de licitações já
existente (`GET /api/search/unified`), que:
1. Com um termo digitado (nome de medicamento), restringe os resultados da
   busca nacional já existente aos órgãos do portfólio saúde.
2. Com o campo vazio, lista as contratações recentes desses órgãos sem exigir
   termo ("buscar todos").
3. Aparece como um botão pílula, no mesmo padrão visual da linha "Radares de
   Atalho" da tela de busca, funcionando como toggle (liga/desliga o escopo).
4. Os resultados usam exatamente os mesmos cards/lista que a busca normal já
   renderiza — nenhuma tela nova.

## Fora de escopo

- Reescrever ou consertar `comprasnet_search_service.py` como um todo (ele é
  reaproveitado só para o método de varredura por UASG, ver abaixo).
- Cobertura 100% garantida de todas as UASGs do Ministério — a lista curada é
  um ponto de partida editável, não uma fonte oficial sincronizada.
- Alterar o comportamento da busca nacional normal quando o filtro está
  desligado (nada muda para quem não usa o botão).

## Arquitetura

### A. Lista curada de órgãos (`backend/services/orgaos_saude_federal.py`, novo)

Lista de dicts, fácil de editar (mesmo padrão de `CATEGORIAS_LMR` /
`FAIXAS_MARGEM_IN428` já usado no código):

```python
ORGAOS_SAUDE_FEDERAL = [
    {
        'nome': 'DLOG - Departamento de Logística em Saúde',
        'uasg': '250005',
        'cnpj': '00394445000139',
        'keywords': ['ministerio da saude', 'departamento de logistica em saude', 'dlog'],
    },
    {
        'nome': 'SESAI / DSEI - Saúde Indígena',
        'uasg': None,  # varias UASGs por DSEI regional, ex: 257025 (Alto Rio Solimões)
        'cnpj': '00394445000139',
        'keywords': ['dsei', 'saude indigena', 'sesai'],
    },
    {
        'nome': 'Fiocruz - Fundação Oswaldo Cruz',
        'uasg': None,  # a validar por unidade
        'cnpj': None,  # CNPJ proprio, diferente do MS - a validar
        'keywords': ['fiocruz', 'fundacao oswaldo cruz'],
    },
    {
        'nome': 'INCA - Instituto Nacional de Câncer',
        'uasg': None,  # a validar
        'cnpj': None,  # CNPJ proprio - a validar
        'keywords': ['inca', 'instituto nacional de cancer'],
    },
    # + hospitais federais, INCQS - completados durante a implementação
]
```

Cada entrada carrega **UASG/CNPJ quando confirmado** e **keywords do nome do
órgão como fallback** — isso cobre unidades cujo UASG/CNPJ exato eu não
conseguir confirmar, já que o nome do órgão vem em todo resultado de busca
(`orgao`).

Uma função utilitária `bate_orgao_saude(orgao_nome: str, orgao_cnpj: str) -> bool`
centraliza o critério de match (CNPJ exato OU substring de keyword,
normalizado sem acento/caixa — reaproveita o padrão de normalização já usado
em `medicamento_query_parser.normalizar`).

### B. `MotorBuscaIndependente.buscar()` (`backend/services/motor_independente.py`)

**Correção de premissa (achado durante a checagem técnica anterior à
implementação):** `GET /api/search/unified` não usa `BuscaServiceV2`
(`busca_service_v2.py`) — esse serviço é importado por outros fluxos, mas o
endpoint real chama `MotorBuscaIndependente.buscar()` em
`motor_independente.py` (v78-80, "100% independente" PNCP + Compras.gov.br).
É esse arquivo que precisa ser alterado, não `busca_service_v2.py`.

Também foi confirmado ao vivo (3 tentativas, 2 endpoints oficiais do PNCP:
`/contratacoes/publicacao` e `/contratacoes/proposta`) que **nenhum parâmetro
de filtro por órgão/CNPJ funciona no lado do servidor** (`orgaoEntidadeCnpj`,
`cnpjOrgao`, `orgaoCnpj` — todos ignorados, resultados voltam de órgãos
aleatórios). Isso confirma que pós-filtro client-side é o único caminho
confiável — não existe atalho de servidor a redescobrir depois.

Novo parâmetro `apenas_ministerio_saude: bool = False` em `buscar()`:

- **Com `termo` preenchido**: fluxo atual roda sem mudanças (`_buscar_pncp` +
  `_buscar_compras_gov` em paralelo, por termo). Logo após
  `todos = self._dedup(todos)`, se `apenas_ministerio_saude`, filtra `todos`
  mantendo só itens onde `bate_orgao_saude(item['orgao'], item.get('_pncp_cnpj') or item.get('orgao_cnpj'))`.
- **Sem `termo`** (`apenas_ministerio_saude=True`, termo vazio, sem uf/município):
  hoje esse caso não é tratado (`buscar()` retorna vazio quando não há termo
  nem uf/município — o próprio endpoint bloqueia essa combinação, ver Seção C).
  Precisa de um novo método `_buscar_ministerio_saude_sem_termo()`, no mesmo
  espírito de `_buscar_por_localizacao()` (que já existe para o caso "sem
  termo, com uf/município"): itera `ORGAOS_SAUDE_FEDERAL` (por CNPJ) ×
  códigos de modalidade via `comprasgov_client.consultar_contratacoes_pncp(orgaoEntidadeCnpj=..., codigoModalidade=...)`
  (ver "Fonte para o modo buscar todos" abaixo — mecanismo confirmado
  funcionando, substitui a ideia original de reviver
  `comprasnet_search_service.py`). Se a chamada falhar (erro de rede, API
  fora do ar), este modo degrada com `fonte_disponivel: False` e um `aviso`
  claro, seguindo o mesmo padrão de resiliência que `_buscar_por_localizacao`
  já usa quando o PNCP está instável.

### C. Endpoint (`backend/server.py`, endpoint `search_unified` em `/api/search/unified`)

Novo parâmetro `ministerio_saude: bool = Query(False, ...)`, repassado para
`motor.buscar(apenas_ministerio_saude=ministerio_saude, ...)`. A validação
atual (`if not tem_localizacao and (not q or len(q.strip()) < 2): raise
HTTPException(400, ...)`) precisa tratar `ministerio_saude=True` como uma
condição válida adicional para permitir busca sem termo (equivalente a
`tem_localizacao`).

### D. Frontend

- `useSearch.js`: novo estado `filtroMinisterioSaude` (bool); quando ativo,
  `executarBusca` inclui `ministerio_saude=true` nos params da chamada e
  permite disparo com `termo` vazio (a guarda atual
  `if (!termo && !cidade && !uf) return;` precisa considerar o filtro ativo
  como condição válida também).
- `SearchTab.jsx`: botão pílula "MINISTÉRIO DA SAÚDE" ao lado da linha
  "Radares de Atalho", mesmo estilo visual (`rounded-full`, mesma
  tipografia), com estado visual ativo/inativo (ex.: mesma lógica de cor já
  usada para `selectedRadarId === r.id` nos radares). Clique liga/desliga
  `filtroMinisterioSaude` e redispara `executarBusca` com o termo atual do
  campo (vazio ou preenchido).
- Resultados renderizam nos mesmos componentes de card já existentes — nenhum
  componente novo de exibição.

## Fonte para o modo "buscar todos" (achado durante validação ao vivo)

A API oficial do PNCP não filtra por órgão/CNPJ em nenhum endpoint (ver Seção
B). `comprasnet_search_service.py` está morto e os endpoints que usa (404
confirmado). Mas o cliente já usado em produção,
`backend/scrapers/comprasgov_client.py` → `consultar_contratacoes_pncp()`
(endpoint `/modulo-contratacoes/1_consultarContratacoes_PNCP_14133` do
Compras.gov.br), **tem um filtro de CNPJ que realmente funciona no
servidor** — confirmado com requisições HTTP reais (não a ferramenta de
fetch genérica, que retorna falsos 404 nesse domínio por causa de
parâmetros obrigatórios que ela não define): sem filtro de CNPJ, uma consulta
retornou 18.605 resultados de dezenas de órgãos distintos; com
`orgaoEntidadeCnpj` do Ministério, retornou exatamente 0 (consistente com um
filtro real, não com um parâmetro ignorado — se fosse ignorado veríamos a
mesma centena de órgãos aleatórios de novo).

**Bug real encontrado, dentro do escopo desta feature:**
`consultar_contratacoes_pncp()` (linha ~191 de `comprasgov_client.py`) envia
o parâmetro como `cnpjOrgao`, mas o nome correto aceito pela API é
**`orgaoEntidadeCnpj`** (confirmado via OpenAPI spec ao vivo em
`/v3/api-docs`). Isso também explica por que esse cliente pode estar
retornando 0 resultados hoje em produção mesmo sem estar quebrado
"visivelmente" (falha silenciosa). Corrigir esse parâmetro é necessário para
esta feature funcionar e está dentro do escopo (é o mecanismo que o modo
"buscar todos" depende).

Esse mesmo endpoint também exige `codigoModalidade` (obrigatório — não tem
busca "todas as modalidades" de uma vez) e um intervalo de datas de no
máximo 365 dias. O modo "buscar todos" portanto itera
`ORGAOS_SAUDE_FEDERAL` (por CNPJ) × códigos de modalidade relevantes
(pregão eletrônico, dispensa eletrônica, concorrência etc. — a lista exata
de códigos é levantada/validada na implementação), dentro de uma janela de
data de até 365 dias, e agrega os resultados. Isso substitui a ideia
original de "varredura por UASG via ComprasNet/CnetMobile" (endpoints
mortos) descartada após a validação.

## Testes

- Unitário: `bate_orgao_saude` — casos de CNPJ exato, keyword com/sem acento,
  não-match.
- Unitário: `BuscaServiceV2.buscar(apenas_ministerio_saude=True)` com termo —
  confirma que resultados de órgãos fora da lista são descartados.
- Unitário: varredura por UASG (termo vazio) — usando fakes de HTTP, confirma
  que itera `ORGAOS_SAUDE_FEDERAL` e agrega resultados.
- Não há teste de integração ao vivo contra PNCP/ComprasNet nesta feature
  (mesma limitação já aceita pelas demais buscas externas do projeto — sem
  mocks de rede, aviso, ver testes existentes de `comprasnet_search_service`
  e `pncp_search_service`, que não têm cobertura unitária hoje).
