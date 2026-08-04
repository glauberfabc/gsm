# Motor de Busca Estrita — Janela ANVISA (DAMA) — Design

## Contexto

O endpoint `GET /api/anvisa/buscar-medicamento?q=` (implementado em
`backend/services/medicamento_search_service.py`, classe
`MedicamentoSearchService.buscar()`) consulta 7 fontes em paralelo (DOU, Base
GSM, CMED-risco, Notícias ANVISA, PNCP Deserto/Fracassado, ANVISA
Descontinuação, Registro ANVISA dados abertos) usando **correspondência de
texto solta**, o que produz falsos positivos:

- **PNCP** (`_buscar_pncp_deserto`, linha 484): o filtro de relevância é
  `termo.lower()[:4] not in full` — basta os 4 primeiros caracteres do termo
  buscado aparecerem em qualquer lugar do título/descrição do edital.
- **DOU** (`_buscar_dou`): aceita o resultado se **qualquer** token >3
  caracteres do termo aparecer no texto (`termos_sig`), sem exigir todas as
  palavras do princípio ativo nem verificar concentração.
- **Base GSM / CMED-risco / Registro ANVISA** (consultas Mongo): regex de
  substring sobre `principio_ativo`/`titulo`/`nome_produto`/
  `medicamento_detectado`, sem nenhuma verificação de concentração ou forma
  farmacêutica.

Não existe hoje nenhum parsing de "MEPOLIZUMABE 100 MG/ML" em componentes
estruturados — o motor inteiro roda sobre uma única string livre (`termo`).

Este documento cobre a **Etapa 1** de um plano em duas etapas (a segunda,
ingestão da tabela de preços CMED PF/PMC/PMVG por UF, é um ciclo de spec
separado, feito só depois de validar esta etapa):

Corrigir o motor de busca para exigir correspondência estrita por **princípio
ativo** (obrigatório) e **concentração** (quando informada na busca),
eliminando falsos positivos nas 7 fontes já existentes, sem trocar a forma
como o usuário pesquisa (segue sendo um único campo de texto livre) e sem
adicionar fontes novas.

## Fora de escopo (Etapa 1)

- Tabela `cmed_precos` (PF/PMC/PMVG por UF, planilhas mensais da ANVISA) —
  próximo ciclo de spec.
- PNCP por item/lote (endpoint oficial de itens da contratação,
  `descricaoItem`) — o PNCP continua no nível de edital (endpoint de busca
  livre já usado hoje). Ver "Limitação conhecida" abaixo.
- Exclusão de "similares terapêuticos" (ex.: descartar Omalizumabe ao buscar
  Mepolizumabe) — exigiria um dicionário/ontologia de moléculas relacionadas
  que não existe no sistema. A Etapa 1 resolve o caso mais comum e mais
  danoso (falso positivo por substring/token solto), não a similaridade
  terapêutica entre moléculas distintas.
- Mudança no formato do campo de busca no frontend (continua um único input
  de texto).

## Parser de query estruturada

Novo módulo `backend/services/medicamento_query_parser.py`, função:

```python
def parse_query(termo: str) -> QueryEstruturada:
    ...
```

`QueryEstruturada` é um `TypedDict`/`dataclass` simples:

```python
class QueryEstruturada(TypedDict):
    termo_original: str
    principio_ativo: str          # sempre presente
    concentracao: Optional[str]   # None se não detectada
    forma_farmaceutica: Optional[str]
```

Estratégia de extração (regex + dicionário, sem dependência externa):

1. **Concentração**: regex sobre padrões de dosagem comuns, nessa ordem de
   prioridade (a primeira que casar vence, para preferir formas compostas):
   - `\d+[.,]?\d*\s*(MG|MCG|G|UI)\s*/\s*(ML|G|DOSE)` (ex: `100 MG/ML`)
   - `\d+[.,]?\d*\s*(MG|MCG|G|UI|ML)` (ex: `50MG`, `10 UI`)
2. **Forma farmacêutica**: lista fixa de termos conhecidos (case-insensitive,
   sem acento), buscada como frase dentro do termo:
   `CANETA APLICADORA`, `CANETA PRE-CHEIA`, `SERINGA PREENCHIDA`,
   `FRASCO-AMPOLA`, `FRASCO AMPOLA`, `PO LIOFILIZADO`, `PO PARA SOLUCAO`,
   `SOLUCAO INJETAVEL`, `COMPRIMIDO`, `CAPSULA`, `XAROPE`, `SUSPENSAO ORAL`,
   `CREME`, `POMADA`, `GEL`. Lista mantida no próprio módulo, extensível.
