#!/usr/bin/env python3
"""Fetch and analyze HA logs for Energa issues"""
import paramiko

HOST = "192.168.70.199"
USER = "root"
PASS = "lab"

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    
    # Get logs directly
    cmd = "ha core logs 2>/dev/null"
    stdin, stdout, stderr = client.exec_command(cmd)
    output = stdout.read().decode()
    
    # Filter locally
    lines = output.split('\n')
    energa_lines = [l for l in lines if 'energa' in l.lower() or 'warning' in l.lower() or 'error' in l.lower()]
    
    print("=" * 60)
    print(f"ENERGA/WARNING/ERROR LOGS ({len(energa_lines)} lines)")
    print("=" * 60)
    
    # Save to file
    with open("logs_energa.txt", "w") as f:
        for line in energa_lines:
            f.write(line + "\n")
    
    print("Saved to logs_energa.txt")
    print("\nLast 15 lines:")
    for line in energa_lines[-15:]:
        print(line)
    
    client.close()

if __name__ == "__main__":
    main()
