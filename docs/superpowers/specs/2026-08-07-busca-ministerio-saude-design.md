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

### B. `BuscaServiceV2.buscar()` (`backend/services/busca_service_v2.py`)

Novo parâmetro `apenas_ministerio_saude: bool = False`.

- **Com `termo_busca` preenchido**: fluxo atual roda sem mudanças (local
  `editais_gsm` + PNCP ao vivo por termo). No fim, se
  `apenas_ministerio_saude`, filtra `resultados_total` mantendo só itens onde
  `bate_orgao_saude(item['orgao'], item['orgao_cnpj'])`.
- **Sem `termo_busca`** (`apenas_ministerio_saude=True` e termo vazio): como a
  busca nacional por termo não roda sem termo, este caso dispara uma
  varredura direta por UASG — revive `_buscar_em_uasgs_saude()` de
  `comprasnet_search_service.py`, atualizado para iterar `ORGAOS_SAUDE_FEDERAL`
  (em vez da lista antiga incompleta) e sem exigir termo de match.

### C. Endpoint (`backend/server.py`)

`GET /api/search/unified` ganha parâmetro opcional `ministerio_saude: bool`,
repassado para `BuscaServiceV2.buscar(apenas_ministerio_saude=...)`.

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

## Risco conhecido

`comprasnet_search_service.py` nunca foi validado em produção (nunca foi
chamado pelo pipeline real). Os endpoints que ele usa (CnetMobile, dados
abertos do Compras.gov.br) podem estar quebrados, mudados ou instáveis. A
primeira tarefa da implementação deve validar ao vivo se pelo menos um desses
endpoints ainda funciona antes de revivê-lo; se nenhum funcionar, o modo
"buscar todos" (termo vazio) usa `pncp_search_service` iterando um termo
neutro por UASG como alternativa, documentada durante a implementação.

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
