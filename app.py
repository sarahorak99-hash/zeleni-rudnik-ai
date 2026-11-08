"""Zeleni rudnik – verzija 2: karta dvorišta + prepoznavanje otpada sa slike.

Pokretanje (u mapi s ovim datotekama):
    py -3.13 -m streamlit run app.py

Mapa mora sadržavati:
    app.py
    reciklazna_dvorista_ociscena.csv
    Zeleni_rudnik_tablica_predmeta.xlsx   (samo za prepoznavanje otpada)

Za prepoznavanje trebaju još: torch, transformers, pillow, openpyxl.
Ako ih nema, stranica karte i dalje radi.
"""
import base64
import html
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo

from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

CSV_PATH = "reciklazna_dvorista_ociscena.csv"
TABLE_PATH = "Zeleni_rudnik_tablica_predmeta.xlsx"
MODEL_NAME = "openai/clip-vit-base-patch32"
ZAGREB_CENTER = (45.8131, 15.9775)
CONFIDENCE_THRESHOLD = 0.60  # ispod ovoga aplikacija ne tvrdi rezultat
TOP_N = 3

# Predmeti čiji se sadržaj ne vidi na slici: tražimo potvrdu korisnika.
CONTENT_DEPENDENT = ["ulje", "lijekov", "pesticid", "zaštitu bilja", "aerosol", "boje", "otapal"]

# Ključna riječ u nazivu predmeta -> stupac u CSV-u dvorišta koji to dvorište mora imati.
YARD_FLAG_BY_KEYWORD = {
    "lijekov": "lijekovi",
    "tekstil": "tekstil",
    "odjeć": "tekstil",
    "akumulator": "akumulatori",
    "fluorescent": "fluorescentne_cijevi",
    "namještaj": "glomazni_otpad",
    "madrac": "glomazni_otpad",
}

