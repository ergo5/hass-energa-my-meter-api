import paramiko
import time

HOST = "192.168.70.199"
USER = "lab"
PASS = "lab"

def restart_ha():
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print(f"Connecting to {HOST} as {USER}...")
        client.connect(HOST, username=USER, password=PASS)
        print("SSH Connection Successful!")

        cmd = "echo lab | sudo -S reboot"
        
        print(f"Executing: {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd)
        
        time.sleep(2)
        
        print("Reboot command sent.")
        client.close()

    except Exception as e:
        print(f"SSH Failed: {e}")

if __name__ == "__main__":
    restart_ha()
