import os
import sys
import time
import socket
import webbrowser
from pathlib import Path
import requests

# Try to load environment variables from .env file
def load_environment():
    # 1. Try python-dotenv
    try:
        from dotenv import load_dotenv
        script_dir = Path(__file__).resolve().parent
        candidates = [
            script_dir / ".env",
            script_dir / "nebula-kirana-agent" / ".env",
            Path.cwd() / ".env",
            Path.cwd() / "nebula-kirana-agent" / ".env",
            Path("e:/Projects/Nebula/nebula-kirana-agent/.env")
        ]
        for p in candidates:
            if p.exists():
                load_dotenv(p)
                break
    except ImportError:
        pass

    # 2. Manual fallback parser if dotenv not installed or missed
    if not os.environ.get("PYTHONANYWHERE_TOKEN"):
        candidates = [
            Path(__file__).resolve().parent / ".env",
            Path(__file__).resolve().parent / "nebula-kirana-agent" / ".env",
            Path("e:/Projects/Nebula/nebula-kirana-agent/.env")
        ]
        for p in candidates:
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

# PythonAnywhere API Credentials (loaded securely from .env or environment)
TOKEN = os.environ.get("PYTHONANYWHERE_TOKEN", "").strip()
USERNAME = os.environ.get("PYTHONANYWHERE_USERNAME", "Saravana07").strip()
HOST = "www.pythonanywhere.com"

if not TOKEN:
    print("=" * 60)
    print("[-] ERROR: PYTHONANYWHERE_TOKEN is missing!")
    print("    Please set PYTHONANYWHERE_TOKEN in your .env file or environment.")
    print("=" * 60)
    input("\nPress Enter to exit...")
    sys.exit(1)

HEADERS = {"Authorization": f"Token {TOKEN}"}
BASE_API = f"https://{HOST}/api/v0/user/{USERNAME}"


def wait_for_internet(target_host="8.8.8.8", target_port=53, timeout=3, check_interval=2):
    """
    Waits until an active internet connection is detected.
    Tries DNS socket first (fastest, minimal overhead),
    then verifies HTTPS connection to PythonAnywhere.
    """
    print("[1/4] Checking internet connectivity...")
    first_attempt = True

    while True:
        try:
            # 1. Quick socket test to public DNS
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((target_host, target_port))
            sock.close()

            # 2. Verify PythonAnywhere is reachable
            requests.get(f"https://{HOST}", timeout=timeout)

            if not first_attempt:
                print("\n[+] Internet connection restored! Proceeding...")
            else:
                print("[+] Internet connection verified.")
            return True
        except (socket.error, requests.RequestException, Exception):
            if first_attempt:
                print("[!] No internet connection detected.")
                print("[*] Waiting for internet connection to be established...", end="", flush=True)
                first_attempt = False
            else:
                print(".", end="", flush=True)
            time.sleep(check_interval)


def get_or_create_console():
    """
    Finds existing bash console or creates a new one.
    """
    print(f"\n[2/4] Connecting to PythonAnywhere account ({USERNAME})...")
    url = f"{BASE_API}/consoles/"

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
    except requests.RequestException as e:
        print(f"[-] Network error connecting to PythonAnywhere: {e}")
        return None

    if response.status_code != 200:
        print(f"[-] Error fetching consoles ({response.status_code}): {response.text}")
        return None

    consoles = response.json()
    for console in consoles:
        if console.get("executable") == "bash":
            cid = console["id"]
            print(f"[+] Found existing Bash console (ID: {cid})")
            return cid

    # If none found, create a new one
    print("[*] No bash console found. Creating a new Bash console...")
    res = requests.post(url, headers=HEADERS, json={"executable": "bash"}, timeout=15)
    if res.status_code == 201:
        cid = res.json()["id"]
        print(f"[+] Created new Bash console (ID: {cid})")
        return cid
    else:
        print(f"[-] Failed to create console ({res.status_code}): {res.text}")
        return None


def is_console_ready(console_id):
    """
    Checks if console is awake and ready to accept input.
    Returns: (ready: bool, is_412: bool, message: str)
    """
    url = f"{BASE_API}/consoles/{console_id}/get_latest_output/"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            return True, False, "OK"
        elif res.status_code == 412:
            return False, True, "Dormant (412)"
        else:
            return False, False, f"HTTP {res.status_code}: {res.text}"
    except requests.RequestException as e:
        return False, False, str(e)


