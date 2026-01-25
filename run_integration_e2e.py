import subprocess
import time
import requests
import sys
import os
import signal

def run_integration_test():
    server_process = None
    try:
        print("--- Starting Server for Integration Test ---")
        # Start Server
        env = os.environ.copy()
        # Set PYTHONPATH to include current directory
        env["PYTHONPATH"] = os.getcwd()
        
        server_process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        ) # Don't block, use PIPE to avoid hanging if buffer fills? Actually PIPE can hang if not read.
          # For test, we might want to redirect to file or inherit.
          # Inheriting is risky if it spams. Let's use log files.
        
        print(f"Server PID: {server_process.pid}")
        
        # Wait for Health Check
        print("Waiting for server to become healthy...")
        healthy = False
        for i in range(30): # 30 seconds wait (MuseTalk init takes time)
            try:
                r = requests.get("http://localhost:8000/health", timeout=1)
                if r.status_code == 200:
                    print(f"Server is UP: {r.json()}")
                    healthy = True
                    break
            except requests.exceptions.ConnectionError:
                pass
            time.sleep(2)
            print(".", end="", flush=True)
            
        if not healthy:
            print("\nSERVER STARTUP FAILED (Timeout)")
            # Try to read stderr
            try:
                outs, errs = server_process.communicate(timeout=1)
                print(f"STDOUT: {outs}")
                print(f"STDERR: {errs}")
            except:
                pass
            return
            
        print("\n--- Running Test Client ---")
        # Run the test client
        client_result = subprocess.run([sys.executable, "test_server_chat.py"], capture_output=True, text=True)
        print("Client Output:")
        print(client_result.stdout)
        print("Client Errors:")
        print(client_result.stderr)
        
        if "video_chunk" in client_result.stdout:
            print("\n>>> INTEGRATION SUCCESS: Video chunks detected in response. <<<")
        else:
            print("\n>>> INTEGRATION FAILURE: No video chunks found. <<<")

    except Exception as e:
        print(f"Test Harness Failed: {e}")
    finally:
        print("--- Teardown ---")
        if server_process:
            print("Killing Server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except:
                server_process.kill()
            print("Server Killed.")

if __name__ == "__main__":
    run_integration_test()
