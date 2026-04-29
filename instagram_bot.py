import os
import json
import time
import random
import datetime
import pytz
import sys
import argparse
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI

# ---------------- CONFIGURATION ----------------
SPREADSHEET_ID = "1fUF6jh-xJ67TjNfrzns-6o6wrSlJquhov440VOzuxNM"
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
SHEET_NAME = "Insatragm test OR"

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
            if ws.title.strip() == SHEET_NAME.strip() or "Insta new Master sheet" in ws.title:
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
            "status": col_map.get("status", -1),
            "last_action": col_map.get("last action date", -1),
            "f1": col_map.get("first follow-up", -1),
            "f2": col_map.get("second follow-up", -1),
            "replied": col_map.get("replied", -1)
        }
        
        import collections
        return worksheet, collections.namedtuple('Indices', indices.keys())(**indices)

    except Exception as e:
        print(f"[-] Failed to setup Google Sheets: {e}")
        sys.exit(1)

def get_username_from_url(url):
    return url.strip().rstrip("/").split("/")[-1]

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

def random_delay(min_sec=3, max_sec=5):
    delay = random.uniform(min_sec, max_sec)
    print(f"[*] Sleeping for {delay:.2f} seconds...")
    time.sleep(delay)

def generate_spun_message(base_message, username):
    print("[*] Generating unique message via ChatGPT...")
    prompt = f"""You are a friendly social media outreacher.
Rewrite the following outreach message to sound very natural and casual, making slight variations to avoid spam filters.
Do NOT change the core meaning or the overarching questions asked.
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
        print(f"[-] OpenAI API failed. Falling back to raw template. Error: {e}")
        return base_message.replace("[Name]", username).replace("(brand name)", username)

def check_if_replied(driver, target_username):
    print(f"[*] Checking chat history for replies from {target_username}...")
    try:
        random_delay(2, 4)
        
        # Inbound messages (replies) show the sender's small profile picture (avatar).
        avatars = driver.find_elements(By.XPATH, "//div[@role='row']//img | //div[@role='listbox']//div[@role='row']//img")
        
        for av in avatars:
            try:
                if not av.is_displayed(): continue
                rect = av.rect
                w = rect.get('width', 0)
                h = rect.get('height', 0)
                if 20 <= w <= 40 and 20 <= h <= 40:
                    print(f"[+] Detected a reply from the target user via avatar presence! (Size: {w}x{h})")
                    return True
            except Exception:
                pass
            
        print("[-] No reply detected. Proceeding with message.")
        return False
    except Exception as e:
        print(f"[-] Could not load chat history reliably: {e}")
        return False

def click_follow_button(driver):
    print("[*] Looking for the 'Follow' button...")
    try:
        # Standard follow button on profile
        follow_btn = driver.find_element(By.XPATH, "//button[div/div[text()='Follow']] | //button[div[text()='Follow']] | //div[text()='Follow']")
        if follow_btn.is_displayed():
            driver.execute_script("arguments[0].click();", follow_btn)
            print("[+] Clicked Follow button!")
            random_delay(2, 3)
            return True
    except Exception:
        print("[-] Follow button not found (might already be following).")
    return False

def click_message_button(driver):
    print("[*] Looking for the 'Message' button...")
    try:
        msg_btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.XPATH, "//div[text()='Message' or text()='Send message'] | //div[@role='button'][text()='Message']"))
        )
        msg_btn.click()
        return True
    except TimeoutException:
        try:
            msg_btns = driver.find_elements(By.XPATH, "//div[@role='button']")
            for btn in msg_btns:
                if btn.text.strip().lower() == "message":
                    btn.click()
                    return True
        except Exception: pass
    print("[-] Could not locate 'Message' button. Profile might be private.")
    return False

def type_and_send(driver, message_text):
    try:
        textboxes = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, "//div[@role='textbox' and @contenteditable='true']"))
        )
        visible_textboxes = [tb for tb in textboxes if tb.is_displayed()]
        if not visible_textboxes:
            raise Exception("No visible textboxes found")
            
        message_box = visible_textboxes[-1]
        message_box.click()
        random_delay(1, 2)
        human_type(driver, message_box, message_text)
        random_delay(1, 2)
        
        print("[*] Attempting to Send message...")
        clicked_send = False
        try:
            send_xpaths = ["//div[@role='button' and text()='Send']", "//div[text()='Send']", "//button[text()='Send']"]
            for xp in send_xpaths:
                btns = driver.find_elements(By.XPATH, xp)
                for btn in btns:
                    if btn.is_displayed():
                        btn.click()
                        clicked_send = True
                        break
                if clicked_send: break
        except Exception: pass
            
        if not clicked_send:
            print("[*] Send button not clicked, hitting Enter key instead...")
            message_box.send_keys(Keys.ENTER)
            
        random_delay(2, 4) 
        return True
    except Exception as e:
        print(f"[-] Sending failed: {e}")
        return False

def process_leads(driver, worksheet, cols):
    print("\n===========================================")
    print("=== Processing Sheet Leads & Follow-ups ===")
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
            # Pad row to ensure we don't hit index errors
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

            # User replied, skip
            if replied.lower() == "yes":
                continue

            if status and status.lower() in ["automated inbox", "skip", "error", "completed"]:
                continue

            eligible_for = None
            
            if not status or status.lower() != "sent":
                eligible_for = "new_outreach"
            elif last_action_date_str:
                try:
                    last_action_date = datetime.datetime.strptime(last_action_date_str, "%d-%m-%Y %I:%M %p")
                    last_action_date = karachi_tz.localize(last_action_date)
                    hours_passed = (now_pkt - last_action_date).total_seconds() / 3600.0
                    
                    if hours_passed >= 24 and not first_followup: 
                        eligible_for = "1st_followup"
                    elif hours_passed >= 72 and first_followup.lower() == "sent" and not second_followup: 
                        eligible_for = "2nd_followup"
                    elif second_followup.lower() == "sent":
                        print(f"[*] {name} has received all 3 messages and no reply. Marking as Completed.")
                        safe_gsheet_call(worksheet.update_cell, row_idx, cols.status + 1, "Completed")
                        continue
                except ValueError:
                    pass # Date format wrong, ignore
                    
            if eligible_for:
                print(f"\n[*] Target Found: {name} (Action: {eligible_for})")
                driver.get(profile_url)
                random_delay(3, 5)
                
                # Press escape once on load in case there are persistent tooltips
                try: driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                except: pass

                if eligible_for == "new_outreach":
                    click_follow_button(driver)
                
                if not click_message_button(driver): continue
                random_delay(4, 6)
                
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
                
                # Use ChatGPT to generate the message variant
                spun_msg = generate_spun_message(base_msg, name)
                
                # Smartly inject the audit link directly into the placeholder for MSG_2
                if eligible_for == "1st_followup" and audit_link_url:
                    if "[Insert audit sheet link]" in spun_msg:
                        spun_msg = spun_msg.replace("[Insert audit sheet link]", audit_link_url)
                    else:
                        # Fallback in case ChatGPT stripped out the exact placeholder string when spinning
                        spun_msg += f"\n\nHere’s your listing audit 👇\n{audit_link_url}"
                    
                if type_and_send(driver, spun_msg):
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
                        print(f"[-] CRITICAL: Failed to update sheet perfectly. Error: {e}")

                    messages_sent += 1
                    random_delay(15, 25)
        except Exception as e:
            print(f"[-] Unhandled error during lead processing for row {row_idx}: {e}")
            print("[*] Moving to the next lead...")
            continue
                
    return messages_sent

def main():
    print("====================================")
    print("=== IG Direct Sheet Bot ===")
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
    
    profile_dir = os.path.abspath("./chrome_profile_ig")
    os.makedirs(profile_dir, exist_ok=True)
    
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,1024")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--headless=new")
    
    driver = uc.Chrome(options=options, user_data_dir=profile_dir, version_main=147)
    
    try:
        driver.get("https://www.instagram.com/")
        random_delay(5, 8)
        
        print("[*] Verifying login status...")
        login_required = False
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//svg[@aria-label='Home' or @aria-label='Search' or @aria-label='New post'] | //img[contains(@alt, 'profile picture')] | //a[contains(@href, '/direct/')]"))
            )
        except TimeoutException:
            login_required = True
            
        while login_required:
            print("\n=======================================================")
            print("[!] MANUAL LOG IN REQUIRED: You are not logged into Instagram.")
            print("[!] Please open the automated Chrome window and log in manually.")
            print("[*] The bot will pause and check again in 20 seconds...")
            print("=======================================================\n")
            time.sleep(20)
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//svg[@aria-label='Home' or @aria-label='Search' or @aria-label='New post'] | //img[contains(@alt, 'profile picture')] | //a[contains(@href, '/direct/')]"))
                )
                login_required = False
                print("[+] Login confirmed. Saving profile for all future runs!")
            except TimeoutException:
                pass
        else:
            print("[+] Logged into Instagram successfully from saved profile!")
        
        # Process the leads linearly (Followups & New Outreach mixed dynamically by Date priority)
        process_leads(driver, worksheet, columns)
        print("\n[+] Run complete.")
        
    finally:
        print("[*] Cleaning up and closing browser...")
        driver.quit()
        print("=== Bot Finished ===")

if __name__ == "__main__":
    main()
