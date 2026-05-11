# 🚀 Guia de Inicialização - Sistema GSM

Este guia fornece os passos exatos para ligar todo o ecossistema do GSM (Backend, Frontend e Banco de Dados) no Windows.

---

## 1. Banco de Dados (MongoDB)
O sistema utiliza o **MongoDB** para armazenar editais e logs de scrapers.

1.  **Certifique-se de que o MongoDB está instalado e rodando.**
2.  Por padrão, o backend busca o banco em: `mongodb://localhost:27017`.
    *   *Dica:* Se você usa o Docker, pode subir o banco com `docker run -d -p 27017:27017 --name gsm-mongo mongo`.
    *   Caso contrário, verifique se o serviço "MongoDB" está "Em Execução" no Gerenciador de Tarefas do Windows (aba Serviços).

---

## 2. Backend (Python + FastAPI)
O erro "Python não foi encontrado" ocorre porque o atalho padrão do Windows está desativado ou o Python não está no seu PATH. Como você já tem uma pasta `.venv`, usaremos ela diretamente.

### Passos:
1.  Abra um terminal na **raiz do projeto** (`i:\programacao\gsm\gsmatual-main`).
2.  **Ative o Ambiente Virtual:**
    ```powershell
    .\.venv\Scripts\activate
    ```
3.  **Instale as Dependências (Apenas na primeira vez ou se houver erros):**
    ```powershell
    python -m pip install -r backend/requirements.txt
    ```
4.  **Inicie o Servidor (da raiz do projeto):**
    ```powershell
    .\.venv\Scripts\python.exe -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
    ```
    *   **Sucesso:** Você verá mensagens de `INFO` e a confirmação de que a API está rodando em `http://127.0.0.1:8000`.
    *   ⚠️ **Importante:** Execute sempre a partir da **raiz do projeto** (`i:\programacao\gsm\gsmatual-main`), **não** da pasta `backend/`.

---

## 3. Frontend (React)
O frontend precisa que o backend esteja ligado para exibir os dados.

### Passos:
1.  Abra um **novo terminal** (mantenha o terminal do backend aberto).
2.  Navegue até a pasta do frontend:
    ```powershell
    cd frontend
    ```
3.  **Instale as Dependências (Se ainda não o fez):**
    ```powershell
    npm install
    # ou se tiver o yarn instalado: yarn install
    ```
4.  **Inicie a Aplicação:**
    ```powershell
    npm start
    ```
5.  Acesse `http://localhost:3000` no seu navegador.

---

## 💡 Solução de Problemas Comuns

### Erro: "Python não foi encontrado"
Isso acontece porque o Windows tenta abrir a Microsoft Store. Para resolver:
*   Use sempre o executável do ambiente virtual: `.\.venv\Scripts\python.exe`
*   Ou ative o venv primeiro com `.\.venv\Scripts\activate` e depois rode os comandos.

### Erro de Conexão (Interface em branco ou erro de fetch)
1.  Verifique se o terminal do **Backend** não fechou.
2.  Verifique se o arquivo `frontend/.env` está assim:
    ```env
    REACT_APP_BACKEND_URL=http://127.0.0.1:8000
    ```

### Erro do MongoDB
Se o backend fechar logo após iniciar, verifique se o MongoDB está aceitando conexões. Você pode testar abrindo o **MongoDB Compass** e tentando conectar em `localhost:27017`.

---

## 🛠️ Resumo para o dia a dia
Para ligar o sistema rapidamente (após a primeira configuração):
1.  Terminal 1 (raiz do projeto): `.\.venv\Scripts\python.exe -m uvicorn backend.server:app --host 127.0.0.1 --port 8000`
2.  Terminal 2 (pasta frontend): `cd frontend; npm start`
