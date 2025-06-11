import subprocess
import sys

required_packages = [
    "pandas", "openpyxl", "httpx", "rapidfuzz", "scrapling"
]

def install_packages():
    for package in required_packages:
        try:
            # Adjust import name if different from pip package name
            if package == "rapidfuzz":
                __import__("rapidfuzz.fuzz")
            else:
                __import__(package)
        except ImportError:
            print(f"Installing missing package: {package}")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

if __name__ == "__main__":
    install_packages()
