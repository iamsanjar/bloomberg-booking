import re
import smtplib
import uuid
from datetime import datetime, date, time, timedelta
from email.message import EmailMessage
from io import BytesIO
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
from supabase import create_client

# ---------------- SETTINGS (change here) ----------------
TZ = ZoneInfo("Asia/Tashkent")
NUM_TERMINALS = 11
OPEN_HOUR, CLOSE_HOUR = 9, 18
SLOT_MINUTES = 45
MAX_DAYS_AHEAD = 7
MAX_PER_DAY = 2
MAJORS = [
    "Economics with Finance",
    "Economics with Data Science",
    "Economics with Business",
    "Business Administration",
    "Business Information Systems",
    "Business Management with Finance",
    "Computer Science",
    "Other",
]
# --------------------------------------------------------

st.set_page_config(page_title="Bloomberg Lab Booking", page_icon="📈", layout="wide")


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
        return "Lab is closed on weekends."
    r = db().table("blocked_days").select("reason").eq("day", str(d)).execute().data
    if r:
        return f"Lab is closed: {r[0].get('reason') or 'holiday'}."
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
    return re.fullmatch(r"[A-Za-z0-9._%+-]+@(students\.)?wiut\.uz", s.lower()) is not None


def send_email(to, d, t, terminal, token):
    base = st.secrets.get("APP_URL", "").rstrip("/")
    msg = EmailMessage()
    msg["Subject"] = "Bloomberg Lab booking confirmed"
    msg["From"] = st.secrets["SMTP_USER"]
    msg["To"] = to
    body = (
        f"Your booking is confirmed.\n\n"
        f"Terminal: {terminal}\nDate: {d:%A, %d %B %Y}\nTime: {slot_label(t)}\n\n"
        f"To cancel: {base}/?cancel={token}\n\nWIUT Bloomberg Lab"
    )
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(st.secrets["SMTP_USER"], st.secrets["SMTP_PASSWORD"])
        s.send_message(msg)


# ---------------- CANCEL VIA LINK ----------------
def cancel_page(token):
    st.title("Cancel booking")
    res = db().table("bookings").select("*").eq("cancel_token", token).eq("status", "active").execute().data
    if not res:
        st.warning("This booking was not found or is already cancelled.")
        return
    b = res[0]
    st.write(f"Terminal {b['terminal']}, {b['booking_date']}, {b['slot_start'][:5]}")
    if st.button("Yes, cancel my booking"):
        db().table("bookings").update({"status": "cancelled"}).eq("id", b["id"]).execute()
        st.success("Your booking is cancelled.")


# ---------------- BOOKING PAGE ----------------
def booking_page():
    st.title("📈 Bloomberg Lab Terminal Booking")
    st.caption(
        f"{NUM_TERMINALS} terminals · {OPEN_HOUR}:00-{CLOSE_HOUR}:00 · {SLOT_MINUTES} minutes per booking · "
        f"book up to {MAX_DAYS_AHEAD} days ahead"
    )

    today = now().date()
    first_open = today
    while first_open.weekday() >= 5:
        first_open += timedelta(days=1)
    d = st.date_input("1. Choose date", value=first_open, min_value=today,
                      max_value=today + timedelta(days=MAX_DAYS_AHEAD))
    closed = is_blocked(d)
    if closed:
        st.error(closed + " Please choose another date.")
        return

    bookings = get_bookings(d)
    taken = {(b["terminal"], b["slot_start"]) for b in bookings}

    st.subheader("Availability")
    grid = {}
    for term in range(1, NUM_TERMINALS + 1):
        col = []
        for t in SLOTS:
            if not slot_is_future(d, t):
                col.append("-")
            elif (term, t) in taken:
                col.append("❌ Taken")
            else:
                col.append("✅ Free")
        grid[f"T{term}"] = col
    st.dataframe(pd.DataFrame(grid, index=[slot_label(t) for t in SLOTS]), width="stretch")

    st.subheader("2. Choose terminal and time")
    term = st.selectbox("Terminal", range(1, NUM_TERMINALS + 1), format_func=lambda x: f"Terminal {x}")
    free = [t for t in SLOTS if slot_is_future(d, t) and (term, t) not in taken]
    if not free:
        st.info("No free times on this terminal for this date. Please choose another terminal or date.")
        return
    slot = st.selectbox("Time", free, format_func=slot_label)

    st.subheader("3. Your details")
    student_id = st.text_input("Student ID (8 digits, e.g. 00020171)").strip()
    major = st.selectbox("Major", MAJORS)
    email = st.text_input("WIUT email (@wiut.uz or @students.wiut.uz)").strip()

    if st.button("Book", type="primary"):
        if not valid_id(student_id):
            st.error("Student ID must be 8 digits and start with 000.")
            return
        if not valid_email(email):
            st.error("Please use your WIUT email (@wiut.uz or @students.wiut.uz).")
            return
        mine = [b for b in bookings if b["student_id"] == student_id]
        if len(mine) >= MAX_PER_DAY:
            st.error(f"You can book at most {MAX_PER_DAY} times per day.")
            return
        token = uuid.uuid4().hex
        try:
            db().table("bookings").insert({
                "student_id": student_id, "major": major, "email": email.lower(),
                "terminal": term, "booking_date": str(d), "slot_start": slot.strftime("%H:%M"),
                "cancel_token": token, "status": "active",
            }).execute()
        except Exception:
            st.error("Sorry, someone has just booked this time or you already have a booking at this time. "
                     "Please choose another time.")
            return
        st.success(f"Booked! Terminal {term}, {d:%d %b %Y}, {slot_label(slot)}.")
        try:
            send_email(email, d, slot, term, token)
            st.info("A confirmation email was sent to you.")
        except Exception:
            st.warning("Booking is saved, but the email could not be sent.")
        st.balloons()


# ---------------- ADMIN PAGE ----------------
def admin_page():
    st.title("Admin")
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
            df = df[["booking_date", "slot_start", "terminal", "student_id", "major", "email", "id"]]
            df["slot_start"] = df["slot_start"].str[:5]
            st.dataframe(df.drop(columns="id"), width="stretch")
            buf = BytesIO()
            df.drop(columns="id").to_excel(buf, index=False)
            st.download_button("Download Excel", buf.getvalue(), "bookings.xlsx")
            st.write("Cancel a booking")
            pick = st.selectbox(
                "Booking", df["id"],
                format_func=lambda i: " | ".join(map(str, df[df["id"] == i].iloc[0][["booking_date", "slot_start", "terminal", "student_id"]])),
            )
            if st.button("Cancel selected booking"):
                db().table("bookings").update({"status": "cancelled"}).eq("id", pick).execute()
                st.rerun()

    with tab2:
        d = st.date_input("Day", value=now().date(), key="admin_day")
        bk = {(b["terminal"], b["slot_start"]): b["student_id"] for b in get_bookings(d)}
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


# ---------------- ROUTER ----------------
params = st.query_params
if "cancel" in params:
    cancel_page(params["cancel"])
else:
    page = st.sidebar.radio("Menu", ["Book a terminal", "Admin"])
    if page == "Book a terminal":
        booking_page()
    else:
        admin_page()
