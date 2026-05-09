import os
import time
import random
import datetime
import pytz
import sys
import argparse
import collections

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
from dotenv import load_dotenv

import db_manager as db

load_dotenv()

# ---------------- CONFIGURATION ----------------
SPREADSHEET_ID = "1fUF6jh-xJ67TjNfrzns-6o6wrSlJquhov440VOzuxNM"
SHEET_NAME = "Facebook  Master sheet leads automation"
SERVICE_ACCOUNT_FILE = "service_account.json"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
# -----------------------------------------------

MSG_1 = """Hey [Name],

We've been following your brand for a while and really like what you're building—your Amazon presence is strong.

We also checked your listing recently and noticed a few gaps compared to your top competitors that could be affecting your sales.

If you want, I can share a quick listing-level audit we prepared for you."""

MSG_2 = """Here's your listing audit 👇
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

I'm curious, what stood out to you the most?

Most brands usually notice a few quick wins on the listing side, but the bigger realization is usually around traffic/PPC once they look deeper."""

MSG_2_ALT = "Hey team [Name]! Just wanted to bump this up in case it got lost 😊 We really do love your work and were curious if you're on Amazon? Would love to connect and chat more!"

client = OpenAI(api_key=OPENAI_API_KEY)

def make_logger(session_id):
    def log(msg):
        print(msg, flush=True)
        db.add_log_line(session_id, msg)
    return log

def safe_gsheet_call(func, *args, **kwargs):
    max_retries = 5
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[*] Sheet call failed ({e}). Retrying in 8s... ({attempt+1}/{max_retries})")
                time.sleep(8)
            else:
                print(f"[-] Sheet call failed after {max_retries} attempts.")
                raise e

def get_google_sheet_and_headers():
    print(f"[*] Connecting to Google Sheets [{SHEET_NAME}]...")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        credentials = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scopes)
        gc = gspread.authorize(credentials)
        sh = gc.open_by_key(SPREADSHEET_ID)

        worksheet = None
        for ws in sh.worksheets():
            if ws.title.strip().lower() == SHEET_NAME.strip().lower() or "facebook master" in ws.title.lower():
                worksheet = ws
                print(f"[+] Found sheet: '{ws.title}'")
                break

        if not worksheet:
            print(f"[-] Sheet '{SHEET_NAME}' not found!")
            sys.exit(1)

        header_row = safe_gsheet_call(worksheet.row_values, 1)
        required_cols = ["Status", "Last Action Date", "First Follow-up", "Second Follow-up", "Replied"]
        needs_update = False
        for col in required_cols:
            if col not in header_row:
                header_row.append(col)
                needs_update = True
        if needs_update:
            safe_gsheet_call(worksheet.update, 'A1:Z1', [header_row])
            print("[+] Updated sheet headers.")

        headers = safe_gsheet_call(worksheet.row_values, 1)
        col_map = {h.lower().strip(): idx for idx, h in enumerate(headers)}

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

        return worksheet, collections.namedtuple('Indices', indices.keys())(**indices)

    except Exception as e:
        print(f"[-] Failed to setup Google Sheets: {e}")
        sys.exit(1)

def get_username_from_url(url):
    return url.strip().rstrip("/").split("/")[-1]

def random_delay(min_sec=3, max_sec=5):
    delay = random.uniform(min_sec, max_sec)
    print(f"[*] Sleeping {delay:.1f}s...")
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
    print("[*] Looking for 'Message' button...")
    try:
        msg_btn = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[@role='button'][@aria-label='Message'] | //div[@role='button'][contains(., 'Message')]"))
        )
        driver.execute_script("arguments[0].click();", msg_btn)
        random_delay(2, 3)
        return True
    except Exception as e:
        print(f"[-] 'Message' button not found: {e}")
        return False

