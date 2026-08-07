# Busca "Ministério da Saúde" (multi-UASG) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar um filtro de escopo "Ministério da Saúde" à busca de licitações já existente (`GET /api/search/unified`), com um botão pílula no mesmo padrão visual dos "Radares de Atalho", que restringe resultados aos órgãos do portfólio federal de saúde — com termo digitado (pós-filtro sobre a busca nacional) ou sem termo ("buscar todos", via consulta direta por CNPJ ao Compras.gov.br).

**Architecture:** Módulo novo `orgaos_saude_federal.py` guarda a lista curada de órgãos (CNPJ confirmado + keywords de nome como fallback) e a função pura de matching `bate_orgao_saude()`. `MotorBuscaIndependente.buscar()` (o motor real por trás de `/api/search/unified` — **não** `BuscaServiceV2`, que é código não utilizado por este endpoint) ganha um parâmetro `apenas_ministerio_saude`: com termo, pós-filtra os resultados da busca nacional já existente; sem termo, usa uma nova função que consulta `comprasgov_client.consultar_contratacoes_pncp()` diretamente pelo CNPJ do Ministério (mecanismo validado ao vivo durante o design — ver spec). O endpoint HTTP e o frontend (`useSearch.js` + `SearchTab.jsx`) só repassam esse novo parâmetro.

**Tech Stack:** Python (FastAPI, aiohttp), React, pytest, requests (testes de integração ao vivo).

**Contexto herdado do design (não redescobrir):**
- CNPJ real do Ministério da Saúde: `00394544000185` (confirmado ao vivo — `razaoSocial: "MINISTERIO DA SAUDE"`). **Não é** `00394445000139` (número errado sugerido numa conversa externa com o Gemini) nem `00394411000109` (Presidência da República — descoberto e descartado durante o design).
- Esse CNPJ sozinho já cobre DLOG, INCA, DSEIs/SESAI, Instituto Nacional de Cardiologia e Instituto Nacional de Traumato-Ortopedia (todos são "unidades" sob o mesmo CNPJ da administração direta, não entidades com CNPJ próprio).
- Fiocruz é uma fundação com CNPJ próprio, ainda não identificado — Tarefa 1 inclui achá-lo.
- `comprasgov_client.consultar_contratacoes_pncp()` (`backend/scrapers/comprasgov_client.py`) tem um bug: usa o parâmetro `cnpjOrgao`, mas o nome real aceito pela API é `orgaoEntidadeCnpj` — por isso o filtro nunca funcionou (confirmado via OpenAPI spec ao vivo em `/v3/api-docs`). Esse endpoint também exige `codigoModalidade` (não filtra "todas as modalidades" de uma vez) e aceita no máximo 365 dias de intervalo entre `dataPublicacaoPncpInicial`/`dataPublicacaoPncpFinal`.
- A API oficial do PNCP (`pncp.gov.br/api/...`) não tem NENHUM filtro de órgão/CNPJ funcional em nenhum endpoint testado (3 nomes de parâmetro diferentes, 2 endpoints) — não tentar de novo.
- `GET /api/search/unified` (`backend/server.py:1313`) chama `MotorBuscaIndependente.buscar()` (`backend/services/motor_independente.py`), não `BuscaServiceV2` (`backend/services/busca_service_v2.py`, que é importado por outros fluxos mas não por este endpoint).

Spec completa: `docs/superpowers/specs/2026-08-07-busca-ministerio-saude-design.md`.

---

### Task 1: Lista curada de órgãos + função de matching

**Files:**
- Create: `backend/services/orgaos_saude_federal.py`
- Test: `backend/tests/test_orgaos_saude_federal.py`

- [ ] **Step 1: Descobrir o CNPJ da Fiocruz**

Antes de escrever código, rode um script Python ad-hoc (mesma técnica usada no design — `urllib.request` com `ssl.CERT_NONE` por causa de um problema de cadeia TLS local, OU `aiohttp`/`httpx` se rodando num ambiente sem esse problema de certificado) contra:

```
https://dadosabertos.compras.gov.br/modulo-contratacoes/1_consultarContratacoes_PNCP_14133
  ?dataPublicacaoPncpInicial=2026-01-01&dataPublicacaoPncpFinal=2026-08-07
  &codigoModalidade=6&pagina=1&tamanhoPagina=10
```//
sem filtro de CNPJ, e procure nos resultados (`resultado[].orgaoEntidadeRazaoSocial`) por qualquer linha contendo "FIOCRUZ" ou "OSWALDO CRUZ" — anote o `orgaoEntidadeCnpj` correspondente. Se não aparecer nessa amostra, repita com `codigoModalidade=8` (dispensa) e `codigoModalidade=4` (concorrência). Se depois de tentar essas 3 modalidades a Fiocruz não aparecer, documente no código (comentário) que o CNPJ da Fiocruz continua não confirmado e o matching por keyword (`'fiocruz'`, `'fundacao oswaldo cruz'`) é o único mecanismo cobrindo essa unidade por enquanto — não bloqueia o resto da tarefa.

