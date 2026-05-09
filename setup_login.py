import os
import shutil
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def start_login_session(profile_name, url):
    print(f"\n[*] Clearing old corrupted Windows profile: {profile_name} ...")
    if os.path.exists(profile_name):
        try:
            shutil.rmtree(profile_name, ignore_errors=True)
            print("[+] Old profile removed.")
        except Exception as e:
            print(f"[-] Could not remove old profile: {e}")
            
    print(f"[*] Starting fresh Linux Chrome for {url} on Port 9222...")
    
    options = Options()
    options.add_argument(f"--user-data-dir={os.path.abspath(profile_name)}")
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--password-store=basic")
    options.add_argument("--remote-debugging-port=9222")
    options.add_argument("--remote-debugging-address=0.0.0.0")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    print(f"\n=========================================================")
    print(f"✅ BROWSER IS READY!")
    print(f"1. Apne Windows mein SSH tunnel chalu rakhein: ssh -L 9223:localhost:9222 root@72.60.68.66")
    print(f"2. Windows Chrome mein kholiye: chrome://inspect/#devices")
    print(f"3. 'Configure...' mein localhost:9223 check karein.")
    print(f"4. Neechay {url} wale link par 'inspect' click karein.")
    print(f"5. Screencast on karein aur apna Email/Password daal kar login kar lein!")
    print(f"=========================================================\n")
    print("WARNING: Jab login poora ho jaye, tou isi terminal mein 'Ctrl+C' dabayein taakay profile permanently save ho jaye.")
    
    driver.get(url)
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[*] Saving profile and closing...")
        driver.quit()
        print(f"[+] Profile '{profile_name}' saved permanently for Linux!")

if __name__ == "__main__":
    print("=== Native VPS Login Setup ===")
    print("1. Setup Facebook Login")
    print("2. Setup Instagram Login")
    choice = input("Select option (1 or 2): ").strip()
    
    if choice == "1":
        start_login_session("chrome_profile", "https://www.facebook.com")
    elif choice == "2":
        start_login_session("chrome_profile_ig", "https://www.instagram.com")
    else:
        print("Invalid choice.")
