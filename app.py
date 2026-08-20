import streamlit as st
import sqlite3
import json
from datetime import datetime, date
import google.generativeai as genai
from PIL import Image

# Konfiguracja strony mobilnej
st.set_page_config(
    page_title="Papierologia",
    page_icon="📁",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Zaawansowane style CSS dla wyglądu natywnej aplikacji
st.markdown("""
    <style>
    /* Ukrycie elementów Streamlita */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Główne tło i odstępy */
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 3rem;
        max-width: 600px;
    }
    
    /* Karty dokumentów */
    .doc-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 14px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    }
    
    /* Plakietki kategorii i statusów */
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-right: 6px;
    }
    .badge-active { background-color: #def7ec; color: #03543f; }
    .badge-warning { background-color: #fef08a; color: #713f12; }
    .badge-expired { background-color: #fde8e8; color: #9b1c1c; }
    .badge-category { background-color: #e1effe; color: #1e429f; }
    
    /* Statystyki na górze */
    .stat-box {
        background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
        color: white;
        padding: 18px;
        border-radius: 18px;
        margin-bottom: 20px;
        box-shadow: 0 6px 16px rgba(30, 58, 138, 0.2);
    }
    </style>
""", unsafe_allow_html=True)

# Pobranie klucza z Secrets
API_KEY = st.secrets.get("GEMINI_API_KEY", "")

# Inicjalizacja bazy
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

# Pomocnicza funkcja liczenia dni
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

# Nagłówek aplikacji
st.title("📁 Papierologia")

# Zakładki
tab_list, tab_add = st.tabs(["📋 Moje Dokumenty", "➕ Dodaj Nowy"])

# --- TAB 1: LISTA I PRZEGLĄDANIE ---
with tab_list:
    # Pobranie danych
    c.execute("SELECT id, title, category, expiry_date, notes FROM docs ORDER BY expiry_date ASC")
    rows = c.fetchall()
    
    # Karta z podsumowaniem
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
        <div class="stat-box">
            <div style="font-size: 0.9rem; opacity: 0.9;">Twój cyfrowy asystent</div>
            <div style="font-size: 1.5rem; font-weight: bold; margin-top: 4px;">Wszystkie dokumenty: {total_docs}</div>
            <div style="font-size: 0.85rem; margin-top: 6px;">⚠️ Wygasające w ciągu 30 dni: <b>{expiring_soon}</b></div>
        </div>
    """, unsafe_allow_html=True)
    
    # Filtrowanie i wyszukiwarka
    search_query = st.text_input("🔍 Szukaj dokumentu...", placeholder="np. pralka, auto, ubezpieczenie")
    
    if not rows:
        st.info("Nie masz jeszcze żadnych zapisanych dokumentów. Przejdź do zakładki '➕ Dodaj Nowy', aby zeskanować pierwszy paragon!")
    else:
        for row in rows:
            doc_id, title, category, expiry, notes = row
            
            # Filtr wyszukiwania
            if search_query and search_query.lower() not in title.lower() and search_query.lower() not in notes.lower():
                continue
                
            status_label, days_label, badge_class = get_status_info(expiry)
            
            st.markdown(f"""
                <div class="doc-card">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <span class="badge badge-category">{category}</span>
                            <span class="badge {badge_class}">{status_label} ({days_label})</span>
                            <h4 style="margin: 8px 0 4px 0; color: #1e293b;">{title}</h4>
                            <p style="margin: 0; color: #64748b; font-size: 0.85rem;">📅 Termin: <b>{expiry}</b></p>
                        </div>
                    </div>
                    <div style="margin-top: 10px; font-size: 0.88rem; color: #475569; background: #f8fafc; padding: 10px; border-radius: 8px;">
                        💡 {notes if notes else 'Brak dodatkowych uwag.'}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            col_del, col_space = st.columns([1, 4])
            with col_del:
                if st.button("🗑️ Usuń", key=f"del_{doc_id}", use_container_width=True):
                    c.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
                    conn.commit()
                    st.rerun()

# --- TAB 2: DODAWANIE DOKUMENTU ---
with tab_add:
    st.subheader("Zeskanuj paragon lub umowę")
    st.caption("AI automatycznie odczyta przedmiot, kategorię i wyliczy datę gwarancji.")
    
    camera_photo = st.camera_input("Zrób zdjęcie aparatem")
    file_upload = st.file_uploader("Lub wybierz plik z pamięci telefonu", type=["jpg", "png", "jpeg"])
    
    photo = camera_photo or file_upload
    
    if photo:
        st.image(photo, caption="Podgląd dokumentu", use_container_width=True)
        if st.button("🚀 Przeanalizuj i zapisz", type="primary", use_container_width=True):
            if not API_KEY:
                st.error("Brak klucza API w ustawieniach.")
            else:
                with st.spinner("AI analizuje dokument..."):
                    try:
                        genai.configure(api_key=API_KEY)
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        image = Image.open(photo)
                        
                        prompt = """
                        Przeanalizuj ten dokument (paragon, faktura, umowa, polisa). 
                        Wyciągnij dane i zwróć WYŁĄCZNIE czysty obiekt JSON (bez znaczników markdown ```json):
                        {
                            "title": "Krótka nazwa przedmiotu/usługi/firmy",
                            "category": "Gwarancja / Ubezpieczenie / Umowa / Pojazd / Mieszkanie",
                            "expiry_date": "YYYY-MM-DD (data końca gwarancji lub umowy; jeśli to paragon bez terminu, dodaj 2 lata do daty zakupu)",
                            "notes": "Maksymalnie 2 kluczowe zdania o warunkach, numerze polisy lub numerze paragonu"
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