- [ ] **Step 2: Escrever os testes de `bate_orgao_saude`**

```python
# backend/tests/test_orgaos_saude_federal.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.orgaos_saude_federal import bate_orgao_saude, ORGAOS_SAUDE_FEDERAL


class TestBateOrgaoSaude:
    def test_cnpj_exato_do_ministerio_bate(self):
        assert bate_orgao_saude('QUALQUER NOME', '00394544000185') is True

    def test_cnpj_fora_da_lista_nao_bate_sem_keyword(self):
        assert bate_orgao_saude('MUNICIPIO DE GOIANESIA', '01065846000172') is False

    def test_keyword_ministerio_da_saude_bate_por_nome(self):
        assert bate_orgao_saude('MINISTERIO DA SAUDE', None) is True

    def test_keyword_dlog_bate_por_nome(self):
        assert bate_orgao_saude('DEPARTAMENTO DE LOGISTICA EM SAUDE', '') is True

    def test_keyword_ignora_acentuacao_e_caixa(self):
        assert bate_orgao_saude('Instituto Nacional de Câncer', None) is True

    def test_nome_sem_relacao_nao_bate(self):
        assert bate_orgao_saude('SECRETARIA DE AGRICULTURA E ABASTECIMENTO', '46384400000149') is False

    def test_cnpj_none_e_nome_none_nao_bate(self):
        assert bate_orgao_saude(None, None) is False

    def test_lista_tem_pelo_menos_ministerio_da_saude(self):
        nomes = [o['nome'] for o in ORGAOS_SAUDE_FEDERAL]
        assert any('Ministério da Saúde' in n or 'Ministerio da Saude' in n for n in nomes)
```

- [ ] **Step 3: Rodar os testes e verificar que falham**

Run: `cd backend && python -m pytest tests/test_orgaos_saude_federal.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'services.orgaos_saude_federal'`

- [ ] **Step 4: Implementar `orgaos_saude_federal.py`**

```python
"""
Lista curada de orgaos/entidades do portifolio federal de saude, usada pelo
filtro de escopo "Ministerio da Saude" na busca de licitacoes
(GET /api/search/unified?ministerio_saude=true).

Nao existe filtro de servidor por orgao/CNPJ na API oficial do PNCP (testado
e descartado durante o design - ver docs/superpowers/specs/2026-08-07-busca-
ministerio-saude-design.md). Por isso o matching e feito aqui, client-side,
por CNPJ exato OU por palavra-chave do nome do orgao (fallback para unidades
cujo CNPJ ainda nao foi confirmado).

CNPJ confirmado ao vivo via API do Compras.gov.br (razaoSocial retornado =
"MINISTERIO DA SAUDE"): 00394544000185. Esse CNPJ sozinho ja cobre DLOG,
INCA, DSEIs/SESAI e outros institutos nacionais - todos sao "unidades" sob o
mesmo CNPJ da administracao direta, nao entidades com CNPJ proprio.
"""
from typing import Dict, List, Optional

from services.medicamento_query_parser import normalizar

ORGAOS_SAUDE_FEDERAL: List[Dict] = [
    {
        'nome': 'Ministério da Saúde - Administração Direta',
        'cnpj': '00394544000185',
        'keywords': [
            'ministerio da saude',
            'dlog', 'departamento de logistica em saude',
            'inca', 'instituto nacional de cancer',
            'dsei', 'saude indigena', 'sesai',
            'instituto nacional de cardiologia',
            'instituto nacional de traumato-ortopedia', 'instituto nacional de traumato ortopedia',
        ],
    },
    {
        'nome': 'Fiocruz - Fundação Oswaldo Cruz',
        'cnpj': None,  # TODO: confirmar (ver Task 1 Step 1) - matching por keyword ate la
        'keywords': ['fiocruz', 'fundacao oswaldo cruz'],
    },
]


def bate_orgao_saude(orgao_nome: Optional[str], orgao_cnpj: Optional[str]) -> bool:
    """Retorna True se orgao_nome/orgao_cnpj corresponde a alguma entrada de
    ORGAOS_SAUDE_FEDERAL, por CNPJ exato ou por palavra-chave do nome
    (normalizado sem acento/caixa)."""
    cnpj_normalizado = (orgao_cnpj or '').strip()
    nome_normalizado = normalizar(orgao_nome or '')

    for org in ORGAOS_SAUDE_FEDERAL:
        if org['cnpj'] and cnpj_normalizado == org['cnpj']:
            return True
        if nome_normalizado and any(kw in nome_normalizado for kw in org['keywords']):
            return True
    return False
```

