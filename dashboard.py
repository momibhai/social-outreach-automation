import streamlit as st
import subprocess
import threading
import queue
import time
import json
import os
import sys
import datetime
from streamlit.runtime.scriptrunner import add_script_run_ctx

# ----------------- CONFIGURATION -----------------
from dotenv import load_dotenv
load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

CONFIG_FILE = "scheduler_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except: pass
    return {
        "max_fb": 10,
        "max_ig": 10,
        "run_fb": True,
        "run_ig": True,
        "schedule_enabled": False,
        "schedule_hour": "12",
        "schedule_minute": "00",
        "schedule_ampm": "AM",
        "schedule_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "last_run_date": ""
    }

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f)

st.set_page_config(
    page_title="Amazesst Command Center",
    page_icon="Amazesstlogo.png",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FAFAFA; }
    .css-1d391kg { background-color: #1a1c23; border-radius: 10px; padding: 20px; }
    .terminal-box {
        background-color: #000000; color: #00FF41;
        font-family: 'Courier New', Courier, monospace;
        font-size: 13px; padding: 15px; height: 400px;
        overflow-y: scroll; border-radius: 8px;
        border: 1px solid #333; margin-bottom: 20px; white-space: pre-wrap;
    }
    h1, h2, h3 { color: #ffffff !important; }
    </style>
""", unsafe_allow_html=True)

try:
    st.image("Amazesstlogo.png", width=200)
except Exception:
    pass

st.title("Amazesst Command Center")
st.markdown("Automate your Google Sheet leads for Facebook & Instagram.")

config = load_config()

# ----------------- UI CONTROLS -----------------
st.sidebar.title("Mode Selection")
app_mode = st.sidebar.radio("Select Outreach Mode:", ["Manual Test Mode", "24/7 Scheduler Mode"])

st.markdown(f"### {app_mode}")

# Limits are common to both modes
st.markdown("#### ⚙️ Set Action Limits")
st.caption("The limit refers to the **total number of actions** per run (new messages + follow-ups).")
col1, col2 = st.columns(2)
with col1:
    st.markdown("##### 📘 Facebook")
    run_fb = st.checkbox("Enable FB", value=config.get("run_fb", True))
    max_fb = st.number_input("FB Limit (Actions/Run)", min_value=1, max_value=100, value=config.get("max_fb", 10))
with col2:
    st.markdown("##### 📸 Instagram")
    run_ig = st.checkbox("Enable IG", value=config.get("run_ig", True))
    max_ig = st.number_input("IG Limit (Actions/Run)", min_value=1, max_value=100, value=config.get("max_ig", 10))

st.markdown("---")

start_btn = False
stop_btn = False

if app_mode == "Manual Test Mode":
    st.info("💡 In this mode, the bots will run immediately when you click Start, so you can test them before deployment.")
    ctrl_col1, ctrl_col2, ctrl_col3 = st.columns([1, 1, 4])
    start_btn = ctrl_col1.button("▶️ START OUTREACH NOW", type="primary", use_container_width=True)
    stop_btn = ctrl_col2.button("🛑 STOP ALL", use_container_width=True)
    
else:
    st.info("⏰ In this mode, the bots run automatically in the background on the days and time you set.")
    sched_col1, sched_col2, sched_col3 = st.columns([1, 2, 2])
    with sched_col1:
        schedule_enabled = st.checkbox("Enable Automatic Scheduling", value=config.get("schedule_enabled", False))
    with sched_col2:
        st.markdown("**Daily Run Time (PKT)**")
        t_col1, t_col2, t_col3 = st.columns(3)
        hours = [str(i).zfill(2) for i in range(1, 13)]
        minutes = [str(i).zfill(2) for i in range(0, 60, 5)]
        
        sel_hour = t_col1.selectbox("Hour", hours, index=hours.index(config.get("schedule_hour", "12")))
        sel_min = t_col2.selectbox("Minute", minutes, index=minutes.index(config.get("schedule_minute", "00")) if config.get("schedule_minute", "00") in minutes else 0)
        sel_ampm = t_col3.selectbox("AM/PM", ["AM", "PM"], index=["AM", "PM"].index(config.get("schedule_ampm", "AM")))
    with sched_col3:
        all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        schedule_days = st.multiselect("Days to Run", options=all_days, default=config.get("schedule_days", all_days))

    if st.button("💾 Save Configuration"):
        config["run_fb"] = run_fb
        config["max_fb"] = max_fb
        config["run_ig"] = run_ig
        config["max_ig"] = max_ig
        config["schedule_enabled"] = schedule_enabled
        config["schedule_hour"] = sel_hour
        config["schedule_minute"] = sel_min
        config["schedule_ampm"] = sel_ampm
        config["schedule_days"] = schedule_days
        save_config(config)
        st.success("Configuration saved for 24/7 Background Scheduler!")

# ----------------- STATE & MULTIPROCESSING -----------------
if "processes" not in st.session_state:
    st.session_state.processes = {}
if "log_queues" not in st.session_state:
    st.session_state.log_queues = {}
if "log_history" not in st.session_state:
    st.session_state.log_history = {"fb": "", "ig": ""}

def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line.decode('utf-8'))
    out.close()

if stop_btn:
    st.markdown("### Stopping processes...")
    for param, p in st.session_state.processes.items():
        if p.poll() is None:
            p.terminate()
            time.sleep(1)
            if p.poll() is None: p.kill()
    st.session_state.processes = {}
    st.success("All automations have been forcefully stopped.")

# ----------------- BACKGROUND SCHEDULER THREAD -----------------
def background_scheduler():
    while True:
        cfg = load_config()
        if cfg.get("schedule_enabled", False):
            now = datetime.datetime.now()
            current_day = now.strftime("%A")
            
            h = int(cfg.get("schedule_hour", "12"))
            m = int(cfg.get("schedule_minute", "00"))
            ampm = cfg.get("schedule_ampm", "AM")
            
            if ampm == "PM" and h != 12: h += 12
            elif ampm == "AM" and h == 12: h = 0
                
            config_time_str = f"{h:02d}:{m:02d}"
            current_time_str = now.strftime("%H:%M")
            today_str = now.strftime("%Y-%m-%d")
            
            if current_day in cfg.get("schedule_days", []) and current_time_str == config_time_str:
                if cfg.get("last_run_date", "") != today_str:
                    cfg["last_run_date"] = today_str
                    save_config(cfg)
                    
                    my_env = os.environ.copy()
                    python_exe = sys.executable
                    if cfg.get("run_fb", True):
                        subprocess.Popen([python_exe, "-u", "facebook_sheet_bot.py", "--max", str(cfg.get("max_fb", 10))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=my_env)
                    if cfg.get("run_ig", True):
                        subprocess.Popen([python_exe, "-u", "instagram_bot.py", "--max", str(cfg.get("max_ig", 10))], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=my_env)
        
        time.sleep(30)

if "scheduler_thread" not in st.session_state:
    t_sched = threading.Thread(target=background_scheduler, daemon=True)
    add_script_run_ctx(t_sched)
    t_sched.start()
    st.session_state.scheduler_thread = t_sched

# ----------------- LIVE LOGS UI -----------------
st.markdown("### 📡 Live Execution Terminals")

log_col1, log_col2 = st.columns(2)
terminal_fb_placeholder = log_col1.empty()
terminal_ig_placeholder = log_col2.empty()

def render_logs():
    terminal_fb_placeholder.markdown(f"**Facebook Logs**\n<div class='terminal-box'>{st.session_state.log_history['fb']}</div>", unsafe_allow_html=True)
    terminal_ig_placeholder.markdown(f"**Instagram Logs**\n<div class='terminal-box'>{st.session_state.log_history['ig']}</div>", unsafe_allow_html=True)

render_logs()

# ----------------- MANUAL EXECUTION LOGIC -----------------
if start_btn:
    import sys
    python_exe = sys.executable
    my_env = os.environ.copy()
    
    if run_fb:
        cmd = [python_exe, "-u", "facebook_sheet_bot.py", "--max", str(max_fb)]
        p_fb = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=my_env)
        q_fb = queue.Queue()
        t_fb = threading.Thread(target=enqueue_output, args=(p_fb.stdout, q_fb), daemon=True)
        add_script_run_ctx(t_fb)
        t_fb.start()
        st.session_state.processes["fb"] = p_fb
        st.session_state.log_queues["fb"] = q_fb
        time.sleep(4)

    if run_ig:
        cmd = [python_exe, "-u", "instagram_bot.py", "--max", str(max_ig)]
        p_ig = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=my_env)
        q_ig = queue.Queue()
        t_ig = threading.Thread(target=enqueue_output, args=(p_ig.stdout, q_ig), daemon=True)
        add_script_run_ctx(t_ig)
        t_ig.start()
        st.session_state.processes["ig"] = p_ig
        st.session_state.log_queues["ig"] = q_ig

    st.success("🤖 Manual Outreach successfully launched!")

# ----------------- CONTINUOUS LOG READER -----------------
if len(st.session_state.processes) > 0:
    all_done = True
    new_logs_found = False
    
    for plat in ["fb", "ig"]:
        q = st.session_state.log_queues.get(plat)
        if q is not None:
            while True:
                try:
                    line = q.get_nowait()
                    st.session_state.log_history[plat] += line
                    new_logs_found = True
                except queue.Empty:
                    break
    
    for plat, p in st.session_state.processes.items():
        if p.poll() is None:
            all_done = False
            
    if new_logs_found:
        render_logs()
        
    if not all_done:
        time.sleep(0.5)
        st.rerun()
    else:
        st.success("✅ All active automations have completed their runs.")
        st.session_state.processes = {}
