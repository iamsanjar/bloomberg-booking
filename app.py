import html as H
import re
import smtplib
import uuid
from datetime import datetime, date, time, timedelta
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from supabase import create_client

# ======================= SETTINGS (change here) =======================
TZ = ZoneInfo("Asia/Tashkent")
NUM_TERMINALS = 11
OPEN_HOUR, CLOSE_HOUR = 9, 18
SLOT_MINUTES = 45
MAX_DAYS_AHEAD = 7
MAX_PER_DAY = 1

MAJORS = [
    "Certificate in International Foundation Studies",
    # Undergraduate
    "BA (Hons) International Relations and Law",
    "BSc (Hons) Economics and its Pathways",
    "BSc (Hons) Computer Science",
    "BA (Hons) Commercial Law",
    "BSc (Hons) Finance",
    "BA (Hons) Business Management and its Pathways",
    "BSc (Hons) Business Information Systems",
    # Postgraduate
    "MBA and its Pathways",
    "MBA in Finance",
    "LLM in International Commercial Law",
    "MSc in Applied Economics",
    "MSc in Business Intelligence and Analytics",
    "MSc in Public Health and Healthcare Management",
    "MSc in Research Methods for Social Sciences",
    "MA in Creative Industries Management",
    "MA in Learning and Teaching (with TESOL pathway)",
    "Postgraduate Certificate in Learning and Teaching",
    "Postgraduate Certificate in Research Methods for Social Sciences",
    "Other",
]
# ======================================================================

LOGO = Path(__file__).parent / "logo.png"

st.set_page_config(
    page_title="WIUT Bloomberg Lab - Booking",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&display=swap');
:root{--amber:#FB8B1E;--blue:#2F7FD8;--green:#18C964;--red:#F0443A;--panel:#0E1116;--line:#262C36;}
[data-testid="stSidebar"],[data-testid="collapsedControl"],[data-testid="stSidebarCollapsedControl"]{display:none !important;}
[data-testid="stHeader"]{background:transparent;}
.block-container{padding-top:1.2rem;padding-bottom:3rem;max-width:1150px;}
h1,h2,h3,.mono{font-family:'IBM Plex Mono',monospace !important;}
h3{color:var(--amber) !important;text-transform:uppercase;font-size:1.02rem !important;letter-spacing:.08em;
    border-bottom:1px solid var(--line);padding-bottom:.45rem;margin-top:1.6rem !important;}
label,[data-testid="stWidgetLabel"] p{font-family:'IBM Plex Mono',monospace !important;font-size:.8rem !important;
    color:#AEB6C2 !important;text-transform:uppercase;letter-spacing:.05em;}
.ticker{border:1px solid var(--line);border-left:3px solid var(--amber);background:#000;overflow:hidden;
    white-space:nowrap;padding:.45rem 0;margin-bottom:1rem;border-radius:3px;}
.ticker span{display:inline-block;padding-left:100%;animation:tick 38s linear infinite;
    font-family:'IBM Plex Mono',monospace;font-size:.8rem;color:var(--amber);}
.ticker b{color:#fff;font-weight:600;}
.ticker i{color:var(--green);font-style:normal;}
@keyframes tick{0%{transform:translateX(0);}100%{transform:translateX(-100%);}}
.brand{font-family:'IBM Plex Mono',monospace;font-weight:700;font-size:1.9rem;color:#fff;line-height:1.15;letter-spacing:.02em;}
.brand em{font-style:normal;color:var(--amber);}
.sub{font-family:'IBM Plex Mono',monospace;color:#8B94A3;font-size:.8rem;letter-spacing:.06em;margin-top:.35rem;text-transform:uppercase;}
.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem;margin:.6rem 0 .4rem 0;}
.stat{background:var(--panel);border:1px solid var(--line);border-top:2px solid var(--amber);border-radius:3px;padding:.7rem .9rem;}
.stat .k{font-family:'IBM Plex Mono',monospace;font-size:.68rem;color:#8B94A3;letter-spacing:.1em;}
.stat .v{font-family:'IBM Plex Mono',monospace;font-size:1.7rem;font-weight:600;color:var(--amber);}
.stat .v.g{color:var(--green);} .stat .v.r{color:var(--red);}
.gridwrap{overflow-x:auto;border:1px solid var(--line);border-radius:3px;background:var(--panel);}
table.grid{border-collapse:collapse;width:100%;font-family:'IBM Plex Mono',monospace;font-size:.82rem;min-width:640px;}
table.grid th{background:#000;color:var(--amber);padding:.5rem .4rem;font-weight:600;border-bottom:1px solid var(--amber);text-align:center;}
table.grid th.tm{text-align:left;padding-left:.8rem;color:#fff;white-space:nowrap;}
table.grid td{text-align:center;padding:.42rem .3rem;border-bottom:1px solid #171B22;border-left:1px solid #171B22;}
table.grid td.f{color:var(--green);background:rgba(24,201,100,.07);}
table.grid td.x{color:var(--red);background:rgba(240,68,58,.12);}
table.grid td.p{color:#3A4250;}
.legend{font-family:'IBM Plex Mono',monospace;font-size:.75rem;color:#8B94A3;margin:.5rem 0 0 0;}
.legend .f{color:var(--green);} .legend .x{color:var(--red);}
.stButton button[kind="primary"],.stDownloadButton button{background:var(--amber);border:0;color:#000;
    font-family:'IBM Plex Mono',monospace;font-weight:700;letter-spacing:.06em;text-transform:uppercase;}
.stButton button[kind="primary"] p,.stDownloadButton button p{color:#000 !important;font-weight:700;}
.stButton button[kind="primary"]:hover{background:#ffa23f;}
.foot{font-family:'IBM Plex Mono',monospace;font-size:.72rem;color:#566070;margin-top:2.5rem;border-top:1px solid var(--line);padding-top:.8rem;}
</style>
"""


# ======================= DATABASE =======================
@st.cache_resource
def db():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def make_slots():
    slots, t = [], datetime.combine(date.today(), time(OPEN_HOUR, 0))
    end = datetime.combine(date.today(), time(CLOSE_HOUR, 0))
    while t + timedelta(minutes=SLOT_MINUTES) <= end:
        slots.append(t.time())
        t += timedelta(minutes=SLOT_MINUTES)
    return slots


SLOTS = make_slots()


def slot_label(t: time):
    end = (datetime.combine(date.today(), t) + timedelta(minutes=SLOT_MINUTES)).time()
    return f"{t:%H:%M}-{end:%H:%M}"


def now():
    return datetime.now(TZ)


def is_blocked(d: date):
    if d.weekday() >= 5:
        return "The lab is closed on weekends."
    r = db().table("blocked_days").select("reason").eq("day", str(d)).execute().data
    if r:
        return f"The lab is closed: {r[0].get('reason') or 'holiday'}."
    return None


def get_bookings(d: date):
    rows = (
        db().table("bookings").select("*")
        .eq("booking_date", str(d)).eq("status", "active").execute().data
    )
    for r in rows:
        r["slot_start"] = datetime.strptime(r["slot_start"][:5], "%H:%
