import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import h3
import branca.colormap

# ----------------------------------------------------
# Caricamento dati
# ----------------------------------------------------
@st.cache_data
def load_data():
    porti = pd.read_csv(
        "https://raw.githubusercontent.com/istat-methodology/istat-ais-lib/refs/heads/main/data/Porti_WORLD_NO_ITA_K3_RES8_NO_DUP.csv",
        sep=";"
    )
    porti_v2 = pd.read_csv(
        "https://raw.githubusercontent.com/istat-methodology/istat-ais-lib/refs/heads/main/data/Porti_WORLD_NO_ITA_K3_RES8_NO_DUP_v2.csv",
        sep=";"
    )
    return porti, porti_v2


# ----------------------------------------------------
# Funzione conversione H3 → GeoJSON
# ----------------------------------------------------
def h3_to_geoj(df, column):
    geojson_out = {
        "type": "FeatureCollection",
        "features": []
    }

    for _, i in df.iterrows():
        geojson_out["features"].append({
            "type": "Feature",
            "properties": {
                "name": i[column[1]]
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    h3.h3_to_geo_boundary(i[column[0]], geo_json=True)
                ]
            }
        })

    return geojson_out


# ----------------------------------------------------
# Streamlit APP
# ----------------------------------------------------

st.title("🌍 AIS - Visualizzazione porti")

# Carico i dati
porti, porti_v2 = load_data()

st.markdown(
    """
    <a href="https://unece.org/trade/cefact/unlocode-code-list-country-and-territory" target="_blank">
        <button style="
            background-color:#0068c9;
            border:none;
            color:white;
            padding:8px 16px;
            text-align:center;
            text-decoration:none;
            display:inline-block;
            font-size:16px;
            border-radius:6px;
            cursor:pointer;
        ">
            🌐 Apri lista UN/LOCODE (UNECE)
        </button>
    </a>
    """,
    unsafe_allow_html=True
)

# ----------------------------------------------------
# SELECTBOX: Scegli il dataset
# ----------------------------------------------------
dataset_choice = st.selectbox(
    "Seleziona il dataset",
    ["Dataset 1 (porti)", "Dataset 2 (porti_v2)"]
)

# Associa la scelta al dataframe corretto
if dataset_choice == "Dataset 1 (porti)":
    df = porti
else:
    df = porti_v2

# ----------------------------------------------------
# SELECTBOX Country (dipendente dal dataset scelto)
# ----------------------------------------------------
country_list = sorted(df["Country"].dropna().unique())
selected_country = st.selectbox("Seleziona il Paese", country_list)

# Filtra sul Paese scelto
df_country = df[df["Country"] == selected_country]

# ----------------------------------------------------
# SELECTBOX Porto (dipendente da Country + Dataset)
# ----------------------------------------------------
port_list = sorted(df_country["Name"].dropna().unique())
selected_port = st.selectbox("Seleziona il Porto", port_list)

# Filtra un singolo porto
df_port = df_country[df_country["Name"] == selected_port]

# Converto in GeoJSON
port_geojson_out = h3_to_geoj(df_port, ["H3_hex_8", "Name"])

# ----------------------------------------------------
# Creazione mappa Folium
# ----------------------------------------------------
map_center = [42.233235, 12.975832]
m = folium.Map(location=map_center, zoom_start=5)

folium.GeoJson(
    port_geojson_out,
    name="Port",
    tooltip=folium.features.GeoJsonTooltip(
        fields=["name"],
        aliases=["Porto:"],
        style=("background-color: white; color: #333333; "
               "font-family: arial; font-size: 12px; padding: 10px;")
    ),
    style_function=lambda x: {
        "fillColor": "blue",
        "color": "blue",
        "weight": 0.7,
        "fillOpacity": 0.4
    }
).add_to(m)

folium.LayerControl().add_to(m)

# ----------------------------------------------------
# Visualizzazione mappa in Streamlit
# ----------------------------------------------------
st_folium(m, width=800, height=600)
