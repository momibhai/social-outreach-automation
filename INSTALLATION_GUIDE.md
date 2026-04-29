# Amazesst Social Media Command Center
### Installation & Setup Guide 🚀

This guide will show you how to easily set up this automated outreach dashboard on your client's (or anyone else's) laptop. 

---

### Prerequisites
1. **Python 3.10+**: Ensure Python is installed.
2. **Google Chrome**: Ensure the regular Google Chrome browser is installed on the laptop.

---

### Step 1: Clone or Copy the Files
Copy this entire `Social_Media_Outreach` folder to the target laptop.
Make sure the `service_account.json` file is inside this folder (this is required to read/write to the Google Sheet).

### Step 2: Create a Virtual Environment
Open the terminal inside the `Social_Media_Outreach` directory and run:
```bash
python3 -m venv venv
```
*(If on Windows, use `python -m venv venv`)*

### Step 3: Activate the Virtual Environment
**On Mac/Linux:**
```bash
source venv/bin/activate
```
**On Windows:**
```cmd
.\venv\Scripts\activate
```

### Step 4: Install Required Packages
With the virtual environment activated, install the necessary Python modules:
```bash
pip install -r requirements.txt
```
*(If you don't have a requirements.txt, run: `pip install undetected-chromedriver selenium gspread google-auth pandas streamlit openai pytz`)*

### Step 5: Start the Dashboard!
Run this command to start the Streamlit Command Center:
```bash
streamlit run dashboard.py
source venv/bin/activate
streamlit run dashboard.py 
```
*(Or `./venv/bin/streamlit run dashboard.py` if testing locally)*

This will open a beautiful UI in your modern web browser at `http://localhost:8501`.

---

### Understanding the Authentication Flow
1. We have securely migrated away from copying "cookies" manually. The bots now run on highly secure "Persistent Profiles".
2. When you run a bot for the very **first time**, you might see a warning in the Dashboard Terminal: `[!] MANUAL LOG IN REQUIRED`.
3. An automated Chrome window will pop up. **Do not close it!**
4. Simply log into Facebook, Instagram, or X.com inside that window using your normal email/password. 
5. The bot will automatically detect that you've successfully logged in and will permanently save the session for all future runs! No more JSON cookie files needed!

---

### Troubleshooting
- **Zombie Browsers**: If you close the terminal abnormally without hitting "Stop All" first, Chrome browsers might get stuck in the background. If the bots crash instantly when you press start, open a fresh terminal and run:
  ```bash
  pkill -f "chrome"
  pkill -f "chromedriver"
  ```
  *(On Windows, you can just restart the laptop or use Task Manager to wipe out background Chrome processes)*
- **Dashboard Logs Freezing**: Ensure you always use the exact search commands. If a bot gets stuck waiting for a passcode or captcha, just look at the open automated Browser window and solve the captcha manually. The bot will seamlessly detect it and continue.
