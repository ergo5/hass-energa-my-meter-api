
import paramiko
import sys
import time

HOST = "192.168.70.199"
USER = "lab"
PASS = "lab"
# Fetch last 100 lines of HA log filtering for Energa
COMMAND = "grep -i 'energa' /config/home-assistant.log | tail -n 50"

def check_logs():
    print(f"Connecting to {HOST} as {USER}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        client.connect(HOST, username=USER, password=PASS, timeout=10)
        print("SSH Connection Successful!")
        print(f"Executing: {COMMAND}")
        stdin, stdout, stderr = client.exec_command(COMMAND)
        
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        
        if out: 
            print("--- LOG ENTRY MATCHES ---")
            print(out)
        else:
            print("No 'energa' entries found in the tail of the log.")
            
        if err:
            print(f"STDERR: {err}")

    except Exception as e:
        print(f"SSH Failed: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    check_logs()
