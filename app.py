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
        "nav_map": "Karta dvorišta",
        "nav_scan": "Prepoznaj otpad",
        "nav_kvart": "Moj kvart (bodovi)",
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
        "title": "Zeleni rudnik",
        "subtitle": "Where to take your waste in Zagreb? Find the nearest recycling yard.",
        "page": "Page",
        "nav_map": "Yard map",
        "nav_scan": "Identify waste",
        "nav_kvart": "My neighbourhood (points)",
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


def show_item(t, lang, item, yards):
    name_key = "hr" if lang == "hr" else "en"
    st.subheader(item[name_key])
    st.markdown(f"**{t['category']}:** {item['kategorija']}")
    st.markdown(f"**{t['where']}:** {item['gdje']}")
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

    lang = st.sidebar.radio("Jezik / Language", ["hr", "en"], horizontal=True)
    t = TEXT[lang]

    st.title(t["title"])
    st.caption(t["subtitle"])

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
    elif page == "scan":
        page_scan(t, lang, yards)
    else:
        from kvart import page_kvart

        page_kvart(lang)


if __name__ == "__main__":
    main()
