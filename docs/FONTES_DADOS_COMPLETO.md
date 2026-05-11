# GSM - Fontes de Dados Completo

## Status Atual: 15+ Fontes de Dados Ativas

---

## Mapa de Cobertura

```
┌──────────────────────────────────────────────────────────────────────┐
│                    GSM - BUSCADOR DE EDITAIS                          │
│                  Cobertura Nacional de Licitações                     │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   ┌─────────────────────────────────────────────────────────────┐    │
│   │            AGREGADORES NACIONAIS (Prioridade 0)              │    │
│   ├─────────────────────────────────────────────────────────────┤    │
│   │  • PNCP-OFICIAL: 25.000+ propostas abertas (API pública)    │    │
│   │  • EFFECTI: 22 portais (incluindo Licitações-e do BB)       │    │
│   │  • ComprasNet: Licitações federais                          │    │
│   │  • PNCP-AUTH: Aguardando credenciais                        │    │
│   └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│   ┌─────────────────────────────────────────────────────────────┐    │
│   │              PORTAIS ESTADUAIS (Prioridade 1-2)              │    │
│   ├─────────────────────────────────────────────────────────────┤    │
│   │  • SP (TCE): ✅      • RJ: ✅       • RS: ✅                 │    │
│   │  • SC: ✅            • PR: ✅       • MG: ✅                 │    │
│   │  • BA: ✅            • PE: ✅       • CE: ✅                 │    │
│   │  • ES: ✅            • GO: ✅       • BEC/SP: ⚠️ (CAPTCHA)  │    │
│   └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
│   ┌─────────────────────────────────────────────────────────────┐    │
│   │              INVESTIGADOS/DEPRIORITIZADOS                     │    │
│   ├─────────────────────────────────────────────────────────────┤    │
│   │  • TCE-PB: Dados históricos (não futuras)                   │    │
│   │  • e-Compras DF: Volume muito baixo                         │    │
│   │  • MS: Coberto via PNCP                                     │    │
│   │  • Licitações-e: Acessível via EFFECTI                      │    │
│   └─────────────────────────────────────────────────────────────┘    │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Comparativo: GSM vs Effecti

| Aspecto | Effecti | GSM |
|---------|---------|-----|
| **Portais** | 22 | 15+ (crescendo) |
| **API Aberta** | ❌ Proprietária | ✅ Sim |
| **Código Aberto** | ❌ | ✅ |
| **Prospecção Futura** | ✅ | ✅ |
| **Iminência** | ✅ | ✅ |
| **Dashboard Saúde** | ❌ | ✅ |
| **Custo** | 💰 Assinatura | ✅ Gratuito |
| **Dependência Externa** | - | ⚠️ Effecti (temporário) |

---

## Estratégia de Independência

### Fase 1: Atual ✅
- Integração Effecti como fonte temporária
- PNCP-OFICIAL como fonte principal independente
- Scrapers diretos para 11 estados

### Fase 2: Próxima
- Configurar perfil Effecti para incluir Licitações-e
- Implementar cache de dados do Effecti
- Desenvolver scrapers diretos para mais estados

### Fase 3: Futuro
- Eliminar dependência do Effecti
- API própria completa e independente
- Cobertura de todos os 27 estados

---

## Endpoints de API PNCP (Documentação)

### Propostas Abertas (Principal para Prospecção)
```
GET https://pncp.gov.br/api/consulta/v1/contratacoes/proposta
Parâmetros:
  - dataFinal: YYYYMMDD (obrigatório)
  - pagina: int (obrigatório)
  - tamanhoPagina: int (opcional, max 500)
```

### Publicações Recentes
```
GET https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao
Parâmetros:
  - dataInicial: YYYYMMDD (obrigatório)
  - dataFinal: YYYYMMDD (obrigatório)
  - codigoModalidadeContratacao: int (obrigatório)
  - pagina: int (obrigatório)
```

### Atas de Registro de Preços
```
GET https://pncp.gov.br/api/consulta/v1/atas
Parâmetros:
  - dataVigenciaInicial: YYYYMMDD
  - dataVigenciaFinal: YYYYMMDD
  - pagina: int
```

---

## Arquivos do Sistema

### Scrapers Ativos
```
/app/backend/scrapers/
├── effecti_client.py        # 22 portais via Effecti
├── pncp_api_oficial.py      # API pública PNCP (25k+ propostas)
├── pncp_client.py           # Cliente PNCP original
├── comprasnet_client.py     # Federal
├── ceara_scraper.py         # CE
├── rio_de_janeiro_scraper.py# RJ
├── rio_grande_do_sul_scraper.py # RS
├── santa_catarina_scraper.py# SC
├── sao_paulo_tce_importer.py# SP
├── parana_csv_importer.py   # PR
├── bahia_csv_importer.py    # BA
├── pernambuco_csv_importer.py# PE
├── minas_gerais_csv_importer.py # MG
├── goias_csv_importer.py    # GO
└── espirito_santo_csv_importer.py # ES
```

### Documentação
```
/app/docs/
├── EFFECTI_API_REFERENCE.md     # Engenharia reversa Effecti
├── EFFECTI_INTEGRACAO.md        # Integração completa
├── FONTES_DADOS_COMPLETO.md     # Este arquivo
├── TCE_PB_INVESTIGACAO.md       # Investigação Paraíba
├── ECOMPRAS_DF_INVESTIGACAO.md  # Investigação DF
└── ARQUITETURA_PROSPECCAO_FUTURA.md # Arquitetura geral
```

---

## Métricas do Sistema

| Métrica | Valor |
|---------|-------|
| **Fontes Ativas** | 13+ |
| **Taxa de Sucesso** | 100% |
| **Propostas PNCP** | 25.000+ |
| **Cobertura Estados** | 15/27 (56%) |

---

*Documento atualizado em: Dezembro 2025*
*GSM - Buscador de Editais*