TEXT = {
    "hr": {
        "title": "Zeleni rudnik",
        "subtitle": "Kamo s otpadom u Zagrebu? Pronađi najbliže reciklažno dvorište.",
        "page": "Stranica",
        "nav_map": "🗺️ Karta dvorišta",
        "nav_scan": "📷 Prepoznaj otpad",
        "nav_kvart": "🏘️ Moj kvart (bodovi)",
        "filters": "Filteri",
        "type": "Vrsta dvorišta",
        "type_opts": {"stalno": "Stalno", "mobilno": "Mobilno"},
        "open_now": "Samo otvoreno sada",
        "extra": "Prima i",
        "extra_opts": {
            "lijekovi": "Stare lijekove",
            "tekstil": "Tekstil i odjeću",
            "akumulatori": "Akumulatore",
            "fluorescentne_cijevi": "Fluorescentne cijevi",
            "glomazni_otpad": "Glomazni otpad",
        },
        "click": "Klikni na kartu da označiš svoju lokaciju.",
        "nearest": "Najbliže dvorište",
        "distance": "Udaljenost (zračno)",
        "route": "Ruta (OpenStreetMap)",
        "open": "Otvoreno",
        "closed": "Zatvoreno",
        "hours": "Radno vrijeme",
        "phone": "Telefon",
        "none": "Nijedno dvorište ne odgovara filterima.",
        "you": "Tvoja lokacija",
        "note": "Napomena: praznici nisu uračunati, a raspored mobilnih dvorišta provjeri na cistoca.hr.",
        "containers_btn": "Spremnici u tvom kvartu (Grad Zagreb)",
        "show_ug": "Prikaži podzemne spremnike (središnji Zagreb)",
        "show_gc": "Prikaži granice gradskih četvrti",
        "gc_name": "Gradska četvrt",
        "ug_name": "Podzemni spremnik",
        "ug_note": "Podzemni spremnici namijenjeni su stanarima kojima su dodijeljeni. Prikazani su samo spremnici iz otvorenog skupa Grada Zagreba (nepotpun popis).",
        "containers_help": "Zelene otoke i polupodzemne spremnike prikazuje karta Grada Zagreba.",
        "scan_title": "Prepoznaj otpad",
        "scan_intro": "Slikaj predmet koji želiš baciti, a mi ćemo ti reći kamo s njim.",
        "src_txt": "Pretraži tekstom",
        "search": "Upiši naziv predmeta (npr. baterija, pizza kutija)",
        "search_none": "Nema rezultata. Probaj drugu riječ ili slikaj predmet.",
        "search_pick": "Odaberi predmet",
        "encourage": "🌱 Hvala što pravilno odlažeš otpad. Svaki predmet je važan!",
        "how_title": "Kako koristiti Zeleni rudnik",
        "how_1": "**1. Slikaj ili upiši** što želiš baciti (stranica Prepoznaj otpad).",
        "how_2": "**2. Potvrdi prijedlog** i saznaj u koji spremnik ide ili gdje ga zbrinuti.",
        "how_3": "**3. Pronađi najbliže dvorište** na karti i pokreni rutu.",
        "how_note": "Ovo je prototip. Prijedlozi su automatski i mogu biti pogrešni, a bodovi kvarta su simulacija.",
        "src_cam": "Snimi kamerom",
        "src_upl": "Učitaj sliku",
        "take": "Slikaj predmet",
        "upload": "Odaberi sliku (jpg, png, webp)",
        "analysing": "Analiziram sliku...",
        "likely": "Najvjerojatnije je",
        "unsure": "Nisam sigurna što je na slici. Odaberi što je najbliže ili probaj ponovno s drugim kutom.",
        "pick": "Što je od ovoga točno?",
        "none_of": "Ništa od ovoga",
        "none_msg": "U redu. Probaj slikati predmet bliže, na jednoj podlozi i uz dobro svjetlo.",
        "category": "Kategorija",
        "where": "Gdje zbrinuti",
        "remark": "Napomena",
        "often_wrong": "Ovo ljudi često bacaju na krivo mjesto.",
        "typical_mistake": "Tipična greška",
        "sensitive": "Ovo ne možemo pouzdano prepoznati sa slike jer ovisi o sadržaju.",
        "confirm": "Potvrđujem da je to točno ono što je u ambalaži",
        "no_pos": "Za najbliže dvorište označi svoju lokaciju na stranici Karta dvorišta.",
        "unavailable": "Prepoznavanje otpada nije dostupno u ovoj verziji (nedostaju biblioteke ili tablica predmeta).",
        "no_table": "Nije pronađena tablica predmeta (Zeleni_rudnik_tablica_predmeta.xlsx).",
        "disclaimer": "Prijedlog je automatski i može biti pogrešan. Ako nisi sigurna, provjeri upute na cistoca.hr.",
    },
    "en": {
        "title": "Green Mine (Zeleni rudnik)",
        "subtitle": "Where to take your waste in Zagreb? Find the nearest recycling yard.",
        "page": "Page",
        "nav_map": "🗺️ Yard map",
        "nav_scan": "📷 Identify waste",
        "nav_kvart": "🏘️ My neighbourhood (points)",
        "filters": "Filters",
        "type": "Yard type",
        "type_opts": {"stalno": "Permanent", "mobilno": "Mobile"},
        "open_now": "Open now only",
        "extra": "Also accepts",
        "extra_opts": {
            "lijekovi": "Old medicines",
            "tekstil": "Textiles and clothes",
            "akumulatori": "Car batteries",
            "fluorescentne_cijevi": "Fluorescent tubes",
            "glomazni_otpad": "Bulky waste",
        },
        "click": "Click on the map to mark your location.",
        "nearest": "Nearest yard",
        "distance": "Distance (straight line)",
        "route": "Route (OpenStreetMap)",
        "open": "Open",
        "closed": "Closed",
        "hours": "Opening hours",
        "phone": "Phone",
        "none": "No yard matches the filters.",
        "you": "Your location",
        "note": "Note: public holidays are not included; check the mobile yard schedule at cistoca.hr.",
        "containers_btn": "Containers in your neighbourhood (City of Zagreb)",
        "show_ug": "Show underground containers (central Zagreb)",
        "show_gc": "Show city district boundaries",
        "gc_name": "City district",
        "ug_name": "Underground container",
        "ug_note": "Underground containers are meant for residents they are assigned to. Only containers from the City of Zagreb open dataset are shown (incomplete list).",
        "containers_help": "Green islands and semi-underground containers are shown on the City of Zagreb map.",
        "scan_title": "Identify waste",
        "scan_intro": "Take a photo of the item you want to throw away and we will tell you where it goes.",
        "src_txt": "Search by text",
        "search": "Type the item name (e.g. battery, pizza box)",
        "search_none": "No results. Try another word or take a photo.",
        "search_pick": "Choose an item",
        "encourage": "🌱 Thank you for sorting your waste properly. Every item counts!",
        "how_title": "How to use Zeleni rudnik",
        "how_1": "**1. Take a photo or type** what you want to throw away (Identify waste page).",
        "how_2": "**2. Confirm the suggestion** and see which bin it goes in or where to take it.",
        "how_3": "**3. Find the nearest yard** on the map and start the route.",
        "how_note": "This is a prototype. Suggestions are automatic and may be wrong, and neighbourhood points are a simulation.",
        "src_cam": "Use camera",
        "src_upl": "Upload image",
        "take": "Take a photo of the item",
        "upload": "Choose an image (jpg, png, webp)",
        "analysing": "Analysing the image...",
        "likely": "Most likely it is",
        "unsure": "I am not sure what is in the picture. Pick the closest option or try again from another angle.",
        "pick": "Which of these is correct?",
        "none_of": "None of these",
        "none_msg": "OK. Try photographing the item closer, on a plain surface and in good light.",
        "category": "Category",
        "where": "Where to dispose",
        "remark": "Note",
        "often_wrong": "People often throw this away in the wrong place.",
        "typical_mistake": "Typical mistake (in Croatian)",
        "sensitive": "We cannot reliably tell this from a photo because it depends on the contents.",
        "confirm": "I confirm this is exactly what is in the packaging",
        "no_pos": "To find the nearest yard, mark your location on the Yard map page.",
        "unavailable": "Waste identification is not available in this version (missing libraries or item table).",
        "no_table": "Item table not found (Zeleni_rudnik_tablica_predmeta.xlsx).",
        "disclaimer": "The suggestion is automatic and may be wrong. If unsure, check the instructions at cistoca.hr.",
    },
}


