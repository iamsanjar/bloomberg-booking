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
        r["slot_start"] = datetime.strptime(r["slot_start"][:5], "%H:%M").time()
    return rows


def slot_is_future(d: date, t: time):
    # minimum 0 hours: a slot can be booked until the moment it starts
    return datetime.combine(d, t, tzinfo=TZ) >= now()


def valid_id(s):
    return re.fullmatch(r"000\d{5}", s) is not None


def valid_email(s):
    return len(s) <= 254 and re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", s) is not None


def send_email(to, d, t, terminal, token):
    base = st.secrets.get("APP_URL", "").rstrip("/")
    cancel = f"{base}/?cancel={token}"
    when = f"{d:%A, %d %B %Y}"
    msg = EmailMessage()
    msg["Subject"] = "Bloomberg Lab booking confirmed"
    msg["From"] = st.secrets["SMTP_USER"]
    msg["To"] = to
    msg.set_content(
        f"Your booking is confirmed.\n\nTerminal: {terminal}\nDate: {when}\nTime: {slot_label(t)}\n\n"
        f"To cancel: {cancel}\n\nWIUT Bloomberg Lab"
    )
    msg.add_alternative(
        f"""
<div style="background:#000;padding:24px;font-family:Arial,Helvetica,sans-serif">
 <div style="max-width:520px;margin:auto;background:#0E1116;border-top:4px solid #FB8B1E;padding:26px;color:#EAEAEA">
  <div style="color:#FB8B1E;font-size:13px;letter-spacing:2px">WIUT BLOOMBERG LAB</div>
  <h2 style="margin:6px 0 18px 0;color:#fff">Booking confirmed</h2>
  <table style="width:100%;font-size:15px;border-collapse:collapse">
   <tr><td style="padding:8px 0;color:#8B94A3">Terminal</td><td style="color:#fff;font-weight:bold">{terminal}</td></tr>
   <tr><td style="padding:8px 0;color:#8B94A3">Date</td><td style="color:#fff;font-weight:bold">{H.escape(when)}</td></tr>
   <tr><td style="padding:8px 0;color:#8B94A3">Time</td><td style="color:#fff;font-weight:bold">{slot_label(t)}</td></tr>
  </table>
  <p style="margin:22px 0 8px 0;color:#8B94A3;font-size:13px">Cannot come? Please cancel so another student can use the terminal.</p>
  <a href="{H.escape(cancel)}" style="display:inline-block;background:#FB8B1E;color:#000;padding:10px 18px;
     text-decoration:none;font-weight:bold;border-radius:3px">Cancel booking</a>
 </div>
</div>""",
        subtype="html",
    )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(st.secrets["SMTP_USER"], st.secrets["SMTP_PASSWORD"])
        s.send_message(msg)


