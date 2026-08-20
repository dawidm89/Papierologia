import streamlit as st
import sqlite3
import json
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

# Zaawansowane style CSS w klimacie Google Gemini (Dark UI)
st.markdown("""
    <style>
    /* Reset i ukrycie domyślnych pasków Streamlita */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Główne tło i typografia */
    .stApp {
        background-color: #131314;
        color: #e3e3e3;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3.5rem;
        max-width: 600px;
    }
    
    /* Nagłówek w stylu Gemini */
    .gemini-header {
        font-size: 1.7rem;
        font-weight: 700;
        background: linear-gradient(90deg, #4da3ff 0%, #9b72cf 50%, #d96570 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    /* Karta podsumowania (Gemini Glow Box) */
    .gemini-stat-box {
        background: #1e1f20;
        border: 1px solid #333538;
        border-radius: 20px;
        padding: 18px 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    
    /* Karty dokumentów */
    .doc-card {
        background: #1e1f20;
        border: 1px solid #2d2f31;
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 12px;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .doc-card:hover {
        border-color: #4da3ff;
    }
    
    /* Plakietki (Badges) w ciemnym motywie */
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.76rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .badge-active { background-color: rgba(34, 197, 94, 0.18); color: #4ade80; border: 1px solid rgba(74, 222, 128, 0.3); }
    .badge-warning { background-color: rgba(234, 179, 8, 0.18); color: #fde047; border: 1px solid rgba(253, 224, 71, 0.3); }
    .badge-expired { background-color: rgba(239, 68, 68, 0.18); color: #f87171; border: 1px solid rgba(248, 113, 113, 0.3); }
    .badge-category { background-color: rgba(77, 163, 255, 0.15); color: #70b5ff; border: 1px solid rgba(112, 181, 255, 0.3); }
    
    /* Dopasowanie pól tekstowych i przycisków */
    .stTextInput > div > div > input {
        background-color: #1e1f20 !important;
        color: #e3e3e3 !important;
        border-radius: 12px !important;
        border: 1px solid #333538 !important;
    }
    .stButton > button {
        border-radius: 12px !important;
    }
    </style>
""", unsafe_allow_html=True)

# Pobranie klucza z Secrets
API_KEY = st.secrets.get("GEMINI_API_KEY", "")

# Inicjalizacja bazy SQLite
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

# Funkcja statusu terminu
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

# Gradientowy nagłówek
st.markdown('<div class="gemini-header">✨ Papierologia</div>', unsafe_allow_html=True)

# Zakładki
tab_list, tab_add = st.tabs(["📋 Moje Dokumenty", "➕ Dodaj Nowy"])

# --- TAB 1: LISTA DOKUMENTÓW ---
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
            <div style="font-size: 0.85rem; color: #a8b3cf;">Podsumowanie archiwum</div>
            <div style="font-size: 1.4rem; font-weight: bold; margin-top: 4px; color: #f1f5f9;">Zapisane dokumenty: {total_docs}</div>
            <div style="font-size: 0.85rem; margin-top: 6px; color: #fde047;">⚠️ Kończące się terminy (30 dni): <b>{expiring_soon}</b></div>
        </div>
    """, unsafe_allow_html=True)
    
    search_query = st.text_input("🔍 Szukaj w dokumentach...", placeholder="Wpisz np. Media Expert, AGD, Polisa OC...")
    
    if not rows:
        st.info("Brak dokumentów w bazie. Przejdź do zakładki '➕ Dodaj Nowy', aby zeskanować swój pierwszy paragon!")
    else:
        for row in rows:
            doc_id, title, category, expiry, notes = row
            
            if search_query and search_query.lower() not in title.lower() and search_query.lower() not in notes.lower():
                continue
                
            status_label, days_label, badge_class = get_status_info(expiry)
            
            st.markdown(f"""
                <div class="doc-card">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <span class="badge badge-category">{category}</span>
                            <span class="badge {badge_class}">{status_label} ({days_label})</span>
                            <h4 style="margin: 8px 0 4px 0; color: #f1f5f9; font-size: 1.05rem;">{title}</h4>
                            <p style="margin: 0; color: #94a3b8; font-size: 0.85rem;">📅 Termin do: <b style="color: #e2e8f0;">{expiry}</b></p>
                        </div>
                    </div>
                    <div style="margin-top: 10px; font-size: 0.85rem; color: #cbd5e1; background: #18191a; padding: 10px; border-radius: 10px; border: 1px solid #282a2c;">
                        💡 {notes if notes else 'Brak dodatkowych szczegółów.'}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            col_del, _ = st.columns([1, 3])
            with col_del:
                if st.button("🗑️ Usuń", key=f"del_{doc_id}", use_container_width=True):
                    c.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
                    conn.commit()
                    st.rerun()

# --- TAB 2: SKANOWANIE AI ---
with tab_add:
    st.subheader("Zeskanuj dokument")
    st.caption("AI przeanalizuje treść, rozpozna nazwę i wyznaczy datę ważności.")
    
    camera_photo = st.camera_input("Zrób zdjęcie aparatem")
    file_upload = st.file_uploader("Lub wybierz plik z galerii", type=["jpg", "png", "jpeg"])
    
    photo = camera_photo or file_upload
    
    if photo:
        st.image(photo, caption="Podgląd zdjęcia", use_container_width=True)
        if st.button("✨ Przeanalizuj przez Gemini AI", type="primary", use_container_width=True):
            if not API_KEY:
                st.error("Brak klucza API w ustawieniach Streamlit Secrets.")
            else:
                with st.spinner("Gemini analizuje dokument..."):
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
                        st.success(f"✅ Dodano pomyślnie: {data.get('title')} (Ważne do: {data.get('expiry_date')})")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Błąd analizy: {e}")
