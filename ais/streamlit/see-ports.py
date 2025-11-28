import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import geopandas as gpd
from shapely.geometry import Polygon
import h3ronpy.pandas.vector as hrpv

# ----------------------------------------------------
# Caricamento dati
# ----------------------------------------------------
@st.cache_data
def load_data():
    # Usa URL pubblici o metti i CSV nella cartella del repo
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
# Funzione conversione H3 → GeoDataFrame
# ----------------------------------------------------
def h3_to_gdf(df, h3_column, name_column):
    # converte H3 → geometrie poligoni Shapely
    geometries = hrpv.cells_to_polygons(df[h3_column].values)
    
    # filtra eventuali None (celle non valide)
    valid_idx = [i for i, geom in enumerate(geometries) if geom is not None]
    df_valid = df.iloc[valid_idx].copy()
    gdf = gpd.GeoDataFrame(df_valid, geometry=[geometries[i] for i in valid_idx], crs="EPSG:4326")
    return gdf

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
df = porti if dataset_choice == "Dataset 1 (porti)" else porti_v2

# ----------------------------------------------------
# SELECTBOX Country
# ----------------------------------------------------
country_list = sorted(df["Country"].dropna().unique())
selected_country = st.selectbox("Seleziona il Paese", country_list)
df_country = df[df["Country"] == selected_country]

# ----------------------------------------------------
# SELECTBOX Porto
# ----------------------------------------------------
port_list = sorted(df_country["Name"].dropna().unique())
selected_port = st.selectbox("Seleziona il Porto", port_list)
df_port = df_country[df_country["Name"] == selected_port]

# ----------------------------------------------------
# Converto H3 → GeoDataFrame
# ----------------------------------------------------
gdf_port = h3_to_gdf(df_port, "H3_int_index_8", "Name")

# ----------------------------------------------------
# Creazione mappa Folium
# ----------------------------------------------------
map_center = [42.233235, 12.975832]
m = folium.Map(location=map_center, zoom_start=5)

for _, row in gdf_port.iterrows():
    folium.GeoJson(
        row.geometry.__geo_interface__,
        name=row["Name"],
        tooltip=folium.Tooltip(f"Porto: {row['Name']}"),
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