3. **Princípio ativo**: o que sobra do termo original após remover (por
   posição, não por regex global) o trecho de concentração e o trecho de
   forma farmacêutica encontrados, com espaços colapsados e `.strip()`.
   Se nada for removido (busca só com o nome), `principio_ativo` é o termo
   inteiro — comportamento idêntico ao atual para buscas simples.

Exemplo: `"MEPOLIZUMABE 100 MG/ML CANETA APLICADORA"` →
`principio_ativo="MEPOLIZUMABE"`, `concentracao="100 MG/ML"`,
`forma_farmaceutica="CANETA APLICADORA"`.

`parse_query` nunca vê `/` diretamente: o split por `/` acontece **antes**,
uma única vez, em `buscar()` (ver "Compatibilidade com nomes compostos"
abaixo), e `parse_query` roda uma vez por metade.

Exemplo: `"Synvisc Classic 2ml / Hilano G-F 20"` → `buscar()` separa em
`["Synvisc Classic 2ml", "Hilano G-F 20"]` e chama `parse_query` em cada
parte, gerando duas `QueryEstruturada` (`principio_ativo="Synvisc
Classic"`/`concentracao="2ML"` e `principio_ativo="Hilano G-F
20"`/`concentracao=None`).

## Matching estrito

Novo helper no mesmo módulo (ou em `backend/utils/`):

```python
def normalizar(texto: str) -> str:
    """minúsculas, sem acento, espaços colapsados"""

def contem_termo_estrito(texto: str, termo: str) -> bool:
    """
    True se TODAS as palavras significativas (>2 chars) de `termo`
    aparecem em `texto`, cada uma respeitando fronteira de palavra
    (\\b), após normalizar ambos.
    """

def contem_concentracao(texto: str, concentracao: str) -> bool:
    """
    Compara concentração tolerando variação de espaço em torno de
    unidades (ex.: '100mg/ml' == '100 MG/ML' == '100 MG / ML').
    """
```

`contem_termo_estrito` substitui:
- o filtro do PNCP (`termo.lower()[:4] not in full`);
- o filtro `termos_sig` do DOU (que aceita **qualquer** token);
- os regex de substring soltos usados nas queries Mongo (a query Mongo
  continua buscando candidatos de forma ampla por performance — ver seção
  seguinte — mas o resultado final é sempre confirmado por
  `contem_termo_estrito` em Python antes de entrar na resposta).

Diferença central da regra atual: hoje "qualquer palavra bate" (OR entre
tokens); a regra nova é "toda palavra do princípio ativo precisa bater" (AND
entre tokens), com fronteira de palavra para não confundir `ACICLOVIR` com
`VALACICLOVIR`.

## Aplicação por fonte

Em `buscar()`, antes de disparar as 7 fontes: se `termo` contém `/`, é
dividido em partes (`partes = [p.strip() for p in termo.split('/') if
p.strip()]`, a mesma lógica hoje restrita às fontes de DB); senão, `partes =
[termo]`. Cada parte passa por `parse_query`, gerando uma lista de
`QueryEstruturada` (`queries_estruturadas`). Essa lista — não mais o `termo`
cru — é repassada a todas as 7 fontes.

O filtro de princípio ativo em cada fonte passa a ser: **item aceito se
`contem_termo_estrito` bater com o `principio_ativo` de QUALQUER uma** das
`queries_estruturadas` (OR entre as partes, AND entre as palavras dentro de
cada parte — igual ao comportamento atual de tentar cada metade do nome
composto, só que agora com matching estrito em vez de substring solto).

| Fonte | Antes | Depois |
|---|---|---|
| DOU (`_buscar_dou`) | aceita se qualquer token >3 chars bate | exige `contem_termo_estrito(titulo+abstract, principio_ativo)` |
| PNCP (`_buscar_pncp_deserto`) | `termo[:4] in full` | exige `contem_termo_estrito(title+desc, principio_ativo)` |
| Base GSM (`_buscar_alertas_db`) | regex substring no Mongo, sem pós-filtro | query Mongo inalterada (candidatos), **+ pós-filtro** `contem_termo_estrito` em Python descarta falsos positivos antes do dedup |
| CMED-risco (`_buscar_cmed_db`) | idem acima | idem acima |
| Registro ANVISA (`_buscar_registro_cancelado`) | idem acima | idem acima |
| Notícias ANVISA (`_buscar_noticias_anvisa`) | filtro por qualquer palavra ≥3 chars | exige `contem_termo_estrito` |
| ANVISA Descontinuação (`_buscar_descontinuacao`) | `termo.lower() in text.lower()` (já é razoavelmente estrito, mas sem fronteira de palavra) | troca para `contem_termo_estrito` |