# ---------------------------------------------------------------- pomoćne funkcije
@st.cache_data
def load_yards() -> pd.DataFrame:
    df = pd.read_csv(CSV_PATH, encoding="utf-8", dtype=str, keep_default_na=False)
    df["lat"] = df["lat"].astype(float)
    df["lon"] = df["lon"].astype(float)
    for col in ["lijekovi", "tekstil", "akumulatori", "fluorescentne_cijevi", "glomazni_otpad"]:
        df[col] = df[col].str.lower().eq("true")
    return df


def to_minutes(hhmm: str):
    if not hhmm:
        return None
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def is_open(row, now: datetime) -> bool:
    """Pon-sub po rasporedu pon_sub_*, nedjelja po ned_* (ako postoji)."""
    if now.weekday() == 6:
        start, end = to_minutes(row["ned_od"]), to_minutes(row["ned_do"])
    else:
        start, end = to_minutes(row["pon_sub_od"]), to_minutes(row["pon_sub_do"])
    if start is None or end is None:
        return False
    current = now.hour * 60 + now.minute
    return start <= current < end


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def hours_text(row) -> str:
    text = f"pon–sub {row['pon_sub_od']}–{row['pon_sub_do']}"
    if row["ned_od"]:
        text += f", ned {row['ned_od']}–{row['ned_do']}"
    return text


def route_url(lat0, lon0, lat1, lon1) -> str:
    return (
        "https://www.openstreetmap.org/directions?engine=fossgis_osrm_car"
        f"&route={lat0:.5f}%2C{lon0:.5f}%3B{lat1:.5f}%2C{lon1:.5f}"
    )


def is_content_dependent(item_hr: str) -> bool:
    name = item_hr.lower()
    return any(key in name for key in CONTENT_DEPENDENT)


def required_yard_flag(item_hr: str):
    name = item_hr.lower()
    for key, flag in YARD_FLAG_BY_KEYWORD.items():
        if key in name:
            return flag
    return None


def goes_to_yard(where_hr: str) -> bool:
    return "dvorišt" in (where_hr or "").lower()


