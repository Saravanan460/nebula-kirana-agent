import os
import sys
from pathlib import Path
import requests

# Try to load environment variables from .env file
def load_environment():
    try:
        from dotenv import load_dotenv
        for p in [Path(__file__).resolve().parent / ".env", Path.cwd() / ".env"]:
            if p.exists():
                load_dotenv(p)
                break
    except ImportError:
        pass

    if not os.environ.get("PYTHONANYWHERE_TOKEN"):
        p = Path(__file__).resolve().parent / ".env"
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            os.environ.setdefault(k.strip(), v.strip().strip("'\""))
            except Exception:
                pass

load_environment()

TOKEN = os.environ.get("PYTHONANYWHERE_TOKEN", "").strip()
USERNAME = os.environ.get("PYTHONANYWHERE_USERNAME", "Saravana07").strip()
HOST = "www.pythonanywhere.com"

if not TOKEN:
    print("[-] Error: PYTHONANYWHERE_TOKEN is not set in .env")
    sys.exit(1)

headers = {"Authorization": f"Token {TOKEN}"}

# 1. Get console output
print("--- CONSOLE OUTPUT ---")
url_consoles = f"https://{HOST}/api/v0/user/{USERNAME}/consoles/"
try:
    response = requests.get(url_consoles, headers=headers, timeout=10)
    if response.status_code == 200:
        consoles = response.json()
        for console in consoles:
            if console.get("executable") == "bash":
                cid = console["id"]
                out_url = f"https://{HOST}/api/v0/user/{USERNAME}/consoles/{cid}/get_latest_output/"
                out_res = requests.get(out_url, headers=headers, timeout=10)
                if out_res.status_code == 200:
                    print(out_res.json().get("output", ""))
                elif out_res.status_code == 412:
                    print("(Console is dormant/sleeping)")
                else:
                    print(f"(Console status: {out_res.status_code})")
                break
    else:
        print(f"Error fetching consoles: {response.status_code}")
except Exception as e:
    print(f"Error checking console: {e}")

# 2. Get bot.log contents
print("\n--- BOT.LOG OUTPUT ---")
files_url = f"https://{HOST}/api/v0/user/{USERNAME}/files/path/home/{USERNAME}/nebula-kirana-agent/bot.log"
try:
    res = requests.get(files_url, headers=headers, timeout=10)
    if res.status_code == 200:
        # Print last 1000 characters
        print(res.text[-1000:])
    else:
        print(f"Failed to get bot.log: {res.status_code} {res.text}")
except Exception as e:
    print(f"Error fetching bot.log: {e}")
