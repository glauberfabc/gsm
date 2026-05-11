# GSM - Buscador de Editais - PRD

## Problema Original
Construir o "GSM - Buscador de Editais", aplicação de busca de licitações 100% independente de dados, com buscas ao vivo em portais governamentais oficiais brasileiros.

## Funcionalidades Principais

### 1. Janela ANVISA (DAMA Intelligence v4)
- **Buscar Medicamento v4** com análise semântica de conteúdo:
  - Filtro Semântica Negativa: CBPF, certificações, registros → classificados como ROTINA
  - **JANELA ABERTA v2**: Somente publicações oficiais (DOU/ANVISA/CMED) com prova forte ativam
  - PNCP = Indicador de Mercado (badge laranja, NÃO ativa Janela Aberta)
  - Hierarquia de prova: DOU Desabastecimento > ANVISA Descontinuação > CMED > PNCP Indicador > Notícias > Rotina
  - Refinamento de conteúdo: busca real do DOU para classificar documentos ambíguos
  - 6 fontes simultâneas com priorização dinâmica
- Filtro temporal >=2025, Tag RECENTE 2026+
- Stress test: Ustequinumabe RE 992/2026 → rotina/BAIXO (CBPF)

### 2. Buscador de Editais & Preços
- Links clicáveis em TODAS as fontes
- Exportação Excel, gráficos de tendência

### 3. DAMA Vigência Normativa (P0) + Esclarecimento v2
- Validação de vigência integrada ao "Gerar Esclarecimento"
- Esclarecimento revisado juridicamente (Lei 14.133/2021)
- Seção obrigatória: Solicitação de Cópia do Processo Judicial
- Base legal: Art. 37 CF/88, Lei 12.527/2011 (LAI), Art. 5º Lei 14.133/2021

## Implementado
- **[2026-03-17]** Central de Preços, Excel, Filtro Período, Gráficos
- **[2026-03-18]** DAMA P0 Vigência, Links Fonte clicáveis
- **[2026-03-19]** Buscar Medicamento v1/v2
- **[2026-03-20]** DAMA v3 Inteligência Analítica:
  - Semântica negativa (CBPF/certificações = rotina)
  - Refinamento DOU (fetch conteúdo real)
  - Esclarecimento jurídico revisado + Processo Judicial
  - Campo busca limpa ao re-focar
- **[2026-03-20]** JANELA ABERTA v2 (P0 Fix):
  - PNCP não ativa mais Janela Aberta (agora é "Indicador de Mercado")
  - Janela Aberta requer publicação oficial DOU/ANVISA/CMED com prova forte
  - Badge laranja "INDICADOR PNCP" substitui badge vermelho
  - Testado: 9/9 testes backend + frontend 100%

- **[2026-04-13]** Refatoracao Estrutural App.jsx (P1):
  - App.jsx: 3600+ linhas -> 140 linhas (orquestrador)
  - 7 hooks: useSearch, usePrecos, useAnvisa, useDama, useCompanies, useEsclarecimento, useListasRadares
  - 7 tab components: SearchTab, ListasTab, RadaresTab, DamaTab, PrecosTab, AnvisaTab, SettingsTab
  - 1 modal: EsclarecimentoModal + EmpresaModal (dentro de DamaTab)
  - Layout: Header, Footer | Common: ErrorBoundary, HighlightText
  - Tooltip educativo no badge INDICADOR PNCP (DOU/ANVISA/CMED = validade juridica)
  - Testado: 12/12 features PASS (iteration_36)

- **[2026-04-13]** P2 Features Implementadas:
  - Lazy Loading (React.lazy + Suspense) em 6 tabs
  - DAMA Checklist Automatizado: verifica vigencia normativa + janela aberta + publicacao oficial
  - Prova Documental PDF: gera PDF formal com cabecalho empresa, fundamentacao legal, declaracao autenticidade
  - Testado: 14/14 features PASS (iteration_37) - backend + frontend

- **[2026-04-13]** P3 Features Implementadas:
  - Motor de Inteligencia Normativa (Revogacao Cruzada):
    - Tabela REVOGACOES no dama_checklist_service.py com 8+ normas mapeadas
    - ChecklistPanel exibe alertas visuais de normas revogadas com sugestao de substituicao
    - Exibe normas vigentes de referencia (RDC 488/2021, RDC 658/2022, etc.)
  - Integracao LMR (IN 428/2026) + Radar de Importacao:
    - Backend: lmr_service.py com analise tributaria, margens, score de oportunidade
    - Endpoints: GET /api/dama/lmr-analysis, POST /api/dama/lmr-analise-medicamento
    - Frontend: Nova aba "Radar LMR" com busca individual, stats cards, lista de oportunidades
    - Hook useRadarLmr.js + RadarLmrTab.jsx (lazy-loaded)
  - Testado: 11/11 backend + frontend 100% PASS (iteration_38)