@st.cache_data
@st.cache_data
def load_underground():
    path = Path(__file__).parent / "podzemni_spremnici.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_items():
    """Predmeti iz tablice: HR (B), EN (C), kategorija HR (D), gdje HR (F), napomena (I)."""
    from openpyxl import load_workbook

    ws = load_workbook(TABLE_PATH, data_only=True)["Predmeti"]
    items = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        hr, en = row[1], row[2]
        if hr and en:
            items.append(
                {
                    "hr": str(hr),
                    "en": str(en),
                    "kategorija": str(row[3] or ""),
                    "gdje": str(row[5] or ""),
                    "kategorija_en": str(row[4] or row[3] or ""),
                    "gdje_en": str(row[6] or row[5] or ""),
                    "napomena": str(row[8] or ""),
                    # stupci M i N (Često se krivo baca / Najčešća greška); stara tablica ih nema
                    "krivo": len(row) > 13 and str(row[12] or "").strip().lower() == "da",
                    "greska": str(row[13] or "") if len(row) > 13 else "",
                }
            )
    return items


@st.cache_resource(show_spinner="Učitavam model...")
def load_model():
    from transformers import CLIPModel, CLIPProcessor

    processor = CLIPProcessor.from_pretrained(MODEL_NAME)
    model = CLIPModel.from_pretrained(MODEL_NAME)
    model.eval()
    return processor, model


def classify(image, items):
    """Vraća [(indeks predmeta, vjerojatnost), ...] za TOP_N najvjerojatnijih."""
    import torch

    processor, model = load_model()
    prompts = [f"a photo of {it['en'].lower()}, a piece of waste" for it in items]
    with torch.no_grad():
        inputs = processor(text=prompts, images=image, return_tensors="pt", padding=True)
        probs = model(**inputs).logits_per_image.softmax(dim=-1)[0]
        top = torch.topk(probs, k=min(TOP_N, len(items)))
    return [(int(i), float(p)) for p, i in zip(top.values, top.indices)]


# ---------------------------------------------------------------- stranica: karta
def page_map(t, yards, now):
    st.info(t["click"])

    st.sidebar.header(t["filters"])
    types = st.sidebar.multiselect(
        t["type"],
        options=list(t["type_opts"].keys()),
        default=list(t["type_opts"].keys()),
        format_func=lambda k: t["type_opts"][k],
    )
    only_open = st.sidebar.checkbox(t["open_now"])
    show_ug = st.sidebar.checkbox(t["show_ug"])
    show_gc = st.sidebar.checkbox(t["show_gc"])
    extras = st.sidebar.multiselect(
        t["extra"],
        options=list(t["extra_opts"].keys()),
        format_func=lambda k: t["extra_opts"][k],
    )

    view = yards[yards["tip"].isin(types)]
    if only_open:
        view = view[view["otvoreno"]]
    for col in extras:
        view = view[view[col]]

    fmap = folium.Map(location=ZAGREB_CENTER, zoom_start=11, tiles="OpenStreetMap")
    for _, r in view.iterrows():
        status = t["open"] if r["otvoreno"] else t["closed"]
        popup = (
            f"<b>{r['naziv']}</b><br>{r['adresa']}<br>"
            f"{t['hours']}: {hours_text(r)}<br>"
            f"{t['phone']}: {r['telefon']}<br><b>{status}</b>"
        )
        folium.Marker(
            [r["lat"], r["lon"]],
            popup=folium.Popup(popup, max_width=300),
            tooltip=r["naziv"],
            icon=folium.Icon(
                color="green" if r["tip"] == "stalno" else "orange",
                icon="recycle",
                prefix="fa",
            ),
        ).add_to(fmap)

    if show_gc:
        gc_path = Path(__file__).parent / "gradske_cetvrti.geojson"
        if gc_path.exists():
            folium.GeoJson(
                gc_path.read_text(encoding="utf-8"),
                style_function=lambda f: {
                    "color": "#2e7d32",
                    "weight": 2,
                    "fillColor": "#a5d6a7",
                    "fillOpacity": 0.15,
                },
                highlight_function=lambda f: {"fillOpacity": 0.35},
                tooltip=folium.GeoJsonTooltip(
                    fields=["JMS_IME"], aliases=[t["gc_name"] + ":"]
                ),
            ).add_to(fmap)

    if show_ug:
        ug = load_underground()
        for _, r in ug.iterrows():
            folium.CircleMarker(
                [r["lat"], r["lon"]],
                radius=5,
                color="#1b5e20",
                fill=True,
                fill_opacity=0.8,
                tooltip=f"{t['ug_name']}: {r['naziv']}",
            ).add_to(fmap)

    if st.session_state.user_pos:
        folium.Marker(
            st.session_state.user_pos,
            tooltip=t["you"],
            icon=folium.Icon(color="blue", icon="user", prefix="fa"),
        ).add_to(fmap)

    result = st_folium(fmap, height=520, use_container_width=True, returned_objects=["last_clicked"])
    if result and result.get("last_clicked"):
        pos = (result["last_clicked"]["lat"], result["last_clicked"]["lng"])
        if pos != st.session_state.user_pos:
            st.session_state.user_pos = pos
            st.rerun()

    if view.empty:
        st.warning(t["none"])
    elif st.session_state.user_pos:
        lat0, lon0 = st.session_state.user_pos
        view = view.assign(
            km=view.apply(lambda r: haversine_km(lat0, lon0, r["lat"], r["lon"]), axis=1)
        ).sort_values("km")
        best = view.iloc[0]
        st.subheader(t["nearest"])
        c1, c2, c3 = st.columns(3)
        c1.metric(best["naziv"], t["open"] if best["otvoreno"] else t["closed"])
        c2.metric(t["distance"], f"{best['km']:.1f} km")
        c3.markdown(f"**{t['hours']}:** {hours_text(best)}  \n**{t['phone']}:** {best['telefon']}")
        st.link_button(t["route"], route_url(lat0, lon0, best["lat"], best["lon"]))

    st.divider()
    if show_ug:
        st.caption(t["ug_note"])
    st.caption(t["containers_help"])
    st.link_button(t["containers_btn"], "https://spremnici.zagreb.hr/")
    st.caption(t["note"])


