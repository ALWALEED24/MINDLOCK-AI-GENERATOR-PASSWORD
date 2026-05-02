##import subprocess
##import threading
##import time
##import webbrowser

##def run_fastapi_with_ngrok(app_path="main:app", port=8000):
    ##def start_uvicorn():
        ##subprocess.run(["uvicorn", app_path, "--reload", "--port", str(port)])

    ##def start_ngrok():
        ##time.sleep(2)
        ##subprocess.run(["ngrok", "config", "add-authtoken", "352eA57Lsv198rOFNeyNuBVFptm_7m4R6mGy1gtnirCi1tTn2"])
        ##subprocess.Popen(["ngrok", "http", str(port)])
        ##time.sleep(3)
        ##webbrowser.open("http://localhost:4040")
        ##print("🔗 ngrok tunnel is running. Visit http://localhost:4040 to see tunnel info.")

    ##threading.Thread(target=start_uvicorn, daemon=True).start()
   ## start_ngrok()