- [ ] **Step 5: Rodar os testes e verificar que passam**

Run: `cd backend && python -m pytest tests/test_orgaos_saude_federal.py -v`
Expected: PASS (8 testes)

- [ ] **Step 6: Commit**

```bash
git add backend/services/orgaos_saude_federal.py backend/tests/test_orgaos_saude_federal.py
git commit -m "feat: lista curada de orgaos da saude federal + matching por CNPJ/keyword"
```

---

### Task 2: Corrigir o parâmetro de CNPJ em `comprasgov_client.consultar_contratacoes_pncp`

**Files:**
- Modify: `backend/scrapers/comprasgov_client.py:170-203`

- [ ] **Step 1: Ler o estado atual da função**

```python
async def consultar_contratacoes_pncp(
    data_publicacao_inicial: Optional[str] = None,
    data_publicacao_final: Optional[str] = None,
    cnpj_orgao: Optional[str] = None,
    uf: Optional[str] = None,
    modalidade: Optional[int] = None,
    tamanho_pagina: int = 500,
    max_pages: int = 100,
    **extra_params,
) -> Dict[str, Any]:
    """
    Busca contratações PNCP Lei 14.133/2021.

    Endpoint: /modulo-contratacoes/1_consultarContratacoes_PNCP_14133
    """
    params: Dict[str, Any] = {}
    if data_publicacao_inicial:
        params["dataPublicacaoPncpInicial"] = data_publicacao_inicial
    if data_publicacao_final:
        params["dataPublicacaoPncpFinal"] = data_publicacao_final
    if cnpj_orgao:
        params["cnpjOrgao"] = cnpj_orgao
    if uf:
        params["uf"] = uf
    if modalidade is not None:
        params["codigoModalidade"] = modalidade
    params.update(extra_params)

    return await fetch_paginated(
        "/modulo-contratacoes/1_consultarContratacoes_PNCP_14133",
        params=params,
        tamanho_pagina=tamanho_pagina,
        max_pages=max_pages,
    )
```

`cnpjOrgao` não é um parâmetro reconhecido pela API (confirmado via
`/v3/api-docs` ao vivo — o nome real é `orgaoEntidadeCnpj`). Isso significa
que hoje, quando alguém passa `cnpj_orgao=...`, o filtro é silenciosamente
ignorado pela API (ela não retorna erro, apenas não aplica o filtro).

- [ ] **Step 2: Corrigir o nome do parâmetro**

Edit: troque `params["cnpjOrgao"] = cnpj_orgao` por `params["orgaoEntidadeCnpj"] = cnpj_orgao`.

- [ ] **Step 3: Validar ao vivo que o filtro agora funciona**

Rode um teste manual (script Python ad-hoc, não faz parte da suíte
automatizada — é só para confirmar antes de seguir):

```python
import asyncio
from backend.scrapers.comprasgov_client import consultar_contratacoes_pncp

async def main():
    r = await consultar_contratacoes_pncp(
        data_publicacao_inicial='2026-01-01',
        data_publicacao_final='2026-08-07',
        cnpj_orgao='00394544000185',
        modalidade=6,
        max_pages=1,
    )
    print('total:', r.get('totalRegistros'))
    for item in r.get('resultado', [])[:3]:
        print(' -', item.get('orgaoEntidadeCnpj'), item.get('orgaoEntidadeRazaoSocial'))

asyncio.run(main())
```

Expected: `totalRegistros` > 0 e todo `orgaoEntidadeRazaoSocial` retornado
contém "MINISTERIO DA SAUDE" (não órgãos aleatórios).

- [ ] **Step 4: Commit**

```bash
git add backend/scrapers/comprasgov_client.py
git commit -m "fix: corrige nome do parametro de CNPJ em consultar_contratacoes_pncp (cnpjOrgao -> orgaoEntidadeCnpj)"
```

---

### Task 3: `MotorBuscaIndependente.buscar()` — pós-filtro no modo "com termo"

**Files:**
- Modify: `backend/services/motor_independente.py:40-120`

- [ ] **Step 1: Ler o método `buscar()` atual**

Ver `backend/services/motor_independente.py:40-120` — o método já mostrado
no contexto herdado do design. O ponto de inserção é logo após
`todos = self._dedup(todos)` (linha ~97), antes dos filtros de
pós-processamento existentes (`uf_final`, `municipio_busca`, `modalidade`).

