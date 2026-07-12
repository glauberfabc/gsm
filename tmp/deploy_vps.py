"""
Deploy script: faz upload dos arquivos modificados e reinicia o backend na VPS.
"""
import paramiko
import os

HOST = '129.121.55.174'
PORT = 22022
USER = 'root'
PASS = 'Glauber2010*'
REMOTE_BASE = '/root/gsm'
LOCAL_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Arquivos backend a subir (relativos ao projeto local)
BACKEND_FILES = [
    'backend/services/medicamento_search_service.py',
    'backend/scrapers/agregador_client.py',
    'backend/scrapers/pncp_api_oficial.py',
    'backend/scrapers/pncp_search_client.py',
    'backend/services/clone_agregador_service.py',
    'backend/services/motor_independente.py',
    'backend/services/motor_sincronizacao_gsm.py',
    'backend/services/normalizador_generico.py',
    'backend/services/pncp_sync_service.py',
]


def ssh_cmd(client, cmd):
    print(f'  $ {cmd}')
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    if out:
        print(f'    {out}')
    if err:
        print(f'    ERR: {err}')
    return out


def upload_files(client):
    sftp = client.open_sftp()
    for rel_path in BACKEND_FILES:
        local = os.path.join(LOCAL_BASE, rel_path.replace('/', os.sep))
        remote = f'{REMOTE_BASE}/{rel_path}'
        if not os.path.exists(local):
            print(f'  [SKIP] {rel_path} - nao encontrado localmente')
            continue
        # Garante que o diretório remoto existe
        remote_dir = os.path.dirname(remote)
        try:
            sftp.stat(remote_dir)
        except FileNotFoundError:
            sftp.mkdir(remote_dir)
        print(f'  [UP] {rel_path}')
        sftp.put(local, remote)
    sftp.close()


def main():
    print('=== CONECTANDO NA VPS ===')
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, port=PORT, username=USER, password=PASS)
    print('Conectado.')

    print('\n=== UPLOAD DE ARQUIVOS BACKEND ===')
    upload_files(client)

    print('\n=== REINICIANDO BACKEND ===')
    # Tenta pm2 primeiro; fallback manual
    pm2_path = ssh_cmd(client, 'which pm2 || ls /root/.nvm/versions/node/*/bin/pm2 2>/dev/null | head -1')
    if pm2_path:
        ssh_cmd(client, f'{pm2_path} restart gsm-backend 2>/dev/null || {pm2_path} start /root/gsm/ecosystem.config.js')
    else:
        # Fallback: mata o uvicorn e reinicia via nohup
        ssh_cmd(client, 'pkill -f "uvicorn backend.server" || true')
        ssh_cmd(client, (
            'cd /root/gsm && nohup .venv/bin/python3 -m uvicorn backend.server:app '
            '--host 127.0.0.1 --port 8000 > /root/gsm/uvicorn.log 2>&1 &'
        ))

    import time
    print('  aguardando 4s para o servidor subir...')
    time.sleep(4)

    print('\n=== VERIFICANDO SE SUBIU ===')
    ssh_cmd(client, 'curl -s http://127.0.0.1:8000/api/health 2>/dev/null | head -c 200 || echo "health check falhou"')
    ssh_cmd(client, 'ps aux | grep uvicorn | grep -v grep')

    client.close()
    print('\n=== DEPLOY CONCLUIDO ===')


if __name__ == '__main__':
    main()
