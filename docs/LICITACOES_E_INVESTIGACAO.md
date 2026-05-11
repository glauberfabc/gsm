# Investigação: Portal Licitações-e (Banco do Brasil)

## Status: ⚠️ BLOQUEADO - Proteção Anti-Bot

---

## Informações do Portal

| Item | Detalhe |
|------|---------|
| **Nome** | Licitações-e |
| **Operador** | Banco do Brasil |
| **URL Principal** | https://www.licitacoes-e.com.br |
| **URL Pesquisa** | https://www.licitacoes-e.com.br/aop/pesquisar-licitacao.aop |
| **Nova Versão** | https://licitacoes-e2.bb.com.br |
| **Proteção** | Cloudflare (cdn-cgi) |

## Estatísticas (Dezembro 2025)

- **1.008.342** compradores cadastrados
- **480** licitações publicadas (ativas)
- **20** com propostas abertas
- **822.746** licitações concluídas

## Problema Identificado

O portal implementa proteção anti-bot via Cloudflare:
```
Ops! Não foi possível completar a sua solicitação.
ID: 9ae9922f9a621121
IP: 35.184.53.215 (IP do servidor/pod)
```

**Motivos prováveis:**
1. IP de datacenter (não residencial)
2. User-Agent de automação detectado
3. Ausência de JavaScript execution patterns esperados
4. Rate limiting ou blocklist

## API Pública

**Resultado da investigação:** ❌ **NÃO EXISTE API PÚBLICA**

- As APIs oficiais do BB são para integração financeira (PIX, Cobrança)
- Não há endpoint REST/JSON público para consulta de licitações
- O portal usa server-side rendering tradicional

## Alternativas Investigadas

### 1. Nova Versão (licitacoes-e2.bb.com.br)
- Status: **Também bloqueado** (403 Forbidden)
- Mesmo sistema de proteção

### 2. PNCP (Portal Nacional de Contratações Públicas)
- Status: **Já integrado parcialmente**
- O PNCP agrega dados de vários portais, incluindo alguns do BB
- **Recomendação:** Ativar PNCP autenticado para cobertura máxima

### 3. Dados Abertos do Governo
- Portal de Dados Abertos pode ter datasets de licitações federais
- Não específico para Licitações-e, mas complementar

## Opções para Integração

### Opção A: Proxy Residencial (Custo)
- Usar serviço de proxy residencial (Bright Data, Oxylabs)
- Custo: $10-50/GB
- Prós: Bypass de bloqueio
- Contras: Custo operacional, possível violação de ToS

### Opção B: Browser Automation Avançada (Complexo)
- Usar undetected-chromedriver ou Playwright com stealth
- Simular comportamento humano (movimentos de mouse, delays)
- Prós: Gratuito
- Contras: Frágil, manutenção constante

### Opção C: Parceria/API Oficial (Ideal)
- Contatar Banco do Brasil para solicitar acesso à API
- Demonstrar uso legítimo (agregador público)
- Prós: Acesso oficial, estável
- Contras: Processo burocrático, sem garantia de aprovação

### Opção D: Foco em Alternativas (Pragmático) ✅
- Priorizar outras fontes com dados públicos abertos
- PNCP autenticado cobre boa parte das licitações federais
- e-Compras DF, TCEs estaduais são mais acessíveis

## Recomendação

**Curto prazo:**
1. ✅ Manter PNCP como fonte principal para dados federais
2. ✅ Documentar Licitações-e como "fonte bloqueada"
3. ⏭️ Seguir para e-Compras DF (próximo P1)

**Médio prazo:**
1. Investigar se PNCP autenticado inclui dados do BB
2. Monitorar se o BB lança API pública

**Longo prazo:**
1. Avaliar parceria comercial se demanda justificar
2. Considerar proxy residencial se volume alto

## URLs para Referência

```
# Página inicial
https://www.licitacoes-e.com.br/aop/index.jsp

# Pesquisa pública (bloqueada para bots)
https://www.licitacoes-e.com.br/aop/pesquisar-licitacao.aop

# Nova versão (também bloqueada)
https://licitacoes-e2.bb.com.br/

# Licitações BB Tecnologia (PDFs)
https://licitacoes.bbts.com.br/
```

## Conclusão

O Licitações-e do Banco do Brasil é uma fonte valiosa, mas possui proteção anti-bot robusta que impede scraping automatizado. 

**Decisão:** Seguir para o próximo item de P1 (e-Compras DF) e manter PNCP como cobertura principal para licitações federais.

---

*Investigação realizada em: Dezembro 2025*
*Status: Bloqueado - Aguardando alternativas*
