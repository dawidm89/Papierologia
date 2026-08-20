import streamlit as st
import sqlite3
import json
from datetime import datetime
import google.generativeai as genai
from PIL import Image

# Konfiguracja strony pod wygląd mobilny
st.set_page_config(page_title="Asystent Biurokracji", page_icon="📄", layout="centered")

# Inicjalizacja bazy danych SQLite
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

st.title("📄 Asystent Biurokracji")

# Konfiguracja API Gemini w pasku bocznym
with st.sidebar:
    st.header("Ustawienia")
    api_key = st.text_input("Wklej klucz Gemini API:", type="password")
    st.caption("Pobierz darmowy klucz na: aistudio.google.com")

# Zakładki: Dodawanie i Przeglądanie
tab1, tab2 = st.tabs(["➕ Dodaj dokument", "📋 Twoje terminy"])

with tab1:
    st.subheader("Zeskanuj paragon lub umowę")
    camera_photo = st.camera_input("Zrób zdjęcie")
    file_upload = st.file_uploader("Lub wybierz plik z galerii", type=["jpg", "png", "jpeg"])
    
    photo = camera_photo or file_upload

    if photo and api_key:
        if st.button("🚀 Przeanalizuj przez AI"):
            with st.spinner("AI analizuje dokument..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    image = Image.open(photo)
                    
                    prompt = """
                    Przeanalizuj ten dokument (paragon, faktura, umowa, polisa). 
                    Wyciągnij dane i zwróć WYŁĄCZNIE czysty obiekt JSON (bez znaczników markdown ```json):
                    {
                        "title": "Krótka nazwa przedmiotu/usługi/firmy",
                        "category": "Gwarancja / Ubezpieczenie / Umowa / Inne",
                        "expiry_date": "YYYY-MM-DD (data końca gwarancji lub umowy; jeśli to zwykły paragon bez podanej daty, dodaj 2 lata do daty zakupu)",
                        "notes": "Krótkie podsumowanie kluczowych warunków (maks. 2 zdania)"
                    }
                    """
                    response = model.generate_content([prompt, image])
                    raw_text = response.text.replace("```json", "").replace("```", "").strip()
                    data = json.loads(raw_text)
                    
                    # Zapis do bazy danych
                    c.execute(
                        "INSERT INTO docs (title, category, expiry_date, notes, created_at) VALUES (?, ?, ?, ?, ?)",
                        (data.get("title", "Bez nazwy"), data.get("category", "Inne"), data.get("expiry_date", ""), data.get("notes", ""), datetime.now().strftime("%Y-%m-%d"))
                    )
                    conn.commit()
                    st.success(f"Dodano: {data.get('title')} (Ważne do: {data.get('expiry_date')})")
                except Exception as e:
                    st.error(f"Błąd analizy: {e}")

with tab2:
    st.subheader("Zapisane gwarancje i polisy")
    c.execute("SELECT id, title, category, expiry_date, notes FROM docs ORDER BY expiry_date ASC")
    rows = c.fetchall()
    
    if not rows:
        st.info("Brak zapisanych dokumentów. Dodaj swój pierwszy paragon w zakładce obok.")
    else:
        for row in rows:
            doc_id, title, category, expiry, notes = row
            with st.expander(f"📌 {title} | Ważne do: {expiry}"):
                st.write(f"**Kategoria:** {category}")
                st.write(f"**Data wygaśnięcia:** {expiry}")
                st.write(f"**Notatki:** {notes}")
                if st.button("🗑️ Usuń", key=f"del_{doc_id}"):
                    c.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
                    conn.commit()
                    st.rerun()
