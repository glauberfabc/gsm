import paramiko
import os
import sys

def upload_zip():
    host = '129.121.55.174'
    port = 22022
    username = 'root'
    password = 'Glauber2010*'

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    import os
    key_path = os.path.expanduser('~/.ssh/vps_gsmatual')
    if os.path.exists(key_path):
        client.connect(host, port=port, username=username, key_filename=key_path, timeout=10)
    else:
        client.connect(host, port=port, username=username, password=password, timeout=10)
    
    sftp = client.open_sftp()
    
    local_path = 'frontend_build.zip'
    remote_path = '/root/frontend_build.zip'
    
    print(f"Uploading {local_path} to {remote_path}...")
    sftp.put(local_path, remote_path)
    sftp.close()
    client.close()
    print("Upload complete.")

if __name__ == '__main__':
    upload_zip()
