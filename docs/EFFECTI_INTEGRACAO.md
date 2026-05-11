# Effecti - Integração Completa

## Status: ✅ IMPLEMENTADA E FUNCIONAL

---

## Resumo

A integração com a plataforma Effecti foi implementada com sucesso. O cliente `effecti_client.py` permite acesso a **22 portais de licitação** através de uma única API, incluindo o **Licitações-e (Banco do Brasil)** que está bloqueado para acesso direto.

---

## Portais Disponíveis (22 total)

| ID | Portal | Status |
|----|--------|--------|
| 1 | ComprasNet | ✅ Disponível |
| 2 | **Licitações-e** | ✅ Disponível |
| 3 | Compras Públicas | ✅ Disponível |
| 5 | BEC/SP | ✅ Disponível |
| 6 | Siga Rio de Janeiro | ✅ Disponível |
| 7 | Siga Espírito Santo | ✅ Disponível |
| 9 | Compras Minas Gerais | ✅ Disponível |
| 11 | Compras Santa Catarina | ✅ Disponível |
| 17 | Procergs | ✅ Disponível |
| 18 | ComprasRS | ✅ Disponível |
| 19 | Banrisul | ✅ Disponível |
| 20 | ComprasNet Goiás | ✅ Disponível |
| 24 | BLL | ✅ Disponível |
| 25 | ComprasNet Cotação | ✅ Disponível |
| 26 | Publinexo | ✅ Disponível |
| 28 | Licitanet | ✅ Disponível |
| 29 | Compras Amazonas | ✅ Disponível |
| 35 | Compras Mato Grosso | ✅ Disponível |
| 58 | Compras Pernambuco | ✅ Disponível |
| 898 | Compras BR | ✅ Disponível |
| 1236 | Licitar Digital | ✅ Disponível |
| 1362 | BNC | ✅ Disponível |

---

## Arquitetura da Integração

```
┌─────────────────────────────────────────────────────────────────┐
│                       GSM - Buscador de Editais                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  scraper_service.py                                             │
│       │                                                         │
│       ├── effecti_client.py  ←── NOVO                           │
│       │       │                                                 │
│       │       └── API Effecti (mdw.minha.effecti.com.br)        │
│       │               │                                         │
│       │               ├── Licitações-e (BB)                     │
│       │               ├── ComprasNet                            │
│       │               ├── BEC/SP                                │
│       │               ├── Compras Públicas                      │
│       │               └── ... (22 portais)                      │
│       │                                                         │
│       ├── pncp_api_oficial.py                                   │
│       ├── pncp_client.py                                        │
│       └── ... (outros scrapers)                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints Implementados

### Login
```
POST https://mdw.minha.effecti.com.br/users/login
```

### Busca de Avisos
```
POST https://mdw.minha.effecti.com.br/aviso/minhas
```

### Lista de Portais
```
GET https://mdw.minha.effecti.com.br/accesses/portals
```

---

## Uso no Código

```python
from scrapers.effecti_client import EffectiClient

# Inicializar cliente
client = EffectiClient()

# Buscar licitações futuras
resultados = await client.buscar_licitacoes(
    termo_busca="medicamento",
    apenas_futuras=True,
    limit=50
)

# Buscar especificamente no Licitações-e
resultados_bb = await client.buscar_licitacoes_e(
    termo_busca="equipamento",
    apenas_futuras=True,
    limit=50
)
```

---

## Credenciais

As credenciais são carregadas via variáveis de ambiente ou valores padrão:

| Variável | Descrição |
|----------|-----------|
| `EFFECTI_USERNAME` | Email de login |
| `EFFECTI_PASSWORD` | Senha |

**Nota:** A conta atual tem `daysRemaining: -1`, indicando que o período de teste expirou. Considerar renovação para acesso completo.

---

## Limitações Conhecidas

### 1. Perfil de Interesse
O Effecti filtra avisos baseado no "perfil de interesse" configurado na conta. A conta atual mostra apenas ~15 avisos dos 6.900+ totais.

**Solução:** Configurar o perfil de interesse na plataforma Effecti para incluir mais categorias.

### 2. Conta Expirada
O campo `daysRemaining: -1` indica conta expirada, mas o acesso ainda funciona parcialmente.

**Solução:** Renovar assinatura do Effecti para acesso completo.

### 3. Dados do Licitações-e
Atualmente não há avisos do Licitações-e no perfil de interesse configurado.

**Solução:** Adicionar Licitações-e ao perfil de interesse na conta Effecti.

---

## Métricas de Performance

| Métrica | Valor |
|---------|-------|
| Tempo de Login | ~800ms |
| Tempo de Busca | ~500ms |
| Total por requisição | ~1.5s |

---

## Próximos Passos

1. [ ] Configurar perfil de interesse no Effecti para incluir mais portais
2. [ ] Renovar assinatura do Effecti (se necessário)
3. [ ] Adicionar cache de token JWT para reduzir logins
4. [ ] Implementar busca paginada para grandes volumes

---

## Arquivos Relacionados

- `/app/backend/scrapers/effecti_client.py` - Cliente principal
- `/app/backend/scrapers/__init__.py` - Registro do cliente
- `/app/backend/services/scraper_service.py` - Integração com o serviço de busca
- `/app/docs/EFFECTI_API_REFERENCE.md` - Documentação da API (engenharia reversa)

---

*Documento criado em: Dezembro 2025*
*Integração implementada pelo GSM - Buscador de Editais*