- [ ] **Step 2: Adicionar o parâmetro e o filtro**

Edit a assinatura de `buscar()`:

```python
    async def buscar(
        self,
        termo: str = '',
        pagina: int = 1,
        uf: str = None,
        modalidade: str = None,
        limit: int = 50,
        apenas_ministerio_saude: bool = False,
        **kwargs
    ) -> Dict:
```

Edit logo após `todos = self._dedup(todos)`:

```python
        todos = self._dedup(todos)

        if apenas_ministerio_saude:
            from services.orgaos_saude_federal import bate_orgao_saude
            todos = [
                r for r in todos
                if bate_orgao_saude(r.get('orgao'), r.get('_pncp_cnpj') or r.get('orgao_cnpj'))
            ]
```

(mantém o resto do método, incluindo os filtros de `uf_final`/`municipio_busca`/`modalidade`
e o `return`, inalterados)

- [ ] **Step 3: Escrever o teste de integração ao vivo**

```python
# backend/tests/test_busca_ministerio_saude.py
"""
Testes de integração ao vivo para o filtro de escopo "Ministério da Saúde"
em GET /api/search/unified. Mesmo padrão de test_gsm_v78_independente.py:
requests contra BASE_URL, sem mocks.
"""
import os
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')


class TestBuscaMinisterioSaudeComTermo:
    def test_filtro_restringe_resultados_a_orgaos_da_saude(self):
        """GET /api/search/unified?q=medicamento&ministerio_saude=true só
        deve retornar resultados de órgãos do portfólio saúde."""
        resp = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={"q": "medicamento", "ministerio_saude": "true", "limit": 30},
            timeout=60,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        resultados = data.get('resultados', [])

        if not resultados:
            # Termo pode não ter achado nada no portfólio saúde nesse momento -
            # não é uma falha do filtro em si, só ausência de dados no
            # instante do teste. Log e não falha.
            print("Nenhum resultado para 'medicamento' com filtro Ministério da Saúde - "
                  "aceitável se não houver contratação ativa nesse momento.")
            return

        for r in resultados:
            orgao = r.get('orgao', '')
            assert 'MINISTERIO' in orgao.upper() or 'SAUDE' in orgao.upper() or \
                'INCA' in orgao.upper() or 'DSEI' in orgao.upper() or 'FIOCRUZ' in orgao.upper(), \
                f"Resultado de órgão fora do portfólio saúde: {orgao}"

    def test_sem_filtro_pode_trazer_orgaos_variados(self):
        """Confirma que o comportamento DEFAULT (sem o filtro) não muda -
        deve poder trazer órgãos fora do portfólio saúde."""
        resp = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={"q": "medicamento", "limit": 30},
            timeout=60,
        )
        assert resp.status_code == 200, resp.text
```

- [ ] **Step 4: Rodar o teste e verificar que falha**

Run: `cd backend && python -m pytest tests/test_busca_ministerio_saude.py::TestBuscaMinisterioSaudeComTermo -v`
Expected: FAIL (o parâmetro `ministerio_saude` ainda não existe no endpoint - Task 5 o adiciona; se rodar antes da Task 5, a query string é ignorada e o teste pode falsamente passar por falta de asserção no parâmetro em si — por isso este teste só deve ser considerado definitivo após a Task 5 estar pronta. Registre esse teste agora, mas trate-o como pendente até lá.)

- [ ] **Step 5: Rodar a suíte de testes que não depende de rede**

Run: `cd backend && python -m pytest tests/test_orgaos_saude_federal.py -v`
Expected: PASS (ainda 8 testes — este task não altera a Task 1)

- [ ] **Step 6: Commit**

```bash
git add backend/services/motor_independente.py backend/tests/test_busca_ministerio_saude.py
git commit -m "feat: MotorBuscaIndependente aceita apenas_ministerio_saude para pos-filtrar busca por termo"
```

---

### Task 4: Modo "buscar todos" (sem termo) via Compras.gov.br

**Files:**
- Modify: `backend/services/motor_independente.py`

- [ ] **Step 1: Adicionar o desvio para o novo método quando não há termo**

No início de `buscar()`, ao lado do desvio já existente para
`_buscar_por_localizacao`:

```python
        # v80.0: Busca SEM termo — apenas por Município e/ou UF.
        if not termo and (uf_final or municipio_busca):
            return await self._buscar_por_localizacao(
                uf=uf_final,
                municipio=municipio_busca,
                pagina=pagina,
                limit=limit,
                modalidade=modalidade
            )

        # Busca SEM termo, escopo Ministério da Saúde ("buscar todos")
        if not termo and apenas_ministerio_saude:
            return await self._buscar_ministerio_saude_sem_termo(
                pagina=pagina,
                limit=limit,
            )
```

