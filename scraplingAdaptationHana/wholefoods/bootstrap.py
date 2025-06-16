import os
import sys
import subprocess
import platform
import importlib.util

VENV_DIR = ".venv"
REQUIRED_PACKAGES = [
    "pandas",
    "openpyxl",
    "httpx",
    "rapidfuzz",
    "scrapling",
    "camoufox"
]

def in_virtualenv():
    return sys.prefix != sys.base_prefix

def install_package_if_missing(package):
    if not importlib.util.find_spec(package):
        print(f"📦 Installing missing package: {package}")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
    else:
        print(f"✅ Package already installed: {package}")

def ensure_all_dependencies():
    for pkg in REQUIRED_PACKAGES:
        install_package_if_missing(pkg)

def ensure_camoufox_ready():
    if platform.system() == "Windows":
        base_dir = os.path.expanduser("~\\AppData\\Local\\camoufox\\camoufox\\Cache")
    else:
        base_dir = os.path.expanduser("~/.local/share/camoufox/camoufox/Cache")

    exe_path = os.path.join(base_dir, "camoufox.exe")
    version_path = os.path.join(base_dir, "version.json")

    if not (os.path.exists(version_path) and os.path.exists(exe_path)):
        print("📦 camoufox missing or incomplete. Fetching...")
        subprocess.check_call([sys.executable, "-m", "camoufox", "fetch", "--force"])
    else:
        print("✅ camoufox browser is ready.")

def bootstrap():
    if not in_virtualenv():
        print("❌ You are not in a virtual environment. Please activate it first.")
        sys.exit(1)
    
    ensure_all_dependencies()
    ensure_camoufox_ready()
