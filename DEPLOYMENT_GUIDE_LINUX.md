# Social Media Outreach Automation - Linux VPS Deployment Guide

This guide explains how to deploy your Facebook and Instagram automation system on a **Hostinger KVM VPS (Ubuntu)** without disturbing other services like n8n or OpenClaw.

---

## 1. Prerequisites (VPS Side)

Login to your VPS via SSH and install the necessary dependencies:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and Pip
sudo apt install python3 python3-pip python3-venv -y

# Install Google Chrome
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb -y

# Install Xvfb (for Virtual Display to handle initial logins)
sudo apt install xvfb -y
```

---

## 2. Project Setup

Create a dedicated folder for your project to keep it isolated from n8n:

```bash
mkdir ~/social-outreach
cd ~/social-outreach

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install streamlit undetected-chromedriver selenium gspread google-auth openai python-dotenv pytz pandas
```

---

## 3. Uploading Files

Upload your files using **FileZilla** or **WinSCP**.

### ⚠️ IMPORTANT: What NOT to put on GitHub
If you use GitHub, **do NOT** upload these files to a public repository:
- `.env` (Contains your OpenAI API Key)
- `service_account.json` (Google Sheets access)
- `chrome_profile/` & `chrome_profile_ig/` (Contains your browser data)

**Upload these files manually from your PC to the VPS `/home/social-outreach` folder.**

---

## 4. Handling Logins on Linux

**Crucial:** Windows browser profiles are encrypted and **cannot** be reused on Linux. You MUST login again on the VPS.

### Option A: Use Xvfb (Command Line)
1. In your `facebook_sheet_bot.py`, temporarily comment out the `--headless=new` line.
2. Run the bot inside a virtual display:
   ```bash
   xvfb-run python3 facebook_sheet_bot.py --max 1
   ```
3. Since you can't see the screen, this is hard. **Better Option:** Use a **VNC Server** on your VPS to open a Desktop once, open Chrome, login to FB/IG manually, and close it. This will save the cookies in the VPS's own `chrome_profile` folder.

---

## 5. Running the Dashboard via IP

To access your dashboard from your laptop's browser using the VPS IP:

```bash
streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501
```

Access it at: `http://YOUR_VPS_IP:8501`

---

## 6. Keeping it Running 24/7 (Systemd)

To make sure the dashboard stays alive even if you close the terminal:

1. Create a service file:
   ```bash
   sudo nano /etc/systemd/system/outreach.service
   ```
2. Paste this configuration:
   ```ini
   [Unit]
   Description=Social Media Outreach Dashboard
   After=network.target

   [Service]
   User=root
   WorkingDirectory=/home/social-outreach
   ExecStart=/home/social-outreach/venv/bin/streamlit run dashboard.py --server.address 0.0.0.0 --server.port 8501
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
3. Start the service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable outreach
   sudo systemctl start outreach
   ```

---

## 🎯 Summary for AI Models (DeepSeek/GPT-4)
If you ask another AI to help you deploy, just paste this:
"I have a Python Streamlit app that uses undetected-chromedriver to automate Facebook/Instagram. It needs Google Chrome installed. I want to deploy it on an Ubuntu VPS using a virtual environment and a systemd service to keep it running 24/7 on port 8501. I need to handle the initial browser login via a virtual display because the Windows profiles are not portable to Linux."
