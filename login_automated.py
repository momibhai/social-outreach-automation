import time
import os
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

def clear_old_profile(profile_dir):
    if os.path.exists(profile_dir):
        print(f"[*] Clearing old profile data from {profile_dir}...")
        try: shutil.rmtree(profile_dir, ignore_errors=True)
        except: pass

def get_standard_driver(profile_dir):
    options = Options()
    options.add_argument(f"--user-data-dir={os.path.abspath(profile_dir)}")
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--password-store=basic")
    options.add_argument("--window-size=1280,1024")
    options.add_argument("--disable-gpu")
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def fb_login(email, password):
    profile_dir = "chrome_profile"
    clear_old_profile(profile_dir)
    
    print("\n[*] Starting Facebook Login (Standard Headless)...")
    driver = get_standard_driver(profile_dir)
    try:
        driver.get("https://www.facebook.com/")
        time.sleep(4)
        
        print("[*] Entering credentials and pressing ENTER...")
        email_input = driver.find_element(By.NAME, "email")
        pass_input = driver.find_element(By.NAME, "pass")
        
        email_input.send_keys(email)
        pass_input.send_keys(password)
        pass_input.send_keys(Keys.ENTER)
        
        print("[*] Waiting for response...")
        time.sleep(15)
        
        # Check for 2FA
        try:
            code_input = driver.find_element(By.NAME, "approvals_code")
            print("\n[!] Facebook is asking for 2-Factor Authentication (OTP)!")
            otp = input("[>] Please enter the 6-digit OTP code sent to your phone/app: ")
            code_input.send_keys(otp)
            code_input.send_keys(Keys.ENTER)
            time.sleep(5)
        except: pass
        
        print("\n[+] SUCCESS: Facebook profile saved permanently! Aap ab bot run kar sakte hain.")
        driver.save_screenshot("fb_success.png")
        print(">>> Saved 'fb_success.png'. <<<")
        
    except Exception as e:
        print(f"\n[-] ERROR: {e}")
        try: driver.save_screenshot("fb_error.png"); print(">>> Saved 'fb_error.png'! <<<")
        except: pass
    finally:
        driver.quit()

def ig_login(username, password):
    profile_dir = "chrome_profile_ig"
    clear_old_profile(profile_dir)
    
    print("\n[*] Starting Instagram Login (Standard Headless)...")
    driver = get_standard_driver(profile_dir)
    try:
        driver.get("https://www.instagram.com/accounts/login/")
        time.sleep(5)
        
        print("[*] Entering credentials and pressing ENTER...")
        user_input = driver.find_element(By.NAME, "username")
        pass_input = driver.find_element(By.NAME, "password")
        
        user_input.send_keys(username)
        pass_input.send_keys(password)
        pass_input.send_keys(Keys.ENTER)
        
        print("[*] Waiting for response...")
        time.sleep(15)
        
        # Check for 2FA
        try:
            code_input = driver.find_element(By.NAME, "verificationCode")
            print("\n[!] Instagram is asking for 2-Factor Authentication (OTP)!")
            otp = input("[>] Please enter the OTP code sent to your phone/app: ")
            code_input.send_keys(otp)
            code_input.send_keys(Keys.ENTER)
            time.sleep(5)
        except: pass
            
        print("\n[+] SUCCESS: Instagram profile saved permanently!")
        driver.save_screenshot("ig_success.png")
        
    except Exception as e:
        print(f"\n[-] ERROR: {e}")
        try: driver.save_screenshot("ig_error.png"); print(">>> Saved 'ig_error.png'! <<<")
        except: pass
    finally:
        driver.quit()

if __name__ == "__main__":
    print("=====================================")
    print("=== Automated Terminal Login Tool ===")
    print("=====================================")
    print("1. Facebook Login")
    print("2. Instagram Login")
    choice = input("\nSelect platform (1 or 2): ").strip()
    
    if choice == "1":
        em = input("Enter Facebook Email/Phone: ")
        pw = input("Enter Facebook Password: ")
        fb_login(em, pw)
    elif choice == "2":
        un = input("Enter Instagram Username: ")
        pw = input("Enter Instagram Password: ")
        ig_login(un, pw)
    else:
        print("Invalid choice.")
