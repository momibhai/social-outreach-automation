import os
import json
import time
import random
import shutil
import datetime
import pytz
import sys
import argparse
import urllib.parse
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from selenium.webdriver.common.keys import Keys
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
import collections

# ---------------- CONFIGURATION ----------------
SPREADSHEET_ID = "1fUF6jh-xJ67TjNfrzns-6o6wrSlJquhov440VOzuxNM"
SHEET_NAME = "Facebook  Master sheet leads automation"
COOKIES_FILE = "facebook_cookies.json"
SERVICE_ACCOUNT_FILE = "service_account.json"
import os
from dotenv import load_dotenv
load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--max", type=int, default=10)
args, unknown = parser.parse_known_args()
MAX_MESSAGES_PER_RUN = args.max

MSG_1 = """Hey [Name],

We’ve been following your brand for a while and really like what you’re building—your Amazon presence is strong.

We also checked your listing recently and noticed a few gaps compared to your top competitors that could be affecting your sales.

If you want, I can share a quick listing-level audit we prepared for you."""

MSG_2 = """Here’s your listing audit 👇
[Insert audit sheet link]

Also, I recorded a quick walkthrough so you know exactly how to read it:
https://www.loom.com/share/23619178401945979eb7f3af09484673

Quick context so you understand the full picture:
Amazon growth has 2 core parts:

Listing optimization (conversion improvement)
PPC + traffic system (scaling + keyword dominance)

This audit mainly covers the listing side, but in most cases the bigger growth lever is PPC structure and keyword strategy.

If you want, we can also prepare a deeper PPC + scaling audit showing exactly how your ads could perform better and where revenue is being left on the table."""

MSG_3 = """Hey, just wanted to check—did you get a chance to go through the audit?

I’m curious, what stood out to you the most?

Most brands usually notice a few quick wins on the listing side, but the bigger realization is usually around traffic/PPC once they look deeper."""

MSG_2_ALT = "Hey team [Name]! Just wanted to bump this up in case it got lost 😊 We really do love your work and were curious if you're on Amazon? Would love to connect and chat more!"

client = OpenAI(api_key=OPENAI_API_KEY)
# -----------------------------------------------

def safe_gsheet_call(func, *args, **kwargs):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[*] Sheet update failed ({e}). Retrying in 5 seconds...")
                time.sleep(5)
            else:
                print(f"[-] Sheet update failed after {max_retries} attempts.")
                raise e

def get_google_sheet_and_headers():
    print(f"[*] Connecting to Google Sheets [{SHEET_NAME}]...")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(SPREADSHEET_ID)
        
        # Try finding the exact sheet or by fallback
        worksheet = None
        for ws in sh.worksheets():
            if ws.title.strip().lower() == SHEET_NAME.strip().lower() or "facebook master" in ws.title.lower():
                worksheet = ws
                print(f"[+] Found sheet: '{ws.title}'")
                break
                
        if not worksheet:
            print(f"[-] Sheet '{SHEET_NAME}' not found! Creating new sheet...")
            worksheet = sh.add_worksheet(title=SHEET_NAME, rows="1000", cols="10")
            worksheet.append_row(["Name", "Screenshot", "Link"])

        # Dynamically map the columns
        header_row = safe_gsheet_call(worksheet.row_values, 1)
        required_cols = ["Status", "Last Action Date", "First Follow-up", "Second Follow-up", "Replied"]
        needs_update = False
        
        for col in required_cols:
            if col not in header_row:
                header_row.append(col)
                needs_update = True
                
        if needs_update:
            safe_gsheet_call(worksheet.update, 'A1:Z1', [header_row])
            print("[+] Updated sheet headers with required tracking columns.")

        # Re-fetch headers to get mapping
        headers = safe_gsheet_call(worksheet.row_values, 1)
        col_map = {h.lower().strip(): idx for idx, h in enumerate(headers)}
        
        # Determine specific columns
        indices = {
            "name": col_map.get("seller name", col_map.get("name", -1)),
            "link": col_map.get("profile url", col_map.get("link", -1)),
            "audit_link": col_map.get("audit link", -1),
            "status": col_map.get("status", col_map.get("status", -1)),
            "last_action": col_map.get("last action date", -1),
            "f1": col_map.get("first follow-up", -1),
            "f2": col_map.get("second follow-up", -1),
            "replied": col_map.get("replied", -1)
        }
        
        return worksheet, collections.namedtuple('Indices', indices.keys())(**indices)

    except Exception as e:
        print(f"[-] Failed to setup Google Sheets: {e}")
        sys.exit(1)