# ---------------------------------------------------------------- stranica: prepoznavanje
def show_nearest_yard(t, yards, flag):
    """Najbliže stalno dvorište (koje prima traženu vrstu otpada, ako je zadana)."""
    if not st.session_state.user_pos:
        st.info(t["no_pos"])
        return
    lat0, lon0 = st.session_state.user_pos
    pool = yards[yards["tip"] == "stalno"]
    if flag:
        pool = pool[pool[flag]]
    if pool.empty:
        st.warning(t["none"])
        return
    pool = pool.assign(
        km=pool.apply(lambda r: haversine_km(lat0, lon0, r["lat"], r["lon"]), axis=1)
    ).sort_values("km")
    best = pool.iloc[0]
    st.subheader(t["nearest"])
    c1, c2, c3 = st.columns(3)
    c1.metric(best["naziv"], t["open"] if best["otvoreno"] else t["closed"])
    c2.metric(t["distance"], f"{best['km']:.1f} km")
    c3.markdown(f"**{t['hours']}:** {hours_text(best)}  \n**{t['phone']}:** {best['telefon']}")
    st.link_button(t["route"], route_url(lat0, lon0, best["lat"], best["lon"]))


CATEGORY_COLOURS = [
    ("opasn", "#fee2e2", "#991b1b"),
    ("baterij", "#fee2e2", "#991b1b"),
    ("elektr", "#ede9fe", "#5b21b6"),
    ("plastik", "#fef3c7", "#7a5b00"),
    ("papir", "#dbeafe", "#1e40af"),
    ("staklo", "#d1fae5", "#065f46"),
    ("bio", "#efe4d3", "#5b3a1a"),
    ("zeleni", "#dcfce7", "#166534"),
    ("tekstil", "#fce7f3", "#9d174d"),
    ("glomaz", "#ffedd5", "#9a3412"),
    ("miješani", "#e5e7eb", "#374151"),
    ("metal", "#e0e7ff", "#3730a3"),
]


def category_badge(name, label=None):
    low = name.lower()
    bg, fg = "#e8f5e9", "#1b5e20"
    for key, b, f in CATEGORY_COLOURS:
        if key in low:
            bg, fg = b, f
            break
    return (
        f'<span class="zr-badge" style="background:{bg};color:{fg}">'
        f"{html.escape(label or name)}</span>"
    )


