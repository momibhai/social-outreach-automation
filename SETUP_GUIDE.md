# Social Media Outreach Automation - Setup Guide

This guide covers the complete A-to-Z setup process for the multi-platform automated outreach system (Facebook, Instagram, X/Twitter, and Threads) running on Linux using Streamlit and Undetected-Chromedriver.

## Prerequisites

Ensure you have a Linux machine (e.g., Ubuntu/Debian) with Python 3.10+ installed.

### 1. Install Google Chrome
The bot requires the official Google Chrome browser to run (Chromium will not work properly with undetected-chromedriver).
```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb
```

### 2. Python Virtual Environment Setup
Inside the `Social_Media_Outreach` folder, create and activate a Python virtual environment to keep dependencies isolated:
```bash
python3 -m venv venv
source venv/bin/activate
```

Install the exact package requirements:
```bash
pip install -r requirements.txt
```

---

## Google Cloud & Google Sheets Integration

The bot reads keywords, URLs, and logs its outbound message statuses directly into a Google Sheet. This requires a `service_account.json` file.

### Step-by-Step: Creating `service_account.json`
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the top-left dropdown and **Create a New Project** (e.g., "Outreach Bot").
3. In the search bar at the top, search for **Google Drive API** and click **Enable**.
4. Search for **Google Sheets API** and click **Enable**.
5. Go to the Hamburger Menu (top left) > **APIs & Services** > **Credentials**.
6. Click **+ CREATE CREDENTIALS** at the top and select **Service Account**.
7. Name the service account (e.g., `bot-sheets-access`) and click **Create and Continue**, then **Done**.
8. In the "Service Accounts" list at the bottom of the Credentials page, click the newly created service account email.
9. Go to the **KEYS** tab.
10. Click **ADD KEY** > **Create new key**.
11. Choose **JSON** and click **Create**.
12. A file will download to your computer. **Rename this file to `service_account.json`** and place it directly inside the `Social_Media_Outreach` folder.

### Step-by-Step: Linking Your Google Sheet
1. Open the JSON file you just downloaded and copy the `client_email` address (e.g., `bot-sheets-access@your-project.iam.gserviceaccount.com`).
2. Go to your active Google Sheet where you track outreach.
3. Click the **Share** button in the top right.
4. Paste the `client_email` and grant it **Editor** access. The bot can now read and write to this spreadsheet!

---

## Authentication & Chrome Profiles

The bots use isolated persistent Google Chrome profiles so they don't have to log in every time. These folders are generated automatically when you run the system, but you must manually log in the **first time**.

### Manual Login Phase
1. Make sure your Python venv is activated.
2. Run the dashboard: `./venv/bin/streamlit run dashboard.py`
3. Check the box for the platform you want to set up (e.g., Threads).
4. A new Google Chrome window will physically open on your screen.
5. Manually log into your account on that platform during the window's grace time. 
6. Once you are logged in, you never need to do it again (unless session cookies expire). The bot will use the saved `chrome_profile_th`, `chrome_profile_fb`, etc., folders dynamically.

---

## Using the Dashboard

To run the system:
```bash
source venv/bin/activate
./venv/bin/streamlit run dashboard.py
```
This will open `http://localhost:8501` in your browser.

- **Checkboxes:** Toggle on the platforms you want to run. Multiple platforms can run in parallel without interfering.
- **Log Viewer:** Live execution logs (terminal output) are securely piped into the Streamlit dashboard window so you can watch exactly what the bots are doing.
- **Auto Stop:** You can click the "Stop Automated Processes" button to safely close browser drivers.

## Project Structure Overview

- `dashboard.py`: The main Streamlit User Interface.
- `facebook_bot.py`: Handles Messenger outreach (DMs) from group/people scraping.
- `ig_bot.py`: Automates Instagram DMs based on hashtag search optimization.
- `x_bot.py`: (Currently functional but requires robust profile configurations) Handles X.com automation.
- `threads_bot.py`: Performs visual DOM scraping to leave replies strictly on targeted posts using exact SVG click listeners.
- `chromedriver_*`: Independent driver binaries that prevent the Parallel Execution bug.
- `chrome_profile_*`: Contains secure cookies, local storage, and sessions for each platform. 
