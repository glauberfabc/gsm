# P1 - Sistema de Notificações Baseadas em Buscas Salvas

## Resumo Executivo
Transformar o GSM de um buscador passivo em uma ferramenta de **inteligência ativa** que alerta usuários automaticamente quando novas licitações de interesse aparecem.

---

## Arquitetura Proposta

### Stack Atual (Manter Consistência)
- **Backend**: FastAPI + Python
- **Banco de Dados**: MongoDB (já configurado)
- **Frontend**: React + Tailwind

### Componentes a Implementar

```
┌─────────────────────────────────────────────────────────────┐
│                    SISTEMA DE NOTIFICAÇÕES                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Frontend  │───▶│   Backend   │───▶│   MongoDB   │     │
│  │  (React)    │    │  (FastAPI)  │    │             │     │
│  └─────────────┘    └──────┬──────┘    └─────────────┘     │
│                            │                                │
│                            ▼                                │
│                   ┌─────────────────┐                       │
│                   │  Job Scheduler  │                       │
│                   │  (Background)   │                       │
│                   └────────┬────────┘                       │
│                            │                                │
│                            ▼                                │
│                   ┌─────────────────┐                       │
│                   │  Notificações   │                       │
│                   │  (Email/Push)   │                       │
│                   └─────────────────┘                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Fase 1: Persistência de Buscas Salvas (DIA 1)

### 1.1 Modelo de Dados MongoDB

```python
# /app/backend/models/saved_search.py

from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class SavedSearch(BaseModel):
    id: str                          # UUID único
    user_id: str                     # ID do usuário (ou "anonymous" se não autenticado)
    nome: str                        # Nome amigável da busca
    termo_busca: str                 # Ex: "insulina", "medicamento"
    
    # Filtros salvos
    apenas_futuras: bool = True
    apenas_saude: bool = True
    apenas_urgentes: bool = False
    categorias_saude: List[str] = [] # ["hospitalar", "medicamentos"]
    esfera_filtro: Optional[str] = None  # "Federal", "Estadual", "Municipal"
    
    # Metadados
    criado_em: datetime
    atualizado_em: datetime
    ultima_verificacao: Optional[datetime] = None
    
    # Configurações de notificação
    notificacoes_ativas: bool = True
    frequencia_verificacao: str = "diario"  # "diario", "semanal", "tempo_real"
    email_notificacao: Optional[str] = None
    
    # Estatísticas
    total_notificacoes_enviadas: int = 0
    ultimas_licitacoes_ids: List[str] = []  # Para evitar duplicatas
```

### 1.2 Coleção MongoDB

```javascript
// Coleção: saved_searches
{
    "id": "uuid-xxx",
    "user_id": "user-123",
    "nome": "Insulina Nacional",
    "termo_busca": "insulina",
    "apenas_futuras": true,
    "apenas_saude": true,
    "categorias_saude": ["medicamentos", "hospitalar"],
    "notificacoes_ativas": true,
    "frequencia_verificacao": "diario",
    "criado_em": ISODate("2025-12-16T22:00:00Z"),
    "ultimas_licitacoes_ids": []
}
```

### 1.3 Endpoints API

```python
# /app/backend/server.py (adicionar)

# ============ BUSCAS SALVAS ============

@app.post("/api/saved-searches", response_model=dict)
async def criar_busca_salva(busca: SavedSearchCreate):
    """Salva uma nova busca para notificações"""
    pass

@app.get("/api/saved-searches", response_model=List[dict])
async def listar_buscas_salvas(user_id: str = Query(...)):
    """Lista todas as buscas salvas do usuário"""
    pass

@app.get("/api/saved-searches/{busca_id}", response_model=dict)
async def obter_busca_salva(busca_id: str):
    """Obtém detalhes de uma busca salva"""
    pass

@app.put("/api/saved-searches/{busca_id}", response_model=dict)
async def atualizar_busca_salva(busca_id: str, busca: SavedSearchUpdate):
    """Atualiza configurações de uma busca salva"""
    pass

@app.delete("/api/saved-searches/{busca_id}")
async def excluir_busca_salva(busca_id: str):
    """Remove uma busca salva"""
    pass

@app.post("/api/saved-searches/{busca_id}/test")
async def testar_busca_salva(busca_id: str):
    """Executa a busca e retorna preview dos resultados"""
    pass
```

---

## Fase 2: Interface de Usuário (DIA 1-2)

### 2.1 Componente React: SavedSearchesManager

```jsx
// /app/frontend/src/components/SavedSearchesManager.js