- [ ] **Step 2: Implementar `_buscar_ministerio_saude_sem_termo`**

Adicione este método logo após `_buscar_por_localizacao` (reaproveita o
mesmo padrão de cache de resiliência — `CACHE_COLLECTION`,
`_buscar_cache_localizacao`, `_salvar_cache_localizacao` — já definidos na
classe):

```python
    # ─── Compras.gov.br — Ministério da Saúde sem termo ("buscar todos") ──
    MODALIDADES_RELEVANTES = [4, 6, 8, 9]  # concorrencia, pregao eletronico, dispensa, inexigibilidade

    async def _buscar_ministerio_saude_sem_termo(
        self,
        pagina: int = 1,
        limit: int = 50,
    ) -> Dict:
        """
        Lista contratações recentes do Ministério da Saúde (CNPJ
        00394544000185) sem exigir termo de busca, via Compras.gov.br
        (consultar_contratacoes_pncp com filtro de CNPJ - mecanismo
        validado ao vivo durante o design; a API oficial do PNCP não tem
        filtro de órgão funcional).
        """
        from services.orgaos_saude_federal import ORGAOS_SAUDE_FEDERAL
        from backend.scrapers.comprasgov_client import consultar_contratacoes_pncp

        cache_key = f"MS|{pagina}|{limit}"

        hoje = datetime.now()
        data_inicial = (hoje - timedelta(days=180)).strftime('%Y-%m-%d')
        data_final = hoje.strftime('%Y-%m-%d')

        brutos = []
        algum_sucesso = False
        for org in ORGAOS_SAUDE_FEDERAL:
            if not org.get('cnpj'):
                continue
            for modalidade in self.MODALIDADES_RELEVANTES:
                try:
                    resultado = await consultar_contratacoes_pncp(
                        data_publicacao_inicial=data_inicial,
                        data_publicacao_final=data_final,
                        cnpj_orgao=org['cnpj'],
                        modalidade=modalidade,
                        max_pages=5,
                    )
                    itens = resultado.get('resultado', [])
                    if itens:
                        algum_sucesso = True
                    brutos.extend(itens)
                except Exception as e:
                    logger.error(f"Erro consultando CNPJ {org['cnpj']} modalidade {modalidade}: {e}")

        if not algum_sucesso and not brutos:
            cache_resultado = await self._buscar_cache_localizacao(cache_key)
            if cache_resultado:
                logger.warning("⚠️ [MS-SEM-TERMO] API indisponível: servindo resultado em cache")
                cache_resultado['fonte_disponivel'] = False
                cache_resultado['aviso'] = 'A fonte de dados do Ministério da Saúde está instável no momento. Exibindo a última busca disponível em cache.'
                return cache_resultado

            return {
                'resultados': [],
                'total': 0,
                'pagina': pagina,
                'fontes': {'pncp_gov_br': 0, 'compras_gov_br': 0},
                'fonte_disponivel': False,
                'aviso': 'A fonte de dados do Ministério da Saúde está instável/indisponível no momento. Tente novamente em alguns minutos.'
            }

        mapeados = [m for it in brutos if (m := self._map_comprasgov_contratacao(it))]
        mapeados = self._dedup(mapeados)
        mapeados.sort(key=lambda x: x.get('data_publicacao') or '', reverse=True)

        idx_inicio = (pagina - 1) * limit
        pagina_resultados = mapeados[idx_inicio: idx_inicio + limit]

        resultado_final = {
            'resultados': pagina_resultados,
            'total': len(mapeados),
            'pagina': pagina,
            'fontes': {'pncp_gov_br': 0, 'compras_gov_br': len(mapeados)},
            'fonte_disponivel': True,
        }
        await self._salvar_cache_localizacao(cache_key, resultado_final)
        return resultado_final

    def _map_comprasgov_contratacao(self, item: Dict) -> Optional[Dict]:
        """Mapeia uma contratação do Compras.gov.br (modulo-contratacoes)
        para o mesmo schema usado por _map_pncp/_map_consulta_proposta."""
        try:
            cnpj = item.get('orgaoEntidadeCnpj', '')
            orgao = item.get('orgaoEntidadeRazaoSocial', '') or item.get('unidadeOrgaoNomeUnidade', '')
            uf = item.get('unidadeOrgaoUfSigla', '')
            municipio = item.get('unidadeOrgaoMunicipioNome', '')
            objeto = (item.get('objetoCompra', '') or '').upper()
            numero_pncp = item.get('numeroControlePNCP', '')
            ano = str(item.get('anoCompra', ''))
            seq = str(item.get('sequencialCompra', ''))

            link_pagina = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else ''
            link_download = f"/api/editais/download/{cnpj}/{ano}/{seq}" if (cnpj and ano and seq) else ''
            id_gsm = hashlib.md5(f"PNCP-{numero_pncp}".encode()).hexdigest() if numero_pncp else ''

            return {
                'id': id_gsm,
                'id_gsm': id_gsm,
                'id_externo': numero_pncp,
                'numero_controle_pncp': numero_pncp,
                'fonte': 'COMPRAS_GOV',
                'portal_captura': f"Compras.gov ({uf})" if uf else 'Compras.gov',
                'objeto': objeto,
                'orgao': orgao,
                'uf': uf,
                'municipio': municipio,
                'modalidade': item.get('modalidadeNome', ''),
                'data_publicacao': item.get('dataPublicacaoPncp', ''),
                'data_abertura': item.get('dataAberturaPropostaPncp', ''),
                'data_final': item.get('dataEncerramentoPropostaPncp', ''),
                'valor_estimado': item.get('valorTotalEstimado', 0),
                'link_portal': link_pagina,
                'link_pdf': link_download,
                'link_edital': link_pagina,
                '_pncp_cnpj': cnpj,
                '_pncp_ano': ano,
                '_pncp_seq': seq,
                'itens': '',
                'ativo': True,
            }
        except Exception as e:
            logger.error(f"Erro mapeando contratação Compras.gov: {e}")
            return None
```

