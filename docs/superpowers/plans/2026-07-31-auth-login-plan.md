# Login com Super Admin / Usuário Normal — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add login (JWT) with two roles — `normal` and `super_admin` — where `super_admin` can create, edit, and delete other logins, and the whole app requires authentication.

**Architecture:** New `User` model + `users` MongoDB collection. Two new FastAPI routers (`auth_router` for login/me, `users_router` for CRUD, both include-time-protected) plus a one-line change that adds `Depends(get_current_user)` to the existing `api_router` include, protecting all ~50 existing routes without touching their code. Frontend gets an `AuthContext` that configures a global `axios` default header so all 21 existing call sites get the token for free, a `Login` screen, and a new "Usuários" tab visible only to `super_admin`.

**Tech Stack:** FastAPI 0.110, Pydantic v2, Motor/PyMongo, PyJWT, passlib+bcrypt (all already in `backend/requirements.txt`, unused until now), React 18 + axios + react-router-dom (frontend, already installed).

**Known gotcha:** `passlib==1.7.4` + `bcrypt==4.1.3` (both already pinned) have a known compatibility wrinkle in some environments (`AttributeError: module 'bcrypt' has no attribute '__about__'`). Task 3's test will surface this immediately if it happens — if it does, pin `bcrypt<4.1` in `backend/requirements.txt` and reinstall.

**Testing approach:** This codebase's existing backend tests (`backend/tests/test_*.py`) are integration tests that hit a **live running server** via `requests`, not `TestClient` — there's no `conftest.py` or fixture infra today. This plan follows that convention for anything that needs the database/server, and adds one new `backend/tests/conftest.py` (fixtures scoped only to the new test files that request them — nothing autouse, so existing tests are untouched). Pure logic (Pydantic models, password hashing, JWT) gets plain pytest unit tests with no server/DB needed. The frontend has no test runner wired up (`craco test` exists but zero test files exist anywhere in `frontend/src`) — frontend tasks use manual browser verification instead of introducing new test infra, which would be out of scope for this feature.

---

## Task 1: Local dev environment — MongoDB + JWT secret

**Files:**
- Modify: `backend/.env`

No code yet — this unblocks every later task that needs a running Mongo + backend.

- [ ] **Step 1: Start a local MongoDB via Docker (skip if `docker ps` already shows one on port 27017)**

Run: `docker run -d -p 27017:27017 --name gsm-mongo mongo`
Expected: prints a container ID. If a container named `gsm-mongo` already exists, run `docker start gsm-mongo` instead.

- [ ] **Step 2: Verify Mongo is reachable**

Run (PowerShell): `Test-NetConnection -ComputerName localhost -Port 27017 -InformationLevel Quiet`
Expected: `True`

- [ ] **Step 3: Generate a JWT secret and add it to `backend/.env`**

Run: `python -c "import secrets; print(secrets.token_hex(32))"`
Copy the printed value. Add this line to `backend/.env` (create the file if you deleted it; current content must stay intact):

```
JWT_SECRET_KEY=<paste the generated value here>
```

`backend/.env` should now look like:

```
MONGO_URL=mongodb://localhost:27017
DB_NAME=gsm_db
REACT_APP_BACKEND_URL=http://localhost:8000
PORT=8000
JWT_SECRET_KEY=<the generated value>
```

- [ ] **Step 4: Commit**