# ======================= UI PIECES =======================
def header():
    st.markdown(CSS, unsafe_allow_html=True)
    stamp = f"{now():%d %b %Y  %H:%M}"
    st.markdown(
        f"""<div class="ticker"><span>
        <b>WIUT BLOOMBERG LAB</b>  ▪  <i>{NUM_TERMINALS} TERMINALS</i>  ▪ 
        OPEN <b>{OPEN_HOUR:02d}:00-{CLOSE_HOUR:02d}:00</b> MON-FRI  ▪ 
        <b>{SLOT_MINUTES} MIN</b> PER SESSION  ▪  <b>{MAX_PER_DAY}</b> BOOKING PER DAY  ▪ 
        BOOK UP TO <b>{MAX_DAYS_AHEAD} DAYS</b> AHEAD  ▪  TASHKENT {stamp}
        </span></div>""",
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([1, 2], vertical_alignment="center")
    with c1:
        if LOGO.exists():
            st.image(str(LOGO), width=250)
        else:
            st.markdown('<div class="brand"><em>WIUT</em> Bloomberg Lab</div>', unsafe_allow_html=True)
    with c2:
        st.markdown(
            '<div class="brand">TERMINAL <em>BOOKING</em></div>'
            '<div class="sub">Reserve your Bloomberg terminal in 4 steps</div>',
            unsafe_allow_html=True,
        )


def grid_html(d, taken):
    head = "".join(f"<th>T{n}</th>" for n in range(1, NUM_TERMINALS + 1))
    rows = []
    for t in SLOTS:
        future = slot_is_future(d, t)
        cells = []
        for n in range(1, NUM_TERMINALS + 1):
            if not future:
                cells.append('<td class="p">–</td>')
            elif (n, t) in taken:
                cells.append('<td class="x">✕</td>')
            else:
                cells.append('<td class="f">●</td>')
        rows.append(f'<tr><th class="tm">{slot_label(t)}</th>{"".join(cells)}</tr>')
    return (
        '<div class="gridwrap"><table class="grid"><thead><tr><th class="tm">TIME</th>'
        + head + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
        '<div class="legend"><span class="f">●</span> free    '
        '<span class="x">✕</span> already booked    – time has passed</div>'
    )


def stat_cards(d, taken):
    future = {t for t in SLOTS if slot_is_future(d, t)}
    total = len(future) * NUM_TERMINALS
    booked = sum(1 for (n, t) in taken if t in future)
    return (
        '<div class="stats">'
        f'<div class="stat"><div class="k">FREE SESSIONS</div><div class="v g">{total - booked}</div></div>'
        f'<div class="stat"><div class="k">BOOKED</div><div class="v r">{booked}</div></div>'
        f'<div class="stat"><div class="k">TERMINALS</div><div class="v">{NUM_TERMINALS}</div></div>'
        "</div>"
    )


# ======================= CANCEL VIA EMAIL LINK =======================
def cancel_page(token):
    st.subheader("Cancel booking")
    res = db().table("bookings").select("*").eq("cancel_token", token).eq("status", "active").execute().data
    if not res:
        st.warning("This booking was not found or is already cancelled.")
        return
    b = res[0]
    st.write(f"Terminal {b['terminal']} · {b['booking_date']} · {b['slot_start'][:5]}")
    if st.button("Yes, cancel my booking", type="primary"):
        db().table("bookings").update({"status": "cancelled"}).eq("id", b["id"]).execute()
        st.success("Your booking is cancelled. Thank you!")


# ======================= BOOKING PAGE =======================
def booking_page():
    flash = st.session_state.pop("flash", None)
    if flash:
        st.success(flash["msg"])
        if flash["mail"]:
            st.info("A confirmation email was sent to you. Please check your inbox (and Spam).")
        else:
            st.warning("Your booking is saved, but we could not send the email. Please take a screenshot of this page.")
        st.balloons()

    today = now().date()
    first_open = today
    while first_open.weekday() >= 5:
        first_open += timedelta(days=1)

    st.subheader("1 · Choose a date")
    d = st.date_input("Date", value=first_open, min_value=today,
                      max_value=today + timedelta(days=MAX_DAYS_AHEAD), label_visibility="collapsed")
    closed = is_blocked(d)
    if closed:
        st.error(closed + " Please choose another date.")
        return

    bookings = get_bookings(d)
    taken = {(b["terminal"], b["slot_start"]) for b in bookings}
    st.markdown(stat_cards(d, taken), unsafe_allow_html=True)
    st.markdown(grid_html(d, taken), unsafe_allow_html=True)

    st.subheader("2 · Choose terminal and time")
    c1, c2 = st.columns(2)
    with c1:
        term = st.selectbox("Terminal", range(1, NUM_TERMINALS + 1), format_func=lambda x: f"Terminal {x}")
    free = [t for t in SLOTS if slot_is_future(d, t) and (term, t) not in taken]
    with c2:
        if free:
            slot = st.selectbox("Time", free, format_func=slot_label)
        else:
            slot = None
            st.selectbox("Time", ["No free time"], disabled=True)
    if not free:
        st.info("This terminal is fully booked for this date. Please choose another terminal or date.")
        return

    st.subheader("3 · Your details")
    name = st.text_input("Full Name", max_chars=100).strip()
    student_id = st.text_input("Student ID (8 digits, e.g. 00020171)", max_chars=8).strip()
    major = st.selectbox("Programme / major", MAJORS)
    email = st.text_input("Email (we send your confirmation here)", max_chars=254).strip()

    if st.button("Book terminal", type="primary"):
        if not name:
            st.error("Please enter your full name.")
            return
        if not valid_id(student_id):
            st.error("Student ID must be 8 digits and start with 000, for example 00020171.")
            return
        if not valid_email(email):
            st.error("Please enter a valid email address, for example name@gmail.com.")
            return
        if any(b["student_id"] == student_id for b in bookings):
            st.error(f"You already have a booking on this day. Only {MAX_PER_DAY} booking per day is allowed.")
            return
        token = uuid.uuid4().hex
        try:
            db().table("bookings").insert({
                "name": name, "student_id": student_id, "major": major, "email": email.lower(),
                "terminal": term, "booking_date": str(d), "slot_start": slot.strftime("%H:%M"),
                "cancel_token": token, "status": "active",
            }).execute()
        except Exception:
            st.error("Sorry, someone has just booked this time, or you already have a booking at this time. "
                     "Please choose another time.")
            return
        try:
            send_email(email, d, slot, term, token)
            mail_ok = True
        except Exception:
            mail_ok = False
        st.session_state["flash"] = {
            "msg": f"Booked! Terminal {term} · {d:%a %d %b %Y} · {slot_label(slot)}",
            "mail": mail_ok,
        }
        st.rerun()

    st.markdown('<div class="foot">WIUT Bloomberg Lab · Westminster International University in Tashkent</div>',
                unsafe_allow_html=True)


# ======================= ADMIN PAGE =======================
def admin_page():
    st.subheader("Admin")
    pw = st.text_input("Password", type="password")
    if pw != st.secrets["ADMIN_PASSWORD"]:
        st.stop()

    tab1, tab2, tab3 = st.tabs(["Bookings", "Day view", "Closed days"])

    with tab1:
        rows = db().table("bookings").select("*").eq("status", "active") \
            .order("booking_date").order("slot_start").execute().data
        df = pd.DataFrame(rows)
        if df.empty:
            st.info("No bookings yet.")
        else:
            df = df[["booking_date", "slot_start", "terminal", "name", "student_id", "major", "email", "id"]]
            df["slot_start"] = df["slot_start"].str[:5]
            st.dataframe(df.drop(columns="id"), width="stretch")
            buf = BytesIO()
            df.drop(columns="id").to_excel(buf, index=False)
            st.download_button("Download Excel", buf.getvalue(), "bookings.xlsx")
            st.write("Cancel a booking")
            pick = st.selectbox(
                "Booking", df["id"],
                format_func=lambda i: " | ".join(
                    map(str, df[df["id"] == i].iloc[0][["booking_date", "slot_start", "terminal", "name", "student_id"]])),
            )
            if st.button("Cancel selected booking"):
                db().table("bookings").update({"status": "cancelled"}).eq("id", pick).execute()
                st.rerun()

    with tab2:
        d = st.date_input("Day", value=now().date(), key="admin_day")
        bk = {(b["terminal"], b["slot_start"]): f"{b.get('name') or ''} ({b['student_id']})" for b in get_bookings(d)}
        grid = {f"T{t}": [bk.get((t, s), "") for s in SLOTS] for t in range(1, NUM_TERMINALS + 1)}
        st.dataframe(pd.DataFrame(grid, index=[slot_label(s) for s in SLOTS]), width="stretch")

    with tab3:
        c1, c2 = st.columns(2)
        day = c1.date_input("Close this day", key="block_day")
        reason = c2.text_input("Reason (e.g. holiday)")
        if st.button("Close day"):
            db().table("blocked_days").upsert({"day": str(day), "reason": reason}).execute()
            st.success("Day closed.")
        for r in db().table("blocked_days").select("*").order("day").execute().data:
            col1, col2 = st.columns([4, 1])
            col1.write(f"{r['day']} - {r.get('reason') or ''}")
            if col2.button("Open", key=r["day"]):
                db().table("blocked_days").delete().eq("day", r["day"]).execute()
                st.rerun()


# ======================= ROUTER =======================
# Students: normal link.   Admin: add  /?admin=1  to the link.
header()
params = st.query_params
if "cancel" in params:
    cancel_page(params["cancel"])
elif "admin" in params:
    admin_page()
else:
    booking_page()
