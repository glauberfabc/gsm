import paramiko
import os
import sys

def upload_zip():
    host = '129.121.55.174'
    port = 22022
    username = 'root'
    password = 'Glauber2010*'

    transport = paramiko.Transport((host, port))
    transport.connect(username=username, password=password)
    sftp = paramiko.SFTPClient.from_transport(transport)
    
    local_path = 'frontend_build.zip'
    remote_path = '/root/frontend_build.zip'
    
    print(f"Uploading {local_path} to {remote_path}...")
    sftp.put(local_path, remote_path)
    sftp.close()
    transport.close()
    print("Upload complete.")

if __name__ == '__main__':
    upload_zip()