def type_and_send_messenger(driver, message_text):
    """Send message in Facebook Messenger popup (bottom-right floating panel)."""
    print("[*] Waiting for Messenger popup to fully load...")
    try:
        # Give the Messenger popup time to render completely
        random_delay(5, 7)

        # Step 1: Check for automated inbox FIRST (before touching anything)
        automated_indicators = [
            "//div[@role='button'][.//span[text()='Get started']]",
            "//div[@role='button'][.//span[text()='Get Started']]",
            "//div[@data-testid='get_started_button']",
            "//span[text()='Tap to send']",
            "//div[text()='Tap to send']",
        ]
        for xp in automated_indicators:
            els = driver.find_elements(By.XPATH, xp)
            if els and any(e.is_displayed() for e in els):
                print("[-] Automated inbox detected. Skipping this profile.")
                return "AUTOMATED"

        # Step 2: Find the textbox using JavaScript position check.
        # The Messenger popup is ALWAYS in the bottom-right corner of the browser.
        # Feed comment boxes are in the center-left of the page.
        # We use screen position to reliably distinguish them.
        message_box = None
        end_time = time.time() + 15
        while time.time() < end_time:
            # Re-check for automated inbox each iteration
            for xp in automated_indicators:
                els = driver.find_elements(By.XPATH, xp)
                if els and any(e.is_displayed() for e in els):
                    print("[-] Automated inbox detected (in loop). Skipping.")
                    return "AUTOMATED"

            # Use JS to find textbox that is in the RIGHT half + BOTTOM half of the screen
            box_el = driver.execute_script("""
                var vw = window.innerWidth;
                var vh = window.innerHeight;
                var boxes = document.querySelectorAll('[role="textbox"][contenteditable="true"]');
                for (var box of boxes) {
                    var rect = box.getBoundingClientRect();
                    var label = (box.getAttribute('aria-label') || '').toLowerCase();
                    // Skip comment boxes and post boxes
                    if (label.includes('comment') || label.includes("what's on your mind") ||
                        label.includes('write a public') || label.includes('write something')) {
                        continue;
                    }
                    // Messenger popup is in the RIGHT half of the screen
                    if (rect.left > vw * 0.45 && rect.top > vh * 0.3 && rect.width > 10) {
                        return box;
                    }
                }
                return null;
            """)
            if box_el:
                message_box = box_el
                break
            time.sleep(1.5)

        if not message_box:
            print("[-] Messenger chat textbox not found in expected position.")
            return False

        print("[+] Messenger textbox found. Typing message...")
        # Extra delay before typing to ensure popup is stable
        random_delay(2, 3)
        driver.execute_script("arguments[0].click();", message_box)
        random_delay(1, 2)
        human_type(driver, message_box, message_text)
        random_delay(3, 5)  # Wait after typing before sending

        # Step 3: Send the message
        try:
            send_btn = driver.find_element(By.XPATH, "//div[@role='button' and @aria-label='Press enter to send']")
            if send_btn.is_displayed():
                driver.execute_script("arguments[0].click();", send_btn)
                print("[+] Message sent via Send button.")
            else:
                message_box.send_keys(Keys.ENTER)
                print("[+] Message sent via Enter key.")
        except Exception:
            message_box.send_keys(Keys.ENTER)
            print("[+] Message sent via Enter key (fallback).")

        random_delay(4, 6)
        return True
    except Exception as e:
        print(f"[-] Failed to send message: {e}")
        return False

def check_if_replied(driver, name):
    """
    Reliable Facebook Messenger reply detection using message position.
    In Messenger popup:
      - Messages WE sent  → appear on the RIGHT side
      - Messages THEY sent (replies) → appear on the LEFT side
    Uses JS position check to avoid false positives from profile avatars.
    """
    print(f"[*] Checking for reply from {name}...")
    try:
        random_delay(2, 3)  # Let chat log load

        replied = driver.execute_script("""
            var vw = window.innerWidth;
            // Messenger popup is bottom-right, received messages appear LEFT within it.
            // We look inside [role=log] or [role=row] containers for left-positioned items.
            var selectors = [
                '[role="log"] [role="row"]',
                '[role="log"] [role="listitem"]',
                '[data-pagelet="MWDialogRoot"] [role="row"]'
            ];
            for (var sel of selectors) {
                var items = document.querySelectorAll(sel);
                for (var item of items) {
                    var rect = item.getBoundingClientRect();
                    var text = (item.innerText || item.textContent || '').trim();
                    // Received messages appear on the LEFT of the Messenger popup.
                    // The popup starts at roughly 60% of screen width.
                    // So LEFT within the popup means rect.left < 85% of vw.
                    // But to be safe we just check the item is in the LEFT half of the popup.
                    // A simpler approach: if rect.left < vw * 0.75 and has real text = reply
                    if (rect.left < vw * 0.78 && rect.width > 20 && text.length > 2) {
                        return true;
                    }
                }
            }
            return false;
        """)

        if replied:
            print(f"[+] Reply detected from {name} (left-side message in Messenger)!")
            return True

    except Exception as e:
        print(f"[-] Reply check error: {e}")

    print("[-] No reply detected.")
    return False