- **[2026-04-13]** P4 Features Implementadas:
  - Smart Cache 24h: SmartCacheService com TTL 24h, namespace support (anvisa_busca, lmr_analysis, lmr_medicamento)
    - Endpoints cacheados: /api/dama/lmr-analysis, /api/dama/lmr-analise-medicamento, /api/anvisa/buscar-medicamento
    - Invalidacao via POST /api/cache/clear (limpa search_cache 10min + smart_cache 24h)
    - Stats via GET /api/cache/stats (hits, misses, hit_rate, namespaces)
  - Alertas de Oportunidade (Score >= 80%):
    - Trigger no lmr_service.py: salva no MongoDB (oportunidades_alertas) quando score >= 80%
    - Endpoints: GET /api/notificacoes/oportunidades, POST /api/notificacoes/oportunidades/{id}/lida
    - Frontend: Sino de notificacoes no Header com badge dourado/verde e dropdown
  - Filtro Criticas no Radar LMR: Toggle "Somente Oportunidades Criticas (80%+)"
  - Prova Documental com LMR: PDF inclui secao "Analise Tributaria LMR" (categoria, carga, beneficio)
  - Testado: 14/14 backend + frontend 100% PASS (iteration_39)

- **[2026-04-13]** P5 Integracao Email Oportunidades:
  - Conectou lmr_service.py ao EmailService existente (Resend)
  - Trigger: score >= 80% -> salva alerta MongoDB -> dispara email via Resend
  - Campos auditoria: email_enviado, email_status, email_destinatario, email_id
  - Modo teste: envia para claudio@gruposmartmedical.com.br (verificado)
  - Producao: CC para hudson@vipfarma.com.br + claudio@gruposmartmedical.com.br
  - Frontend: dropdown exibe "E-mail enviado" em verde por alerta
  - Removidos campos mock (notificacao_email/whatsapp/slack)
  - Testado: 23/23 backend + frontend 100% PASS (iteration_40)

- **[2026-04-13]** Bugfix: Link Email Prova Documental LMR:
  - Corrigido: botao do email agora aponta para /api/dama/prova-documental-lmr/{alerta_id} (nosso PDF)
  - Antes: redirecionava para pncp.gov.br (generico, sem fundamentacao juridica)
  - Novo endpoint: GET /api/dama/prova-documental-lmr/{id} gera PDF on-the-fly com analise LMR
  - Texto botao: "Ver Analise no DAMA / Baixar Prova Documental" (verde) vs "Ver Edital / Baixar PDF" (azul)
  - Testado: 8/8 backend + frontend 100% PASS (iteration_41)

- **[2026-04-13]** Deep-link Email -> Frontend:
  - Email agora envia URL do frontend: https://dama-legal...?alerta=<ID>
  - Frontend le ?alerta=, abre aba Radar LMR, carrega AlertaEmailPanel automaticamente
  - Painel exibe: Score, Categoria, Carga Tributaria, Beneficio, Estrategia Tributaria Detalhada
  - Botao "Baixar Prova Documental PDF" gera PDF on-the-fly
  - Fallback: se alerta nao encontrado, exibe mensagem de erro (nao pagina vazia)
  - Endpoint individual: GET /api/notificacoes/oportunidades/{id} retorna alerta + analise_lmr + pdf_url
  - Testado: 12/12 backend + frontend 100% PASS (iteration_42)

- **[2026-04-13]** Bugfix: insertBefore + Category Tabs:
  - Fix insertBefore: cada tab lazy-loaded agora tem seu proprio <Suspense> boundary isolado
  - LazyFallback movido para fora do render como elemento estavel (evita recreacao)
  - Category tabs: TODOS, SINTETICO, BIOLOGICO, GENERICO, SIMILAR, EXCEPCIONAL
  - Sincronizacao bidirecional entre tabs de categoria e select dropdown
  - Backend retorna aliquotas diferenciadas por tipo (biologico=21%, sintetico=20.5%)
  - Testado: 14/14 backend + frontend 100% PASS (iteration_43)

