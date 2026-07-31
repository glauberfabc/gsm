# Autenticação e Gerenciamento de Usuários — Design

## Contexto

Hoje o GSM (Buscador de Editais) não tem nenhum conceito de usuário: todas as
rotas `/api/*` são abertas, sem autenticação, e o backend usa um
`user_id = "default_user"` fixo em 5 pontos do `server.py` (marcados com
`# TODO: Quando implementar autenticação, usar user_id real`). O frontend é
uma SPA em `App.jsx` com abas locais (`useState('search')`), sem rotas
protegidas.

Este documento cobre a adição de login com dois papéis — `normal` e
`super_admin` — onde o `super_admin` pode criar, editar e deletar outros
logins. Depois desta mudança, o app inteiro passa a exigir login.

## Modelo de dados

Nova collection no MongoDB: `users`, com índice único em `email`.

`backend/models/user.py` (segue a convenção `Xyz`/`XyzCreate`/`XyzUpdate` já
usada em `backend/models/`):

```python
from typing import Literal, Optional
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone

Role = Literal["normal", "super_admin"]

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    password_hash: str
    role: Role = "normal"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserCreate(BaseModel):
    email: str
    password: str
    role: Role = "normal"

class UserUpdate(BaseModel):
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[Role] = None

class UserPublic(BaseModel):
    id: str
    email: str
    role: Role
    created_at: datetime
```

`UserPublic` é o único formato devolvido pela API — `password_hash` nunca sai
do backend.

### Regras de segurança

- Não é permitido deletar nem rebaixar (mudar `role` para `normal`) o
  **último** `super_admin` restante no sistema — evita ficar sem nenhum admin.
- Não é permitido deletar a própria conta logada.
- Login é feito por e-mail (não há campo de username separado).

## Backend

### Bibliotecas

`passlib`, `bcrypt`, `PyJWT` e `python-jose` já estão em
`backend/requirements.txt`, mas não são usados em lugar nenhum hoje. Nenhuma
dependência nova precisa ser adicionada.

### `backend/utils/security.py` (novo)

- `hash_password(password) -> str` / `verify_password(password, hash) -> bool`
  — via passlib (bcrypt).
- `create_access_token(user: User) -> str` — JWT assinado com
  `JWT_SECRET_KEY`, payload `{sub: user.id, role: user.role, exp}`, expiração
  de 7 dias.
- `decode_access_token(token) -> dict` — decodifica e valida assinatura/exp.
- `get_current_user` (FastAPI dependency) — lê `Authorization: Bearer <token>`,
  decodifica, busca o usuário no Mongo por `id`, injeta no request. Levanta
  `HTTPException(401)` se token ausente, inválido, expirado, ou usuário não
  existe mais.
- `require_super_admin` (FastAPI dependency) — depende de `get_current_user`;
  levanta `HTTPException(403)` se `role != "super_admin"`.

Variável nova em `backend/.env`: `JWT_SECRET_KEY` (valor aleatório gerado na
implementação).

### `backend/routers/auth_router.py` (novo)

Router **sem** proteção global (incluído separadamente, sem dependency no
`include_router`):

- `POST /api/auth/login` — body `{email, password}` → `401` se credenciais
  inválidas, senão `{access_token, token_type: "bearer", user: UserPublic}`.
- `GET /api/auth/me` — `Depends(get_current_user)` na própria rota → devolve
  `UserPublic` do usuário logado. Usado pelo frontend para validar o token
  salvo ao carregar a página.

### `backend/routers/users_router.py` (novo)

Incluído com `dependencies=[Depends(require_super_admin)]` no
`app.include_router(...)` — protege as 4 rotas de uma vez, sem precisar
repetir a dependency em cada função:

- `GET /api/users` — lista todos os usuários (`UserPublic[]`).
- `POST /api/users` — cria usuário (`UserCreate` → `UserPublic`, `409` se
  e-mail já existe).
- `PUT /api/users/{id}` — edita e-mail/senha/papel (`UserUpdate` →
  `UserPublic`). `400` se violar a regra do último super_admin.
