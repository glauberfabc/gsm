# ✅ CHECKLIST DE DEPLOY - GSM V3.0

## 🎯 Objetivo
Deploy da versão 3.0 do GSM - Buscador de Editais em ambiente de produção.

---

## 📋 PRÉ-DEPLOY

### Código e Testes
- [x] ✅ Código committed no repositório
- [x] ✅ Testes de regressão executados (80% aprovação)
- [x] ✅ Documentação técnica atualizada
- [x] ✅ Documentação de usuário criada
- [x] ✅ CHANGELOG atualizado

### Ambiente
- [ ] ⏳ Variáveis de ambiente configuradas em produção
- [ ] ⏳ MongoDB em produção configurado e testado
- [ ] ⏳ Backup do banco de dados atual realizado
- [ ] ⏳ DNS configurado (se aplicável)
- [ ] ⏳ SSL/TLS certificados válidos

### Dependências
- [x] ✅ `requirements.txt` atualizado
- [x] ✅ `package.json` atualizado
- [ ] ⏳ Playwright browsers instalados em produção
- [ ] ⏳ Todas as dependências testadas em staging

---

## 🚀 DURANTE O DEPLOY

### Backend
- [ ] ⏳ Build da imagem Docker
- [ ] ⏳ Push para registry
- [ ] ⏳ Deploy no Kubernetes
- [ ] ⏳ Health check passou
- [ ] ⏳ Logs sem erros críticos

### Frontend
- [ ] ⏳ Build de produção (`yarn build`)
- [ ] ⏳ Assets otimizados
- [ ] ⏳ Deploy no CDN/servidor
- [ ] ⏳ Cache invalidado
- [ ] ⏳ Página carrega corretamente

### Database
- [ ] ⏳ Migrations executadas (se aplicável)
- [ ] ⏳ Índices criados
- [ ] ⏳ Conexões testadas
- [ ] ⏳ Backup pós-deploy realizado

---

## 🧪 PÓS-DEPLOY (SMOKE TESTS)

### Funcionalidades Críticas
- [ ] ⏳ **Busca básica** funciona
- [ ] ⏳ **Filtros avançados** funcionam
- [ ] ⏳ **Exportação CSV** funciona
- [ ] ⏳ **Exportação JSON** funciona
- [ ] ⏳ **Dashboard de saúde** acessível
- [ ] ⏳ **Gerenciamento de listas** funciona

### Performance
- [ ] ⏳ Tempo de resposta < 15s (busca)
- [ ] ⏳ Tempo de resposta < 3s (outros endpoints)
- [ ] ⏳ Frontend carrega < 2s
- [ ] ⏳ Sem erros no console do browser

### Monitoramento
- [ ] ⏳ Logs sendo coletados
- [ ] ⏳ Métricas sendo enviadas
- [ ] ⏳ Alertas configurados
- [ ] ⏳ Dashboard de monitoramento ativo

---

## 📊 VALIDAÇÃO DE PRODUÇÃO

### Testes Manuais (15 min)
- [ ] ⏳ Fazer busca por "insulina"
- [ ] ⏳ Aplicar 3 filtros diferentes
- [ ] ⏳ Criar uma lista customizada
- [ ] ⏳ Exportar resultados em CSV
- [ ] ⏳ Exportar resultados em JSON
- [ ] ⏳ Acessar dashboard de saúde
- [ ] ⏳ Verificar responsividade mobile

### Testes de Integração
- [ ] ⏳ PNCP retornando dados
- [ ] ⏳ ComprasNet retornando dados
- [ ] ⏳ Scrapers estaduais funcionando
- [ ] ⏳ MongoDB gravando dados
- [ ] ⏳ Health monitor registrando execuções

---

## 🛡️ SEGURANÇA

- [ ] ⏳ HTTPS funcionando
- [ ] ⏳ Headers de segurança configurados
- [ ] ⏳ CORS configurado corretamente
- [ ] ⏳ Rate limiting ativo (se aplicável)
- [ ] ⏳ Credenciais não expostas

---

## 📢 COMUNICAÇÃO

- [ ] ⏳ Stakeholders notificados sobre deploy
- [ ] ⏳ Usuários informados sobre novas features
- [ ] ⏳ Equipe de suporte treinada
- [ ] ⏳ Documentação disponibilizada

---

## 🔄 ROLLBACK PLAN

### Se algo der errado:

**Critérios para Rollback:**
- ❌ Taxa de erro > 10%
- ❌ Performance degradada (>30s)
- ❌ Funcionalidade crítica quebrada
- ❌ Perda de dados

**Passos de Rollback:**
1. Reverter deploy no Kubernetes (`kubectl rollout undo`)
2. Invalidar cache do frontend
3. Restaurar backup do MongoDB (se necessário)
4. Notificar equipe
5. Investigar causa raiz
6. Aplicar fix
7. Tentar deploy novamente

---

## 📝 NOTAS DO DEPLOY

**Data/Hora do Deploy:**
```
Data: _____________________
Hora Início: _______________
Hora Fim: _________________
```

**Responsável:**
```
Nome: _____________________
Email: ____________________
```

**Issues Encontrados:**
```
- 
- 
- 
```

**Ações Corretivas:**
```
- 
- 
- 
```

---

## ✅ APROVAÇÃO FINAL

- [ ] ⏳ Testes de regressão: PASSOU
- [ ] ⏳ Smoke tests: PASSOU
- [ ] ⏳ Performance: ACEITÁVEL
- [ ] ⏳ Segurança: VALIDADA
- [ ] ⏳ Documentação: COMPLETA

**DEPLOY APROVADO:** ☐ SIM ☐ NÃO

**Assinatura:** _____________________

---

## 🎉 PÓS-DEPLOY

- [ ] ⏳ Monitorar logs por 24h
- [ ] ⏳ Coletar feedback de usuários
- [ ] ⏳ Atualizar documentação conforme necessário
- [ ] ⏳ Planejar próxima iteração (V3.1 ou V4.0)

---

**Última atualização:** Dezembro 2024
**Versão:** 3.0.0