- **[2026-04-15]** Radar Farmaceutico - Inteligencia de Desabastecimento (Fase 1+2):
  - Collection `lista_interesse_estrategica`: CRUD completo + 4 seeds (Pembrolizumabe, Canabidiol, Semaglutida, Eculizumabe)
  - Collection `desabastecimento_inteligencia`: cruzamento automatico lista de interesse X DOU/ANVISA
  - Scraper DOU expandido: 4 novos termos de busca (suspensao fabricacao, interrupcao definitiva, descontinuidade temporaria, reativacao fabricacao)
  - Integracao LMR: lmr_service.py faz lookup em desabastecimento_inteligencia, score_boost=95 para matches
  - Trigger Resend: alerta email automatico quando medicamento da lista entra em desabastecimento
  - 8 endpoints: GET/POST/PUT/DELETE lista-interesse, POST scan, GET desabastecimento, GET stats, POST seed
  - Frontend: Nova aba "Radar Farma" com tabela de interesse, stats cards, painel de desabastecimento, scan button
  - Auto-seed no startup do backend
  - Testado: 12/12 backend + frontend 100% PASS (iteration_44)

## Backlog
- **(P2)** DAMA Checklist Automatizado -- CONCLUIDO
- **(P2)** Automacao Prova Documental (PDF) -- CONCLUIDO
- **(P3)** DAMA LMR (IN 428/2026), Radar de Importacao -- CONCLUIDO
- **(P4)** Cache Inteligente TTL 24h para buscas -- CONCLUIDO
- **(P4)** Alertas de Oportunidade (Score >= 80%) -- CONCLUIDO
- **(P4)** Filtro Criticas Radar LMR -- CONCLUIDO
- **(P4)** Prova Documental com LMR Tax -- CONCLUIDO
- **(P5)** Integracao Email Oportunidades via Resend -- CONCLUIDO
- **(P5)** Radar Farmaceutico Fase 1+2 (Inteligencia Desabastecimento) -- CONCLUIDO
- **(P6)** Verificacao Dominio Resend (gruposmartmedical.com.br)
- **(P6)** Radar Farmaceutico Fase 3+ (Scheduler automatico, PowerBI ANVISA)

## Arquitetura Frontend (pos-refatoracao)
```
src/
├── App.jsx                           # Orquestrador (~200 linhas)
├── hooks/
│   ├── useSearch.js                  # Busca unificada
│   ├── usePrecos.js                  # Central de Precos
│   ├── useAnvisa.js                  # JANELA ANVISA + busca medicamento
│   ├── useDama.js                    # Motor de propostas DAMA IA
│   ├── useCompanies.js               # CRUD empresas
│   ├── useEsclarecimento.js          # Esclarecimento + vigencia
│   ├── useListasRadares.js           # Listas e radares
│   ├── useDamaChecklist.js           # Checklist DAMA + Prova PDF
│   ├── useRadarLmr.js               # Radar LMR (IN 428/2026)
│   └── useRadarFarmaceutico.js       # Radar Farmaceutico (Desabastecimento)
├── components/
│   ├── tabs/
│   │   ├── SearchTab.jsx             # Aba Pesquisa
│   │   ├── ListasTab.jsx             # Aba Minhas Listas
│   │   ├── RadaresTab.jsx            # Aba Radares
│   │   ├── DamaTab.jsx               # Aba DAMA IA
│   │   ├── PrecosTab.jsx             # Aba Central de Precos
│   │   ├── AnvisaTab.jsx             # Aba Janela ANVISA + ChecklistPanel
│   │   ├── RadarLmrTab.jsx           # Aba Radar LMR (IN 428/2026)
│   │   ├── RadarFarmaceuticoTab.jsx  # Aba Radar Farma (Desabastecimento)
│   │   └── SettingsTab.jsx           # Aba Configuracoes
│   ├── modals/
│   │   └── EsclarecimentoModal.jsx   # Modal esclarecimento
│   ├── layout/
│   │   ├── Header.jsx                # Navbar + logo (9 tabs)
│   │   └── Footer.jsx                # Rodape
│   └── common/
│       ├── ErrorBoundary.jsx         # Error boundary
│       └── HighlightText.jsx         # Highlight de texto
```

## Arquitetura Backend - Radar Farmaceutico
```
backend/services/
├── radar_farmaceutico_service.py     # Service principal (CRUD + scan + alert)
├── lmr_service.py                    # Atualizado: lookup desabastecimento_inteligencia
├── anvisa_scraper.py                 # Atualizado: 4 novos termos DOU Secao 1
└── email_service.py                  # Resend (trigger para score >= 95)
```

## Limitacoes
- SEI-ANVISA: 403 Forbidden (sistema interno)
- Portal BI ANVISA: Sem filtros dinâmicos (MicroStrategy embarcado)
- DOU: Alguns abstracts vazios (full-text no documento)
- ANVISA Descontinuacao: Sem CSV direto; dados via MicroStrategy/SAD bloqueado