- `DELETE /api/users/{id}` — deleta. `400` se for a própria conta logada ou o
  último super_admin.

### Proteger o restante do app

Em `server.py`, a linha:

```python
app.include_router(api_router)
```

vira:

```python
app.include_router(api_router, dependencies=[Depends(get_current_user)])
```

Isso exige um JWT válido em **todas** as ~50 rotas já existentes em
`api_router`, numa única mudança — sem editar nenhuma das funções de rota
atuais.

`auth_router` e `users_router` são incluídos separadamente (não fazem parte
de `api_router`), com suas próprias regras de proteção descritas acima.

### Consistência com o código existente

Os 5 pontos em `server.py` com `user_id = "default_user"` (TODO de
autenticação) passam a receber `current_user: User = Depends(get_current_user)`
como parâmetro e usar `current_user.id` no lugar do valor fixo.

## Script de bootstrap (`backend/scripts/create_admin.py`)

Script standalone, rodado manualmente na VPS (`python -m
backend.scripts.create_admin`):

1. Carrega `MONGO_URL`/`DB_NAME` do `.env` (mesma config do resto do app).
2. Pede e-mail e senha via `input()`/`getpass()`.
3. Se já existe usuário com esse e-mail, avisa e cancela.
4. Cria o usuário com `role="super_admin"`, senha com hash.

Não há criação automática de admin no boot do backend — só via este script,
rodado manualmente uma vez.

## Frontend

### `frontend/src/context/AuthContext.jsx` (novo)

- Estado: `token`, `user`, `loading`.
- Ao montar: lê `token` do `localStorage`; se existir, seta
  `axios.defaults.headers.common['Authorization'] = 'Bearer ' + token'` e
  valida batendo em `GET /api/auth/me` (limpa tudo e desloga se falhar).
- `login(email, password)`: chama `POST /api/auth/login`, salva token no
  `localStorage`, seta o header global do axios, guarda `user` no estado.
- `logout()`: limpa `localStorage`, remove o header do axios, zera `user`.
- Registra `axios.interceptors.response.use(...)` uma única vez: qualquer
  resposta `401` de qualquer chamada dispara `logout()` automaticamente.

Como as 21 chamadas existentes em hooks/páginas fazem `import axios from
'axios'` direto (mesmo módulo singleton, sem instância própria configurada),
setar o header em `axios.defaults` é suficiente para autenticar todas elas —
nenhum desses 21 arquivos precisa ser editado.

### `frontend/src/components/Login.jsx` (novo)

Formulário simples: e-mail, senha, botão "Entrar". Mostra erro se
`login()` falhar (credenciais inválidas).

### `frontend/src/App.jsx`

Envolve a árvore atual com `AuthProvider`. Se `!user`, renderiza só
`<Login/>`. Se `user`, renderiza a estrutura de abas já existente, sem
mudanças na lógica atual de abas.

### Nova aba "Usuários"

Segue o padrão de `frontend/src/components/tabs/*Tab.jsx` (mesma estrutura
das abas existentes como `ListasTab.jsx`). Só aparece na lista de abas quando
`user.role === 'super_admin'`. Conteúdo: tabela com os usuários (e-mail,
papel, data de criação) + formulário de criar (e-mail, senha, papel) +
ações de editar/deletar por linha, com confirmação antes de deletar.

### Logout

Botão "Sair" visível no layout (mesma área onde ficam as outras
configurações/abas), chama `logout()` do `AuthContext`.

## Fora de escopo (não incluído neste design)

- Recuperação de senha / "esqueci minha senha".
- Refresh token / renovação automática de sessão (expira em 7 dias, usuário
  faz login de novo).
- Auditoria/log de quem criou/editou/deletou cada usuário.
- Qualquer diferença de funcionalidade entre `normal` e `super_admin` além do
  gerenciamento de usuários — ambos os papéis usam o resto do app
  (busca, listas, radares etc.) da mesma forma.
