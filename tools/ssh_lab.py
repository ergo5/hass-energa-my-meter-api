#!/usr/bin/env python3
"""SSH helper for lab HA - executes commands via SSH"""
import subprocess
import sys

HOST = "192.168.70.199"
USER = "root"
PASS = "lab"

def ssh_exec(cmd):
    """Execute command on lab via SSH using paramiko"""
    try:
        import paramiko
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(HOST, username=USER, password=PASS)
        stdin, stdout, stderr = client.exec_command(cmd)
        output = stdout.read().decode() + stderr.read().decode()
        client.close()
        return output
    except ImportError:
        return "ERROR: Install paramiko: pip install paramiko"
    except Exception as e:
        return f"ERROR: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ssh_lab.py <command>")
        print("Example: python ssh_lab.py 'grep energa /config/home-assistant.log'")
        sys.exit(1)
    
    cmd = " ".join(sys.argv[1:])
    print(f"Executing on {HOST}: {cmd}")
    print("-" * 40)
    output = ssh_exec(cmd)
    print(output)
