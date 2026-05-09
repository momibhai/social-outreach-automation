import os
import json
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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
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
SHEET_NAME = "Insatragm test OR"
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
            if ws.title.strip() == SHEET_NAME.strip() or "insta" in ws.title.lower():
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
    print("[*] Generating message via ChatGPT...")
    prompt = f"""You are a friendly social media outreacher on Instagram.
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
        print(f"[-] OpenAI failed. Falling back. Error: {e}")
        return base_message.replace("[Name]", username)

def click_follow_button(driver):
    print("[*] Looking for Follow button...")
    try:
        follow_btn = driver.find_element(By.XPATH, "//button[div/div[text()='Follow']] | //button[div[text()='Follow']]")
        if follow_btn.is_displayed():
            driver.execute_script("arguments[0].click();", follow_btn)
            print("[+] Follow clicked!")
            random_delay(2, 3)
            return True
    except Exception:
        print("[-] Follow button not found.")
    return False

def click_message_button(driver):
    print("[*] Looking for Message button on IG profile...")
    # Instagram DM button XPath patterns
    xpaths = [
        "//div[@role='button'][.//div[text()='Message']]",
        "//a[contains(@href, '/direct/')]//div[text()='Message']",
        "//button[text()='Message']",
        "//div[text()='Message' and @role='button']",
        "//span[text()='Message']//ancestor::div[@role='button']",
    ]
    for xp in xpaths:
        try:
            btn = WebDriverWait(driver, 5).until(EC.element_to_be_clickable((By.XPATH, xp)))
            driver.execute_script("arguments[0].click();", btn)
            print(f"[+] Message button clicked!")
            random_delay(3, 5)  # Wait for DM dialog to fully open
            return True
        except TimeoutException:
            pass
        except Exception:
            pass
    # Last resort: iterate all buttons looking for 'Message' text
    try:
        btns = driver.find_elements(By.XPATH, "//div[@role='button']")
        for btn in btns:
            if btn.text.strip() == "Message" and btn.is_displayed():
                driver.execute_script("arguments[0].click();", btn)
                print("[+] Message button clicked via fallback!")
                random_delay(3, 5)
                return True
    except Exception:
        pass
    print("[-] Message button not found.")
    return False

def type_and_send(driver, message_text):
    """Type and send a message in the Instagram DM chat dialog."""
    print("[*] Waiting for Instagram DM text box...")
    try:
        # IG DM compose box: look inside the dialog/thread view
        message_box = None
        end_time = time.time() + 15
        while time.time() < end_time:
            candidates = driver.find_elements(By.XPATH,
                "//div[@role='textbox' and @contenteditable='true' "
                "and not(contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'search'))"
                " and not(contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'comment'))]"
            )
            visible = [c for c in candidates if c.is_displayed()]
            if visible:
                message_box = visible[-1]
                break
            time.sleep(1)

        if not message_box:
            print("[-] IG DM textbox not found.")
            return False

        print("[+] DM text box found. Typing...")
        message_box.click()
        random_delay(1, 2)
        human_type(driver, message_box, message_text)
        random_delay(1, 2)

        # Try clicking Send button first
        clicked_send = False
        send_xpaths = [
            "//div[@role='button' and text()='Send']",
            "//div[@role='button'][.//span[text()='Send']]",
            "//button[text()='Send']",
        ]
        for xp in send_xpaths:
            try:
                btns = driver.find_elements(By.XPATH, xp)
                for btn in btns:
                    if btn.is_displayed():
                        btn.click()
                        clicked_send = True
                        print("[+] Message sent via Send button.")
                        break
                if clicked_send:
                    break
            except Exception:
                pass

        if not clicked_send:
            message_box.send_keys(Keys.ENTER)
            print("[+] Message sent via Enter key.")

        random_delay(2, 4)
        return True
    except Exception as e:
        print(f"[-] IG send failed: {e}")
        return False

def check_if_replied(driver, name):
    """
    Reliable Instagram reply detection using message position.
    In Instagram DM threads:
      - Messages WE sent  → appear on the RIGHT side of the screen
      - Messages THEY sent (replies) → appear on the LEFT side
    We use JS to detect any bubble positioned in the LEFT portion of the viewport.
    This completely avoids the avatar false-positive issue.
    """
    print(f"[*] Checking for reply from {name}...")
    try:
        random_delay(3, 4)  # Let the DM thread fully load

        replied = driver.execute_script("""
            var vw = window.innerWidth;
            // Instagram DM rows / listitems contain message bubbles.
            // Received messages (from them) are anchored to the left.
            // We check multiple container selectors for robustness.
            var selectors = [
                '[role="main"] [role="row"]',
                '[role="main"] [role="listitem"]',
                '[role="dialog"] [role="row"]',
                '[role="dialog"] [role="listitem"]'
            ];
            for (var sel of selectors) {
                var items = document.querySelectorAll(sel);
                for (var item of items) {
                    var rect = item.getBoundingClientRect();
                    var text = (item.innerText || item.textContent || '').trim();
                    // LEFT-anchored bubble with real text = reply from them
                    if (rect.left < vw * 0.40 && rect.width > 20 && text.length > 2) {
                        return true;
                    }
                }
            }
            return false;
        """)

        if replied:
            print(f"[+] Reply detected from {name} (left-side message bubble)!")
            return True

    except Exception as e:
        print(f"[-] Reply check error: {e}")

    print("[-] No reply detected.")
    return False

def setup_driver(profile_dir):
    import subprocess, platform
    # Only kill chromedriver, NOT all chrome.exe (would kill user's browser)
    print("[*] Cleaning up stale ChromeDriver processes...")
    try:
        if platform.system() == "Windows":
            subprocess.run(["taskkill","/F","/IM","chromedriver.exe","/T"],
                          capture_output=True, timeout=5)
        else:
            subprocess.run(["pkill","-9","-f","chromedriver"], capture_output=True)
            subprocess.run(["pkill","-9","-f","chrome"], capture_output=True)
        time.sleep(2)
    except Exception as e:
        print(f"[!] ChromeDriver kill warning: {e}")

    # Remove all stale lock files
    for lock in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
        p = os.path.join(profile_dir, lock)
        if os.path.exists(p):
            try: os.remove(p); print(f"[*] Removed lock: {lock}")
            except Exception: pass

    headless = os.environ.get("HEADLESS", "false").lower() == "true"
    print(f"[*] Launching Chrome via SeleniumBase (headless={headless})...")
    
    from seleniumbase import Driver
    driver = Driver(
        uc=True, 
        user_data_dir=profile_dir, 
        headless=headless, 
        no_sandbox=True, 
        disable_gpu=True,
        chromium_arg="--disable-dev-shm-usage,--password-store=basic"
    )
    
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def process_leads(driver, worksheet, cols, session_id, max_new_messages, row_start, row_end):
    log = make_logger(session_id)
    log("\n===========================================")
    log("=== Processing IG Sheet Leads & Follow-ups ===")
    log("===========================================")

    if cols.link == -1 or cols.status == -1:
        log("[-] Necessary columns not found!")
        return 0, 0, 0

    all_rows = safe_gsheet_call(worksheet.get_all_values)
    if len(all_rows) <= 1:
        log("[-] Sheet is empty.")
        return 0, 0, 0

    karachi_tz = pytz.timezone('Asia/Karachi')
    now_pkt = datetime.datetime.now(karachi_tz)
    new_sent = 0
    followups_sent = 0
    skipped = 0

    data_rows = all_rows[1:]
    start_idx = max(0, row_start - 2)
    end_idx = (row_end - 1) if row_end > 1 else len(data_rows)
    data_rows = data_rows[start_idx:end_idx]

    max_col_idx = max([v for v in [cols.name, cols.link, cols.audit_link, cols.status, cols.last_action, cols.f1, cols.f2, cols.replied] if v != -1]) + 1

    # All terminal statuses — NEVER process these again
    TERMINAL = {"completed", "ig_completed", "fb_completed", "automated_inbox",
                "skip", "error", "automated inbox"}

    def parse_row(row):
        r = list(row)
        while len(r) < max_col_idx:
            r.append("")
        profile_url = r[cols.link].strip() if r[cols.link] else ""
        name = r[cols.name].strip() if cols.name != -1 and r[cols.name] else get_username_from_url(profile_url)
        audit_link_url = r[cols.audit_link].strip() if cols.audit_link != -1 and cols.audit_link < len(r) else ""
        status = r[cols.status].strip() if cols.status != -1 else ""
        last_action_str = r[cols.last_action].strip() if cols.last_action != -1 else ""
        f1 = r[cols.f1].strip() if cols.f1 != -1 else ""
        f2 = r[cols.f2].strip() if cols.f2 != -1 else ""
        replied = r[cols.replied].strip() if cols.replied != -1 else ""
        return profile_url, name, audit_link_url, status, last_action_str, f1, f2, replied

    def send_ig_message(row, actual_row_idx, eligible_for, name, profile_url, audit_link_url):
        """Open IG profile, check reply, send message, update sheet. Returns 'sent'/'skipped'/'replied'/'error'."""
        log(f"\n[*] Target: {name} | Action: {eligible_for} | Row: {actual_row_idx}")
        driver.get(profile_url)
        random_delay(3, 5)
        try:
            driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        except Exception:
            pass

        if eligible_for == "new_outreach":
            click_follow_button(driver)

        if not click_message_button(driver):
            db.log_message(session_id, "instagram", name, profile_url, eligible_for, "skipped", "Message button not found")
            return "skipped"

        random_delay(3, 5)

        # Check for reply before sending any follow-up
        if eligible_for != "new_outreach":
            if check_if_replied(driver, name):
                log(f"[+] {name} replied! Marking Replied=Yes.")
                safe_gsheet_call(worksheet.update_cell, actual_row_idx, cols.replied + 1, "Yes")
                db.log_message(session_id, "instagram", name, profile_url, eligible_for, "replied")
                return "replied"

        if eligible_for == "new_outreach":
            base_msg = MSG_1
        elif eligible_for == "1st_followup":
            base_msg = MSG_2 if audit_link_url else MSG_2_ALT
        else:
            base_msg = MSG_3

        spun_msg = generate_spun_message(base_msg, name)
        if eligible_for == "1st_followup" and audit_link_url:
            if "[Insert audit sheet link]" in spun_msg:
                spun_msg = spun_msg.replace("[Insert audit sheet link]", audit_link_url)
            else:
                spun_msg += f"\n\nHere's your listing audit 👇\n{audit_link_url}"

        if type_and_send(driver, spun_msg):
            time_str = now_pkt.strftime("%d-%m-%Y %I:%M %p")
            log(f"[+] Message sent to {name}! Updating sheet...")
            try:
                if eligible_for == "new_outreach":
                    safe_gsheet_call(worksheet.update_cell, actual_row_idx, cols.status + 1, "Sent")
                    safe_gsheet_call(worksheet.update_cell, actual_row_idx, cols.last_action + 1, time_str)
                elif eligible_for == "1st_followup":
                    safe_gsheet_call(worksheet.update_cell, actual_row_idx, cols.f1 + 1, "Sent")
                    safe_gsheet_call(worksheet.update_cell, actual_row_idx, cols.last_action + 1, time_str)
                elif eligible_for == "2nd_followup":
                    safe_gsheet_call(worksheet.update_cell, actual_row_idx, cols.f2 + 1, "Sent")
                    safe_gsheet_call(worksheet.update_cell, actual_row_idx, cols.last_action + 1, time_str)
            except Exception as e:
                log(f"[-] CRITICAL: Sheet update failed after send: {e}")
            db.log_message(session_id, "instagram", name, profile_url, eligible_for, "sent")
            random_delay(15, 25)
            return "sent"

        db.log_message(session_id, "instagram", name, profile_url, eligible_for, "error", "Send failed")
        return "error"

    # ── PASS 1: Follow-ups (NOT counted against daily limit) ──
    log("\n[*] === PASS 1: Checking Pending Follow-ups ===")
    for slice_idx, row in enumerate(data_rows):
        actual_row_idx = slice_idx + row_start
        try:
            profile_url, name, audit_link_url, status, last_action_str, f1, f2, replied = parse_row(row)
            if not profile_url or "instagram.com" not in profile_url: continue
            if not audit_link_url or "docs.google.com" not in audit_link_url: continue
            if replied.lower() == "yes": continue
            if status.lower() in TERMINAL: continue
            # Only rows where first message was already sent
            if status.lower() not in ["sent", "ig_sent"]: continue

            # Mark completed if all 3 done
            if f1.lower() in ["sent", "f1_sent"] and f2.lower() in ["sent", "f2_sent"]:
                log(f"[*] {name}: All 3 messages done. Marking Completed.")
                safe_gsheet_call(worksheet.update_cell, actual_row_idx, cols.status + 1, "Completed")
                continue

            eligible_for = None
            if last_action_str:
                try:
                    # Clean up date string before parsing (handle multiple spaces)
                    clean_last = " ".join(last_action_str.split())
                    # Support multiple formats just in case Google Sheets changed it
                    for fmt in ["%d-%m-%Y %I:%M %p", "%d/%m/%Y %I:%M %p", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S"]:
                        try:
                            last_dt = datetime.datetime.strptime(clean_last, fmt)
                            break
                        except ValueError:
                            last_dt = None
                    
                    if last_dt:
                        last_dt = karachi_tz.localize(last_dt)
                        hrs = (now_pkt - last_dt).total_seconds() / 3600.0
                        if not f1 and hrs >= 24:
                            eligible_for = "1st_followup"
                        elif f1.lower() in ["sent", "f1_sent"] and not f2 and hrs >= 72:
                            eligible_for = "2nd_followup"
                    else:
                        log(f"[!] Could not parse date format for '{name}': {last_action_str}")
                except Exception as e:
                    log(f"[!] Date logic error for {name}: {e}")

            if not eligible_for: continue

            result = send_ig_message(row, actual_row_idx, eligible_for, name, profile_url, audit_link_url)
            if result == "sent":
                followups_sent += 1
            elif result in ["skipped", "error"]:
                skipped += 1
        except Exception as e:
            log(f"[-] Follow-up row {actual_row_idx} error: {e}")
            skipped += 1

    # ── PASS 2: New Outreach (strictly limited to max_new_messages) ──
    log(f"\n[*] === PASS 2: New Outreach (limit={max_new_messages}) ===")
    for slice_idx, row in enumerate(data_rows):
        if new_sent >= max_new_messages:
            log(f"[!] Daily limit reached ({max_new_messages}). Stopping.")
            break
        actual_row_idx = slice_idx + row_start
        try:
            profile_url, name, audit_link_url, status, last_action_str, f1, f2, replied = parse_row(row)
            if not profile_url or "instagram.com" not in profile_url:
                skipped += 1; continue
            if not audit_link_url or "docs.google.com" not in audit_link_url:
                skipped += 1; continue
            if replied.lower() == "yes":
                skipped += 1; continue
            # Skip ALL rows that are already in any non-fresh state
            if status.lower() in TERMINAL or status.lower() in ["sent", "ig_sent"]:
                skipped += 1; continue

            result = send_ig_message(row, actual_row_idx, "new_outreach", name, profile_url, audit_link_url)
            if result == "sent":
                new_sent += 1
            else:
                skipped += 1
        except Exception as e:
            log(f"[-] New outreach row {actual_row_idx} error: {e}")
            skipped += 1

    return new_sent, followups_sent, skipped


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=10, help="Max NEW messages per run")
    parser.add_argument("--row-start", type=int, default=2)
    parser.add_argument("--row-end", type=int, default=0)
    parser.add_argument("--triggered-by", type=str, default="scheduler")
    args, _ = parser.parse_known_args()

    print("====================================")
    print("=== IG Direct Sheet Bot (Selenium) ===")
    print("====================================")
    print(f"[*] Max new messages: {args.max} | Rows: {args.row_start}-{args.row_end or 'END'}")

    worksheet, columns = get_google_sheet_and_headers()

    profile_dir = os.path.abspath("./chrome_profile_ig")
    os.makedirs(profile_dir, exist_ok=True)

    try:
        import subprocess, platform
        if platform.system() != "Windows":
            subprocess.run(["pkill", "-f", "chrome"], capture_output=True)
            time.sleep(2)
    except Exception:
        pass

    session_id = db.create_session(
        platform="instagram",
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

        driver.get("https://www.instagram.com/")
        random_delay(5, 8)

        log("[*] Verifying Instagram login...")
        login_required = False
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//svg[@aria-label='Home' or @aria-label='Search'] | //a[contains(@href, '/direct/')]"))
            )
        except TimeoutException:
            login_required = True

        if login_required:
            log("[!] NOT logged in. Profile may be expired. Exiting.")
            db.finish_session(session_id, 0, 0, 0, "error")
            return

        log("[+] Instagram login confirmed!")

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
        log("=== IG Bot Finished ===")

if __name__ == "__main__":
    main()