def add_friend_if_possible(driver):
    try:
        follow_btn = driver.find_element(By.XPATH, "//div[@role='button'][@aria-label='Follow' or .//span[text()='Follow']]")
        if follow_btn.is_displayed():
            driver.execute_script("arguments[0].click();", follow_btn)
            print("[+] Follow clicked!")
            random_delay(2, 3)
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            return True
    except Exception:
        pass
    try:
        add_btn = driver.find_element(By.XPATH, "//div[@role='button'][@aria-label='Add Friend' or @aria-label='Add friend' or .//span[text()='Add Friend']]")
        if add_btn.is_displayed():
            driver.execute_script("arguments[0].click();", add_btn)
            print("[+] Friend Request sent!")
            random_delay(2, 3)
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            return True
    except Exception:
        pass
    print("[-] Neither Follow nor Add Friend found.")
    return False

def setup_driver(profile_dir):
    import subprocess, platform, shutil
    print("[*] Cleaning up stale ChromeDriver processes...")
    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill","/F","/IM","chromedriver.exe","/T"], capture_output=True, timeout=5)
        else:
            subprocess.run(["pkill","-9","-f","chromedriver"], capture_output=True)
            subprocess.run(["pkill","-9","-f","chrome"], capture_output=True)
        time.sleep(2)
    except Exception as e:
        print(f"[!] ChromeDriver kill warning: {e}")

    # Remove stale profile lock files AND Local State (to fix uc=True crash)
    for lock in ["SingletonLock", "SingletonCookie", "SingletonSocket", "Local State"]:
        p = os.path.join(profile_dir, lock)
        if os.path.exists(p):
            try: os.remove(p); print(f"[*] Removed lock: {lock}")
            except Exception: pass

    headless = os.environ.get("HEADLESS", "false").lower() == "true"
    print(f"[*] Launching Chrome (headless={headless})...")
    
    options = Options()
    options.add_argument(f"--user-data-dir={os.path.abspath(profile_dir)}")
    options.add_argument("--window-size=1280,1024")
    options.add_argument("--no-sandbox")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--password-store=basic")
    options.add_argument("--remote-debugging-port=0")
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--disable-extensions")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
    return driver