HERO_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 200'>"
    "<g fill='#ffffff' fill-opacity='0.22'>"
    "<path d='M60 190 C20 140 40 70 120 40 C140 110 120 160 60 190Z'/>"
    "<path d='M140 190 C110 130 150 60 240 30 C250 110 210 170 140 190Z'/>"
    "<path d='M215 195 C200 160 220 120 270 100 C285 150 260 185 215 195Z'/>"
    "</g>"
    "<g stroke='#ffffff' stroke-opacity='0.35' stroke-width='3' fill='none'>"
    "<path d='M60 190 C75 140 95 90 120 40'/>"
    "<path d='M140 190 C170 130 200 80 240 30'/>"
    "</g></svg>"
)
HERO_URI = "data:image/svg+xml;base64," + base64.b64encode(HERO_SVG.encode("utf-8")).decode("ascii")


STYLE = """
<style>
:root, .stApp { color-scheme: dark; }
.stApp { background: #46591a; }
div.block-container { padding-top: 4rem; }
header[data-testid="stHeader"] { background: transparent; }
section[data-testid="stSidebar"] > div { background: #364614; }
section[data-testid="stSidebar"] { border-right: 1px solid #6b7f2e; }
h1, h2, h3, h4, html, body, .stApp, .stApp p, .stApp li, .stApp label, .stApp span,
div[data-testid="stCaptionContainer"], div[data-testid="stCaptionContainer"] p, .stApp small,
div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] p,
div[data-testid="stMetricValue"], div[data-testid="stExpander"] summary * { color: #ffffff !important; opacity: 1 !important; }
.zr-badge, .zr-badge * { color: inherit !important; }
div[data-testid="stAlert"] { background: #2b3810 !important; border: 1px solid #b8c97a; border-radius: 14px; }
div[data-testid="stAlert"] * { color: #ffffff !important; opacity: 1 !important; }
div[data-baseweb="input"] *, div[data-baseweb="select"] *, div[data-baseweb="textarea"] *,
div[data-testid="stFileUploader"] section * { color: #1f2a0c !important; }
div.stButton > button, div[data-testid="stLinkButton"] a {
    border-radius: 12px; background: #6f8a26; border: 1px solid #b8c97a;
}
div.stButton > button *, div[data-testid="stLinkButton"] a * { color: #ffffff !important; }
div[data-testid="stExpander"] { background: rgba(0,0,0,0.22); border: 1px solid #6b7f2e; border-radius: 14px; }
div[data-testid="stMetric"] { background: rgba(0,0,0,0.22); border: 1px solid #6b7f2e; border-radius: 14px; padding: 0.6rem 0.9rem; }
.zr-hero {
    background: linear-gradient(135deg, #4f6b17 0%, #8aa43a 100%);
    padding: 1.2rem 1.5rem; border-radius: 18px; margin-bottom: 1rem;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}
.zr-hero, .zr-hero h1, .zr-hero p { color: #ffffff !important; }
.zr-hero h1 { margin: 0; font-size: 2.1rem; padding: 0; }
.zr-hero p { margin: 0.3rem 0 0 0; font-size: 1.05rem; }
.zr-photos { display: flex; gap: 0.6rem; margin-bottom: 1rem; }
.zr-photos img { flex: 1 1 0; min-width: 0; height: 130px; object-fit: cover; border-radius: 14px; border: 2px solid #ffffff; }
.zr-quote {
    font-family: Georgia, 'Times New Roman', serif; font-style: italic; font-weight: 700;
    font-size: 1.15rem; line-height: 1.35; text-align: center; color: #ffffff !important;
    letter-spacing: 0.04em; padding: 0.9rem 0.8rem; margin-bottom: 0.8rem;
    background: rgba(0,0,0,0.2); border-top: 3px solid #b8c97a; border-bottom: 3px solid #b8c97a;
    border-radius: 6px;
}
.zr-footer {
    margin-top: 2rem; padding: 1rem 1.3rem; border-radius: 16px;
    background: #2b3810; text-align: center; font-size: 1.05rem;
    border: 1px solid #b8c97a;
}
.zr-footer, .zr-footer p { color: #ffffff !important; }
.zr-badge {
    display: inline-block; padding: 0.2rem 0.8rem; border-radius: 999px;
    font-weight: 600; font-size: 0.9rem;
}
</style>
"""


PHOTO_DIR = Path(__file__).parent / "slike"


