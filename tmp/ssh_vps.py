import paramiko
import sys

def execute(cmd):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    import os
    key_path = os.path.expanduser('~/.ssh/vps_gsmatual')
    try:
        if os.path.exists(key_path):
            client.connect('129.121.55.174', port=22022, username='root', key_filename=key_path, timeout=10)
        else:
            client.connect('129.121.55.174', port=22022, username='root', password='Glauber2010*', timeout=10)
        stdin, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode('utf-8')
        err = stderr.read().decode('utf-8')
        print("STDOUT:")
        print(out)
        print("STDERR:")
        print(err)
    except Exception as e:
        print("ERROR:", e)
    finally:
        client.close()

if __name__ == '__main__':
    execute(sys.argv[1])
