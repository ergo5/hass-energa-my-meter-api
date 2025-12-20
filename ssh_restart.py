
import paramiko
import sys
import time

HOST = "192.168.70.199"
USER = "lab"
PASS = "lab"
COMMAND = "echo lab | sudo -S reboot"

def run_ssh():
    print(f"Connecting to {HOST} as {USER}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOST, username=USER, password=PASS, timeout=10)
        print("SSH Connection Successful!")
        print(f"Executing: {COMMAND}")
        stdin, stdout, stderr = client.exec_command(COMMAND)
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status == 0:
            print("Reboot command sent successfully.")
        else:
            print(f"Command failed with exit code {exit_status}")

    except Exception as e:
        if "Server connection dropped" in str(e) or "Connection reset" in str(e):
             print("Reboot initiated (Connection dropped as expected).")
        else:
             print(f"SSH Failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    run_ssh()