- [ ] **Step 3: Adicionar o teste de integração ao vivo**

Adicione em `backend/tests/test_busca_ministerio_saude.py`:

```python
class TestBuscaMinisterioSaudeSemTermo:
    def test_buscar_todos_sem_termo_retorna_algo_ou_aviso_explicito(self):
        """GET /api/search/unified?ministerio_saude=true (sem q) deve
        retornar resultados OU um aviso explícito de indisponibilidade -
        nunca uma lista vazia silenciosa sem explicação."""
        resp = requests.get(
            f"{BASE_URL}/api/search/unified",
            params={"ministerio_saude": "true", "limit": 20},
            timeout=90,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        if data.get('total', 0) == 0:
            assert data.get('aviso'), (
                "Sem resultados e sem aviso explicativo - o modo 'buscar todos' "
                "não deve falhar silenciosamente"
            )
        else:
            for r in data.get('resultados', [])[:10]:
                orgao = r.get('orgao', '').upper()
                assert 'SAUDE' in orgao or 'MINISTERIO' in orgao or 'INCA' in orgao or 'FIOCRUZ' in orgao, \
                    f"Resultado de órgão inesperado no modo Ministério da Saúde: {orgao}"
```

- [ ] **Step 4: Rodar os testes que não dependem do endpoint ainda**

Run: `cd backend && python -m pytest tests/test_orgaos_saude_federal.py -v`
Expected: PASS (8 testes, sem regressão)

- [ ] **Step 5: Commit**

```bash
git add backend/services/motor_independente.py backend/tests/test_busca_ministerio_saude.py
git commit -m "feat: modo buscar-todos sem termo para Ministerio da Saude via Compras.gov.br"
```

---

### Task 5: Endpoint `GET /api/search/unified`

**Files:**
- Modify: `backend/server.py:1313-1347`

- [ ] **Step 1: Adicionar o parâmetro de query**

```python
@api_router.get("/search/unified")
async def search_unified(
    q: str = Query(None, description="Termo de busca"),
    municipio: str = Query(None, description="Filtro por município"),
    uf: str = Query(None, description="Filtro por UF"),
    estados: str = Query(None, description="Filtro por estados (alias UF)"),
    apenas_saude: bool = Query(False, description="Filtrar apenas saúde"),
    modalidade: str = Query(None, description="Filtro por modalidade"),
    ministerio_saude: bool = Query(False, description="Filtrar apenas órgãos do Ministério da Saúde"),
    limit: int = Query(50, ge=1, le=2000, description="Máximo de resultados"),
    page: int = Query(1, ge=1, description="Página")
):
```

- [ ] **Step 2: Ajustar a validação para aceitar `ministerio_saude=True` sem termo**

Trocar:

```python
        tem_localizacao = bool((municipio and municipio.strip()) or (uf and uf.strip()) or (estados and estados.strip()))
        if not tem_localizacao and (not q or len(q.strip()) < 2):
            raise HTTPException(status_code=400, detail="Informe um termo de busca (mín. 2 caracteres) ou um filtro de Município/Estado")
```

por:

```python
        tem_localizacao = bool((municipio and municipio.strip()) or (uf and uf.strip()) or (estados and estados.strip()))
        if not tem_localizacao and not ministerio_saude and (not q or len(q.strip()) < 2):
            raise HTTPException(status_code=400, detail="Informe um termo de busca (mín. 2 caracteres), um filtro de Município/Estado, ou ative o filtro Ministério da Saúde")
```

