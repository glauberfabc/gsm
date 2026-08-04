# Radar LMR — Rótulo, Card RDC 81 e Correção Tributária — Design

## Contexto

Ajuste cirúrgico em três pontos da aba Radar LMR (`frontend/src/components/tabs/RadarLmrTab.jsx`
+ `backend/services/lmr_service.py`), sem tocar em nenhuma outra aba/módulo da
plataforma:

1. Rótulo da busca individual.
2. Novo card de resumo regulatório (registro ANVISA + desabastecimento +
   viabilidade RDC 81/2008), exibido ao clicar em "Analisar".
3. Correção do motor de cálculo de impostos de importação, que hoje soma
   alíquotas de forma simples (`ii + icms + pis + cofins`) em vez de calcular
   em cascata (cada imposto incidindo sobre a base correta, com ICMS "por
   dentro").

Nenhum anexo com a tabela oficial de alíquotas de SP chegou nesta conversa.
Ficou definido com o usuário: implementar a estrutura de cálculo em cascata
com o modelo fiscal brasileiro padrão de importação (o que está descrito
abaixo), mantendo as alíquotas nominais já usadas hoje pelo sistema, para
validação posterior contra a tabela real.

## 1. Rótulo

`frontend/src/components/tabs/RadarLmrTab.jsx:115`, trocar o texto:

```jsx
<span className="text-sm font-black text-slate-700 uppercase tracking-wide">Analise Individual LMR</span>
```

por:

```jsx
<span className="text-sm font-black text-slate-700 uppercase tracking-wide">Analise Individual do Medicamento e LMR</span>
```

## 2. Card de Resumo Regulatório e RDC 81/2008

### 2.1 Problema de dados a resolver primeiro

`backend/services/anvisa_registro_service.py` sincroniza o CSV de dados
abertos da ANVISA, mas **descarta linhas com `SITUACAO_REGISTRO == 'Ativo'`**
(comentário no código: "um registro ativo não é evidência de
desabastecimento"). A coleção `anvisa_registro_medicamentos` só contém
registros cancelados/vencidos/inativos — usada hoje como fonte "Registro
ANVISA (Cancelados/Inativos)" da Janela ANVISA
(`medicamento_search_service.py`, método `_buscar_registro_cancelado`, ver
também o plano pausado
`docs/superpowers/plans/2026-08-04-busca-medicamento-strict-match.md`, cuja
Task 8 reescreve esse método assumindo esse mesmo desenho de dados).

Para responder "Registro na ANVISA: SIM/NÃO + Laboratório" com confiança,
sem alterar o comportamento/nome/conteúdo da coleção existente (risco zero
para a Janela ANVISA e para o plano pausado), `sincronizar_registro_medicamentos`
passa a gravar os registros **ativos** numa coleção nova e separada,
**no mesmo download/processamento do CSV** (sem baixar o arquivo duas
vezes):

```python
async def sincronizar_registro_medicamentos(db) -> int:
    """Baixa o CSV aberto da ANVISA uma vez e atualiza DUAS coleções:
    - anvisa_registro_medicamentos: só não-ativos (cancelados/vencidos/
      inativos) - inalterado, usado pela Janela ANVISA como indicador de
      mercado.
    - anvisa_registro_medicamentos_ativos: só ativos - usado pelo Radar
      LMR para responder se há similar registrado no Brasil (RDC 81/2008).
    """
    ... (download do CSV inalterado) ...

    docs_inativos = []
    docs_ativos = []
    for row in reader:
        situacao = (row.get('SITUACAO_REGISTRO') or '').strip()
        nome = (row.get('NOME_PRODUTO') or '').strip()
        principio = (row.get('PRINCIPIO_ATIVO') or '').strip()
        if not situacao or (not nome and not principio):
            continue

        doc = {
            'nome_produto': nome,
            'principio_ativo': principio,
            'situacao_registro': situacao,
            'data_finalizacao_processo': (row.get('DATA_FINALIZACAO_PROCESSO') or '').strip(),
            'data_vencimento_registro': (row.get('DATA_VENCIMENTO_REGISTRO') or '').strip(),
            'categoria_regulatoria': (row.get('CATEGORIA_REGULATORIA') or '').strip(),
            'classe_terapeutica': (row.get('CLASSE_TERAPEUTICA') or '').strip(),
            'empresa_detentora_registro': (row.get('EMPRESA_DETENTORA_REGISTRO') or '').strip(),
            'numero_registro_produto': (row.get('NUMERO_REGISTRO_PRODUTO') or '').strip(),
            'atualizado_em': agora,
        }

        if situacao.lower() == 'ativo':
            docs_ativos.append(doc)
        else:
            docs_inativos.append(doc)

    if docs_inativos:
        await db.anvisa_registro_medicamentos.delete_many({})
        await db.anvisa_registro_medicamentos.insert_many(docs_inativos)
    if docs_ativos:
        await db.anvisa_registro_medicamentos_ativos.delete_many({})
        await db.anvisa_registro_medicamentos_ativos.insert_many(docs_ativos)

    return len(docs_inativos) + len(docs_ativos)
```

O chamador (`scheduler.py:895-896`) não muda — é a mesma função, mesma
assinatura, mesmo job agendado.

### 2.2 `LmrService` — nova consulta e novo bloco no resultado

Em `backend/services/lmr_service.py`, novo método:

```python
async def _verificar_registro_ativo(self, medicamento: str) -> List[Dict]:
    """Retorna os registros ATIVOS da ANVISA que casam com o medicamento
    buscado (usado para responder se há similar registrado no Brasil,
    conforme RDC 81/2008)."""
    try:
        docs = await self.db.anvisa_registro_medicamentos_ativos.find(
            {'$or': [
                {'nome_produto': {'$regex': medicamento, '$options': 'i'}},
                {'principio_ativo': {'$regex': medicamento, '$options': 'i'}},
            ]},
            {'_id': 0},
        ).to_list(length=20)
    except Exception:
        docs = []
    return docs
```

E o novo bloco de montagem do resumo:

```python
def _montar_resumo_regulatorio(self, classificacao: Dict, registros_ativos: List[Dict]) -> Dict:
    """Monta o card 'Resumo Regulatório e Viabilidade RDC 81/2008'."""
    registrado = len(registros_ativos) > 0
    laboratorios = sorted({
        r['empresa_detentora_registro'] for r in registros_ativos
        if r.get('empresa_detentora_registro')
    })

    desab_info = classificacao.get('desabastecimento_info')
    if desab_info and desab_info.get('status'):
        situacao_desabastecimento = desab_info['status']
    elif classificacao.get('janela_aberta'):
        situacao_desabastecimento = 'Indício de desabastecimento identificado (janela aberta)'
    else:
        situacao_desabastecimento = 'Sem indício de desabastecimento identificado'

    if classificacao.get('via_judicial'):
        viabilidade = 'VIÁVEL — importação amparada por ordem/decisão judicial'
    elif classificacao.get('desabastecimento_detectado') or classificacao.get('janela_aberta'):
        viabilidade = (
            'VIÁVEL — desabastecimento oficial reconhecido autoriza '
            'importação excepcional (RDC 81/2008)'
        )
    elif registrado:
        viabilidade = (
            'NÃO RECOMENDADA / INVIÁVEL por via administrativa ordinária — '
            'há similar registrado e ativo no Brasil (RDC 81/2008), salvo '
            'desabastecimento oficial ou ordem judicial'
        )
    else:
        viabilidade = (
            'SEM SIMILAR ATIVO IDENTIFICADO NA BASE ANVISA — avaliar '
            'viabilidade caso a caso'
        )

    return {
        'registrado_anvisa': registrado,
        'laboratorios_referencia': laboratorios,
        'situacao_desabastecimento': situacao_desabastecimento,
        'viabilidade_importacao_rdc81': viabilidade,
        'norma_referencia_viabilidade': (
            'RDC 81/2008 (ANVISA) — Regulamento Técnico de Importação de '
            'Produtos Sujeitos à Vigilância Sanitária'
        ),
    }
```

Em `analisar_medicamento`, logo após calcular `classificacao` (linha 89 do
arquivo original):

```python
        # 1. Verificar classificacao LMR
        classificacao = await self._classificar_lmr(medicamento)
        resultado['classificacao_lmr'] = classificacao

        # 1b. Resumo regulatório e viabilidade RDC 81/2008
        registros_ativos = await self._verificar_registro_ativo(medicamento)
        resultado['resumo_regulatorio_rdc81'] = self._montar_resumo_regulatorio(
            classificacao, registros_ativos
        )
```

`POST /api/dama/lmr-analise-medicamento` (`server.py:5906-5932`) não muda —
já retorna o dict inteiro de `analisar_medicamento`, então o campo novo
chega ao frontend automaticamente.

### 2.3 Frontend — novo card

Em `RadarLmrTab.jsx`, dentro de `AnaliseDetalheCard` (que já recebe `data`
= a resposta completa), adicionar um bloco entre "Classificação LMR" e
"Estratégia Tributária" (após a linha 346, `</div>` que fecha o bloco de
Classificação):

```jsx
        {/* Resumo Regulatorio e RDC 81 */}
        {data.resumo_regulatorio_rdc81 && (
          <ResumoRegulatorioCard resumo={data.resumo_regulatorio_rdc81} />
        )}
```

Novo componente (mesmo arquivo, junto aos demais componentes auxiliares
como `MiniStat`/`TributoBadge`):

```jsx
function ResumoRegulatorioCard({ resumo }) {
  const viavel = resumo.viabilidade_importacao_rdc81?.startsWith('VIÁVEL');
  return (
    <div className="bg-slate-50 border-2 border-slate-200 rounded-xl overflow-hidden" data-testid="resumo-regulatorio-rdc81">
      <div className="bg-slate-700 px-4 py-2">
        <p className="text-xs font-black text-white uppercase tracking-wide">
          📋 Análise Regulatória e Viabilidade RDC 81/2008
        </p>
      </div>
      <div className="p-4 space-y-3">
        <div>
          <p className="text-[10px] font-bold text-slate-400 uppercase">1. Registro na ANVISA</p>
          <p className="text-sm font-bold text-slate-700">
            {resumo.registrado_anvisa ? 'SIM' : 'NÃO'}
            {resumo.laboratorios_referencia?.length > 0 && (
              <span className="font-normal text-slate-500"> — {resumo.laboratorios_referencia.join(', ')}</span>
            )}
          </p>
        </div>
        <div>
          <p className="text-[10px] font-bold text-slate-400 uppercase">2. Situação de Falta / Desabastecimento</p>
          <p className="text-sm font-semibold text-slate-700">{resumo.situacao_desabastecimento}</p>
        </div>
        <div>
          <p className="text-[10px] font-bold text-slate-400 uppercase">3. Viabilidade de Importação (RDC 81/2008)</p>
          <p className={`text-sm font-bold ${viavel ? 'text-emerald-700' : 'text-red-700'}`}>
            {resumo.viabilidade_importacao_rdc81}
          </p>
        </div>
      </div>
    </div>
  );
}
```

## 3. Motor de cálculo tributário em cascata

`backend/services/lmr_service.py`, método `_calcular_tributacao`
(linhas 178-213 do arquivo original). Hoje soma alíquotas nominais
diretamente (`carga_total = ii + icms + pis + cofins`) e aplica sobre o
preço de referência sem considerar que cada imposto incide sobre uma base
diferente — é a distorção citada na instrução.

Novo cálculo (modelo padrão de importação brasileira, ICMS "por dentro"):

```python
    def _calcular_tributacao(self, categoria: str, faixa: Dict, preco_ref: float) -> Dict:
        """
        Calcula a carga tributaria em cascata (modelo padrao de importacao
        brasileira):
          - II incide sobre o valor aduaneiro (CIF = preco de referencia).
          - PIS/COFINS-Importacao incidem sobre CIF + despesas aduaneiras.
          - ICMS incide "por dentro" (embutido na propria base: Lei
            Kandir, art. 13 §1 I), sobre CIF + II + PIS + COFINS +
            despesas aduaneiras e nao-aduaneiras, com a aliquota de
            destino (18% padrao SP, ou reduzida conforme categoria).
        Despesas aduaneiras/nao-aduaneiras (capatazia, armazenagem,
        SISCOMEX, despachante etc.) ainda nao tem valor de referencia
        confirmado - ficam em 0 ate validacao contra a tabela oficial;
        a formula ja esta pronta para recebe-las.
        """
        if categoria == 'excepcional':
            aliquota_ii = 0.0
            aliquota_icms = ALIQUOTAS_TRIBUTARIAS['icms_reduzido']
            beneficio_extra = 'Isencao II + ICMS reduzido (Art. 12, IN 428/2026)'
        elif categoria == 'judicial':
            aliquota_ii = 0.0
            aliquota_icms = 0.0
            beneficio_extra = 'Isencao total conforme liminar judicial'
        elif categoria == 'lista_positiva':
            aliquota_ii = ALIQUOTAS_TRIBUTARIAS['ii_medicamento'] * 0.5
            aliquota_icms = ALIQUOTAS_TRIBUTARIAS['icms_reduzido']
            beneficio_extra = 'Reducao II 50% + ICMS reduzido (LMR positiva)'
        else:
            aliquota_ii = ALIQUOTAS_TRIBUTARIAS['ii_medicamento']
            aliquota_icms = ALIQUOTAS_TRIBUTARIAS['icms_padrao']
            beneficio_extra = 'Sem beneficio tributario especial'

        aliquota_pis = ALIQUOTAS_TRIBUTARIAS['pis']
        aliquota_cofins = ALIQUOTAS_TRIBUTARIAS['cofins']
        despesas_aduaneiras = 0.0
        despesas_nao_aduaneiras = 0.0

        if preco_ref > 0:
            cif = preco_ref
            valor_ii = cif * aliquota_ii
            base_pis_cofins = cif + despesas_aduaneiras
            valor_pis = base_pis_cofins * aliquota_pis
            valor_cofins = base_pis_cofins * aliquota_cofins

            base_icms_sem_icms = (
                cif + valor_ii + valor_pis + valor_cofins
                + despesas_aduaneiras + despesas_nao_aduaneiras
            )
            if aliquota_icms > 0:
                base_icms = base_icms_sem_icms / (1 - aliquota_icms)
                valor_icms = base_icms * aliquota_icms
            else:
                valor_icms = 0.0

            custo_importacao_estimado = base_icms_sem_icms + valor_icms
            carga_tributaria_total = (
                (valor_ii + valor_pis + valor_cofins + valor_icms) / cif * 100
            )
        else:
            custo_importacao_estimado = 0
            carga_tributaria_total = (
                (aliquota_ii + aliquota_icms + aliquota_pis + aliquota_cofins) * 100
            )

        return {
            'imposto_importacao': round(aliquota_ii * 100, 2),
            'icms': round(aliquota_icms * 100, 2),
            'pis': round(aliquota_pis * 100, 2),
            'cofins': round(aliquota_cofins * 100, 2),
            'carga_tributaria_total': round(carga_tributaria_total, 2),
            'beneficio': beneficio_extra,
            'custo_importacao_estimado': round(custo_importacao_estimado, 2) if custo_importacao_estimado > 0 else None,
            'margem_distribuidora': round(faixa['margem_distribuidora'] * 100, 2),
            'margem_farmacia': round(faixa['margem_farmacia'] * 100, 2),
        }
```

Mudanças de comportamento:
- `imposto_importacao`, `icms`, `pis`, `cofins` continuam sendo as
  alíquotas **nominais** em %, exatamente como hoje (nenhum teste ou tela
  quebra).
- `carga_tributaria_total` deixa de ser a soma simples das alíquotas e
  passa a refletir o custo tributário **efetivo** sobre o CIF — sempre
  maior que a soma nominal, por causa do ICMS "por dentro" (correção
  central pedida na instrução).
- `custo_importacao_estimado` passa a ser CIF + todos os tributos
  calculados em cascata (antes era `preco_ref * (1 + soma_simples)`).
- `margem_distribuidora`/`margem_farmacia` **não mudam** (vêm de
  `FAIXAS_MARGEM_IN428`, testados em `test_lmr_category_margins.py` com
  valores exatos — 21.0% biológico, 20.5% sintético — este código não é
  tocado).

Nenhum teste existente do repositório verifica valor exato de
`imposto_importacao`, `icms`, `pis`, `cofins`, `carga_tributaria_total` ou
`custo_importacao_estimado` (confirmado por busca em `backend/tests/`) —
só a presença das chaves. A mudança de fórmula não quebra nenhum teste
atual.

## Fora de escopo

- Valores reais de despesas aduaneiras/não-aduaneiras (ficam em 0,
  parametrizados, até o usuário confirmar contra a tabela oficial).
- Qualquer alíquota diferente das já usadas hoje pelo sistema (não foram
  fornecidas alíquotas novas).
- Qualquer outra aba/módulo da plataforma.
- Endpoint manual para forçar a sincronização de registros ativos (roda
  apenas pelo job agendado existente, como já acontece hoje).

## Testes

Estender:
- `backend/tests/test_lmr_category_margins.py` — já cobre margem por
  categoria; adicionar verificação de que `resumo_regulatorio_rdc81` está
  presente na resposta.
- `backend/tests/test_lmr_revogacao.py` — já cobre estrutura de
  `estrategia_tributaria`.

Novos casos (unitários, sem rede — testando `LmrService` diretamente com
um fake de `db`, no mesmo estilo do plano de busca estrita):
1. `_calcular_tributacao`: para `categoria='lista_negativa'`,
   `preco_ref=1000`, `carga_tributaria_total` calculado é maior que a soma
   simples das 4 alíquotas nominais (prova de que a cascata está ativa).
2. `_calcular_tributacao`: para `categoria='judicial'` (`aliquota_ii=0`,
   `aliquota_icms=0`, mas PIS/COFINS continuam sendo cobrados — isso já é
   o comportamento atual, não alterado por esta mudança), com
   `preco_ref=1000`, `custo_importacao_estimado` deve ser
   `1000 + 1000*0.0165 + 1000*0.076 = 1092.5` (CIF + PIS + COFINS, sem II
   nem ICMS).
3. `_montar_resumo_regulatorio`: via judicial → viabilidade começa com
   "VIÁVEL"; desabastecimento sem judicial → "VIÁVEL"; registrado ativo
   sem desabastecimento/judicial → "NÃO RECOMENDADA"; nada encontrado →
   "SEM SIMILAR ATIVO".
4. `sincronizar_registro_medicamentos` (com CSV fake em memória): linha
   com `SITUACAO_REGISTRO=Ativo` vai para `anvisa_registro_medicamentos_ativos`;
   linha com `SITUACAO_REGISTRO=Cancelado` vai para
   `anvisa_registro_medicamentos`; nenhuma linha ativa "vaza" para a
   coleção de inativos e vice-versa.
