import paramiko

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
import os
key_path = os.path.expanduser('~/.ssh/vps_gsmatual')
if os.path.exists(key_path):
    client.connect('129.121.55.174', port=22022, username='root', key_filename=key_path, timeout=10)
else:
    client.connect('129.121.55.174', port=22022, username='root', password='Glauber2010*', timeout=10)

cmds = [
    'pm2 jlist 2>/dev/null | python3 -c "import sys,json; [print(p[\"name\"],p[\"pid\"]) for p in json.load(sys.stdin)]" 2>/dev/null || echo NO_PM2',
    'cat /root/gsm/ecosystem.config.js 2>/dev/null || echo NO_ECOSYSTEM',
    'cat /etc/systemd/system/gsm*.service 2>/dev/null || echo NO_SYSTEMD',
]

for cmd in cmds:
    print('CMD:', cmd[:70])
    stdin, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode('utf-8', errors='replace'))
    print('---')

client.close()
