# Sino de Notificações — Feed de Inteligência Regulatória — Design

## Contexto

O sino de notificações no topo da aplicação (`frontend/src/components/layout/Header.jsx`,
usado em `App.jsx`, o módulo "Janela ANVISA"/DAMA) hoje é alimentado
**exclusivamente** pelos alertas de oportunidade LMR (score ≥ 80%, motor
tributário implementado numa sessão anterior — `LmrService._salvar_alerta_oportunidade`,
coleção `oportunidades_alertas`, endpoint `GET /api/notificacoes/oportunidades`,
hook `frontend/src/hooks/useNotificacoes.js`).

**Importante — não confundir com outro sistema:** existe um segundo componente de
notificações no repositório, `frontend/src/components/NotificacaoBadge.js` +
`frontend/src/pages/NotificacoesPage.js`, que gerencia alertas de **licitação**
(palavra-chave/estado/modalidade, coleções `alertas`/`notificacoes`). Esse sistema
é usado por outras telas do app (fora do módulo Janela ANVISA) e **não faz parte
deste ajuste** — nenhuma mudança nele.

Esta spec cobre a transformação do sino do módulo Janela ANVISA (`Header.jsx`) num
feed de inteligência regulatória, disparando exclusivamente para 4 categorias de
eventos ANVISA/DOU, cada um com link rastreável até a fonte oficial. Os alertas de
oportunidade LMR saem do sino (confirmado com o usuário) — o motor e o e-mail de
oportunidade continuam funcionando normalmente, só não aparecem mais no dropdown do
sino.

## Fora de escopo

- Sistema de alertas de licitação (`NotificacaoBadge.js`/`NotificacoesPage.js`) — não
  relacionado, não tocado.
- E-mail para as novas notificações regulatórias — só o feed do sino. O motor de
  e-mail de oportunidade LMR (`_disparar_email_oportunidade`) continua existindo,
  apenas não aparece mais no sino.
- Categoria "regulamentação"/"informativo" (tipos já existentes em `anvisa_alertas`)
  — continuam sendo classificados e salvos como antes, mas não geram notificação no
  sino (não são nenhuma das 4 categorias pedidas).

## Fontes de dados por categoria

### 1. Desabastecimento + 2. Cancelamentos e Suspensões (RE) + 4. Notícias de Laboratório

Fonte: job já existente `job_anvisa_radar` (`backend/scheduler.py`, roda a cada 12h
às 7h/19h), que chama `AnvisaScraper.coletar_tudo()` +
`DesabastecimentoService.processar_alertas()`. Esse pipeline já classifica cada item
coletado do DOU/notícias ANVISA num `tipo_alerta`, majoritariamente via IA (Gemini,
`_analisar_com_ia`), com fallback por palavra-chave (`_analise_keywords`) quando a
IA falha ou não está configurada.

Mapeamento `tipo_alerta` → categoria do sino:

| `tipo_alerta` (já existente ou novo) | Categoria do sino |
|---|---|
| `desabastecimento`, `interrupção fabricação` | `desabastecimento` |
| `descontinuação`, `recolhimento`, `proibição` | `cancelamento_suspensao` |
| `laboratorio` (**novo**, ver abaixo) | `laboratorio` |
| `importação excepcional`, `decisão judicial`, `regulamentação`, `informativo` | *(nenhuma — não gera notificação no sino)* |

#### Adição do tipo `laboratorio`

A classificação primária é feita pelo Gemini (`_analisar_com_ia`,
`backend/services/desabastecimento_service.py`), cujo system prompt define um enum
fechado de `tipo_alerta` — hoje sem nenhum valor para mudança de titularidade/rótulo/
bula. É necessário adicionar um 10º valor ao enum do prompt:

```
3. "tipo_alerta": "importação excepcional" | "decisão judicial" | "desabastecimento" | "descontinuação" | "interrupção fabricação" | "recolhimento" | "proibição" | "regulamentação" | "laboratorio" | "informativo"
```

com uma linha explicando o novo valor, por exemplo:

```
"laboratorio": mudança de titularidade de registro, alteração pós-registro,
atualização de bula ou rotulagem crítica de medicamento por parte do laboratório
detentor (não é desabastecimento nem cancelamento).
```

O fallback por palavra-chave (`_analise_keywords`) ganha um novo grupo de
verificação (`is_laboratorio`, testado antes do `else: informativo` final) com
termos como `transferência de titularidade`, `alteração pós-registro`,
`atualização de bula`, `alteração de rotulagem`.

