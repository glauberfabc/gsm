# Relatório de Engenharia Reversa - Plataformas de Inteligência de Mercado

## Data: Dezembro 2024/2025

## Plataformas Analisadas

### 1. eLicitacao (https://app.elicitacao.com.br)
- **Status**: Login bloqueado por reCAPTCHA
- **Observações**: Plataforma usa ASP.NET com jQuery
- **Fontes prováveis**: PNCP, portais estaduais

### 2. Effecti (https://minha.effecti.com.br)
- **Status**: Login bloqueado por reCAPTCHA
- **Observações**: SPA Angular/React, usa Mixpanel para analytics
- **Fontes prováveis**: PNCP, ComprasNet, portais estaduais

## Limitações Encontradas
- Ambas as plataformas implementam reCAPTCHA v2/v3
- Não foi possível acessar APIs internas sem autenticação humana
- Sessões têm timeout curto e validação de origem

## Lições Aprendidas e Boas Práticas

### 1. Fontes de Dados
As plataformas de mercado agregam dados de fontes públicas:
- **PNCP** (pncp.gov.br) - Portal Nacional de Contratações Públicas
- **ComprasNet** (compras.dados.gov.br) - Dados abertos federais
- **Portais Estaduais** - BEC/SP, compras.rj.gov.br, etc.
- **Licitações-e** - Banco do Brasil

### 2. Estrutura de Dados Comum
Campos presentes em todas as plataformas:
- Órgão licitante
- Objeto da licitação
- Modalidade (Pregão, Concorrência, etc.)
- Datas (publicação, abertura, encerramento)
- Valor estimado
- Status (Ativa, Encerrada, etc.)
- Link para edital (PDF)

### 3. Estratégias de Busca
- Busca por palavra-chave no objeto
- Filtros por estado/região
- Filtros por modalidade
- Filtros por período (data de abertura)
- Ordenação por urgência (data limite)

### 4. Frequência de Atualização
- **Padrão de mercado**: Verificação a cada 4-6 horas para alertas
- **Cache**: 1 hora para buscas manuais
- **Notificações**: Diárias ou imediatas para itens críticos

### 5. Técnicas de Scraping Eficazes
- **Playwright/Puppeteer** para sites JavaScript-heavy
- **Navegação dupla**: Lista → Detalhes → PDF
- **Múltiplos seletores** com fallbacks
- **Rate limiting** para evitar bloqueios
- **User-Agent rotation** para parecer tráfego real

## Aplicação no GSM - Buscador de Editais

### Já Implementado ✅
- Scrapers com Playwright (RJ, BEC/SP, MG)
- Navegação dupla para extração de PDFs
- Múltiplos seletores com fallbacks
- Rate limiting entre requisições
- Estrutura de dados padronizada (23+ campos)

### A Implementar
1. **Sistema de Notificações (P2)**
   - Alertas baseados em palavras-chave
   - Frequência de verificação: 6 horas
   - Dashboard interno para visualização

2. **Melhorias Futuras**
   - Integração com API do Portal da Transparência
   - Scraper para Licitações-e (BB)
   - Sistema de score de relevância

## Conclusão
O GSM já segue as melhores práticas identificadas nas plataformas de mercado.
O próximo passo é implementar o sistema de notificações para engajamento do usuário.