`.env` is not tracked by git in this repo (verify with `git check-ignore backend/.env` — if it prints the path, it's ignored, nothing to commit). If it's NOT ignored, do not commit a real secret — instead confirm with the user before proceeding. Assuming it's ignored (typical), there is nothing to commit for this task; continue to Task 2.

---

## Task 2: `User` Pydantic models

**Files:**
- Create: `backend/models/user.py`
- Test: `backend/tests/test_user_models.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_user_models.py
"""
Testes puros do modelo Pydantic de usuario (backend/models/user.py).
Nao precisam de servidor rodando nem de MongoDB.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from pydantic import ValidationError

from models.user import User, UserCreate, UserUpdate, UserPublic


def test_user_create_requires_email_and_password():
    user_create = UserCreate(email="admin@gsm.com", password="senha123")
    assert user_create.email == "admin@gsm.com"
    assert user_create.password == "senha123"
    assert user_create.role == "normal"


def test_user_create_rejects_invalid_role():
    with pytest.raises(ValidationError):
        UserCreate(email="a@b.com", password="x", role="gerente")


def test_user_create_accepts_super_admin_role():
    user_create = UserCreate(email="admin@gsm.com", password="senha123", role="super_admin")
    assert user_create.role == "super_admin"


def test_user_update_all_fields_optional():
    update = UserUpdate()
    assert update.email is None
    assert update.password is None
    assert update.role is None


def test_user_public_has_no_password_hash_field():
    assert "password_hash" not in UserPublic.model_fields


def test_user_generates_id_and_timestamps_automatically():
    user = User(email="a@b.com", password_hash="hashed")
    assert user.id
    assert user.created_at is not None
    assert user.updated_at is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run (from project root, venv active): `.\.venv\Scripts\python.exe -m pytest backend/tests/test_user_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'models.user'`

- [ ] **Step 3: Write the model**

```python
# backend/models/user.py
from datetime import datetime, timezone
from typing import Literal, Optional
import uuid

from pydantic import BaseModel, Field

Role = Literal["normal", "super_admin"]


class User(BaseModel):
    """Documento de usuario armazenado na collection `users`."""
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
    """Formato devolvido pela API — nunca inclui password_hash."""
    id: str
    email: str
    role: Role
    created_at: datetime
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_user_models.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/models/user.py backend/tests/test_user_models.py
git commit -m "feat: adicionar modelo User (id, email, role, password_hash)"
```

---

## Task 3: Password hashing utilities

**Files:**
- Create: `backend/utils/security.py`
- Test: `backend/tests/test_security_utils.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_security_utils.py
"""
Testes puros de hashing de senha e JWT (backend/utils/security.py).
Nao precisam de servidor rodando; precisam apenas de JWT_SECRET_KEY
no backend/.env (ver Task 1).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from utils.security import hash_password, verify_password


def test_hash_password_returns_different_string_than_input():
    hashed = hash_password("minhasenha123")
    assert hashed != "minhasenha123"
    assert len(hashed) > 20


def test_verify_password_accepts_correct_password():
    hashed = hash_password("minhasenha123")
    assert verify_password("minhasenha123", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("minhasenha123")
    assert verify_password("senhaerrada", hashed) is False


def test_hash_password_is_salted_differently_each_time():
    hash1 = hash_password("minhasenha123")
    hash2 = hash_password("minhasenha123")
    assert hash1 != hash2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_security_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'utils.security'`

- [ ] **Step 3: Write the password hashing functions**

```python
# backend/utils/security.py
"""
Utilitarios de autenticacao: hash de senha, JWT, e FastAPI dependencies
(get_current_user, require_super_admin) usadas para proteger rotas.
"""
import os
from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return _pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _pwd_context.verify(password, password_hash)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_security_utils.py -v`
Expected: `4 passed`

If you instead see `AttributeError: module 'bcrypt' has no attribute '__about__'`, that's the known passlib/bcrypt version wrinkle noted in the plan header — run `.\.venv\Scripts\python.exe -m pip install "bcrypt<4.1"` and re-run the test.

- [ ] **Step 5: Commit**

```bash
git add backend/utils/security.py backend/tests/test_security_utils.py
git commit -m "feat: adicionar hashing de senha (bcrypt via passlib)"
```

---

## Task 4: JWT create/decode

**Files:**
- Modify: `backend/utils/security.py`
- Test: `backend/tests/test_security_utils.py`

- [ ] **Step 1: Add failing tests to the same test file**

Append to `backend/tests/test_security_utils.py`:

```python
import pytest
import jwt as pyjwt
from models.user import User
from utils.security import create_access_token, decode_access_token


def _sample_user():
    return User(id="user-123", email="a@b.com", password_hash="hashed", role="normal")


def test_create_access_token_can_be_decoded_back():
    user = _sample_user()
    token = create_access_token(user)
    payload = decode_access_token(token)
    assert payload["sub"] == "user-123"
    assert payload["role"] == "normal"


def test_decode_access_token_rejects_garbage_token():
    with pytest.raises(pyjwt.PyJWTError):
        decode_access_token("isso-nao-e-um-jwt-valido")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_security_utils.py -v`
Expected: FAIL with `ImportError: cannot import name 'create_access_token' from 'utils.security'`

- [ ] **Step 3: Implement JWT create/decode**

Append to `backend/utils/security.py`:

```python
import jwt

from models.user import User

JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_DAYS = 7


def _get_secret_key() -> str:
    # Lido dentro da funcao (nao no import do modulo) para nao depender
    # da ordem de load_dotenv() em relacao a este import, igual ao resto
    # do backend/server.py.
    return os.environ["JWT_SECRET_KEY"]


def create_access_token(user: User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRATION_DAYS)
    payload = {"sub": user.id, "role": user.role, "exp": expire}
    return jwt.encode(payload, _get_secret_key(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, _get_secret_key(), algorithms=[JWT_ALGORITHM])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_security_utils.py -v`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add backend/utils/security.py backend/tests/test_security_utils.py
git commit -m "feat: adicionar criacao/decodificacao de JWT (expira em 7 dias)"
```

---

## Task 5: Shared test fixtures (`conftest.py`)

**Files:**
- Create: `backend/tests/conftest.py`

No test to write here — this file provides fixtures the next tasks' integration tests will use. It touches MongoDB directly (bypassing the API) so tests can set up scenarios like "a super_admin already exists" without a chicken-and-egg problem.

- [ ] **Step 1: Write the fixtures file**

```python
# backend/tests/conftest.py
"""
Fixtures compartilhadas pelos testes de autenticacao/usuarios.
Usa pymongo (sincrono) direto na collection `users`, sem depender da API,
para poder montar cenarios que a propria API protege (ex: criar o primeiro
super_admin nao tem endpoint publico).

So afeta os testes que pedem essas fixtures explicitamente (nada autouse) -
os testes existentes em backend/tests/ continuam intocados.
"""
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent.parent / '.env')

from utils.security import hash_password  # noqa: E402

MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']


@pytest.fixture
def mongo_db():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    client.close()


@pytest.fixture
def clean_users(mongo_db):
    """Limpa a collection users antes e depois do teste que a solicitar."""
    mongo_db.users.delete_many({})
    yield
    mongo_db.users.delete_many({})


def create_test_user(mongo_db, email, password, role="normal"):
    """Insere um usuario de teste direto no Mongo (sem passar pela API)."""
    doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    mongo_db.users.insert_one(doc)
    return doc
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend/tests'); import conftest; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: adicionar fixtures de mongo para testes de auth/usuarios"
```

---

## Task 6: Auth dependencies + `/api/auth/login` + `/api/auth/me`

**Files:**
- Modify: `backend/utils/security.py`
- Create: `backend/routers/auth_router.py`
- Modify: `backend/server.py`
- Test: `backend/tests/test_auth_router.py`

This task requires the local backend server running (Task 1's Mongo must be up). Keep a terminal open with:
`.\.venv\Scripts\python.exe -m uvicorn backend.server:app --host 127.0.0.1 --port 8000 --reload`
(run from project root, per `GUIA_INICIALIZACAO.md`). `--reload` picks up the code changes in this task automatically; if a test fails right after saving a file, wait ~2s for the reload log line and re-run.

- [ ] **Step 1: Write the failing integration tests**

```python
# backend/tests/test_auth_router.py
"""
Testes de integracao para /api/auth/login e /api/auth/me.
Requerem o backend local rodando (uvicorn) e MongoDB acessivel.
"""
import os
import requests

from conftest import create_test_user

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://127.0.0.1:8000').rstrip('/')


def test_login_with_valid_credentials_returns_token(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")

    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@gsm.com",
        "password": "senha123",
    })

    assert response.status_code == 200, response.text
    data = response.json()
    assert "access_token" in data
    assert data["user"]["email"] == "admin@gsm.com"
    assert data["user"]["role"] == "super_admin"
    assert "password_hash" not in data["user"]


def test_login_with_wrong_password_returns_401(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123")

    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@gsm.com",
        "password": "senhaerrada",
    })

    assert response.status_code == 401


def test_login_with_unknown_email_returns_401(clean_users):
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "naoexiste@gsm.com",
        "password": "qualquer",
    })

    assert response.status_code == 401


def test_me_with_valid_token_returns_user(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123")
    login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "admin@gsm.com",
        "password": "senha123",
    })
    token = login_resp.json()["access_token"]

    response = requests.get(f"{BASE_URL}/api/auth/me", headers={
        "Authorization": f"Bearer {token}"
    })

    assert response.status_code == 200, response.text
    assert response.json()["email"] == "admin@gsm.com"


def test_me_without_token_returns_401(clean_users):
    response = requests.get(f"{BASE_URL}/api/auth/me")
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_auth_router.py -v`
Expected: FAIL with connection errors or 404s (`/api/auth/login` doesn't exist yet)

- [ ] **Step 3: Add `get_current_user` dependency to `security.py`**

Append to `backend/utils/security.py`:

```python
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token nao fornecido")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido ou expirado")

    db = request.app.state.db
    user_doc = await db.users.find_one({"id": payload.get("sub")}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario nao encontrado")

    return User(**user_doc)


async def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "super_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso restrito a super admin")
    return current_user
```

(`request.app.state.db` is set in Step 5 below — this avoids a circular import between `security.py` and `server.py`, matching how the rest of the codebase passes `db` around explicitly instead of importing the `server` module.)

- [ ] **Step 4: Create the auth router**

```python
# backend/routers/auth_router.py
"""
Rotas de autenticacao: login e dados do usuario logado.
Este router NAO tem protecao global - POST /login precisa ser publico
(GET /me se protege sozinha via Depends(get_current_user) na propria rota).
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from models.user import User, UserPublic
from utils.security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, request: Request):
    db = request.app.state.db
    user_doc = await db.users.find_one({"email": payload.email}, {"_id": 0})
    if not user_doc or not verify_password(payload.password, user_doc["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email ou senha invalidos")

    user = User(**user_doc)
    token = create_access_token(user)
    return LoginResponse(access_token=token, user=UserPublic(**user.model_dump()))


@router.get("/me", response_model=UserPublic)
async def me(current_user: User = Depends(get_current_user)):
    return UserPublic(**current_user.model_dump())
```

- [ ] **Step 5: Wire into `server.py`**

In `backend/server.py`, change line 1's import to add `Depends`:

```python
from fastapi import FastAPI, APIRouter, HTTPException, Query, File, UploadFile, Form, BackgroundTasks, Depends
```

After line 66 (`from services.email_service import get_email_service`), add:

```python
from models.user import User
from utils.security import get_current_user
from routers.auth_router import router as auth_router
```

After the line `app = FastAPI(title="BEM - Buscador Estadual de Medicamentos")` (line 77), add:

```python
app.state.db = db
```

After the line `app.include_router(api_router)` (line 6333), add:

```python
app.include_router(auth_router)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_auth_router.py -v`
Expected: `5 passed`

- [ ] **Step 7: Commit**

```bash
git add backend/utils/security.py backend/routers/auth_router.py backend/server.py backend/tests/test_auth_router.py
git commit -m "feat: adicionar POST /api/auth/login e GET /api/auth/me"
```

---

## Task 7: `/api/users` CRUD (super_admin only)

**Files:**
- Create: `backend/routers/users_router.py`
- Modify: `backend/server.py`
- Test: `backend/tests/test_users_router.py`

Keep the local server running with `--reload` as in Task 6.

- [ ] **Step 1: Write the failing integration tests**

```python
# backend/tests/test_users_router.py
"""
Testes de integracao para /api/users (CRUD, exclusivo super_admin).
Requerem o backend local rodando e MongoDB acessivel.
"""
import os
import requests

from conftest import create_test_user

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://127.0.0.1:8000').rstrip('/')


def _login(email, password):
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password})
    return resp.json()["access_token"]


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_normal_user_cannot_list_users(clean_users, mongo_db):
    create_test_user(mongo_db, "user@gsm.com", "senha123", role="normal")
    token = _login("user@gsm.com", "senha123")

    response = requests.get(f"{BASE_URL}/api/users", headers=_auth_headers(token))

    assert response.status_code == 403