def process_leads(driver, worksheet, cols, session_id, max_new_messages, row_start, row_end):
    log = make_logger(session_id)
    log("\n===========================================")
    log("=== Processing FB Sheet Leads & Follow-ups ===")
    log("===========================================")

    if cols.link == -1 or cols.status == -1:
        log("[-] Necessary columns not found!"); return 0, 0, 0

    all_rows = safe_gsheet_call(worksheet.get_all_values)
    if len(all_rows) <= 1:
        log("[-] Sheet is empty."); return 0, 0, 0

    karachi_tz = pytz.timezone('Asia/Karachi')
    now_pkt = datetime.datetime.now(karachi_tz)
    new_sent = followups_sent = skipped = 0

    data_rows = all_rows[1:]
    start_idx = max(0, row_start - 2)
    end_idx = (row_end - 1) if row_end > 1 else len(data_rows)
    data_rows = data_rows[start_idx:end_idx]

    max_col_idx = max([v for v in [cols.name, cols.link, cols.audit_link,
                       cols.status, cols.last_action, cols.f1, cols.f2,
                       cols.replied] if v != -1]) + 1

    # Statuses that mean "all done" — NEVER open these profiles again
    TERMINAL = {"completed","fb_completed","ig_completed",
                "automated_inbox","automated inbox","skip","error"}

    def parse_row(row):
        r = list(row)
        while len(r) < max_col_idx: r.append("")
        url    = r[cols.link].strip()        if cols.link != -1 else ""
        name   = (r[cols.name].strip()       if cols.name != -1 and r[cols.name]
                  else get_username_from_url(url))
        audit  = (r[cols.audit_link].strip() if cols.audit_link != -1
                                               and cols.audit_link < len(r) else "")
        status = r[cols.status].strip()      if cols.status != -1 else ""
        last   = r[cols.last_action].strip() if cols.last_action != -1 else ""
        f1     = r[cols.f1].strip()          if cols.f1 != -1 else ""
        f2     = r[cols.f2].strip()          if cols.f2 != -1 else ""
        rep    = r[cols.replied].strip()     if cols.replied != -1 else ""
        return url, name, audit, status, last, f1, f2, rep

    def send_fb(row, idx, action, name, url, audit):
        log(f"\n[*] {name} | {action} | Row {idx}")
        driver.get(url); random_delay(4, 6)
        try: driver.find_element(By.TAG_NAME,"body").send_keys(Keys.ESCAPE)
        except Exception: pass

        if action == "new_outreach": add_friend_if_possible(driver)
        if not check_and_click_message(driver):
            db.log_message(session_id,"facebook",name,url,action,"skipped","No msg btn")
            return "skipped"

        if action != "new_outreach" and check_if_replied(driver, name):
            log(f"[+] {name} replied! Marking.")
            safe_gsheet_call(worksheet.update_cell, idx, cols.replied+1, "Yes")
            db.log_message(session_id,"facebook",name,url,action,"replied")
            return "replied"

        base = MSG_1 if action=="new_outreach" else (MSG_2 if audit else MSG_2_ALT) if action=="1st_followup" else MSG_3
        msg = generate_spun_message(base, name)
        if action == "1st_followup" and audit:
            msg = msg.replace("[Insert audit sheet link]", audit) if "[Insert audit sheet link]" in msg else msg+f"\n\nHere's your listing audit 👇\n{audit}"

        result = type_and_send_messenger(driver, msg)
        if result == "AUTOMATED":
            log(f"[-] {name}: Automated inbox.")
            safe_gsheet_call(worksheet.update_cell, idx, cols.status+1, "automated_inbox")
            db.log_message(session_id,"facebook",name,url,action,"skipped","Automated inbox")
            return "skipped"

        if result is True:
            ts = now_pkt.strftime("%d-%m-%Y %I:%M %p")
            log(f"[+] Sent to {name}! Updating sheet...")
            try:
                if action=="new_outreach":
                    safe_gsheet_call(worksheet.update_cell,idx,cols.status+1,"Sent")
                    safe_gsheet_call(worksheet.update_cell,idx,cols.last_action+1,ts)
                elif action=="1st_followup":
                    safe_gsheet_call(worksheet.update_cell,idx,cols.f1+1,"Sent")
                    safe_gsheet_call(worksheet.update_cell,idx,cols.last_action+1,ts)
                elif action=="2nd_followup":
                    safe_gsheet_call(worksheet.update_cell,idx,cols.f2+1,"Sent")
                    safe_gsheet_call(worksheet.update_cell,idx,cols.last_action+1,ts)
            except Exception as e: log(f"[-] Sheet update failed: {e}")
            db.log_message(session_id,"facebook",name,url,action,"sent")
            random_delay(15,25)
            return "sent"
        return "error"

    # ═══ PASS 1: Follow-ups (unlimited, not in daily count) ═══
    log("\n[*] === PASS 1: Follow-ups ===")
    for i, row in enumerate(data_rows):
        idx = i + row_start
        try:
            url,name,audit,status,last,f1,f2,rep = parse_row(row)
            if not url or "facebook.com" not in url: continue
            if not audit or "docs.google.com" not in audit: continue
            if rep.lower()=="yes": continue
            if status.lower() in TERMINAL: continue      # Skip Completed / automated etc.
            # All variants that mean "first message was sent" — covers both old and new status values
            FIRST_SENT = {"sent", "fb_sent", "ig_sent"}
            if status.lower() not in FIRST_SENT: continue

            if f1.lower() in {"sent","f1_sent"} and f2.lower() in {"sent","f2_sent"}:
                log(f"[*] {name}: All 3 done. Marking Completed.")
                safe_gsheet_call(worksheet.update_cell,idx,cols.status+1,"Completed")
                continue

            action = None
            if last:
                try:
                    # Clean up date string before parsing (handle multiple spaces)
                    clean_last = " ".join(last.split())
                    # Support multiple formats just in case Google Sheets changed it
                    for fmt in ["%d-%m-%Y %I:%M %p", "%d/%m/%Y %I:%M %p", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"]:
                        try:
                            dt = datetime.datetime.strptime(clean_last, fmt)
                            break
                        except ValueError:
                            dt = None
                    
                    if dt:
                        dt = karachi_tz.localize(dt)
                        hrs = (now_pkt-dt).total_seconds()/3600.0
                        if not f1 and hrs>=24: action="1st_followup"
                        elif f1.lower() in {"sent","f1_sent"} and not f2 and hrs>=72: action="2nd_followup"
                    else:
                        log(f"[!] Could not parse date format for '{name}': {last}")
                except Exception as e: log(f"[!] Date logic error for {name}: {e}")
            if not action: continue

            r = send_fb(row,idx,action,name,url,audit)
            if r=="sent": followups_sent+=1
            elif r in {"skipped","error"}: skipped+=1
        except Exception as e:
            log(f"[-] Follow-up row {idx} error: {e}"); skipped+=1

    # ═══ PASS 2: New Outreach (strictly limited) ═══
    log(f"\n[*] === PASS 2: New Outreach (limit={max_new_messages}) ===")
    for i, row in enumerate(data_rows):
        if new_sent >= max_new_messages:
            log(f"[!] Limit reached ({max_new_messages}). Stopping."); break
        idx = i + row_start
        try:
            url,name,audit,status,last,f1,f2,rep = parse_row(row)
            if not url or "facebook.com" not in url: skipped+=1; continue
            if not audit or "docs.google.com" not in audit: skipped+=1; continue
            if rep.lower()=="yes": skipped+=1; continue
            if status.lower() in TERMINAL: skipped+=1; continue
            if status.lower() in {"sent","fb_sent"}: skipped+=1; continue

            r = send_fb(row,idx,"new_outreach",name,url,audit)
            if r=="sent": new_sent+=1
            else: skipped+=1
        except Exception as e:
            log(f"[-] New outreach row {idx} error: {e}"); skipped+=1

    return new_sent, followups_sent, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=10, help="Max NEW messages per run")
    parser.add_argument("--row-start", type=int, default=2, help="Sheet row to start from (inclusive)")
    parser.add_argument("--row-end", type=int, default=0, help="Sheet row to end at (inclusive, 0=all)")
    parser.add_argument("--triggered-by", type=str, default="scheduler", help="'scheduler' or 'manual'")
    args, _ = parser.parse_known_args()

    print("====================================")
    print("=== FB Direct Sheet Bot (Selenium) ===")
    print("====================================")
    print(f"[*] Max new messages: {args.max} | Rows: {args.row_start}-{args.row_end or 'END'}")

    worksheet, columns = get_google_sheet_and_headers()

    profile_dir = os.path.abspath("./chrome_profile")
    os.makedirs(profile_dir, exist_ok=True)

    try:
        import subprocess, platform
        if platform.system() != "Windows":
            subprocess.run(["pkill", "-f", "chrome"], capture_output=True)
            time.sleep(2)
    except Exception:
        pass

    session_id = db.create_session(
        platform="facebook",
        row_start=args.row_start,
        row_end=args.row_end,
        daily_limit=args.max,
        triggered_by=args.triggered_by
    )

    log = make_logger(session_id)
    log(f"[*] Session ID: {session_id}")

    driver = None
    try:
        driver = setup_driver(profile_dir)

        driver.get("https://www.facebook.com/")
        random_delay(5, 8)

        log("[*] Verifying Facebook login...")
        login_required = False
        try:
            WebDriverWait(driver, 8).until(
                EC.presence_of_element_located((By.XPATH, "//div[@aria-label='Create' or @aria-label='Messenger'] | //svg[contains(@aria-label, 'Home')]"))
            )
        except TimeoutException:
            login_required = True

        if login_required:
            log("[!] NOT logged in. Profile may be expired. Exiting.")
            db.finish_session(session_id, 0, 0, 0, "error")
            return

        log("[+] Facebook login confirmed!")

        new_sent, followups_sent, skipped = process_leads(
            driver, worksheet, columns, session_id,
            max_new_messages=args.max,
            row_start=args.row_start,
            row_end=args.row_end
        )

        log(f"\n[+] Run complete! New: {new_sent} | Follow-ups: {followups_sent} | Skipped: {skipped}")
        db.finish_session(session_id, new_sent, followups_sent, skipped, "done")

    except Exception as e:
        log(f"[-] Fatal error: {e}")
        db.finish_session(session_id, 0, 0, 0, "error")
    finally:
        if driver:
            log("[*] Closing browser...")
            driver.quit()
        log("=== FB Bot Finished ===")

if __name__ == "__main__":
    main()