def scene_strip():
    """Gornji dio naslovnice: vaše fotografije iz mape slike/ ili ilustracije ako je mapa prazna."""
    uris = []
    if PHOTO_DIR.is_dir():
        for f in sorted(PHOTO_DIR.iterdir())[:3]:
            mime = {".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp"}.get(f.suffix.lower())
            if mime:
                uris.append(f"data:image/{mime};base64," + base64.b64encode(f.read_bytes()).decode("ascii"))
    if not uris:
        def tile(bg, body):
            svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 300 130' preserveAspectRatio='xMidYMid slice'>"
                   f"<rect width='300' height='130' fill='{bg}'/>{body}</svg>")
            return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
        bins = "".join(
            f"<rect x='{x}' y='50' width='44' height='62' rx='6' fill='{c}'/><rect x='{x - 3}' y='44' width='50' height='9' rx='3' fill='#37474f'/>"
            for x, c in ((50, "#1976d2"), (128, "#fbc02d"), (206, "#388e3c")))
        tree = ("<rect y='100' width='300' height='30' fill='#8bc34a'/><rect x='140' y='55' width='14' height='50' fill='#6d4c41'/>"
                "<circle cx='147' cy='45' r='34' fill='#2e7d32'/><circle cx='120' cy='65' r='22' fill='#388e3c'/><circle cx='175' cy='65' r='22' fill='#388e3c'/>")
        flowers = "<rect y='95' width='300' height='35' fill='#8bc34a'/>" + "".join(
            f"<line x1='{x}' y1='115' x2='{x}' y2='80' stroke='#2e7d32' stroke-width='4'/><circle cx='{x}' cy='72' r='11' fill='{c}'/><circle cx='{x}' cy='72' r='4' fill='#f9a825'/>"
            for x, c in ((50, "#f48fb1"), (105, "#fff176"), (160, "#ce93d8"), (215, "#f48fb1"), (265, "#fff176")))
        uris = [tile("#e3f2fd", bins), tile("#e3f2fd", tree), tile("#fff9c4", flowers)]
    imgs = "".join(f'<img src="{u}" alt="">' for u in uris)
    st.markdown(f'<div class="zr-photos">{imgs}</div>', unsafe_allow_html=True)


FOOTER = {
    "hr": [
        "♻️ Svaki razvrstani predmet je jedan manje na odlagalištu. Hvala ti što si dio promjene!",
        "🌱 Otpad nije smeće dok ga ne pomiješamo. Razvrstaj ga i daj mu novi život!",
        "🌍 Mali koraci svakog građana zajedno čine čist i zelen Zagreb.",
    ],
    "en": [
        "♻️ Every item you sort is one less in the landfill. Thank you for being part of the change!",
        "🌱 Waste only becomes trash when we mix it. Sort it and give it a new life!",
        "🌍 Small steps from every citizen together make a clean and green Zagreb.",
    ],
}


def show_footer(lang, idx):
    st.markdown(f'<div class="zr-footer">{html.escape(FOOTER[lang][idx])}</div>', unsafe_allow_html=True)


def show_item(t, lang, item, yards):
    name_key = "hr" if lang == "hr" else "en"
    st.subheader(item[name_key])
    st.caption(t["encourage"])
    cat_label = item["kategorija"] if lang == "hr" else item["kategorija_en"]
    where_label = item["gdje"] if lang == "hr" else item["gdje_en"]
    st.markdown(
        f"**{t['category']}:** " + category_badge(item["kategorija"], cat_label),
        unsafe_allow_html=True,
    )
    st.markdown(f"**{t['where']}:** {where_label}")
    if item["napomena"]:
        st.markdown(f"**{t['remark']}:** {item['napomena']}")

    if item["krivo"]:
        text = f"**{t['often_wrong']}**"
        if item["greska"]:
            text += f"  \n{t['typical_mistake']}: {item['greska']}"
        st.warning(text, icon="⚠️")

    if is_content_dependent(item["hr"]):
        st.warning(t["sensitive"])
        if not st.checkbox(t["confirm"], key="confirm_" + item["hr"]):
            return

    if goes_to_yard(item["gdje"]):
        show_nearest_yard(t, yards, required_yard_flag(item["hr"]))

    st.caption(t["disclaimer"])