def test_super_admin_can_create_and_list_users(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")
    token = _login("admin@gsm.com", "senha123")

    create_resp = requests.post(f"{BASE_URL}/api/users", headers=_auth_headers(token), json={
        "email": "novo@gsm.com",
        "password": "outrasenha",
        "role": "normal",
    })
    assert create_resp.status_code == 201, create_resp.text
    assert create_resp.json()["email"] == "novo@gsm.com"
    assert "password_hash" not in create_resp.json()

    list_resp = requests.get(f"{BASE_URL}/api/users", headers=_auth_headers(token))
    emails = [u["email"] for u in list_resp.json()]
    assert "admin@gsm.com" in emails
    assert "novo@gsm.com" in emails


def test_creating_duplicate_email_returns_409(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")
    token = _login("admin@gsm.com", "senha123")

    requests.post(f"{BASE_URL}/api/users", headers=_auth_headers(token), json={
        "email": "dup@gsm.com", "password": "x", "role": "normal"
    })
    response = requests.post(f"{BASE_URL}/api/users", headers=_auth_headers(token), json={
        "email": "dup@gsm.com", "password": "y", "role": "normal"
    })

    assert response.status_code == 409


def test_super_admin_can_edit_user_role(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")
    other = create_test_user(mongo_db, "outro@gsm.com", "senha123", role="normal")
    token = _login("admin@gsm.com", "senha123")

    response = requests.put(f"{BASE_URL}/api/users/{other['id']}", headers=_auth_headers(token), json={
        "role": "super_admin"
    })

    assert response.status_code == 200, response.text
    assert response.json()["role"] == "super_admin"


def test_cannot_delete_own_account(clean_users, mongo_db):
    admin = create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")
    token = _login("admin@gsm.com", "senha123")

    response = requests.delete(f"{BASE_URL}/api/users/{admin['id']}", headers=_auth_headers(token))

    assert response.status_code == 400


def test_cannot_demote_last_super_admin(clean_users, mongo_db):
    admin = create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")
    other_admin = create_test_user(mongo_db, "admin2@gsm.com", "senha123", role="super_admin")
    token_admin2 = _login("admin2@gsm.com", "senha123")

    # admin2 deleta o admin original - ainda sobra admin2, deve funcionar
    ok_resp = requests.delete(f"{BASE_URL}/api/users/{admin['id']}", headers=_auth_headers(token_admin2))
    assert ok_resp.status_code == 204

    # agora so sobra admin2 - rebaixar o unico super_admin restante deve falhar
    demote_resp = requests.put(f"{BASE_URL}/api/users/{other_admin['id']}", headers=_auth_headers(token_admin2), json={
        "role": "normal"
    })
    assert demote_resp.status_code == 400


def test_can_delete_normal_user(clean_users, mongo_db):
    create_test_user(mongo_db, "admin@gsm.com", "senha123", role="super_admin")
    normal = create_test_user(mongo_db, "user@gsm.com", "senha123", role="normal")
    token = _login("admin@gsm.com", "senha123")

    response = requests.delete(f"{BASE_URL}/api/users/{normal['id']}", headers=_auth_headers(token))

    assert response.status_code == 204
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_users_router.py -v`
Expected: FAIL (404s, `/api/users` doesn't exist yet)

- [ ] **Step 3: Create the users router**

```python
# backend/routers/users_router.py
"""
Rotas de gerenciamento de usuarios - exclusivas do super_admin.
Protegidas em bloco via dependencies=[Depends(require_super_admin)]
no app.include_router() (ver backend/server.py).
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status

from models.user import User, UserCreate, UserPublic, UserUpdate
from utils.security import get_current_user, hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


async def _count_super_admins(db) -> int:
    return await db.users.count_documents({"role": "super_admin"})


@router.get("", response_model=List[UserPublic])
async def listar_usuarios(request: Request):
    db = request.app.state.db
    docs = await db.users.find({}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    return [UserPublic(**d) for d in docs]


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def criar_usuario(payload: UserCreate, request: Request):
    db = request.app.state.db
    existing = await db.users.find_one({"email": payload.email})
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Ja existe um usuario com esse email")

    user = User(email=payload.email, password_hash=hash_password(payload.password), role=payload.role)
    doc = user.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    doc["updated_at"] = doc["updated_at"].isoformat()
    await db.users.insert_one(doc)
    return UserPublic(**user.model_dump())


@router.put("/{user_id}", response_model=UserPublic)
async def editar_usuario(user_id: str, payload: UserUpdate, request: Request):
    db = request.app.state.db
    existing = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    updates = {}
    if payload.email is not None:
        updates["email"] = payload.email
    if payload.password is not None:
        updates["password_hash"] = hash_password(payload.password)
    if payload.role is not None:
        if existing["role"] == "super_admin" and payload.role != "super_admin":
            if await _count_super_admins(db) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Nao e possivel rebaixar o ultimo super admin",
                )
        updates["role"] = payload.role

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        await db.users.update_one({"id": user_id}, {"$set": updates})

    updated = await db.users.find_one({"id": user_id}, {"_id": 0})
    return UserPublic(**updated)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_usuario(user_id: str, request: Request, current_user: User = Depends(get_current_user)):
    if user_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nao e possivel deletar a propria conta")

    db = request.app.state.db
    existing = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario nao encontrado")

    if existing["role"] == "super_admin" and await _count_super_admins(db) <= 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nao e possivel deletar o ultimo super admin")

    await db.users.delete_one({"id": user_id})
```

- [ ] **Step 4: Wire into `server.py`**

After the `from routers.auth_router import router as auth_router` line added in Task 6, add:

```python
from utils.security import require_super_admin
from routers.users_router import router as users_router
```

(Combine with the existing `from utils.security import get_current_user` line instead of duplicating the import if you prefer — either works.)

After the `app.include_router(auth_router)` line added in Task 6, add:

```python
app.include_router(users_router, dependencies=[Depends(require_super_admin)])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_users_router.py -v`
Expected: `7 passed`

- [ ] **Step 6: Commit**

```bash
git add backend/routers/users_router.py backend/server.py backend/tests/test_users_router.py
git commit -m "feat: adicionar CRUD de usuarios em /api/users (exclusivo super_admin)"
```

---

## Task 8: Protect the entire existing API + clean up the `default_user` TODOs

**Files:**
- Modify: `backend/server.py:121` (function signature of `criar_lista`), `backend/server.py:6333` (or wherever it landed after Task 6/7 edits — search for `app.include_router(api_router)`)
- Test: `backend/tests/test_protected_routes.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_protected_routes.py
"""
Confirma que as ~50 rotas existentes do api_router agora exigem
autenticacao, e que continuam funcionando normalmente com um token valido.
"""
import os
import requests

from conftest import create_test_user

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'http://127.0.0.1:8000').rstrip('/')


def test_listas_without_token_returns_401(clean_users):
    response = requests.get(f"{BASE_URL}/api/listas")
    assert response.status_code == 401


def test_listas_with_valid_token_returns_200(clean_users, mongo_db):
    create_test_user(mongo_db, "user@gsm.com", "senha123", role="normal")
    login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "user@gsm.com", "password": "senha123"
    })
    token = login_resp.json()["access_token"]

    response = requests.get(f"{BASE_URL}/api/listas", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_protected_routes.py -v`
Expected: FAIL on `test_listas_without_token_returns_401` (currently returns 200, not 401 — the route is still open)

- [ ] **Step 3: Protect `api_router` globally**

In `backend/server.py`, find the line `app.include_router(api_router)` and change it to:

```python
app.include_router(api_router, dependencies=[Depends(get_current_user)])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_protected_routes.py -v`
Expected: `2 passed`

- [ ] **Step 5: Clean up the two `default_user` TODOs**

In `backend/server.py`, find `criar_lista` (around line 120-129):

```python
@api_router.post("/listas", response_model=dict, status_code=201)
async def criar_lista(lista: ListaMedicamentosCreate):
    """
    Cria uma nova lista customizada de medicamentos

    Limite: Máximo 5 listas por usuário
    """
    try:
        # TODO: Quando implementar autenticação, usar user_id real
        user_id = "default_user"
```

Replace with:

```python
@api_router.post("/listas", response_model=dict, status_code=201)
async def criar_lista(lista: ListaMedicamentosCreate, current_user: User = Depends(get_current_user)):
    """
    Cria uma nova lista customizada de medicamentos

    Limite: Máximo 5 listas por usuário
    """
    try:
        user_id = current_user.id
```

Find `listar_listas` (around line 183-190):

```python
@api_router.get("/listas", response_model=dict)
async def listar_listas():
    """
    Lista todas as listas customizadas do usuário
    """
    try:
        # TODO: Quando implementar autenticação, usar user_id real
        user_id = "default_user"
```

Replace with:

```python
@api_router.get("/listas", response_model=dict)
async def listar_listas(current_user: User = Depends(get_current_user)):
    """
    Lista todas as listas customizadas do usuário
    """
    try:
        user_id = current_user.id
```

- [ ] **Step 6: Run the full auth test suite to confirm nothing broke**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_user_models.py backend/tests/test_security_utils.py backend/tests/test_auth_router.py backend/tests/test_users_router.py backend/tests/test_protected_routes.py -v`
Expected: all passed (24 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/server.py backend/tests/test_protected_routes.py
git commit -m "feat: proteger todas as rotas existentes com login + usar current_user.id real em listas"
```

---

## Task 9: Bootstrap script for the first super admin

**Files:**
- Create: `backend/scripts/create_admin.py`

No automated test (it's an interactive script) — manual verification steps included.

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
# backend/scripts/create_admin.py
"""
Cria o primeiro super_admin do sistema. Rodar manualmente uma unica vez
(na VPS ou localmente), a partir da raiz do projeto:
    .\.venv\Scripts\python.exe -m backend.scripts.create_admin
"""
import asyncio
import getpass
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

from utils.security import hash_password

load_dotenv(Path(__file__).parent.parent / '.env')


async def create_admin():
    mongo_url = os.environ['MONGO_URL']
    db_name = os.environ['DB_NAME']
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Garante o indice unico em email (idempotente - so precisa rodar uma vez,
    # mas nao ha problema em chamar de novo a cada execucao do script).
    await db.users.create_index("email", unique=True)

    email = input("Email do super admin: ").strip()
    existing = await db.users.find_one({"email": email})
    if existing:
        print(f"Ja existe um usuario com o email {email}. Cancelando.")
        client.close()
        return

    password = getpass.getpass("Senha: ")
    password_confirm = getpass.getpass("Confirme a senha: ")
    if password != password_confirm:
        print("As senhas nao conferem. Cancelando.")
        client.close()
        return

    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(password),
        "role": "super_admin",
        "created_at": now,
        "updated_at": now,
    }
    await db.users.insert_one(doc)
    print(f"Super admin '{email}' criado com sucesso.")
    client.close()


if __name__ == '__main__':
    asyncio.run(create_admin())
```

- [ ] **Step 2: Run it manually and verify**

Run (from project root): `.\.venv\Scripts\python.exe -m backend.scripts.create_admin`
Enter an email (e.g. `voce@gsm.com`) and a password twice.
Expected: `Super admin 'voce@gsm.com' criado com sucesso.`

Then verify login works:

Run: `.\.venv\Scripts\python.exe -c "import requests; r = requests.post('http://127.0.0.1:8000/api/auth/login', json={'email': 'voce@gsm.com', 'password': '<a senha que voce digitou>'}); print(r.status_code, r.json())"`
Expected: `200 {'access_token': '...', 'token_type': 'bearer', 'user': {...'role': 'super_admin'...}}`

- [ ] **Step 3: Commit**

```bash
git add backend/scripts/create_admin.py
git commit -m "feat: adicionar script de bootstrap do primeiro super admin"
```

---

## Task 10: Frontend `AuthContext`

**Files:**
- Create: `frontend/src/context/AuthContext.jsx`

No automated test (no frontend test runner is wired up in this repo — see plan header). Manual verification happens at the end of Task 12.

- [ ] **Step 1: Write the context**

```jsx
// frontend/src/context/AuthContext.jsx
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
const TOKEN_KEY = 'gsm_auth_token';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const applyToken = useCallback((token) => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      delete axios.defaults.headers.common['Authorization'];
      localStorage.removeItem(TOKEN_KEY);
    }
  }, []);

  const logout = useCallback(() => {
    applyToken(null);
    setUser(null);
  }, [applyToken]);

  useEffect(() => {
    const interceptorId = axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response && error.response.status === 401) {
          logout();
        }
        return Promise.reject(error);
      }
    );
    return () => axios.interceptors.response.eject(interceptorId);
  }, [logout]);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setLoading(false);
      return;
    }
    applyToken(token);
    axios
      .get(`${API}/auth/me`)
      .then((res) => setUser(res.data))
      .catch(() => applyToken(null))
      .finally(() => setLoading(false));
  }, [applyToken]);

  const login = useCallback(
    async (email, password) => {
      const res = await axios.post(`${API}/auth/login`, { email, password });
      applyToken(res.data.access_token);
      setUser(res.data.user);
    },
    [applyToken]
  );

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth deve ser usado dentro de AuthProvider');
  return ctx;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/context/AuthContext.jsx
git commit -m "feat: adicionar AuthContext (token global no axios, login/logout)"
```

---

## Task 11: `Login` component

**Files:**
- Create: `frontend/src/components/Login.jsx`

- [ ] **Step 1: Write the component**

```jsx
// frontend/src/components/Login.jsx
import React, { useState } from 'react';
import { LogIn, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await login(email, password);
    } catch (err) {
      setError('Email ou senha invalidos');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center px-4">
      <form
        onSubmit={handleSubmit}
        className="bg-white p-10 rounded-2xl shadow-2xl border border-slate-200 w-full max-w-md space-y-6"
        data-testid="login-form"
      >
        <h1 className="text-2xl font-black text-slate-800 uppercase text-center">GSM Intelligence</h1>

        <div className="space-y-2">
          <label className="text-xs font-black text-slate-500 uppercase">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-blue-400"
            data-testid="login-email"
          />
        </div>

        <div className="space-y-2">
          <label className="text-xs font-black text-slate-500 uppercase">Senha</label>
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-blue-400"
            data-testid="login-password"
          />
        </div>

        {error && <p className="text-red-600 text-sm font-bold" data-testid="login-error">{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full bg-blue-600 text-white py-3 rounded-xl font-black uppercase flex items-center justify-center gap-2 hover:bg-blue-700 disabled:opacity-50"
          data-testid="login-submit"
        >
          {submitting ? <Loader2 className="animate-spin" size={18} /> : <LogIn size={18} />}
          Entrar
        </button>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/Login.jsx
git commit -m "feat: adicionar tela de Login"
```

---

## Task 12: Wire `AuthProvider` + `Login` into `App.jsx`

**Files:**
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Add imports**

At the top of `frontend/src/App.jsx`, after the existing `import { Loader2 } from 'lucide-react';` line, add:

```jsx
import { AuthProvider, useAuth } from './context/AuthContext';
import { Login } from './components/Login';
```

- [ ] **Step 2: Get `user`/`logout` inside `AppContent` and pass to `Header`**

In `AppContent()`, right after `const [activeTab, setActiveTab] = useState('search');`, add:

```jsx
  const { user, logout } = useAuth();
```

Change the `<Header ... />` call to also pass `user` and `onLogout`:

```jsx
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onAnvisaLoad={anvisa.carregarAnvisa}
        notificacoes={notificacoesHook}
        user={user}
        onLogout={logout}
      />
```

- [ ] **Step 3: Add the auth gate and wrap with `AuthProvider`**

Replace the final block of the file:

```jsx
export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </ErrorBoundary>
  );
}
```

with:

```jsx
function AuthGate() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-100">
        <Loader2 className="animate-spin text-blue-500" size={48} />
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  return <AppContent />;
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <AuthGate />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
```

- [ ] **Step 4: Manual verification**

With the backend running (Task 6-9 done, at least one super_admin created via Task 9's script) and Mongo up, run:

```
cd frontend
npm start
```

Open `http://localhost:3000`. Expected: you see the Login screen (not the app). Log in with the super_admin credentials from Task 9. Expected: the normal app UI appears (search tab etc.), and if you open browser dev tools → Application → Local Storage, you see a `gsm_auth_token` key.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat: exigir login para acessar o app (AuthProvider + AuthGate)"
```

---

## Task 13: `Header` — "Usuários" tab (super_admin only) + logout button

**Files:**
- Modify: `frontend/src/components/layout/Header.jsx`

- [ ] **Step 1: Add icons and accept new props**

Change the lucide-react import line to add `Users` and `LogOut`:

```jsx
import { Search, ListChecks, Radar, TrendingUp, Pill, Zap, Settings, ShieldCheck, BriefcaseBusiness, Target, Bell, Activity, Users, LogOut } from 'lucide-react';
```

Change the function signature:

```jsx
export default function Header({ activeTab: propsActiveTab, setActiveTab: propsSetActiveTab, onAnvisaLoad, notificacoes, user, onLogout }) {
```

- [ ] **Step 2: Compute the tab list conditionally**

Right after the line `const activeTab = getActiveTabFromPath();`, add:

```jsx
  const tabs = user?.role === 'super_admin'
    ? [...TABS, { id: 'usuarios', label: 'Usuarios', icon: Users, color: 'slate' }]
    : TABS;
```

Change the tabs render loop from `{TABS.map(tab => (` to `{tabs.map(tab => (`.

- [ ] **Step 3: Add the logout button next to the Settings button**

Right after the closing `</button>` of the Settings button (the one with `data-testid="tab-settings"`), add:

```jsx
          <button
            onClick={onLogout}
            data-testid="logout-button"
            className="p-3 text-slate-400 hover:text-red-400 transition-all rounded-xl"
            title="Sair"
          >
            <LogOut size={22} />
          </button>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/layout/Header.jsx
git commit -m "feat: adicionar aba Usuarios (super_admin) e botao de logout no header"
```

---

## Task 14: `useUsers` hook

**Files:**
- Create: `frontend/src/hooks/useUsers.js`

- [ ] **Step 1: Write the hook**

```js
// frontend/src/hooks/useUsers.js
import { useCallback, useEffect, useState } from 'react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export function useUsers() {
  const [usuarios, setUsuarios] = useState([]);
  const [loading, setLoading] = useState(true);

  const carregarUsuarios = useCallback(() => {
    setLoading(true);
    axios
      .get(`${API}/users`)
      .then((res) => setUsuarios(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    carregarUsuarios();
  }, [carregarUsuarios]);

  const criarUsuario = useCallback((payload) => {
    return axios.post(`${API}/users`, payload).then((res) => {
      setUsuarios((prev) => [...prev, res.data]);
      return res.data;
    });
  }, []);

  const editarUsuario = useCallback((id, payload) => {
    return axios.put(`${API}/users/${id}`, payload).then((res) => {
      setUsuarios((prev) => prev.map((u) => (u.id === id ? res.data : u)));
      return res.data;
    });
  }, []);

  const deletarUsuario = useCallback((id) => {
    return axios.delete(`${API}/users/${id}`).then(() => {
      setUsuarios((prev) => prev.filter((u) => u.id !== id));
    });
  }, []);

  return { usuarios, loading, carregarUsuarios, criarUsuario, editarUsuario, deletarUsuario };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useUsers.js
git commit -m "feat: adicionar hook useUsers (list/create/edit/delete)"
```

---

## Task 15: `UsersTab` component + wire into `App.jsx`

**Files:**
- Create: `frontend/src/components/tabs/UsersTab.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1: Write the component**

```jsx
// frontend/src/components/tabs/UsersTab.jsx
import React, { useState } from 'react';
import { Plus, Trash2, Pencil, ShieldCheck, User as UserIcon } from 'lucide-react';
import { useUsers } from '../../hooks/useUsers';

const emptyForm = { email: '', password: '', role: 'normal' };

export function UsersTab() {
  const { usuarios, loading, criarUsuario, editarUsuario, deletarUsuario } = useUsers();
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState('');

  const resetForm = () => {
    setForm(emptyForm);
    setEditingId(null);
    setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      if (editingId) {
        const payload = { email: form.email, role: form.role };
        if (form.password) payload.password = form.password;
        await editarUsuario(editingId, payload);
      } else {
        await criarUsuario(form);
      }
      resetForm();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao salvar usuario');
    }
  };

  const startEdit = (usuario) => {
    setEditingId(usuario.id);
    setForm({ email: usuario.email, password: '', role: usuario.role });
  };

  const handleDelete = async (usuario) => {
    if (!window.confirm(`Deletar o login ${usuario.email}?`)) return;
    try {
      await deletarUsuario(usuario.id);
    } catch (err) {
      alert(err.response?.data?.detail || 'Erro ao deletar usuario');
    }
  };

  return (
    <div className="space-y-8">
      <h2 className="text-3xl font-black text-slate-800 uppercase tracking-tight">Usuarios</h2>

      <form onSubmit={handleSubmit} className="bg-white p-8 rounded-2xl shadow-lg border border-slate-200 space-y-4" data-testid="users-form">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <input
            type="email"
            required
            placeholder="Email"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            className="p-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-blue-400"
            data-testid="users-form-email"
          />
          <input
            type="password"
            required={!editingId}
            placeholder={editingId ? 'Nova senha (opcional)' : 'Senha'}
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
            className="p-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-blue-400"
            data-testid="users-form-password"
          />
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            className="p-3 bg-slate-50 border border-slate-200 rounded-xl outline-none focus:border-blue-400"
            data-testid="users-form-role"
          >
            <option value="normal">Normal</option>
            <option value="super_admin">Super Admin</option>
          </select>
        </div>

        {error && <p className="text-red-600 text-sm font-bold" data-testid="users-form-error">{error}</p>}

        <div className="flex gap-3">
          <button
            type="submit"
            className="bg-blue-600 text-white px-8 py-3 rounded-xl font-black text-sm uppercase flex items-center gap-2 hover:bg-blue-700"
            data-testid="users-form-submit"
          >
            <Plus size={18} /> {editingId ? 'Salvar edicao' : 'Criar login'}
          </button>
          {editingId && (
            <button type="button" onClick={resetForm} className="px-8 py-3 rounded-xl font-black text-sm uppercase text-slate-500 hover:text-slate-700">
              Cancelar
            </button>
          )}
        </div>
      </form>

      {loading ? (
        <p className="text-slate-400 font-bold uppercase text-sm">Carregando...</p>
      ) : (
        <div className="bg-white rounded-2xl shadow-lg border border-slate-200 overflow-hidden">
          <table className="w-full text-left">
            <thead className="bg-slate-50 text-slate-500 text-xs font-black uppercase">
              <tr>
                <th className="px-6 py-4">Email</th>
                <th className="px-6 py-4">Papel</th>
                <th className="px-6 py-4">Criado em</th>
                <th className="px-6 py-4 text-right">Acoes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {usuarios.map((usuario) => (
                <tr key={usuario.id} data-testid={`user-row-${usuario.id}`}>
                  <td className="px-6 py-4 font-bold text-slate-700">{usuario.email}</td>
                  <td className="px-6 py-4">
                    <span
                      className={`px-3 py-1 rounded-full text-[10px] font-black uppercase flex items-center gap-1 w-fit ${
                        usuario.role === 'super_admin' ? 'bg-purple-100 text-purple-700' : 'bg-slate-100 text-slate-600'
                      }`}
                    >
                      {usuario.role === 'super_admin' ? <ShieldCheck size={12} /> : <UserIcon size={12} />}
                      {usuario.role === 'super_admin' ? 'Super Admin' : 'Normal'}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-slate-400 text-sm">{new Date(usuario.created_at).toLocaleDateString('pt-BR')}</td>
                  <td className="px-6 py-4 text-right space-x-2">
                    <button
                      onClick={() => startEdit(usuario)}
                      data-testid={`user-edit-${usuario.id}`}
                      className="p-2 rounded-lg text-slate-400 hover:text-blue-600 hover:bg-blue-50"
                    >
                      <Pencil size={16} />
                    </button>
                    <button
                      onClick={() => handleDelete(usuario)}
                      data-testid={`user-delete-${usuario.id}`}
                      className="p-2 rounded-lg text-slate-400 hover:text-red-600 hover:bg-red-50"
                    >
                      <Trash2 size={16} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Lazy-import it and render it in `App.jsx`**

Add near the other `const XyzTab = lazy(...)` lines:

```jsx
const UsersTab = lazy(() => import('./components/tabs/UsersTab').then(m => ({ default: m.UsersTab })));
```

Add a render block right after the `{activeTab === 'settings' && (...)}` block:

```jsx
        {activeTab === 'usuarios' && (
          <Suspense fallback={LazyFallback}>
            <UsersTab />
          </Suspense>
        )}
```

- [ ] **Step 3: Manual verification**

With backend + frontend running and logged in as the super_admin created in Task 9:
1. Click the "Usuarios" tab (should be visible in the header). Expected: table shows the super_admin account.
2. Create a new login with role "Normal". Expected: appears in the table.
3. Log out (logout button), log back in with the new normal-user login. Expected: the "Usuarios" tab is **not** visible in the header.
4. Log back in as super_admin, edit the normal user's role to "Super Admin", then delete it. Expected: both actions succeed and the table updates.
5. Try deleting your own (currently logged-in) account. Expected: an alert shows the backend's error message ("Nao e possivel deletar a propria conta") and the row remains.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/tabs/UsersTab.jsx frontend/src/App.jsx
git commit -m "feat: adicionar tela de gerenciamento de usuarios (criar/editar/deletar)"
```

---

## Task 16: End-to-end sanity pass

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend test suite**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/test_user_models.py backend/tests/test_security_utils.py backend/tests/test_auth_router.py backend/tests/test_users_router.py backend/tests/test_protected_routes.py -v`
Expected: all passed

- [ ] **Step 2: Confirm existing (pre-auth) tests still pass or fail for unrelated reasons only**

Run: `.\.venv\Scripts\python.exe -m pytest backend/tests/ -v -k "not test_user_models and not test_security_utils and not test_auth_router and not test_users_router and not test_protected_routes"`
Note: some of these older tests hit real external APIs (PNCP, ANVISA) and may already fail/timeout for reasons unrelated to this change — the thing to confirm here is that they don't fail differently now (e.g. new 401s) because of the auth changes. If any now fail with 401, they're hitting `/api/*` without a token and need the same treatment as `test_protected_routes.py` (out of scope for this plan — flag to the user if seen).

- [ ] **Step 3: Full manual browser pass**

Repeat Task 15 Step 3's manual verification once more end-to-end (fresh browser tab, clear localStorage first) to confirm the whole flow works after all commits: login screen on first load → login as super_admin → full app visible incl. Usuarios tab → create/edit/delete logins → logout → login as a normal user → Usuarios tab hidden → logout.