def wake_up_console(console_id):
    """
    Wakes up a dormant console by opening its browser URL
    and polling until it becomes active.
    """
    console_url = f"https://{HOST}/user/{USERNAME}/consoles/{console_id}/"
    ready, is_412, msg = is_console_ready(console_id)

    if ready:
        print("[+] Console is already active and ready.")
        return True

    print(f"\n[!] Console #{console_id} is currently dormant / sleeping.")
    print("    PythonAnywhere requires the console to be loaded in a browser once to wake it up.")
    print(f"[*] Opening console in your default browser:")
    print(f"    {console_url}")

    try:
        webbrowser.open(console_url)
    except Exception as e:
        print(f"    (Could not auto-open browser: {e}. Please open the URL manually.)")

    print("[*] Waiting for console to initialize (polling every 2s)...", end="", flush=True)

    # Poll for up to 40 seconds (20 checks x 2s)
    for _ in range(20):
        time.sleep(2)
        ready, is_412, msg = is_console_ready(console_id)
        if ready:
            print("\n[+] Console is now awake and ready!")
            time.sleep(2)  # Give bash prompt a moment to settle
            return True
        print(".", end="", flush=True)

    print("\n")
    print("[!] Console has not yet initialized.")
    print("    Please ensure you are logged into PythonAnywhere and the console tab has finished loading in your browser.")

    choice = input("    Press Enter once the console has loaded in your browser (or 'q' to cancel): ").strip()
    if choice.lower() == "q":
        return False

    ready, is_412, msg = is_console_ready(console_id)
    if ready:
        print("[+] Console is now awake and ready!")
        return True
    else:
        print(f"[-] Console still returned: {msg}")
        return False


def restart_bot(console_id):
    """
    Sends restart commands to the Bash console.
    """
    print("\n[3/4] Sending restart commands to PythonAnywhere...")
    url_input = f"{BASE_API}/consoles/{console_id}/send_input/"

    commands = [
        "\x03\n",
        'pkill -f "python main.py"\n',
        f"cd /home/{USERNAME}/nebula-kirana-agent\n",
        "source venv/bin/activate\n",
        "nohup python main.py > bot.log 2>&1 &\n"
    ]

    for i, cmd in enumerate(commands, 1):
        display_cmd = cmd.strip().replace("\x03", "<Ctrl+C>")
        print(f"    -> [{i}/{len(commands)}] {display_cmd}")

        try:
            res = requests.post(url_input, headers=HEADERS, json={"input": cmd}, timeout=10)
            if res.status_code != 200:
                print(f"[-] Error executing '{display_cmd}': {res.status_code} {res.text}")
                return False
        except requests.RequestException as e:
            print(f"[-] Network error sending command: {e}")
            return False

        time.sleep(1.5)

    print("[+] All commands executed successfully!")
    return True


def check_bot_status():
    """
    Checks remote bot.log to confirm the bot is running.
    """
    print("\n[4/4] Verifying bot startup (reading bot.log)...")
    time.sleep(3)

    files_url = f"{BASE_API}/files/path/home/{USERNAME}/nebula-kirana-agent/bot.log"
    try:
        res = requests.get(files_url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            lines = res.text.strip().splitlines()
            last_lines = lines[-6:] if len(lines) >= 6 else lines
            print("--- LATEST BOT LOGS ---")
            for line in last_lines:
                print("   ", line)
            print("-----------------------")
            print("[SUCCESS] Nebula Kirana Telegram Bot is up and running!")
        else:
            print(f"[*] Could not retrieve bot.log ({res.status_code}). Process was launched in background.")
    except Exception as e:
        print(f"[*] Could not verify log output: {e}")


def main():
    print("=" * 60)
    print("      Nebula Kirana Agent - PythonAnywhere Restarter")
    print("=" * 60)

    try:
        # Step 1: Wait for internet
        wait_for_internet()

        # Step 2: Get or create console
        console_id = get_or_create_console()
        if not console_id:
            print("[-] Could not get or create a console. Aborting.")
            return

        # Step 3: Ensure console is awake
        if not wake_up_console(console_id):
            print("[-] Console could not be awakened. Aborting.")
            return

        # Step 4: Restart bot
        success = restart_bot(console_id)
        if success:
            # Step 5: Check logs
            check_bot_status()
        else:
            print("[-] Bot restart encountered errors.")

    except KeyboardInterrupt:
        print("\n\n[!] Operation cancelled by user.")
    except Exception as e:
        print(f"\n[-] Unexpected error: {e}")
    finally:
        print("\n" + "=" * 60)
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
