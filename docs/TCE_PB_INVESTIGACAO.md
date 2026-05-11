# TCE-PB (Paraíba) - Investigação de Dados Abertos

## Resumo Executivo

**Resultado:** ⚠️ **PARCIALMENTE ÚTIL** - Dados históricos disponíveis, mas não adequados para prospecção futura.

---

## Portal de Dados Abertos

**URL:** https://dados.tce.pb.gov.br

### Dataset de Licitações Disponível

| Campo | Valor |
|-------|-------|
| **Arquivo** | `TCE-PB-Portal-Gestor-Licitacoes_Propostas.txt.gz` |
| **Tamanho** | 44.8 MB (compactado) |
| **Registros** | 605.637 |
| **Última Atualização** | 19/11/2025 |
| **Formato** | TXT (pipe-delimited), UTF-8, GZip |

### Estrutura dos Dados

```
protocolo_licitacao|numero_licitacao|nome_modalidade_licitacao|nome_municipio|
cd_ugestora|jurisdicionado_id|nome_jurisdicionado|nome_tipo_jurisdicionado|
nome_tipo_administracao_jurisdicionado|nome_esfera_jurisdicionado|objeto_licitacao|
valor_estimado_licitacao|valor_licitado_licitacao|data_homologacao_licitacao|
ano_homologacao_licitacao|situacao_fracassada_licitacao|nome_proponente|
cpf_cnpj_proponente|valor_proposta|situacao_proposta|nome_estagio_processual_licitacao|
nome_setor_atual_licitacao|url
```

### Distribuição por Ano

| Ano | Registros |
|-----|-----------|
| 2025 | 68.943 |
| 2024 | 73.392 |
| 2023 | 77.347 |
| 2022 | 71.174 |
| 2021 | 62.779 |
| 2020 | 42.304 |

### Modalidades (Top 10)

| Modalidade | Registros |
|------------|-----------|
| Pregão Presencial (Lei 10.520/2002) | 172.730 |
| Pregão Eletrônico (Lei 10.520/2002) | 102.106 |
| Dispensa (Lei 8.666/1993) | 63.493 |
| Pregão (Lei 14.133/2021) | 60.594 |
| Dispensa (Lei 14.133/2021) | 45.320 |
| Inexigibilidade (Lei 8.666/1993) | 38.116 |
| Tomada de Preços (Lei 8.666/1993) | 31.311 |
| Chamada Pública | 20.521 |
| Inexigibilidade (Lei 14.133/2021) | 16.389 |
| Adesão a ARP (Lei 8.666/1993) | 12.020 |

### Estágios Processuais (2025)

| Estágio | Registros | % |
|---------|-----------|---|
| Formalizado | 68.416 | 99.2% |
| Juntado | 318 | 0.5% |
| Decisão Publicada | 61 | 0.1% |
| Outros | 148 | 0.2% |

---

## Problema para Prospecção

### ❌ Dados são de Licitações JÁ HOMOLOGADAS

O campo principal de data é `data_homologacao_licitacao`, que indica quando o processo foi **finalizado**, não quando foi **aberto**.

**Impacto:** Os dados não são úteis para o objetivo principal do GSM (prospecção de oportunidades futuras).

### Campos Ausentes para Prospecção

- ❌ Data de Abertura das Propostas
- ❌ Data Limite para Envio de Propostas
- ❌ Status de Abertura (Aberta/Publicada/Em Andamento)
- ❌ Link Direto para o Edital (PDF)

---

## Uso Alternativo

### ✅ Análise Histórica

Os dados **podem ser úteis** para:

1. **Análise de Mercado:** Identificar padrões de compras por órgão/modalidade
2. **Inteligência Competitiva:** Ver quais empresas vencem licitações em determinados segmentos
3. **Benchmarking de Preços:** Comparar valores estimados vs. licitados
4. **Relatórios Estatísticos:** Gerar dashboards de tendências

### Implementação Sugerida (Baixa Prioridade)

Se futuramente quisermos adicionar uma feature de "Análise Histórica", podemos:

1. Criar um importer para carregar dados históricos do TCE-PB
2. Adicionar filtros de análise (por proponente, por órgão, por valor)
3. Gerar relatórios de inteligência competitiva

---

## Outras Fontes TCE-PB

### Portal de Transparência da Paraíba

**URL:** https://transparencia.pb.gov.br

Investigação pendente. Pode ter dados de licitações abertas/em andamento.

### Portal do Gestor (Tramita)

**URL:** https://tramita.tce.pb.gov.br

Este é o sistema de tramitação interno do TCE-PB. Os links `url` no dataset apontam para consultas nesse sistema.

---

## Conclusão

| Aspecto | Avaliação |
|---------|-----------|
| Disponibilidade de Dados | ✅ Excelente |
| Atualização | ✅ Mensal |
| Formato | ✅ Padronizado |
| Utilidade para Prospecção | ❌ Baixa |
| Utilidade para Análise | ✅ Alta |

**Recomendação:** Deprioritizar integração do TCE-PB para prospecção. Manter na lista para futura feature de "Análise Histórica".

---

## Próximos Passos

1. ~~Investigar TCE-PB~~ ✅ CONCLUÍDO
2. **Investigar e-Compras DF** (próximo)
3. Verificar se PNCP cobre adequadamente a Paraíba

---

*Documento gerado em: Dezembro 2025*
*Investigação realizada pelo GSM - Buscador de Editais*
