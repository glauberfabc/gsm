# e-Compras DF (Distrito Federal) - Investigação de Portal

## Resumo Executivo

**Resultado:** ⚠️ **POSSÍVEL MAS BAIXO VOLUME** - Portal funcional com API interna, mas volume de dados próprios é baixo.

---

## Portal de Compras DF

**URL Principal:** https://portal.compras.df.gov.br
**URL Licitações:** https://portal.compras.df.gov.br/licitacao

### Tecnologia

| Componente | Tecnologia |
|------------|------------|
| Framework | ASP.NET MVC 5.2 |
| Servidor | IIS + Cloudflare |
| Frontend | jQuery + DataTables |
| Autenticação | Sessions (.NET) |

---

## API Interna Descoberta

### Endpoint de Consulta

```
POST /Licitacao/_ConsultaLicitacaoResultado
Content-Type: application/x-www-form-urlencoded
X-Requested-With: XMLHttpRequest

Parâmetros:
- orgao: string (código do órgão)
- ano: int (ex: 2025)
- situacao: string (ex: "Aberto", "Deserta", "Homologado")
- edital: string (número do edital)
- dataPublicacaoInicial: date
- dataPublicacaoFinal: date
- objeto: string (busca textual)
- item: string (busca por item)
```

### Estrutura de Resposta (HTML)

Retorna tabela HTML com colunas:
- Edital (link para detalhes)
- Modalidade
- Órgão
- Objeto
- Situação
- Data/Hora Publicação
- **Data Limite para inscrição de Propostas** ✅
- Documentos
- Acompanhar Sessão

### Endpoint de Detalhes

```
GET /licitacao/detalhar/{id}
```

Retorna página com informações completas e links para documentos.

### Endpoint de Documentos

```javascript
fnDocumentoEdital(id)           // Documentos do edital
fnDocumentosPorFornecedor(id, fornecedorId)  // Documentos por fornecedor
```

---

## Dados Observados (Dez/2025)

### Volume de Licitações

| Situação | Quantidade |
|----------|------------|
| Anulado/Revogado | ~1 |
| Deserta | ~4 |
| Homologado Total | ~1 |
| **Total 2025** | **~6** |

**⚠️ BAIXO VOLUME:** O portal próprio do DF tem pouquíssimas licitações. A maioria das compras públicas do DF são feitas via:
- ComprasNet (Federal)
- PNCP (Federal)
- Pregões Eletrônicos via BEC/ComprasNet

### Modalidades Encontradas

- Dispensa Eletrônica (maioria)
- Pregão Eletrônico (raro no portal próprio)

---

## Análise de Viabilidade

### ✅ Pontos Positivos

1. **Dados Estruturados:** API retorna HTML bem formatado
2. **Data Limite Disponível:** Campo crítico para prospecção
3. **Links para Documentos:** Acesso aos editais
4. **Sem CAPTCHA:** Acesso direto via HTTP

### ❌ Pontos Negativos

1. **Volume Muito Baixo:** Apenas ~6 licitações em 2025
2. **Maioria Finalizada:** Poucos processos abertos
3. **Duplicação Potencial:** Dados podem estar no PNCP
4. **HTML Parsing:** Requer scraping de HTML, não JSON

---

## Decisão

### Recomendação: **DEPRIORITIZAR**

**Justificativa:**
1. O volume de dados próprios do e-Compras DF é muito baixo para justificar um importer dedicado
2. As licitações do DF provavelmente já estão cobertas pelo PNCP-Oficial
3. O custo/benefício de implementar um parser HTML é alto para poucos registros

### Alternativa

Confiar na cobertura do PNCP para o Distrito Federal, que tem acesso às mesmas licitações federais e estaduais.

---

## Se Implementar Futuramente

### Estrutura do Importer

```python
class EComprasDFScraper:
    BASE_URL = "https://portal.compras.df.gov.br"
    
    async def buscar_licitacoes(self, ano: int = 2025) -> List[Dict]:
        url = f"{self.BASE_URL}/Licitacao/_ConsultaLicitacaoResultado"
        data = {"ano": ano, "situacao": ""}
        # Parse HTML response
        # Extract: edital, modalidade, orgao, objeto, situacao, 
        #          data_publicacao, data_limite, link_detalhes
        
    async def obter_documentos(self, edital_id: int) -> List[str]:
        # Buscar links de documentos (PDFs)
        pass
```

---

## Fontes Alternativas para DF

| Fonte | Status | Cobertura |
|-------|--------|-----------|
| PNCP-Oficial | ✅ ATIVO | Federal + DF |
| ComprasNet | ✅ ATIVO | Federal |
| Portal Compras DF | ⚠️ BAIXO | Apenas DF próprio |

---

## Conclusão

O e-Compras DF foi investigado e documentado, mas será **deprioritizado** devido ao baixo volume de licitações próprias. O sistema GSM já cobre o Distrito Federal através do:

- **PNCP-API-OFICIAL:** Cobertura ampla de licitações federais e estaduais
- **ComprasNet:** Licitações federais incluindo órgãos do DF

---

*Documento gerado em: Dezembro 2025*
*Investigação realizada pelo GSM - Buscador de Editais*
