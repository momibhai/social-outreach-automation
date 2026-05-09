import time
import os
import shutil
from seleniumbase import SB

def clear_old_profile(profile_dir):
    if os.path.exists(profile_dir):
        print(f"[*] Clearing old profile data from {profile_dir}...")
        try: shutil.rmtree(profile_dir, ignore_errors=True)
        except: pass

def fb_login(email, password):
    profile_dir = "chrome_profile"
    clear_old_profile(profile_dir)
    
    print("\n[*] Starting Facebook Login (Headless)...")
    with SB(uc=True, user_data_dir=profile_dir, headless=True) as sb:
        try:
            sb.open("https://www.facebook.com/")
            sb.sleep(4)
            
            # Dismiss Cookie popup if it blocks the page
            if sb.is_element_visible('button[title*="Allow"]'):
                sb.click('button[title*="Allow"]')
                sb.sleep(2)
            elif sb.is_element_visible('button:contains("Allow all cookies")'):
                sb.click('button:contains("Allow all cookies")')
                sb.sleep(2)
            
            print("[*] Entering credentials...")
            sb.type('input[name="email"]', email)
            sb.type('input[name="pass"]', password)
            
            # Try multiple login button formats
            if sb.is_element_visible('button[name="login"]'):
                sb.click('button[name="login"]')
            elif sb.is_element_visible('#loginbutton'):
                sb.click('#loginbutton')
            else:
                sb.click('button[type="submit"]')
            
            print("[*] Waiting for response...")
            sb.sleep(8)
            
            # Check for 2FA
            if sb.is_element_visible('input[name="approvals_code"]'):
                print("\n[!] Facebook is asking for 2-Factor Authentication (OTP)!")
                otp = input("[>] Please enter the 6-digit OTP code sent to your phone/app: ")
                sb.type('input[name="approvals_code"]', otp)
                sb.click('button[value="Continue"], button[type="submit"]')
                sb.sleep(5)
                
                # Click "Save Browser" if prompted
                if sb.is_element_visible('input[value="Save Browser"]'):
                    sb.click('input[value="Save Browser"]')
                    sb.click('button[value="Continue"]')
                    sb.sleep(3)
            
            print("\n[+] SUCCESS: Facebook profile saved permanently!")
            sb.save_screenshot("fb_success.png")
            print(">>> Saved 'fb_success.png'. Aap usay khol kar dekh sakte hain. <<<")
            
        except Exception as e:
            print(f"\n[-] ERROR: {e}")
            try:
                sb.save_screenshot("fb_error.png")
                print(">>> Saved 'fb_error.png' in your folder! Open it to see exactly why it failed! <<<")
            except: pass

def ig_login(username, password):
    profile_dir = "chrome_profile_ig"
    clear_old_profile(profile_dir)
    
    print("\n[*] Starting Instagram Login (Headless)...")
    with SB(uc=True, user_data_dir=profile_dir, headless=True) as sb:
        try:
            sb.open("https://www.instagram.com/accounts/login/")
            sb.sleep(5)
            
            if sb.is_element_visible('button:contains("Allow all cookies")'):
                sb.click('button:contains("Allow all cookies")')
                sb.sleep(2)
            
            print("[*] Entering credentials...")
            sb.type('input[name="username"]', username)
            sb.type('input[name="password"]', password)
            sb.click('button[type="submit"]')
            
            print("[*] Waiting for response...")
            sb.sleep(8)
            
            # Check for 2FA
            if sb.is_element_visible('input[name="verificationCode"]'):
                print("\n[!] Instagram is asking for 2-Factor Authentication (OTP)!")
                otp = input("[>] Please enter the OTP code sent to your phone/app: ")
                sb.type('input[name="verificationCode"]', otp)
                sb.click('button[type="button"]')
                sb.sleep(5)
                
            print("\n[+] SUCCESS: Instagram profile saved permanently!")
            sb.save_screenshot("ig_success.png")
            
        except Exception as e:
            print(f"\n[-] ERROR: {e}")
            try:
                sb.save_screenshot("ig_error.png")
                print(">>> Saved 'ig_error.png' in your folder! Open it to see exactly why it failed! <<<")
            except: pass

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