O filtro de relevância do scraper (`AnvisaScraper._filtrar_relevantes`, em
`backend/services/anvisa_scraper.py`) precisa reconhecer esses mesmos termos como
relevantes (`KW_LABORATORIO`, nova lista de palavras-chave), senão esses itens nunca
chegam a ser classificados — hoje só passam pelo filtro itens que batem em
`KW_IMPORTACAO`/`KW_JUDICIAL`/`KW_DESABASTECIMENTO`/`KW_SAUDE` ou têm `numero_re`/
`tipo_documento`. `KW_SAUDE` já é ampla o suficiente para deixar passar a maior
parte dessas notícias (contém `medicamento`, `farmácia`), mas `KW_LABORATORIO`
garante isso de forma explícita e documentada, sem depender de coincidência.

Essa mudança é aditiva e segura para os demais consumidores de `anvisa_alertas`
(`medicamento_search_service.py`, `LmrService._classificar_lmr`) — nenhum deles faz
switch exaustivo sobre `tipo_alerta`; todos usam `.get()` com fallback ou checagem
de substring, então um valor novo não quebra nada existente.

### 3. Novos Registros

Fonte: job diário `job_anvisa_registro` (`backend/scheduler.py`), que chama
`sincronizar_registro_medicamentos` (`backend/services/anvisa_registro_service.py`,
já reescrito numa sessão anterior para separar registros ativos/inativos em duas
coleções com troca atômica via rename).

**Mecanismo de detecção de "novo"**: antes de fazer a troca atômica da coleção
`anvisa_registro_medicamentos_ativos`, ler o conjunto de `numero_registro_produto`
já presentes nela (o snapshot "antigo", ainda live até o rename acontecer) e
comparar contra o `numero_registro_produto` de cada doc em `docs_ativos` (o lote
"novo" que acabou de ser baixado do CSV). Registros cujo `numero_registro_produto`
não estava no snapshot antigo geram uma notificação `novo_registro`.

```python
async def _detectar_novos_registros(db, docs_ativos: list) -> list:
    """Retorna os docs de docs_ativos cujo numero_registro_produto nao
    estava na colecao anvisa_registro_medicamentos_ativos antes desta
    sincronizacao (chamado ANTES da troca atomica de colecao)."""
    numeros_novos = {d['numero_registro_produto'] for d in docs_ativos if d.get('numero_registro_produto')}
    if not numeros_novos:
        return []
    existentes = await db.anvisa_registro_medicamentos_ativos.find(
        {'numero_registro_produto': {'$in': list(numeros_novos)}},
        {'_id': 0, 'numero_registro_produto': 1},
    ).to_list(length=len(numeros_novos))
    numeros_existentes = {e['numero_registro_produto'] for e in existentes}
    return [d for d in docs_ativos if d.get('numero_registro_produto') and d['numero_registro_produto'] not in numeros_existentes]
```

Chamado dentro de `sincronizar_registro_medicamentos`, logo antes de
`await _substituir_colecao(db, 'anvisa_registro_medicamentos_ativos', docs_ativos)`.
Na primeira execução após este deploy, a coleção `anvisa_registro_medicamentos_ativos`
já estará populada (desde a sessão anterior) — então **não** vai gerar uma avalanche
de "novos registros" para todo o dataset existente; só registros que aparecerem a
partir de agora contam como novos. (Se a coleção estivesse vazia na primeira
execução, todo o dataset seria marcado como "novo" — não é o caso aqui.)

## Coleção e endpoints novos

Nova coleção `notificacoes_regulatorias`:

```python
{
    'id': str,                      # uuid4
    'categoria': str,                # 'desabastecimento' | 'cancelamento_suspensao' | 'novo_registro' | 'laboratorio'
    'titulo': str,
    'descricao': str,                # resumo, ate 500 chars
    'medicamento': str,              # quando aplicavel, pode ser vazio
    'url_fonte_oficial': str,        # link da fonte (DOU/ANVISA) ou '' se indisponivel
    'data_evento': str,              # data_publicacao da fonte, quando disponivel
    'chave_dedup': str,              # link/titulo (fontes 1,2,4) ou numero_registro_produto (fonte 3)
    'lida': bool,
    'criado_em': str,                # ISO 8601 UTC
}
```

Novo módulo `backend/services/notificacoes_regulatorias_service.py`:

```python
import uuid
from datetime import datetime, timezone
from typing import Dict, List

CATEGORIAS_BELL = {
    'desabastecimento': 'desabastecimento',
    'interrupção fabricação': 'desabastecimento',
    'descontinuação': 'cancelamento_suspensao',
    'recolhimento': 'cancelamento_suspensao',
    'proibição': 'cancelamento_suspensao',
    'laboratorio': 'laboratorio',
}


async def criar_a_partir_de_alertas_anvisa(db, alertas_processados: List[Dict]) -> int:
    """Cria notificacoes regulatorias (fontes 1, 2, 4) a partir da lista
    retornada por DesabastecimentoService.processar_alertas(). Deduplica
    por link (ou titulo, se nao houver link)."""
    criadas = 0
    for alerta in alertas_processados:
        categoria = CATEGORIAS_BELL.get(alerta.get('tipo_alerta'))
        if not categoria:
            continue

        chave_dedup = alerta.get('link') or alerta.get('titulo', '')[:120]
        if not chave_dedup:
            continue

        existente = await db.notificacoes_regulatorias.find_one({'chave_dedup': chave_dedup})
        if existente:
            continue

        doc = {
            'id': str(uuid.uuid4()),
            'categoria': categoria,
            'titulo': alerta.get('titulo', ''),
            'descricao': (alerta.get('descricao') or alerta.get('situacao') or '')[:500],
            'medicamento': alerta.get('medicamento_detectado') or alerta.get('medicamento') or '',
            'url_fonte_oficial': alerta.get('link', ''),
            'data_evento': alerta.get('data_publicacao', ''),
            'chave_dedup': chave_dedup,
            'lida': False,
            'criado_em': datetime.now(timezone.utc).isoformat(),
        }
        await db.notificacoes_regulatorias.insert_one(doc)
        criadas += 1

    return criadas


async def criar_a_partir_de_novos_registros(db, novos_registros: List[Dict]) -> int:
    """Cria notificacoes regulatorias (fonte 3) a partir dos registros
    detectados como novos por _detectar_novos_registros(). Deduplica por
    numero_registro_produto.

    Nota: o dataset de dados abertos da ANVISA nao fornece uma URL por
    registro individual, entao `url_fonte_oficial` fica vazio aqui (ver
    secao "Limitacao conhecida" abaixo) - o frontend simplesmente nao
    mostra o botao de link para esta categoria.
    """
    criadas = 0
    for registro in novos_registros:
        numero = registro.get('numero_registro_produto', '')
        if not numero:
            continue

        existente = await db.notificacoes_regulatorias.find_one({'chave_dedup': numero})
        if existente:
            continue

        nome = registro.get('nome_produto', '')
        empresa = registro.get('empresa_detentora_registro', '')
        doc = {
            'id': str(uuid.uuid4()),
            'categoria': 'novo_registro',
            'titulo': f'Novo registro ANVISA - {nome}',
            'descricao': f"Empresa: {empresa} | Registro nº {numero}"[:500],
            'medicamento': nome,
            'url_fonte_oficial': '',
            'data_evento': registro.get('data_finalizacao_processo', ''),
            'chave_dedup': numero,
            'lida': False,
            'criado_em': datetime.now(timezone.utc).isoformat(),
        }
        await db.notificacoes_regulatorias.insert_one(doc)
        criadas += 1

    return criadas
```

### Limitação conhecida — link oficial na categoria "Novos Registros"

O CSV de dados abertos da ANVISA (fonte de `anvisa_registro_service.py`) não traz
uma URL individual por registro — só os campos tabulares (nome, princípio ativo,
empresa, número de registro, datas). Não há, hoje, uma forma confirmada de montar um
link direto e válido para "Consulta de Produtos" da ANVISA por número de registro
sem verificar o formato real da URL (evitando fabricar uma URL não confirmada).
Por isso, para a categoria `novo_registro`, `url_fonte_oficial` fica vazio e o botão
"🔗 Acessar Documento Oficial" **não é exibido** nesse caso (a UI já trata isso
condicionalmente). As outras 3 categorias (desabastecimento, cancelamento_suspensao,
laboratorio) sempre têm `url_fonte_oficial` preenchido, pois vêm de itens do
DOU/notícias ANVISA que já carregam `link`.

Novos endpoints em `backend/server.py`, seguindo o padrão já existente das rotas
`/notificacoes/oportunidades/*`:

```python
@api_router.get("/notificacoes/regulatorias")
async def listar_notificacoes_regulatorias(limite: int = Query(15, ge=1, le=50)):
    """Lista notificacoes regulatorias (sino), mais recentes primeiro."""
    try:
        notificacoes = await db.notificacoes_regulatorias.find(
            {}, {"_id": 0}
        ).sort("criado_em", -1).to_list(length=limite)
        nao_lidas = sum(1 for n in notificacoes if not n.get('lida'))
        return {
            "alertas": notificacoes,
            "total": len(notificacoes),
            "nao_lidas": nao_lidas,
        }
    except Exception as e:
        logger.error(f"Erro ao listar notificacoes regulatorias: {e}")
        return {"alertas": [], "total": 0, "nao_lidas": 0}


@api_router.post("/notificacoes/regulatorias/{notificacao_id}/lida")
async def marcar_notificacao_regulatoria_lida(notificacao_id: str):
    """Marca uma notificacao regulatoria como lida."""
    try:
        result = await db.notificacoes_regulatorias.update_one(
            {"id": notificacao_id},
            {"$set": {"lida": True}}
        )
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Notificacao nao encontrada")
        return {"message": "Notificacao marcada como lida", "id": notificacao_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao marcar notificacao regulatoria: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

O formato de resposta (`alertas`/`total`/`nao_lidas`) é o mesmo já usado por
`GET /api/notificacoes/oportunidades`, propositalmente — mantém o hook
`useNotificacoes.js` funcionando com a troca mínima de URL, sem mudar a forma como
consome a resposta (`res.data.alertas`).

As rotas `/notificacoes/oportunidades/*` (LMR) **não são removidas** — continuam
existindo para o fluxo de e-mail de oportunidade (deep-link `?alerta={id}` já usado
por `_disparar_email_oportunidade`).

## Frontend

### `useNotificacoes.js`

Passa a chamar `GET /api/notificacoes/regulatorias?limite=15` (em vez de
`/notificacoes/oportunidades`) e `POST /api/notificacoes/regulatorias/{id}/lida` (em
vez de `/notificacoes/oportunidades/{id}/lida`). Mesma forma de hook (`notificacoes`,
`naoLidas`, `showDropdown`, `marcarLida`), sem mudança de interface para
`Header.jsx` além dos campos que cada item carrega.

### `Header.jsx`

O bloco do dropdown (`data-testid="notificacao-dropdown"`) é reescrito para:
- Cabeçalho: troca "⚡ Alertas de Oportunidade" por algo como "📋 Feed Regulatório
  ANVISA/DOU".
- Cada item mostra: badge de categoria (cor por categoria: desabastecimento=vermelho,
  cancelamento_suspensao=laranja, novo_registro=azul, laboratorio=roxo), título,
  medicamento (quando houver), data do evento.
- Clique no item expande (mesmo padrão de `expandedIdx` já usado em
  `RadarLmrTab.jsx`'s `OportunidadeCard`) mostrando a descrição completa e um botão
  "🔗 Acessar Documento Oficial" (`<a href={item.url_fonte_oficial} target="_blank"
  rel="noopener noreferrer">`) — só renderizado se `url_fonte_oficial` não for vazio.
  Expandir também chama `marcarLida(item.id)` (mesmo comportamento de clique atual).

## Testes

Backend, sem rede/DB real (fakes, seguindo o padrão já usado nas sessões
anteriores — `backend/tests/test_lmr_service_unit.py`,
`backend/tests/test_anvisa_registro_service_sync.py`):

1. `criar_a_partir_de_alertas_anvisa`: mapeia corretamente cada `tipo_alerta` para
   sua categoria (ou nenhuma, para os tipos fora de escopo); dedup por `link`
   funciona (segunda chamada com o mesmo `link` não cria duplicata).
2. `criar_a_partir_de_novos_registros`: só cria notificação para
   `numero_registro_produto` que não estava na coleção antes; dedup funciona.
3. `_detectar_novos_registros`: com coleção "antiga" vazia vs. com conteúdo prévio,
   retorna os deltas corretos.
4. Fallback de palavra-chave (`_analise_keywords`) classifica corretamente um texto
   com termos de `KW_LABORATORIO` como `tipo_alerta='laboratorio'`.
5. `_filtrar_relevantes` deixa passar um item cujo único gatilho é
   `KW_LABORATORIO` (não teria passado antes desta mudança).
6. Regressão de integração: `GET /api/notificacoes/regulatorias` retorna a
   estrutura esperada (campos presentes).

Frontend: sem testes automatizados de componente no repositório (convenção já
confirmada nas sessões anteriores) — verificação via `npm run build` +
checagem manual no navegador.
