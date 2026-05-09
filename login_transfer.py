import os
import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

def inject_cookies(profile_dir, url, cookie_file):
    if not os.path.exists(cookie_file):
        print(f"[!] Error: File '{cookie_file}' not found in the folder.")
        return

    print(f"[*] Starting Chrome for {url}...")
    options = Options()
    options.add_argument(f"--user-data-dir={os.path.abspath(profile_dir)}")
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--password-store=basic")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    
    print(f"[*] Opening {url}...")
    driver.get(url)
    time.sleep(3)
    
    try:
        with open(cookie_file, 'r') as f:
            cookies = json.load(f)
        
        count = 0
        for c in cookies:
            cookie_dict = {'name': c['name'], 'value': c['value']}
            if 'domain' in c: cookie_dict['domain'] = c['domain']
            if 'path' in c: cookie_dict['path'] = c['path']
            if 'secure' in c: cookie_dict['secure'] = c['secure']
            if 'expirationDate' in c: cookie_dict['expiry'] = int(c['expirationDate'])
            try: 
                driver.add_cookie(cookie_dict)
                count += 1
            except Exception: 
                pass
        
        print(f"[+] Injected {count} cookies successfully!")
        print("[*] Refreshing page to save login state into Linux Profile...")
        driver.refresh()
        time.sleep(5)
        print(f"[+] Done! Profile '{profile_dir}' is now permanently logged in on VPS.")
    except Exception as e:
        print(f"[-] Error injecting cookies: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    print("=== Permanent Login Transfer Tool ===")
    print("1. Inject Facebook Cookies")
    print("2. Inject Instagram Cookies")
    choice = input("Select option (1 or 2): ").strip()
    
    if choice == "1":
        inject_cookies("chrome_profile", "https://www.facebook.com", "fb_cookies.json")
    elif choice == "2":
        inject_cookies("chrome_profile_ig", "https://www.instagram.com", "ig_cookies.json")
    else:
        print("Invalid choice.")
