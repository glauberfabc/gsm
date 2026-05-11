# Portais de Licitação do Brasil - Análise Comparativa

## Fonte: eLicitação/Forseti + Effecti + Pesquisa

---

## 🔴 PORTAIS FEDERAIS

| Portal | URL | Gratuito | GSM Status | Prioridade |
|--------|-----|----------|------------|------------|
| **ComprasGov (ComprasNet)** | gov.br/compras | ✅ | ✅ Implementado | - |
| **PNCP** | pncp.gov.br | ✅ | ⚠️ Parcial (aguardando credenciais) | P0 |
| **Licitações-e (Banco do Brasil)** | licitacoes-e.com.br | ❌ Pago | ❌ Não temos | **P1** |
| **Portal Caixa Econômica** | licitacoes.caixa.gov.br | ✅ | ❌ Não temos | P2 |

---

## 🟡 PORTAIS AGREGADORES NACIONAIS

| Portal | URL | Gratuito | GSM Status | Prioridade |
|--------|-----|----------|------------|------------|
| **Portal de Compras Públicas** | portaldecompraspublicas.com.br | ❌ Pago | ❌ Não temos | P2 |
| **Bolsa de Licitações do Brasil (BLL)** | bll.org.br | ❌ Pago | ❌ Não temos | P3 |
| **Bolsa Nacional de Compras (BNC)** | bnc.org.br | ❌ Pago | ❌ Não temos | P3 |
| **Licitar Digital** | licitar.digital | ⚠️ Freemium | ❌ Não temos | P3 |
| **Licitanet** | licitanet.com.br | ⚠️ Freemium | ❌ Não temos | P3 |

---

## 🟢 PORTAIS ESTADUAIS

### Estados que JÁ TEMOS ✅

| UF | Portal | URL | Implementação |
|----|--------|-----|---------------|
| SP | BEC/e-Negócios | bec.sp.gov.br | ✅ Playwright (CAPTCHA) |
| SP | TCE-SP | tce.sp.gov.br | ✅ CSV Importer |
| RJ | SIGA RJ | compras.rj.gov.br | ✅ Playwright |
| MG | Compras MG | compras.mg.gov.br | ✅ CSV Importer |
| RS | CELIC RS | compras.rs.gov.br | ✅ Playwright |
| SC | CIASC SC | - | ✅ Playwright |
| PR | Portal PR | - | ✅ Playwright |
| BA | ComprasNet BA | - | ✅ CSV Importer |
| PE | PE Integrado | - | ✅ Playwright |
| CE | Ceará | - | ✅ Playwright |
| GO | Portal GO | comprasnet.go.gov.br | ✅ CSV Importer |
| ES | Portal ES | compras.es.gov.br | ✅ CSV Importer |

### Estados que NÃO TEMOS ❌

| UF | Portal | URL | Prioridade | Observação |
|----|--------|-----|------------|------------|
| **MS** | Portal MS | - | **P0** | Importer já criado, falta integrar |
| **DF** | e-Compras DF | ecompras.df.gov.br | **P1** | Distrito Federal - Alto volume |
| **MT** | Portal MT | - | P2 | Investigado - sem CSV encontrado |
| **AM** | e-Compras AM | - | P2 | Investigado - sem CSV encontrado |
| **PA** | Portal PA | - | P2 | Investigado - sem CSV encontrado |
| **RN** | Portal RN | - | P2 | Investigado - sem CSV encontrado |
| **MA** | Portal MA | - | P2 | Investigado - sem CSV encontrado |
| **PI** | Portal PI | - | P3 | Baixo volume |
| **PB** | TCE-PB | tce.pb.gov.br | P1 | A investigar |
| **AL** | Portal AL | - | P2 | A investigar |
| **SE** | Portal SE | - | P2 | A investigar |
| **TO** | Portal TO | - | P3 | A investigar |
| **AC** | Portal AC | - | P3 | Baixo volume |
| **RO** | Portal RO | - | P3 | Baixo volume |
| **RR** | Portal RR | - | P3 | Baixo volume |
| **AP** | Portal AP | - | P3 | Baixo volume |

---

## 📊 RESUMO COMPARATIVO

### GSM (Nosso Sistema)
- **Fontes ativas:** 13
- **Estados cobertos:** 12 UFs
- **Foco:** CSV/API First (dados abertos)

### Effecti
- **Fontes ativas:** 22 portais
- **Diferenciais:** PNCP autenticado, iminência, alertas

### eLicitação (Forseti)
- **Fontes ativas:** 13+ portais listados
- **Diferenciais:** Licitações-e (BB), robô de lances

---

## 🎯 PRÓXIMAS AÇÕES (Ordem de Prioridade)

### P0 - Imediato
1. **Finalizar MS** - Importer já criado, só integrar
2. **PNCP Autenticado** - Aguardando credenciais

### P1 - Alta Prioridade (Novos Portais)
1. **Licitações-e (Banco do Brasil)** - Muito usado por prefeituras
2. **e-Compras DF** - Distrito Federal, alto volume
3. **TCE-PB** - Investigar CSV

### P2 - Média Prioridade
1. **Portal Caixa** - Banco estatal
2. **Portal de Compras Públicas** - Agregador de prefeituras
3. Estados sem CSV (MT, AM, PA, RN, MA)

### P3 - Baixa Prioridade
1. BLL, BNC, Licitar Digital (pagos)
2. Estados de baixo volume (AC, RO, RR, AP, PI)

---

## 🔗 URLs para Investigação

### Licitações-e (Banco do Brasil)
```
https://www.licitacoes-e.com.br/aop/index.jsp
https://www.licitacoes-e.com.br/aop/pesquisar-licitacao.aop
```

### e-Compras DF
```
https://ecompras.df.gov.br/
https://www.compras.df.gov.br/
```

### Portal Caixa
```
https://licitacoes.caixa.gov.br/SitePages/pagina_inicial.aspx
```

### Portal de Compras Públicas
```
https://www.portaldecompraspublicas.com.br/
```

---

## 📈 Roadmap de Cobertura

```
Atual: 13 fontes → 12 UFs + Federal (parcial)

Fase 1 (P0-P1):
  + MS, PNCP completo, Licitações-e, DF
  = 17 fontes → 14 UFs + Federal (completo)

Fase 2 (P2):
  + PB, AL, SE, TO, Caixa, Portal Compras Públicas
  = 23 fontes → 18 UFs + Federal + Agregadores

Fase 3 (P3):
  + Restantes (MT, AM, PA, etc. se dados disponíveis)
  = 27+ fontes → 27 UFs (cobertura nacional)
```

---

## 🔧 Estratégia Técnica

### Para Portais com CSV/API (Preferido)
1. Procurar portal de "Dados Abertos" ou "Transparência"
2. Verificar se TCE do estado tem base de dados
3. Implementar importer com chunking

### Para Portais sem CSV
1. Analisar se tem API pública
2. Avaliar se Playwright é viável (CAPTCHA, login)
3. Considerar parceria ou desistir temporariamente

### Para Agregadores Pagos
1. Avaliar custo-benefício
2. Verificar se tem API para integradores
3. Considerar como fonte complementar, não primária