def page_scan(t, lang, yards):
    st.header(t["scan_title"])
    st.write(t["scan_intro"])

    try:
        items = load_items()
    except FileNotFoundError:
        st.error(t["no_table"])
        return
    name_key = "hr" if lang == "hr" else "en"

    source = st.radio(
        t["scan_title"],
        [t["src_cam"], t["src_upl"], t["src_txt"]],
        horizontal=True,
        label_visibility="collapsed",
    )

    # --- pretraga tekstom (ne treba model)
    if source == t["src_txt"]:
        q = st.text_input(t["search"]).strip().lower()
        if not q:
            return
        matches = [it for it in items if q in it["hr"].lower() or q in it["en"].lower()]
        if not matches:
            st.info(t["search_none"])
            return
        item = st.selectbox(t["search_pick"], matches, format_func=lambda it: it[name_key])
        show_item(t, lang, item, yards)
        return

    # --- fotografija
    try:
        from PIL import Image, ImageOps
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        st.warning(t["unavailable"])
        return

    if source == t["src_cam"]:
        file = st.camera_input(t["take"])
    else:
        file = st.file_uploader(t["upload"], type=["jpg", "jpeg", "png", "webp"])
    if file is None:
        return

    image = ImageOps.exif_transpose(Image.open(file)).convert("RGB")
    st.image(image, width=300)

    with st.spinner(t["analysing"]):
        top = classify(image, items)

    best_idx, best_p = top[0]
    if best_p >= CONFIDENCE_THRESHOLD:
        st.success(f"{t['likely']}: **{items[best_idx][name_key]}** ({best_p:.0%})")
    else:
        st.warning(t["unsure"])

    options = [idx for idx, _ in top] + [-1]
    probs = dict(top)

    def label(idx):
        if idx == -1:
            return t["none_of"]
        return f"{items[idx][name_key]} ({probs[idx]:.0%})"

    choice = st.radio(t["pick"], options, format_func=label, index=0)
    if choice == -1:
        st.info(t["none_msg"])
        return

    show_item(t, lang, items[choice], yards)


# ---------------------------------------------------------------- glavni dio
def main():
    st.set_page_config(page_title="Zeleni rudnik", page_icon="♻️", layout="wide")

    if "user_pos" not in st.session_state:
        st.session_state.user_pos = None

    quote_box = st.sidebar.container()
    lang = st.sidebar.radio("Jezik / Language", ["hr", "en"], horizontal=True)
    quote = {
        "hr": "„ONO ŠTO BACAMO NIJE SMEĆE NEGO SIROVINA“",
        "en": "“WHAT WE THROW AWAY IS NOT TRASH BUT A RESOURCE”",
    }[lang]
    quote_box.markdown(f'<div class="zr-quote">{quote}</div>', unsafe_allow_html=True)
    t = TEXT[lang]

    st.markdown(STYLE, unsafe_allow_html=True)
    st.markdown(
        f'<div class="zr-hero" style="background-image:url({HERO_URI}),linear-gradient(135deg,#4f6b17,#8aa43a);'
        f'background-repeat:no-repeat,no-repeat;background-position:right 1rem center,center;'
        f'background-size:auto 95%,cover"><h1>♻️ {html.escape(t["title"])}</h1>'
        f'<p>{html.escape(t["subtitle"])}</p></div>',
        unsafe_allow_html=True,
    )

    scene_strip()

    with st.expander(t["how_title"], expanded=True):
        st.markdown(t["how_1"])
        st.markdown(t["how_2"])
        st.markdown(t["how_3"])
        st.caption(t["how_note"])

    yards = load_yards()
    now = datetime.now(ZoneInfo("Europe/Zagreb"))
    yards["otvoreno"] = yards.apply(lambda r: is_open(r, now), axis=1)

    page = st.sidebar.radio(t["page"], ["map", "scan", "kvart"], format_func=lambda k: t["nav_" + k])

    if page == "map":
        page_map(t, yards, now)
        show_footer(lang, 0)
    elif page == "scan":
        page_scan(t, lang, yards)
        show_footer(lang, 1)
    else:
        from kvart import page_kvart

        page_kvart(lang)
        show_footer(lang, 2)


if __name__ == "__main__":
    main()