def get_username_from_url(url):
    return url.strip().rstrip("/").split("/")[-1]

def random_delay(min_sec=3, max_sec=5):
    delay = random.uniform(min_sec, max_sec)
    print(f"[*] Sleeping for {delay:.2f} seconds...")
    time.sleep(delay)

def human_type(driver, element, text):
    lines = text.split('\n')
    for i, line in enumerate(lines):
        for char in line:
            if ord(char) > 0xFFFF:
                driver.execute_script("document.execCommand('insertText', false, arguments[0]);", char)
            else:
                try:
                    element.send_keys(char)
                except Exception:
                    driver.execute_script("document.execCommand('insertText', false, arguments[0]);", char)
            time.sleep(random.uniform(0.02, 0.08))
        if i < len(lines) - 1:
            element.send_keys(Keys.SHIFT, Keys.RETURN)
            time.sleep(0.1)

def generate_spun_message(base_message, username):
    print("[*] Generating unique message via ChatGPT...")
    prompt = f"""You are a friendly social media outreacher on Facebook.
Rewrite the following outreach message to sound very natural and casual, making slight variations to avoid spam filters.
Keep the exact same warm tone and emojis if possible.
In place of [Name] or (brand name), insert exactly '{username}'.
The message to rewrite is:
"{base_message}"
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[-] OpenAI API failed. Falling back. Error: {e}")
        return base_message.replace("[Name]", username)

def ensure_target_profile(driver, target_name="Syed Hur Abbas"):
    print(f"[*] Verifying active account profile is '{target_name}'...")
    try:
        try:
            account_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//svg[@aria-label='Your profile'] | //div[@role='button'][@aria-label='Account'] | //div[@aria-label='Your profile'] | //div[@aria-label='Menu']"))
            )
            account_btn.click()
            random_delay(2, 3)
        except TimeoutException:
            print("[-] Could not find the Account menu button.")
            return False
        
        correct_profile_active = False
        try:
            active_profile_spans = driver.find_elements(By.XPATH, "//div[@role='menu']//a[@href='/me/']//span")
            for span in active_profile_spans:
                if target_name.lower() in span.text.lower():
                    correct_profile_active = True
                    break
        except Exception:
            pass
            
        if correct_profile_active:
            print(f"[+] '{target_name}' is already active.")
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            return True
            
        print(f"[*] '{target_name}' not active. Attempting to switch profiles...")
        try:
            see_all = driver.find_element(By.XPATH, "//span[contains(text(), 'See all profiles')]")
            see_all.click()
            random_delay(2, 3)
        except NoSuchElementException:
            pass 
            
        try:
            target_profile_btn = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, f"//span[text()='{target_name}']"))
            )
            driver.execute_script("arguments[0].click();", target_profile_btn)
            print(f"[+] Switching to profile '{target_name}'... waiting for reload.")
            random_delay(8, 12)
            return True
        except TimeoutException:
            try:
                fallback_btn = driver.find_element(By.XPATH, f"//span[contains(text(), '{target_name}')]")
                driver.execute_script("arguments[0].click();", fallback_btn)
                print(f"[+] Switched to profile using partial match... waiting for reload.")
                random_delay(8, 12)
                return True
            except NoSuchElementException:
                print(f"[-] Complete failure finding profile '{target_name}' button in menu.")
                try: driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE) 
                except: pass
                return False
    except Exception as e:
        print(f"[-] Could not verify or switch profile: {e}")
        try: driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception: pass
    return False

def add_friend_if_possible(driver):
    print("[*] Attempting to Follow or Add Friend...")
    try:
        try:
            # Strictly match 'Follow' to prevent clicking 'Following' which opens the settings dialog
            follow_btn = driver.find_element(By.XPATH, "//div[@role='button'][@aria-label='Follow' or .//span[text()='Follow']]")
            if follow_btn.is_displayed():
                driver.execute_script("arguments[0].click();", follow_btn)
                print("[+] Follow button clicked!")
                random_delay(2, 4)
                # Press Escape just in case any dialog box pops up
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                return True
        except NoSuchElementException:
            pass

        try:
            # Strictly match 'Add Friend' or 'Add friend'
            add_btn = driver.find_element(By.XPATH, "//div[@role='button'][@aria-label='Add Friend' or @aria-label='Add friend' or .//span[text()='Add Friend'] or .//span[text()='Add friend']]")
            if add_btn.is_displayed():
                driver.execute_script("arguments[0].click();", add_btn)
                print("[+] Friend Request sent!")
                random_delay(2, 4)
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                return True
        except NoSuchElementException:
            pass
        print("[-] Neither 'Follow' nor 'Add Friend' button found (or profile already followed).")
    except Exception as e:
        print(f"[-] Error trying to Follow/Add Friend: {e}")
    return False

def close_all_chat_tabs(driver):
    try:
        close_btns = driver.find_elements(By.XPATH, "//div[@aria-label='Close chat' and @role='button']")
        for btn in close_btns:
            if btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.5)
    except Exception:
        pass

def check_and_click_message(driver):
    close_all_chat_tabs(driver)
    print("[*] Looking for the 'Message' button...")
    try:
        msg_btn = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.XPATH, "//div[@role='button'][@aria-label='Message'] | //div[@role='button'][contains(., 'Message')]"))
        )
        # Using Javascript click to avoid ElementClickInterceptedException if a dialog is floating above
        driver.execute_script("arguments[0].click();", msg_btn)
        random_delay(2, 3)
        return True
    except Exception as e:
        print(f"[-] 'Message' button not found or could not be clicked: {e}")
        return False

def type_and_send_messenger(driver, message_text):
    print("[*] Waiting for Messenger window to load...")
    try:
        try:
            close_btn = driver.find_element(By.XPATH, "//div[@role='button' and @aria-label='Close']")
            if close_btn.is_displayed():
                close_btn.click()
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                random_delay(1, 2)
        except NoSuchElementException:
            pass
        
        # Check for message box or 'Get started' automated inbox
        end_time = time.time() + 10
        message_box = None
        while time.time() < end_time:
            # Check if Get started button exists and is visible
            get_started = driver.find_elements(By.XPATH, "//div[@role='button'][.//span[text()='Get started' or text()='Get Started'] or text()='Get started' or text()='Get Started']")
            if get_started and any(btn.is_displayed() for btn in get_started):
                print("[-] Automated inbox detected ('Get started'). Cannot send custom message.")
                return "AUTOMATED"
                
            textboxes = driver.find_elements(By.XPATH, "//div[@role='textbox' and @contenteditable='true']")
            visible_textboxes = [tb for tb in textboxes if tb.is_displayed()]
            if visible_textboxes:
                message_box = visible_textboxes[-1] # Pick the last one to avoid comment boxes on feed
                break
                
            time.sleep(1)
            
        if not message_box:
            print("[-] Message text box did not appear.")
            return False
            
        message_box.click()
        random_delay(1, 2)
        human_type(driver, message_box, message_text)
        random_delay(2, 3)
        
        try:
            send_btn = driver.find_element(By.XPATH, "//div[@role='button' and @aria-label='Press enter to send']")
            if send_btn.is_displayed():
                send_btn.click()
                print("[+] Message sent successfully!")
            else:
                print("[*] Send button not visible, hitting Enter...")
                message_box.send_keys(Keys.ENTER)
        except Exception:
            message_box.send_keys(Keys.ENTER)
        
        random_delay(3, 5)
        return True
    except Exception as e:
        print(f"[-] Failed to send message: {e}")
        return False

def check_if_replied(driver, name):
    print(f"[*] Checking for replies in the chat from {name}...")
    try:
        random_delay(2, 4)
        # Search specifically inside role='row' which represents messages in the chat tab
        avatars = driver.find_elements(By.XPATH, "//div[@role='row']//image | //div[@role='row']//img")
        for av in avatars:
            try:
                if not av.is_displayed(): continue
                rect = av.rect
                w = rect.get('width', 0)
                h = rect.get('height', 0)
                # Filtering out tiny "seen" icons (<20px) and large link preview embedded images (>50px)
                # The user avatar profile picture next to a reply is specifically 28x28 or 36x36 in Facebook Messenger
                if 20 < w < 50 and 20 < h < 50:
                    print(f"[+] Detected a reply from {name} via avatar presence! (Size: {w}x{h})")
                    return True
            except Exception:
                pass
    except Exception as e:
        print(f"[-] Could not reliably check for replies: {e}")
    print("[-] No reply detected. Proceeding with message.")
    return False

def process_leads(driver, worksheet, cols):
    print("\n===========================================")
    print("=== Processing FB Sheet Leads & Follow-ups ===")
    print("===========================================")
    
    if cols.link == -1 or cols.status == -1:
        print("[-] Failed to find necessary columns! Ensure 'Link' and 'Status' columns exist.")
        return 0

    all_rows = safe_gsheet_call(worksheet.get_all_values)
    if len(all_rows) <= 1:
        print("[-] Sheet is empty.")
        return 0
        
    karachi_tz = pytz.timezone('Asia/Karachi')
    now_pkt = datetime.datetime.now(karachi_tz)
    messages_sent = 0
    max_cols = max([cols.name, cols.link, cols.audit_link, cols.status, cols.last_action, cols.f1, cols.f2, cols.replied]) + 1
    
    for idx, row in enumerate(all_rows[1:]):
        if messages_sent >= MAX_MESSAGES_PER_RUN:
            print("[!] Limit reached for this run.")
            break
            
        row_idx = idx + 2
        try:
            while len(row) < max_cols: row.append("")
                
            profile_url = row[cols.link].strip() if row[cols.link] else ""
            if not profile_url or not profile_url.startswith("http"):
                continue

            name = row[cols.name].strip() if cols.name != -1 and row[cols.name] else get_username_from_url(profile_url)
            audit_link_url = row[cols.audit_link].strip() if cols.audit_link != -1 and cols.audit_link < len(row) else ""
            status = row[cols.status].strip() if cols.status != -1 else ""
            last_action_date_str = row[cols.last_action].strip() if cols.last_action != -1 else ""
            first_followup = row[cols.f1].strip() if cols.f1 != -1 else ""
            second_followup = row[cols.f2].strip() if cols.f2 != -1 else ""
            replied = row[cols.replied].strip() if cols.replied != -1 else ""
            
            if not audit_link_url or "docs.google.com" not in audit_link_url:
                continue

            if replied.lower() == "yes":
                continue

            # Skip explicitly marked statuses
            if status and status.lower() in ["automated inbox", "skip", "error", "completed"]:
                continue

            eligible_for = None
            
            if not status or status.lower() != "sent":
                eligible_for = "new_outreach"
            elif last_action_date_str:
                try:
                    last_dt = datetime.datetime.strptime(last_action_date_str, "%d-%m-%Y %I:%M %p")
                    last_dt = karachi_tz.localize(last_dt)
                    hours_passed = (now_pkt - last_dt).total_seconds() / 3600.0
                    
                    if hours_passed >= 24 and not first_followup: 
                        eligible_for = "1st_followup"
                    elif hours_passed >= 72 and first_followup.lower() == "sent" and not second_followup: 
                        eligible_for = "2nd_followup"
                    elif second_followup.lower() == "sent":
                        print(f"[*] {name} has received all 3 messages and no reply. Marking as Completed.")
                        safe_gsheet_call(worksheet.update_cell, row_idx, cols.status + 1, "Completed")
                        continue
                except ValueError:
                    pass 
                    
            if eligible_for:
                print(f"\n[*] Target Found: {name} (Action: {eligible_for})")
                driver.get(profile_url)
                random_delay(4, 6)
                
                # Press escape once on load in case there are persistent tooltips
                try: driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                except: pass
                
                if eligible_for == "new_outreach":
                    add_friend_if_possible(driver)
                
                if not check_and_click_message(driver): continue
                
                if eligible_for != "new_outreach" and check_if_replied(driver, name):
                    print(f"[+] User {name} replied! Marking as Replied.")
                    safe_gsheet_call(worksheet.update_cell, row_idx, cols.replied + 1, "Yes")
                    continue
                    
                if eligible_for == "new_outreach":
                    base_msg = MSG_1
                elif eligible_for == "1st_followup":
                    base_msg = MSG_2 if audit_link_url else MSG_2_ALT
                else:
                    base_msg = MSG_3
                
                spun_msg = generate_spun_message(base_msg, name)
                
                # Smartly inject the audit link directly into the placeholder for MSG_2
                if eligible_for == "1st_followup" and audit_link_url:
                    if "[Insert audit sheet link]" in spun_msg:
                        spun_msg = spun_msg.replace("[Insert audit sheet link]", audit_link_url)
                    else:
                        spun_msg += f"\n\nHere’s your listing audit 👇\n{audit_link_url}"
                        
                send_result = type_and_send_messenger(driver, spun_msg)
                
                if send_result == "AUTOMATED":
                    print(f"[-] Marking {name} as 'Automated Inbox' in sheet...")
                    try:
                        safe_gsheet_call(worksheet.update_cell, row_idx, cols.status + 1, "Automated Inbox")
                    except Exception as e:
                        print(f"[-] Failed to update sheet with Automated Inbox status: {e}")
                    continue
                    
                if send_result == True:
                    print(f"[+] Message sent! Updating sheet...")
                    
                    time_str = now_pkt.strftime("%d-%m-%Y %I:%M %p")
                    
                    try:
                        if eligible_for == "new_outreach":
                            safe_gsheet_call(worksheet.update_cell, row_idx, cols.status + 1, "Sent")
                            safe_gsheet_call(worksheet.update_cell, row_idx, cols.last_action + 1, time_str)
                        elif eligible_for == "1st_followup":
                            safe_gsheet_call(worksheet.update_cell, row_idx, cols.f1 + 1, "Sent")
                            safe_gsheet_call(worksheet.update_cell, row_idx, cols.last_action + 1, time_str)
                        elif eligible_for == "2nd_followup":
                            safe_gsheet_call(worksheet.update_cell, row_idx, cols.f2 + 1, "Sent")
                            safe_gsheet_call(worksheet.update_cell, row_idx, cols.last_action + 1, time_str)
                    except Exception as e:
                        print(f"[-] CRITICAL: Message sent but sheet failed to update: {e}")

                    messages_sent += 1
                    random_delay(15, 25)
        except Exception as e:
            print(f"[-] Unhandled error during lead processing for row {row_idx}: {e}")
            print("[*] Moving to the next lead...")
            continue
            
    return messages_sent
                
    return messages_sent

def main():
    print("====================================")
    print("=== FB Direct Sheet Bot ===")
    print("====================================")
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, help="Max messages per run")
    args = parser.parse_args()
    
    global MAX_MESSAGES_PER_RUN
    if args.max:
        MAX_MESSAGES_PER_RUN = args.max
        print(f"[*] Set max messages to {MAX_MESSAGES_PER_RUN}")
        
    worksheet, columns = get_google_sheet_and_headers()
    print("\n[*] Launching undetectable browser safely with persistent profile...")
    
    profile_dir = os.path.abspath("./chrome_profile")
    os.makedirs(profile_dir, exist_ok=True)
    
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,1024")
    options.add_argument("--disable-popup-blocking")
    # --- Robust Cleanup to prevent SessionNotCreated errors ---
    import subprocess
    try:
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/T"], capture_output=True)
        subprocess.run(["taskkill", "/F", "/IM", "chromedriver.exe", "/T"], capture_output=True)
    except: pass
    
    uc_path = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "undetected_chromedriver")
    if os.path.exists(uc_path):
        try: shutil.rmtree(uc_path)
        except: pass
    # ---------------------------------------------------------

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless=new")
    options.add_argument("--remote-debugging-port=0")
    driver = uc.Chrome(options=options, user_data_dir=profile_dir, version_main=147)
    
    try:
        driver.get("https://www.facebook.com/")
        random_delay(5, 8)
        
        print("[*] Verifying login status...")
        login_required = False
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Create' or @aria-label='Messenger'] | //svg[contains(@aria-label, 'Home')]"))
            )
        except TimeoutException:
            login_required = True
            
        while login_required:
            print("\n=======================================================")
            print("[!] MANUAL LOG IN REQUIRED: You are not logged into Facebook.")
            print("[!] Please open the automated Chrome window and log in manually.")
            print("[*] The bot will pause and check again in 20 seconds...")
            print("=======================================================\n")
            time.sleep(20)
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Create' or @aria-label='Messenger'] | //svg[contains(@aria-label, 'Home')]"))
                )
                login_required = False
                print("[+] Login confirmed. Saving profile for all future runs!")
            except TimeoutException:
                pass
        else:
            print("[+] Logged into Facebook successfully from saved profile!")
        
        ensure_target_profile(driver, "Syed Hur Abbas")
        
        process_leads(driver, worksheet, columns)
        print("\n[+] Run complete.")
        
    finally:
        print("[*] Cleaning up and closing browser...")
        driver.quit()
        print("=== Bot Finished ===")

if __name__ == "__main__":
    main()
