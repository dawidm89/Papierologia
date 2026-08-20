import streamlit as st
import sqlite3
import json
import calendar
from datetime import datetime, date
import google.generativeai as genai
from PIL import Image

# Konfiguracja strony pod wygląd mobilny
st.set_page_config(
    page_title="Papierologia",
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Zaawansowane style CSS w klimacie Gemini + TimeTree
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    .stApp {
        background-color: #131314;
        color: #e3e3e3;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 3.5rem;
        max-width: 600px;
    }
    
    .gemini-header {
        font-size: 1.65rem;
        font-weight: 700;
        background: linear-gradient(90deg, #4da3ff 0%, #9b72cf 50%, #d96570 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 12px;
    }
    
    .gemini-stat-box {
        background: #1e1f20;
        border: 1px solid #333538;
        border-radius: 18px;
        padding: 16px 18px;
        margin-bottom: 16px;
    }
    
    .doc-card {
        background: #1e1f20;
        border: 1px solid #2d2f31;
        border-radius: 16px;
        padding: 14px;
        margin-bottom: 12px;
    }
    
    .badge {
        display: inline-block;
        padding: 3px 8px;
        border-radius: 10px;
        font-size: 0.74rem;
        font-weight: 600;
        margin-right: 5px;
    }
    .badge-active { background-color: rgba(34, 197, 94, 0.18); color: #4ade80; border: 1px solid rgba(74, 222, 128, 0.3); }
    .badge-warning { background-color: rgba(234, 179, 8, 0.18); color: #fde047; border: 1px solid rgba(253, 224, 71, 0.3); }
    .badge-expired { background-color: rgba(239, 68, 68, 0.18); color: #f87171; border: 1px solid rgba(248, 113, 113, 0.3); }
    .badge-category { background-color: rgba(77, 163, 255, 0.15); color: #70b5ff; border: 1px solid rgba(112, 181, 255, 0.3); }

    /* Style siatki kalendarza TimeTree */
    .cal-header {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        text-align: center;
        font-size: 0.75rem;
        font-weight: 600;
        color: #8ab4f8;
        margin-bottom: 6px;
    }
    .cal-grid {
        display: grid;
        grid-template-columns: repeat(7, 1fr);
        gap: 4px;
        margin-bottom: 15px;
    }
    .cal-cell {
        background: #1e1f20;
        border: 1px solid #2d2f31;
        border-radius: 10px;
        min-height: 48px;
        padding: 4px 2px;
        text-align: center;
        font-size: 0.8rem;
    }
    .cal-cell-empty {
        background: transparent;
        border: 1px solid transparent;
    }
    .cal-cell-today {
        border-color: #8ab4f8 !important;
        background: #282a2c;
    }
    .cal-cell-has-event {
        background: linear-gradient(180deg, #1e1f20 0%, #222d3d 100%);
        border-color: #4da3ff;
    }
    .cal-dot {
        height: 6px;
        width: 6px;
        background: #4da3ff;
        border-radius: 50%;
        display: inline-block;
        margin: 2px 1px;
    }
    .event-card {
        background: #1e1f20;
        border-left: 4px solid #4da3ff;
        padding: 10px 14px;
        border-radius: 0 12px 12px 0;
        margin-bottom: 8px;
    }
    </style>
""", unsafe_allow_html=True)

API_KEY = st.secrets.get("GEMINI_API_KEY", "")

# Baza danych SQLite
conn = sqlite3.connect('documents.db', check_same_thread=False)
c = conn.cursor()
c.execute('''
    CREATE TABLE IF NOT EXISTS docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        category TEXT,
        expiry_date TEXT,
        notes TEXT,
        created_at TEXT
    )
''')
conn.commit()

def get_status_info(expiry_str):
    try:
        exp_date = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        today = date.today()
        delta = (exp_date - today).days
        if delta < 0:
            return "Wygasło", f"{abs(delta)} dni temu", "badge-expired"
        elif delta <= 30:
            return "Wygasa wkrótce", f"Zostało {delta} dni", "badge-warning"
        else:
            return "Aktywne", f"Zostało {delta} dni", "badge-active"
    except Exception:
        return "Brak terminu", "-", "badge-category"

st.markdown('<div class="gemini-header">✨ Papierologia</div>', unsafe_allow_html=True)

# 3 Zakładki: Lista, Kalendarz, Dodawanie
tab_list, tab_cal, tab_add = st.tabs(["📋 Dokumenty", "📅 Kalendarz", "➕ Dodaj Nowy"])

# --- TAB 1: LISTA ---
with tab_list:
    c.execute("SELECT id, title, category, expiry_date, notes FROM docs ORDER BY expiry_date ASC")
    rows = c.fetchall()
    
    total_docs = len(rows)
    expiring_soon = 0
    today = date.today()
    
    for r in rows:
        try:
            d = datetime.strptime(r[3], "%Y-%m-%d").date()
            if 0 <= (d - today).days <= 30:
                expiring_soon += 1
        except Exception:
            pass
            
    st.markdown(f"""
        <div class="gemini-stat-box">
            <div style="font-size: 0.82rem; color: #a8b3cf;">Archiwum</div>
            <div style="font-size: 1.3rem; font-weight: bold; margin-top: 2px; color: #f1f5f9;">Wszystkie terminy: {total_docs}</div>
            <div style="font-size: 0.82rem; margin-top: 4px; color: #fde047;">⚠️ Kończące się (30 dni): <b>{expiring_soon}</b></div>
        </div>
    """, unsafe_allow_html=True)
    
    search_query = st.text_input("🔍 Szukaj...", placeholder="Wyszukaj dokument...")
    
    if not rows:
        st.info("Brak dokumentów. Dodaj pierwszy w zakładce '➕ Dodaj Nowy'.")
    else:
        for row in rows:
            doc_id, title, category, expiry, notes = row
            if search_query and search_query.lower() not in title.lower() and search_query.lower() not in notes.lower():
                continue
                
            status_label, days_label, badge_class = get_status_info(expiry)
            st.markdown(f"""
                <div class="doc-card">
                    <span class="badge badge-category">{category}</span>
                    <span class="badge {badge_class}">{status_label} ({days_label})</span>
                    <h4 style="margin: 6px 0 2px 0; color: #f1f5f9;">{title}</h4>
                    <p style="margin: 0; color: #94a3b8; font-size: 0.82rem;">📅 Ważne do: <b style="color: #e2e8f0;">{expiry}</b></p>
                    <div style="margin-top: 8px; font-size: 0.82rem; color: #cbd5e1; background: #18191a; padding: 8px; border-radius: 8px;">
                        💡 {notes if notes else 'Brak uwag.'}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            col_del, _ = st.columns([1, 3])
            with col_del:
                if st.button("🗑️ Usuń", key=f"del_{doc_id}", use_container_width=True):
                    c.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
                    conn.commit()
                    st.rerun()

# --- TAB 2: KALENDARZ (TIMETREE STYLE) ---
with tab_cal:
    if "cal_year" not in st.session_state:
        st.session_state.cal_year = date.today().year
        st.session_state.cal_month = date.today().month

    c.execute("SELECT id, title, category, expiry_date, notes FROM docs")
    all_docs = c.fetchall()
    
    # Grupowanie terminów po dacie
    events_by_date = {}
    for doc in all_docs:
        exp = doc[3]
        if exp:
            events_by_date.setdefault(exp, []).append(doc)

    # Nawigacja miesiącami
    col_prev, col_month_name, col_next = st.columns([1, 3, 1])
    with col_prev:
        if st.button("◀", use_container_width=True):
            if st.session_state.cal_month == 1:
                st.session_state.cal_month = 12
                st.session_state.cal_year -= 1
            else:
                st.session_state.cal_month -= 1
            st.rerun()
            
    with col_next:
        if st.button("▶", use_container_width=True):
            if st.session_state.cal_month == 12:
                st.session_state.cal_month = 1
                st.session_state.cal_year += 1
            else:
                st.session_state.cal_month += 1
            st.rerun()

    month_names_pl = ["", "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec", "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień"]
    cur_year = st.session_state.cal_year
    cur_month = st.session_state.cal_month
    
    with col_month_name:
        st.markdown(f"<h4 style='text-align: center; margin: 4px 0; color: #f1f5f9;'>{month_names_pl[cur_month]} {cur_year}</h4>", unsafe_allow_html=True)

    # Dni tygodnia
    st.markdown("""
        <div class="cal-header">
            <div>PN</div><div>WT</div><div>ŚR</div><div>CZ</div><div>PT</div><div>SB</div><div>ND</div>
        </div>
    """, unsafe_allow_html=True)

    # Budowanie siatki
    cal_matrix = calendar.monthcalendar(cur_year, cur_month)
    today_str = date.today().strftime("%Y-%m-%d")
    
    cal_html = '<div class="cal-grid">'
    month_events = []

    for week in cal_matrix:
        for day in week:
            if day == 0:
                cal_html += '<div class="cal-cell cal-cell-empty"></div>'
            else:
                d_str = f"{cur_year:04d}-{cur_month:02d}-{day:02d}"
                has_event = d_str in events_by_date
                is_today = (d_str == today_str)
                
                cell_class = "cal-cell"
                if is_today:
                    cell_class += " cal-cell-today"
                if has_event:
                    cell_class += " cal-cell-has-event"
                    month_events.extend([(d_str, doc) for doc in events_by_date[d_str]])
                
                dots = '<div class="cal-dot"></div>' if has_event else ''
                cal_html += f'<div class="{cell_class}"><div>{day}</div>{dots}</div>'
    
    cal_html += '</div>'
    st.markdown(cal_html, unsafe_allow_html=True)

    # Lista terminów w wybranym miesiącu
    st.subheader("Wydarzenia w tym miesiącu")
    if not month_events:
        st.caption("Brak wygasających gwarancji lub umów w tym miesiącu.")
    else:
        for d_str, doc in sorted(month_events, key=lambda x: x[0]):
            _, title, cat, _, notes = doc
            st.markdown(f"""
                <div class="event-card">
                    <div style="font-size: 0.78rem; color: #8ab4f8; font-weight: 600;">📅 {d_str} ({cat})</div>
                    <div style="font-weight: 600; color: #f1f5f9; margin-top: 2px;">{title}</div>
                    <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 2px;">{notes}</div>
                </div>
            """, unsafe_allow_html=True)

# --- TAB 3: DODAWANIE ---
with tab_add:
    st.subheader("Zeskanuj dokument")
    st.caption("AI wyciągnie termin i automatycznie umieści go w Twoim kalendarzu.")
    
    camera_photo = st.camera_input("Zrób zdjęcie aparatem")
    file_upload = st.file_uploader("Lub wybierz plik z galerii", type=["jpg", "png", "jpeg"])
    
    photo = camera_photo or file_upload
    
    if photo:
        st.image(photo, caption="Podgląd dokumentu", use_container_width=True)
        if st.button("✨ Przeanalizuj i zapisz", type="primary", use_container_width=True):
            if not API_KEY:
                st.error("Brak klucza API w Secrets.")
            else:
                with st.spinner("AI analizuje dokument..."):
                    try:
                        genai.configure(api_key=API_KEY)
                        model = genai.GenerativeModel('gemini-3.6-flash')
                        image = Image.open(photo)
                        
                        prompt = """
                        Przeanalizuj ten dokument (paragon, faktura, umowa, polisa). 
                        Wyciągnij dane i zwróć WYŁĄCZNIE czysty obiekt JSON (bez znaczników markdown ```json):
                        {
                            "title": "Krótka nazwa przedmiotu/usługi/firmy",
                            "category": "Gwarancja / Ubezpieczenie / Umowa / Pojazd / AGD/RTV",
                            "expiry_date": "YYYY-MM-DD (data końca gwarancji lub umowy; jeśli to paragon bez terminu, dodaj 2 lata do daty zakupu)",
                            "notes": "Maksymalnie 2 kluczowe zdania o warunkach, numerze polisy lub paragonu"
                        }
                        """
                        response = model.generate_content([prompt, image])
                        raw_text = response.text.replace("```json", "").replace("```", "").strip()
                        data = json.loads(raw_text)
                        
                        c.execute(
                            "INSERT INTO docs (title, category, expiry_date, notes, created_at) VALUES (?, ?, ?, ?, ?)",
                            (data.get("title", "Bez nazwy"), data.get("category", "Inne"), data.get("expiry_date", ""), data.get("notes", ""), datetime.now().strftime("%Y-%m-%d"))
                        )
                        conn.commit()
                        st.success(f"✅ Zapisano w kalendarzu: {data.get('title')} (Termin: {data.get('expiry_date')})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Błąd analizy: {e}")
