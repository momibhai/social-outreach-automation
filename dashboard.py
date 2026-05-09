import streamlit as st
import subprocess
import threading
import queue
import time
import json
import os
import sys
import datetime
import pytz
from streamlit.runtime.scriptrunner import add_script_run_ctx
from dotenv import load_dotenv
import db_manager as db

load_dotenv()
PKT = pytz.timezone('Asia/Karachi')

# ─────────────────── CONFIG FILE ───────────────────
CONFIG_FILE = "scheduler_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "max_fb": 10, "max_ig": 10,
        "run_fb": True, "run_ig": True,
        "row_start_fb": 2, "row_end_fb": 0,
        "row_start_ig": 2, "row_end_ig": 0,
        "schedule_enabled": False,
        "schedule_hour": "09", "schedule_minute": "00", "schedule_ampm": "AM",
        "schedule_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
        "last_run_date_fb": "", "last_run_date_ig": ""
    }

def save_config(cfg):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)

# ─────────────────── PAGE SETUP ───────────────────
st.set_page_config(
    page_title="Amazesst Command Center",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background: #0a0b0f; color: #e2e8f0; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f1117 0%, #141720 100%) !important;
    border-right: 1px solid #1e2130;
}

/* Cards */
.metric-card {
    background: linear-gradient(135deg, #141720 0%, #1a1f2e 100%);
    border: 1px solid #1e2130;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
    transition: all 0.2s ease;
}
.metric-card:hover { border-color: #3b82f6; transform: translateY(-2px); }
.metric-value { font-size: 2rem; font-weight: 700; color: #3b82f6; }
.metric-label { font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; margin-top: 4px; }

/* Terminal */
.terminal-box {
    background: #050608;
    color: #00ff88;
    font-family: 'Courier New', monospace !important;
    font-size: 12px;
    padding: 16px;
    height: 380px;
    overflow-y: auto;
    border-radius: 10px;
    border: 1px solid #1e2130;
    white-space: pre-wrap;
    line-height: 1.5;
}

/* Status badges */
.badge-sent { background: #065f46; color: #34d399; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.badge-skip { background: #1e1a05; color: #fbbf24; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.badge-error { background: #450a0a; color: #f87171; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.badge-replied { background: #1e1b4b; color: #818cf8; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }
.badge-running { background: #0c1a3d; color: #60a5fa; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; }

/* Section headers */
.section-header {
    color: #fff;
    font-size: 1.1rem;
    font-weight: 600;
    padding: 8px 0;
    border-bottom: 2px solid #3b82f6;
    margin-bottom: 16px;
}

h1, h2, h3 { color: #ffffff !important; }
.stButton > button {
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────── HEADER ───────────────────
col_logo, col_title = st.columns([1, 8])
with col_logo:
    try:
        st.image("Amazesstlogo.png", width=70)
    except Exception:
        st.markdown("🚀")
with col_title:
    st.markdown("# Amazesst Command Center")
    st.markdown("<span style='color:#94a3b8;font-size:0.9rem'>Facebook & Instagram Automated Outreach — VPS Edition</span>", unsafe_allow_html=True)

st.markdown("---")

# ─────────────────── SIDEBAR NAV ───────────────────
st.sidebar.markdown("## ⚡ Navigation")
page = st.sidebar.radio("", ["🏠 Dashboard", "▶️ Run Bots", "📊 Run History", "🗃️ Log Viewer", "⚙️ Settings"])

config = load_config()

# ───────────────────────────────────────────────────────────
# ░░ PAGE 1: DASHBOARD ░░
# ───────────────────────────────────────────────────────────
if page == "🏠 Dashboard":
    st.markdown("### 📈 Today's Overview")

    sessions = db.get_all_sessions(100)
    today_str = datetime.datetime.now(PKT).strftime("%Y-%m-%d")

    today_sessions = [s for s in sessions if s.get("started_at", "").startswith(today_str)]
    total_new_today = sum(s.get("new_messages_sent", 0) for s in today_sessions)
    total_fu_today = sum(s.get("followups_sent", 0) for s in today_sessions)
    total_skip_today = sum(s.get("skipped", 0) for s in today_sessions)
    fb_today = [s for s in today_sessions if s.get("platform") == "facebook"]
    ig_today = [s for s in today_sessions if s.get("platform") == "instagram"]

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{total_new_today}</div><div class="metric-label">New Messages Today</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{total_fu_today}</div><div class="metric-label">Follow-ups Today</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{total_skip_today}</div><div class="metric-label">Skipped Today</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#1d9bf0">{len(fb_today)}</div><div class="metric-label">FB Runs Today</div></div>', unsafe_allow_html=True)
    with c5:
        st.markdown(f'<div class="metric-card"><div class="metric-value" style="color:#e1306c">{len(ig_today)}</div><div class="metric-label">IG Runs Today</div></div>', unsafe_allow_html=True)

    st.markdown("")
    st.markdown("### 🕐 Recent Runs")

    recent = sessions[:8]
    if not recent:
        st.info("No runs yet. Go to 'Run Bots' to start.")
    else:
        for s in recent:
            platform_icon = "📘" if s.get("platform") == "facebook" else "📸"
            status = s.get("status", "?")
            badge = f'<span class="badge-{status if status in ["sent","running","error"] else "skip"}">{status.upper()}</span>'
            if status == "done":
                badge = '<span class="badge-sent">✅ DONE</span>'
            elif status == "running":
                badge = '<span class="badge-running">⚡ RUNNING</span>'
            elif status == "error":
                badge = '<span class="badge-error">❌ ERROR</span>'

            with st.expander(f"{platform_icon} {s.get('platform','').upper()} | Started: {s.get('started_at','')} | {badge}", expanded=False):
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("New Sent", s.get("new_messages_sent", 0))
                r2.metric("Follow-ups", s.get("followups_sent", 0))
                r3.metric("Skipped", s.get("skipped", 0))
                r4.metric("Triggered By", s.get("triggered_by", "?"))
                st.caption(f"Rows: {s.get('row_start')} → {s.get('row_end') or 'END'} | Limit: {s.get('daily_limit')} | Finished: {s.get('finished_at', 'Still running...')}")

    st.markdown("---")
    st.markdown("### ⏰ Scheduler Status")
    
    cfg_status = "🟢 **Scheduler is ACTIVE**" if config.get("schedule_enabled") else "🔴 **Scheduler is DISABLED**"
    st.markdown(f"{cfg_status}")
    
    if config.get("schedule_enabled"):
        c_time1, c_time2, c_time3 = st.columns(3)
        next_run_time = f"{config.get('schedule_hour')}:{config.get('schedule_minute')} {config.get('schedule_ampm')} PKT"
        
        c_time1.metric("Daily Run Time", next_run_time)
        c_time2.metric("Active Days", ", ".join([d[:3] for d in config.get('schedule_days', [])]))
        
        # Calculate time remaining
        now = datetime.datetime.now(PKT)
        h = int(config.get("schedule_hour", "09"))
        m = int(config.get("schedule_minute", "00"))
        ampm = config.get("schedule_ampm", "AM")
        
        if ampm == "PM" and h != 12: h += 12
        elif ampm == "AM" and h == 12: h = 0
        
        target_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if target_time < now:
            target_time += datetime.timedelta(days=1)
            
        time_left = target_time - now
        hours_left, remainder = divmod(time_left.total_seconds(), 3600)
        minutes_left, _ = divmod(remainder, 60)
        
        c_time3.metric("Time Until Next Run", f"{int(hours_left)}h {int(minutes_left)}m")
    else:
        st.info("Schedule is off. You can configure it in the ⚙️ Settings page or run bots manually.")


# ───────────────────────────────────────────────────────────
# ░░ PAGE 2: RUN BOTS ░░
# ───────────────────────────────────────────────────────────
elif page == "▶️ Run Bots":
    st.markdown("### ▶️ Manual Bot Execution")
    st.info("Yahan se aap bots ko manually chala sakte hain. Yeh schedule ko affect nahi karega.")

    if "processes" not in st.session_state:
        st.session_state.processes = {}
    if "log_queues" not in st.session_state:
        st.session_state.log_queues = {}
    if "log_history" not in st.session_state:
        st.session_state.log_history = {"fb": "", "ig": ""}

    tab1, tab2 = st.tabs(["📘 Facebook", "📸 Instagram"])

    def render_run_ui(platform_key, platform_name, profile_icon, default_sheet_name):
        max_key = f"max_{platform_key}"
        rs_key = f"row_start_{platform_key}"
        re_key = f"row_end_{platform_key}"
        run_key = f"run_{platform_key}"

        st.markdown(f'<div class="section-header">{profile_icon} {platform_name} Settings</div>', unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            max_msgs = st.number_input(f"Daily New Message Limit", min_value=1, max_value=100,
                                        value=config.get(max_key, 10), key=f"max_{platform_key}_input",
                                        help="Only NEW outreach messages count. Follow-ups are NOT included in this limit.")
        with c2:
            row_start = st.number_input("Row Start (Sheet Row#)", min_value=2, value=config.get(rs_key, 2), key=f"rs_{platform_key}")
        with c3:
            row_end = st.number_input("Row End (0 = all rows)", min_value=0, value=config.get(re_key, 0), key=f"re_{platform_key}",
                                       help="0 means process all rows from start to end.")

        st.caption("ℹ️ Only profiles with an **Audit Link** (docs.google.com) will be messaged. Others are skipped automatically.")

        col_start, col_stop = st.columns([1, 1])
        start_clicked = col_start.button(f"▶️ Start {platform_name}", type="primary", key=f"start_{platform_key}", use_container_width=True)
        stop_clicked = col_stop.button(f"🛑 Stop {platform_name}", key=f"stop_{platform_key}", use_container_width=True)

        if stop_clicked:
            proc = st.session_state.processes.get(platform_key)
            if proc and proc.poll() is None:
                proc.terminate()
                time.sleep(1)
                if proc.poll() is None:
                    proc.kill()
                st.session_state.processes.pop(platform_key, None)
                st.success(f"⛔ {platform_name} bot stopped.")
            else:
                st.warning("No running bot to stop.")

        if start_clicked:
            python_exe = sys.executable
            script = "facebook_sheet_bot.py" if platform_key == "fb" else "instagram_bot.py"
            
            # Use xvfb-run on Linux (Docker/VPS) to provide a virtual display
            if sys.platform != "win32":
                cmd = [
                    "xvfb-run", "--server-args=-screen 0 1280x1024x24", 
                    python_exe, "-u", script,
                    "--max", str(max_msgs),
                    "--row-start", str(row_start),
                    "--row-end", str(row_end),
                    "--triggered-by", "manual"
                ]
            else:
                cmd = [
                    python_exe, "-u", script,
                    "--max", str(max_msgs),
                    "--row-start", str(row_start),
                    "--row-end", str(row_end),
                    "--triggered-by", "manual"
                ]
                
            my_env = os.environ.copy()
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=my_env)
            q = queue.Queue()

            def reader(out, q):
                for line in iter(out.readline, b''):
                    q.put(line.decode('utf-8', errors='replace'))
                out.close()

            t = threading.Thread(target=reader, args=(p.stdout, q), daemon=True)
            add_script_run_ctx(t)
            t.start()

            st.session_state.processes[platform_key] = p
            st.session_state.log_queues[platform_key] = q
            st.session_state.log_history[platform_key] = ""
            st.success(f"🤖 {platform_name} bot launched!")

        # Live log terminal
        st.markdown(f"**Live Terminal — {platform_name}**")
        terminal_placeholder = st.empty()

        q = st.session_state.log_queues.get(platform_key)
        if q:
            while True:
                try:
                    line = q.get_nowait()
                    st.session_state.log_history[platform_key] += line
                except queue.Empty:
                    break

        log_content = st.session_state.log_history.get(platform_key, "Bot not started yet...")
        terminal_placeholder.markdown(
            f'<div class="terminal-box">{log_content}</div>',
            unsafe_allow_html=True
        )

        proc = st.session_state.processes.get(platform_key)
        if proc and proc.poll() is None:
            time.sleep(1.5)
            st.rerun()

    with tab1:
        render_run_ui("fb", "Facebook", "📘", "Facebook Master sheet leads automation")
    with tab2:
        render_run_ui("ig", "Instagram", "📸", "Instagram sheet")


# ───────────────────────────────────────────────────────────
# ░░ PAGE 3: RUN HISTORY ░░
# ───────────────────────────────────────────────────────────
elif page == "📊 Run History":
    st.markdown("### 📊 Full Run History")

    sessions = db.get_all_sessions(200)

    if not sessions:
        st.info("No run history yet.")
    else:
        filter_platform = st.selectbox("Filter by Platform", ["All", "facebook", "instagram"])
        filter_status = st.selectbox("Filter by Status", ["All", "done", "running", "error"])

        filtered = sessions
        if filter_platform != "All":
            filtered = [s for s in filtered if s.get("platform") == filter_platform]
        if filter_status != "All":
            filtered = [s for s in filtered if s.get("status") == filter_status]

        st.markdown(f"Showing **{len(filtered)}** runs")

        for s in filtered:
            platform_icon = "📘" if s.get("platform") == "facebook" else "📸"
            status = s.get("status", "?")
            status_icon = {"done": "✅", "running": "⚡", "error": "❌"}.get(status, "❓")

            with st.expander(f"{platform_icon} {s.get('platform','').upper()} — {s.get('started_at','')} {status_icon}", expanded=False):
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("New Messages", s.get("new_messages_sent", 0))
                c2.metric("Follow-ups", s.get("followups_sent", 0))
                c3.metric("Skipped", s.get("skipped", 0))
                c4.metric("Status", status.upper())

                st.caption(f"📅 Started: {s.get('started_at')} | Finished: {s.get('finished_at','Still running...')}")
                st.caption(f"📋 Rows: {s.get('row_start')} → {s.get('row_end') or 'END'} | Daily Limit: {s.get('daily_limit')} | Triggered: {s.get('triggered_by')}")

                # Message detail table
                msgs = db.get_session_messages(s.get("id"))
                if msgs:
                    st.markdown("**Message Details:**")
                    rows_data = []
                    for m in msgs:
                        status_badge = {
                            "sent": "✅ Sent",
                            "skipped": "⏭️ Skipped",
                            "error": "❌ Error",
                            "replied": "💬 Replied"
                        }.get(m.get("status",""), m.get("status",""))
                        rows_data.append({
                            "Name": m.get("name",""),
                            "Type": m.get("message_type",""),
                            "Status": status_badge,
                            "Reason": m.get("reason","—"),
                            "Time": m.get("sent_at","")
                        })
                    st.dataframe(rows_data, use_container_width=True)

                # Delete button
                if st.button(f"🗑️ Delete This Run", key=f"del_{s['id']}"):
                    db.delete_session(s.get("id"))
                    st.success("Run deleted.")
                    st.rerun()


# ───────────────────────────────────────────────────────────
# ░░ PAGE 4: LOG VIEWER ░░
# ───────────────────────────────────────────────────────────
elif page == "🗃️ Log Viewer":
    st.markdown("### 🗃️ Raw Terminal Log Viewer")

    sessions = db.get_all_sessions(50)
    if not sessions:
        st.info("No sessions found.")
    else:
        options = {f"#{s['id']} | {s.get('platform','').upper()} | {s.get('started_at','')} [{s.get('status','')}]": s['id'] for s in sessions}
        selected_label = st.selectbox("Select Session", list(options.keys()))
        selected_id = options[selected_label]

        lines = db.get_log_lines(selected_id)
        log_text = "\n".join(lines) if lines else "No log lines recorded for this session."

        st.markdown(f'<div class="terminal-box" style="height:500px">{log_text}</div>', unsafe_allow_html=True)

        session_info = db.get_session_by_id(selected_id)
        if session_info:
            st.caption(f"Session: {session_info.get('platform')} | New: {session_info.get('new_messages_sent')} | FU: {session_info.get('followups_sent')} | Skipped: {session_info.get('skipped')}")


# ───────────────────────────────────────────────────────────
# ░░ PAGE 5: SETTINGS ░░
# ───────────────────────────────────────────────────────────
elif page == "⚙️ Settings":
    st.markdown("### ⚙️ Scheduler & Configuration Settings")

    st.markdown('<div class="section-header">📅 24/7 Auto Scheduler (CRUD)</div>', unsafe_allow_html=True)
    st.info("You can edit/delete or diable scheduler from here.")

    sch_enabled = st.checkbox("Enable 24/7 Auto Scheduling", value=config.get("schedule_enabled", False))

    c1, c2, c3 = st.columns(3)
    with c1:
        hours = [str(i).zfill(2) for i in range(1, 13)]
        sel_hour = st.selectbox("Hour (PKT)", hours, index=hours.index(config.get("schedule_hour", "09")))
    with c2:
        minutes = [str(i).zfill(2) for i in range(0, 60, 5)]
        sel_min = st.selectbox("Minute", minutes, index=minutes.index(config.get("schedule_minute", "00")) if config.get("schedule_minute", "00") in minutes else 0)
    with c3:
        sel_ampm = st.selectbox("AM/PM", ["AM", "PM"], index=["AM", "PM"].index(config.get("schedule_ampm", "AM")))

    all_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    schedule_days = st.multiselect("Active Days", options=all_days, default=config.get("schedule_days", all_days))

    st.markdown('<div class="section-header">📘 Facebook Settings</div>', unsafe_allow_html=True)
    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        fb_enabled = st.checkbox("Run Facebook Bot in Schedule", value=config.get("run_fb", True))
    with fc2:
        max_fb = st.number_input("FB Daily New Limit", min_value=1, max_value=100, value=config.get("max_fb", 10))
    fc4, fc5 = st.columns(2)
    with fc4:
        row_start_fb = st.number_input("FB Row Start", min_value=2, value=config.get("row_start_fb", 2))
    with fc5:
        row_end_fb = st.number_input("FB Row End (0=all)", min_value=0, value=config.get("row_end_fb", 0))

    st.markdown('<div class="section-header">📸 Instagram Settings</div>', unsafe_allow_html=True)
    ic1, ic2, ic3 = st.columns(3)
    with ic1:
        ig_enabled = st.checkbox("Run Instagram Bot in Schedule", value=config.get("run_ig", True))
    with ic2:
        max_ig = st.number_input("IG Daily New Limit", min_value=1, max_value=100, value=config.get("max_ig", 10))
    ic4, ic5 = st.columns(2)
    with ic4:
        row_start_ig = st.number_input("IG Row Start", min_value=2, value=config.get("row_start_ig", 2))
    with ic5:
        row_end_ig = st.number_input("IG Row End (0=all)", min_value=0, value=config.get("row_end_ig", 0))

    col_save, col_del = st.columns(2)
    with col_save:
        if st.button("💾 Save Schedule & Settings", type="primary", use_container_width=True):
            config.update({
                "schedule_enabled": sch_enabled,
                "schedule_hour": sel_hour,
                "schedule_minute": sel_min,
                "schedule_ampm": sel_ampm,
                "schedule_days": schedule_days,
                "run_fb": fb_enabled,
                "max_fb": max_fb,
                "row_start_fb": row_start_fb,
                "row_end_fb": row_end_fb,
                "run_ig": ig_enabled,
                "max_ig": max_ig,
                "row_start_ig": row_start_ig,
                "row_end_ig": row_end_ig,
            })
            save_config(config)
            st.success("✅ Configuration saved globally!")
            
    with col_del:
        if st.button("🗑️ Delete / Disable Schedule", use_container_width=True):
            config["schedule_enabled"] = False
            save_config(config)
            st.warning("⚠️ Schedule has been disabled.")
            st.rerun()


# ─────────────────── BACKGROUND SCHEDULER ───────────────────
def background_scheduler():
    """Runs in a thread — checks every 60s if it's time to run bots."""
    while True:
        try:
            cfg = load_config()
            if cfg.get("schedule_enabled", False):
                now = datetime.datetime.now(PKT)
                current_day = now.strftime("%A")

                h = int(cfg.get("schedule_hour", "9"))
                m = int(cfg.get("schedule_minute", "00"))
                ampm = cfg.get("schedule_ampm", "AM")

                if ampm == "PM" and h != 12:
                    h += 12
                elif ampm == "AM" and h == 12:
                    h = 0

                config_time = f"{h:02d}:{m:02d}"
                current_time = now.strftime("%H:%M")
                today_str = now.strftime("%Y-%m-%d")

                if current_day in cfg.get("schedule_days", []) and current_time == config_time:
                    python_exe = sys.executable
                    my_env = os.environ.copy()

                    if cfg.get("run_fb", True) and cfg.get("last_run_date_fb", "") != today_str:
                        cfg["last_run_date_fb"] = today_str
                        save_config(cfg)
                        
                        cmd_fb = [
                            python_exe, "-u", "facebook_sheet_bot.py",
                            "--max", str(cfg.get("max_fb", 10)),
                            "--row-start", str(cfg.get("row_start_fb", 2)),
                            "--row-end", str(cfg.get("row_end_fb", 0)),
                            "--triggered-by", "scheduler"
                        ]
                        if sys.platform != "win32":
                            cmd_fb = ["xvfb-run", "--server-args=-screen 0 1280x1024x24"] + cmd_fb
                            
                        subprocess.Popen(cmd_fb, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=my_env)

                    if cfg.get("run_ig", True) and cfg.get("last_run_date_ig", "") != today_str:
                        cfg["last_run_date_ig"] = today_str
                        save_config(cfg)
                        
                        cmd_ig = [
                            python_exe, "-u", "instagram_bot.py",
                            "--max", str(cfg.get("max_ig", 10)),
                            "--row-start", str(cfg.get("row_start_ig", 2)),
                            "--row-end", str(cfg.get("row_end_ig", 0)),
                            "--triggered-by", "scheduler"
                        ]
                        if sys.platform != "win32":
                            cmd_ig = ["xvfb-run", "--server-args=-screen 0 1280x1024x24"] + cmd_ig
                            
                        subprocess.Popen(cmd_ig, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=my_env)

        except Exception as e:
            print(f"[Scheduler Error] {e}")

        time.sleep(60)

if "scheduler_started" not in st.session_state:
    t = threading.Thread(target=background_scheduler, daemon=True)
    add_script_run_ctx(t)
    t.start()
    st.session_state.scheduler_started = True
