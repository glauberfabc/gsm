import paramiko
import time
import sys

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
import os
key_path = os.path.expanduser('~/.ssh/vps_gsmatual')
if os.path.exists(key_path):
    client.connect('129.121.55.174', port=22022, username='root', key_filename=key_path, timeout=10)
else:
    client.connect('129.121.55.174', port=22022, username='root', password='Glauber2010*', timeout=10)

def safe_print(text):
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', errors='replace').decode('ascii'))

def run(cmd):
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace').strip()
    err = stderr.read().decode('utf-8', errors='replace').strip()
    return out, err

# Restart via PM2
print('Reiniciando gsm-backend via PM2...')
out, err = run('/usr/bin/pm2 restart gsm-backend')
# pm2 restart retorna tabela com caracteres especiais - ignoramos
print('Saida PM2 (exit ok se sem erro abaixo)')
if err:
    safe_print('ERR: ' + err[:300])

time.sleep(5)

print('\nVerificando processo uvicorn...')
out, err = run('ps aux | grep uvicorn | grep -v grep')
safe_print(out)

print('\nHealth check...')
out, err = run('curl -s http://127.0.0.1:8000/api/health 2>/dev/null | head -c 300')
safe_print(out if out else '(sem resposta)')

print('\nCache clear para limpar cache de 24h das buscas anteriores...')
out, err = run('curl -s -X POST http://127.0.0.1:8000/api/cache/clear')
safe_print(out[:200] if out else '(sem resposta)')

client.close()
print('\nConcluido.')