### Concentração (quando `parse_query` detectou uma)

Para cada resultado que passou no filtro de princípio ativo, usa-se a
`concentracao` da **mesma parte** (`QueryEstruturada`) cujo `principio_ativo`
casou o resultado (no caso comum de termo sem `/`, é a única parte). Se essa
parte tem `concentracao`:
- roda `contem_concentracao(titulo+descricao, concentracao)`;
- se `True` → `resultado['concentracao_confirmada'] = True`;
- se `False` → `resultado['concentracao_confirmada'] = False` (**item
  mantido**, não descartado — textos curtos de edital/notícia frequentemente
  omitem a dose).

Se a parte que casou não tinha concentração detectada, `concentracao_confirmada
= None` (campo neutro, sem verificação aplicável).

### Impacto na priorização (`_calcular_prioridade`)

`concentracao_confirmada == False` soma +1 à prioridade calculada atualmente
(desloca para depois dos resultados com concentração confirmada, mas antes
de "rotina"/"obsoleto"), exceto quando a classificação já é `rotina` ou o
item já está marcado obsoleto — nesses casos a prioridade existente (5 ou 6)
prevalece, pois já é o pior nível.

### Compatibilidade com nomes compostos (`Synvisc Classic 2ml / Hilano G-F 20`)

Hoje só `_buscar_alertas_db`, `_buscar_cmed_db` e `_buscar_registro_cancelado`
fazem split manual por `/` (comentário existente: "banco pode ter armazenado
apenas uma das formas do nome"); DOU e PNCP não tratam esse caso. Com a
mudança descrita em "Aplicação por fonte", o split por `/` passa a acontecer
uma única vez em `buscar()`, antes de qualquer fonte, e vale para as 7 —
unificando o comportamento (DOU e PNCP passam a se beneficiar do split
também, o que é uma correção incidental, não uma regressão).

## Resposta da API

`buscar()` passa a incluir no dict de retorno o parse da **primeira** parte
(`queries_estruturadas[0]` — no caso comum sem `/`, é a única):

```python
"search_query_parsed": {
    "principio_ativo": "...",
    "concentracao": "..." | None,
    "forma_farmaceutica": "..." | None,
},
```

Esse campo é informativo (mostra ao usuário o que o parser entendeu do termo
buscado); o matching real usa todas as partes, conforme "Aplicação por
fonte".

Cada item em `resultados` ganha o campo `concentracao_confirmada: bool |
None`, conforme regra acima. Nenhum campo existente é removido ou renomeado
— mudança aditiva, o frontend atual continua funcionando sem alteração
(pode opcionalmente exibir os campos novos depois).

## Limitação conhecida (documentada, não corrigida nesta etapa)

Como o PNCP continua no nível de edital (não por item/lote), um edital que
tenha um lote de Mepolizumabe e outro de Omalizumabe **ainda vai aparecer**
na busca por Mepolizumabe, porque o princípio ativo bate em algum lugar do
texto do edital. A Etapa 1 elimina os falsos positivos por substring/token
solto (o problema mais comum e mais grave hoje), mas não a mistura de lotes
dentro do mesmo edital — isso requer o endpoint de itens da contratação do
PNCP, fora de escopo aqui.

## Testes

Arquivos existentes a estender:
- `backend/tests/test_buscar_medicamento_v2_dama.py`
- `backend/tests/test_buscar_medicamento_v3_janela_refactor.py`

Novos casos:
1. `parse_query`: extrai corretamente princípio ativo / concentração / forma
   farmacêutica para os formatos do exemplo (`MEPOLIZUMABE 100 MG/ML`,
   `MEPOLIZUMABE 100 MG/ML CANETA APLICADORA`, busca só com nome).
2. `contem_termo_estrito`: `"ACICLOVIR"` não bate em texto que só contém
   `"VALACICLOVIR"` (regressão do bug de substring); `"ACIDO
   VALPROICO"` exige as duas palavras presentes.
3. PNCP: edital cujo texto contém uma palavra que só coincide nos 4 primeiros
   caracteres do termo buscado (ex. termo `"ATENOLOL"`, texto contendo
   apenas `"atendimento"`, sem `"atenolol"`) deixa de aparecer — hoje esse
   edital passaria pelo filtro `termo[:4] in full`.
4. DOU: resultado que bate em token genérico mas não no princípio ativo
   completo é descartado.
5. Concentração ausente no texto → resultado mantido com
   `concentracao_confirmada=False`, não descartado.
6. Regressão do caso `Synvisc Classic 2ml / Hilano G-F 20` (split por `/`
   continua funcionando).
7. Resposta da API inclui `search_query_parsed` com os valores esperados.