// Funcionalidades:
// - Modal para salvar busca atual
// - Lista de buscas salvas
// - Editar/Excluir buscas
// - Toggle de notificações
// - Preview de resultados
```

### 2.2 Integração na SearchPage

```jsx
// Adicionar botão "Salvar Busca" após realizar uma busca
// Quando clicado, abre modal para nomear e configurar notificações
```

### 2.3 Nova Página: /alertas

```jsx
// /app/frontend/src/pages/AlertasPage.js

// Dashboard de alertas:
// - Lista de buscas salvas
// - Histórico de notificações
// - Configurações de frequência
// - Estatísticas
```

---

## Fase 3: Sistema de Verificação (DIA 2-3)

### 3.1 Job Scheduler Background

```python
# /app/backend/services/notification_service.py

class NotificationService:
    """
    Serviço que verifica periodicamente as buscas salvas
    e envia notificações quando encontra novas licitações
    """
    
    async def verificar_buscas_salvas(self):
        """Executa todas as buscas salvas e verifica novas licitações"""
        pass
    
    async def verificar_busca(self, busca: SavedSearch) -> List[dict]:
        """Executa uma busca específica e retorna novas licitações"""
        pass
    
    async def enviar_notificacao(self, busca: SavedSearch, novas_licitacoes: List[dict]):
        """Envia notificação ao usuário"""
        pass
```

### 3.2 Scheduler com APScheduler

```python
# /app/backend/scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# Verificar buscas diárias às 8h
@scheduler.scheduled_job('cron', hour=8)
async def verificar_diarias():
    await notification_service.verificar_buscas_por_frequencia("diario")

# Verificar buscas semanais (segunda-feira)
@scheduler.scheduled_job('cron', day_of_week='mon', hour=8)
async def verificar_semanais():
    await notification_service.verificar_buscas_por_frequencia("semanal")
```

---

## Fase 4: Sistema de Notificações (DIA 3-4)

### 4.1 Opções de Notificação

| Tipo | Implementação | Prioridade |
|------|---------------|------------|
| **Dashboard** | Badge + Lista no frontend | P0 - Implementar primeiro |
| **Email** | SendGrid/Resend API | P1 - Após dashboard |
| **Push** | Web Push API | P2 - Futuro |

### 4.2 Modelo de Notificação

```python
class Notification(BaseModel):
    id: str
    user_id: str
    busca_id: str
    tipo: str  # "nova_licitacao", "licitacao_urgente"
    titulo: str
    mensagem: str
    licitacoes: List[str]  # IDs das licitações
    lida: bool = False
    criado_em: datetime
```

---

## Checklist de Implementação

### Dia 1 - Backend
- [ ] Criar modelo `SavedSearch` em `/app/backend/models/saved_search.py`
- [ ] Implementar endpoints CRUD em `server.py`
- [ ] Criar índices MongoDB para `saved_searches`
- [ ] Testar endpoints via curl

### Dia 1-2 - Frontend
- [ ] Criar componente `SavedSearchesManager.js`
- [ ] Adicionar botão "Salvar Busca" na `SearchPage.js`
- [ ] Criar página `/alertas` com dashboard
- [ ] Atualizar Header com link para Alertas

### Dia 2-3 - Scheduler
- [ ] Instalar APScheduler: `pip install apscheduler`
- [ ] Criar `notification_service.py`
- [ ] Implementar lógica de verificação
- [ ] Integrar scheduler no startup do FastAPI

### Dia 3-4 - Notificações
- [ ] Criar modelo `Notification`
- [ ] Implementar notificações no dashboard
- [ ] (Opcional) Integrar SendGrid para email

---

## Dependências a Instalar

```bash
# Backend
pip install apscheduler  # Scheduler para jobs periódicos

# Frontend (se usar notificações push)
yarn add react-toastify  # Toast notifications
```

---

## Notas Importantes

1. **Autenticação**: O sistema atual não tem autenticação. Para MVP, usar `user_id = "default"` ou implementar autenticação simples.

2. **Rate Limiting**: Limitar número de buscas salvas por usuário (ex: máximo 10).

3. **Deduplicação**: Manter lista de `ultimas_licitacoes_ids` para não notificar a mesma licitação duas vezes.

4. **Performance**: Com a API PNCP desbloqueada, cada verificação pode retornar rapidamente. O scheduler deve processar buscas em lotes.

---

## Links Úteis

- Swagger PNCP: https://pncp.gov.br/api/consulta/swagger-ui/index.html
- APScheduler Docs: https://apscheduler.readthedocs.io/
- SendGrid API: https://docs.sendgrid.com/

---

*Documento criado em: 16/12/2025*
*Próxima sessão: Implementar Fase 1 (Backend)*