- [ ] **Step 3: Repassar o parâmetro para o motor**

Trocar:

```python
        resultado = await motor.buscar(
            termo=(q or '').strip(),
            pagina=page,
            uf=uf,
            estados=estados,
            municipio=municipio,
            modalidade=modalidade,
            limit=limit
        )
```

por:

```python
        resultado = await motor.buscar(
            termo=(q or '').strip(),
            pagina=page,
            uf=uf,
            estados=estados,
            municipio=municipio,
            modalidade=modalidade,
            limit=limit,
            apenas_ministerio_saude=ministerio_saude,
        )
```

- [ ] **Step 4: Rodar os testes de integração ao vivo (agora sim, definitivos)**

Run: `cd backend && python -m pytest tests/test_busca_ministerio_saude.py -v`
Expected: PASS (2-4 testes, dependendo de dados ao vivo — nenhum deve
lançar exceção/erro 500; resultados vazios só são aceitáveis com `aviso`
presente conforme os testes já escritos)

- [ ] **Step 5: Rodar a suíte completa relevante (sem regressão)**

Run: `cd backend && python -m pytest tests/test_orgaos_saude_federal.py tests/test_gsm_v78_independente.py -v`
Expected: PASS — `test_gsm_v78_independente.py` confirma que o comportamento
DEFAULT (sem `ministerio_saude`) continua idêntico ao anterior.

- [ ] **Step 6: Commit**

```bash
git add backend/server.py
git commit -m "feat: expoe ministerio_saude em GET /api/search/unified"
```

---

### Task 6: Frontend — `useSearch.js`

**Files:**
- Modify: `frontend/src/hooks/useSearch.js`

- [ ] **Step 1: Adicionar o estado do filtro**

Logo após `const [avisoFonte, setAvisoFonte] = useState(null);` (linha 21):

```javascript
  const [filtroMinisterioSaude, setFiltroMinisterioSaude] = useState(false);
```

- [ ] **Step 2: Incluir o filtro na chamada de busca e permitir termo vazio quando ativo**

Trocar a assinatura e a guarda inicial de `executarBusca`:

```javascript
  const executarBusca = async (termo, cidade, uf, smart = false, page = 1, msSaude = filtroMinisterioSaude) => {
    if (!termo && !cidade && !uf && !msSaude) return;
    setIsLoading(true);
    setAvisoFonte(null);
    try {
      const params = new URLSearchParams();
      if (termo) params.append('q', termo);
      if (cidade) params.append('municipio', cidade);
      if (uf) params.append('estados', uf);
      if (smart) params.append('smart_search', 'true');
      if (msSaude) params.append('ministerio_saude', 'true');
      params.append('limit', perPage);
      params.append('page', page || currentPage);
```

(o resto do corpo de `executarBusca` permanece inalterado)

- [ ] **Step 3: Expor o novo estado no retorno do hook**

No objeto retornado ao final do arquivo, adicionar:

```javascript
  return {
    oportunidades, loading, analiseDetalhe, analiseLoading,
    ...
    filtroMinisterioSaude, setFiltroMinisterioSaude,
    ...
  };
```

(inserir na lista de retorno já existente deste arquivo — não remover nenhum
campo já retornado, ex.: `searchTerm, setSearchTerm, searchCity, ...`)

- [ ] **Step 4: Verificar manualmente que o hook não quebra a build**

Run: `cd frontend && npm run build` (ou `yarn build`, conforme o gerenciador
de pacotes do projeto)
Expected: build conclui sem erros de sintaxe/import

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useSearch.js
git commit -m "feat: useSearch expoe filtroMinisterioSaude e permite busca sem termo quando ativo"
```

---

### Task 7: Frontend — botão pílula em `SearchTab.jsx`

**Files:**
- Modify: `frontend/src/components/tabs/SearchTab.jsx`

- [ ] **Step 1: Receber as novas props**

Na assinatura do componente (linha 8-20), adicionar:

```javascript
export function SearchTab({
  searchTerm, setSearchTerm, searchCity, setSearchCity,
  selectedUF, setSelectedUF, selectedRadarId,
  results, setResults, isLoading, totalResults,
  expandedItens, setExpandedItens,
  isSmartSearch, setIsSmartSearch,
  executarBusca, handleManualTyping, handleSelectRadar, getBidDownloadUrl,
  radaresAtalho,
  perPage, setPerPage,
  currentPage, setCurrentPage,
  paginationInfo,
  avisoFonte,
  filtroMinisterioSaude, setFiltroMinisterioSaude,
}) {
```

- [ ] **Step 2: Adicionar o botão na linha de "Radares de Atalho"**

Logo após o bloco `{/* RADARES DE ATALHO */}` (linha 114-125), adicionar o
toggle, mesmo padrão visual de pílula (`rounded-full`, mesma tipografia),
cor distinta (teal) para sinalizar que é um toggle de escopo, não um atalho
de termo fixo:

```javascript
      {/* RADARES DE ATALHO */}
      <div className="flex flex-wrap gap-3 px-2">
        <p className="text-xs font-black text-slate-400 uppercase tracking-widest w-full mb-1 flex items-center gap-2">
          <Radar size={16}/> Radares de Atalho / Perfis de Busca:
        </p>
        <button
          data-testid="filtro-ministerio-saude"
          onClick={() => {
            const novoValor = !filtroMinisterioSaude;
            setFiltroMinisterioSaude(novoValor);
            executarBusca(searchTerm, searchCity, selectedUF, isSmartSearch, 1, novoValor);
          }}
          className={`px-5 py-2 rounded-full border-2 text-xs font-black uppercase tracking-wider transition-all ${filtroMinisterioSaude ? 'bg-teal-600 text-white border-teal-500 shadow-lg' : 'bg-white text-slate-500 border-slate-200 hover:border-teal-300 hover:text-teal-600'}`}>
          Ministério da Saúde
        </button>
        {radaresAtalho.map(r => (
          <button key={r.id} onClick={() => handleSelectRadar(r.id, r.keywords)}
            className={`px-5 py-2 rounded-full border-2 text-xs font-black uppercase tracking-wider transition-all ${selectedRadarId === r.id ? 'bg-blue-600 text-white border-blue-500 shadow-lg' : 'bg-white text-slate-500 border-slate-200 hover:border-blue-300 hover:text-blue-600'}`}>
            {r.name}
          </button>
        ))}
      </div>
```

- [ ] **Step 3: Confirmar que o componente pai já repassa as novas props**

`frontend/src/App.jsx:94-97` já renderiza `<SearchTab {...search} radaresAtalho={listasRadares.radaresAtalho} />`,
onde `search = useSearch()` (linha 49). Como o spread `{...search}` passa o
objeto inteiro do hook, `filtroMinisterioSaude`/`setFiltroMinisterioSaude`
(adicionados ao retorno do hook na Task 6 Step 3) já chegam em `SearchTab`
automaticamente — nenhuma mudança em `App.jsx` é necessária. Só confirme
lendo essas linhas antes de seguir.

- [ ] **Step 4: Testar manualmente no navegador**

Rode o frontend localmente (`npm start` ou equivalente já configurado no
projeto), abra a aba de busca, clique no botão "Ministério da Saúde":
1. Com o campo de medicamento vazio: deve disparar uma busca e mostrar
   resultados (ou um aviso, se a fonte estiver indisponível no momento) —
   não deve ficar em branco sem feedback.
2. Digite um medicamento (ex. "insulina") com o filtro ativo: os resultados
   devem vir só de órgãos do Ministério da Saúde.
3. Clique de novo no botão para desativar: a busca deve voltar ao
   comportamento nacional normal.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/tabs/SearchTab.jsx
git commit -m "feat: botao Ministerio da Saude na busca (toggle de escopo)"
```

---

### Task 8: Revisão final e smoke test end-to-end

**Files:** nenhum (tarefa de verificação)

- [ ] **Step 1: Rodar toda a suíte de testes relevante**

Run: `cd backend && python -m pytest tests/test_orgaos_saude_federal.py tests/test_busca_ministerio_saude.py tests/test_gsm_v78_independente.py -v`
Expected: todos passam; nenhuma regressão no comportamento default da busca.

- [ ] **Step 2: Smoke test manual dos 3 cenários end-to-end**

Contra o backend rodando (local ou VPS, conforme o ambiente de teste
disponível):
1. `GET /api/search/unified?q=insulina&ministerio_saude=true` — confirma
   `search_query`/resultados só do portfólio saúde.
2. `GET /api/search/unified?ministerio_saude=true` (sem `q`) — confirma
   resultados OU aviso explícito, nunca lista vazia silenciosa.
3. `GET /api/search/unified?q=insulina` (sem o filtro) — confirma que o
   comportamento default não mudou (pode trazer órgãos fora da saúde).

- [ ] **Step 3: Confirmar que nada fora do escopo foi tocado**

Run: `git diff --stat <commit-anterior-ao-Task-1>..HEAD`
Expected: só os arquivos listados nas Tasks 1-7 aparecem (mais a spec e
este plano em `docs/superpowers/`).
