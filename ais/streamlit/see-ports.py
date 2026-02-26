import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import h3ronpy.pandas.vector as hrpv
from h3ronpy import grid_disk
import numpy as np

# =====================================================
# CONFIG APP
# =====================================================
st.set_page_config(layout="wide")
st.title("🌍 AIS - Visualizzazione porti e H3")

# =====================================================
# LOAD DATA (UNA SOLA VOLTA)
# =====================================================
@st.cache_data
def load_data():

    ita_ports = pd.read_csv(
        "https://raw.githubusercontent.com/istat-methodology/istat-ais-lib/refs/heads/main/data/Porti_ITA_fitted_RES_8_V3.csv",
        sep=";",
        dtype={"H3_hex_8": str}
    )

    no_ita_ports = pd.read_csv(
        "https://raw.githubusercontent.com/istat-methodology/istat-ais-lib/refs/heads/main/data/porti_WORLD_NO_ITA_K3_RES8_NO_DUP_v3.csv",
        sep=";",
        dtype={"H3_hex_8": str}
    )

    offshore_platforms = pd.read_csv(
        "https://raw.githubusercontent.com/istat-methodology/istat-ais-lib/refs/heads/main/data/OFFSHORE_PLATFORM.csv",
        sep=";",
        dtype={"H3_hex_8": str}
    )

    return {
        "Italian ports (v3)": ita_ports,
        "No italian ports (v3)": no_ita_ports,
        "Offshore platforms (v1)": offshore_platforms,
    }


# =====================================================
# CONVERSIONE H3 → GEOMETRIE (COSTOSA)
# =====================================================
def h3_to_gdf(df, h3_column):

    # HEX string → uint64 corretto per h3ronpy
    h3_uint64 = df[h3_column].apply(lambda x: int(x, 16)).values

    geometries = hrpv.cells_to_polygons(h3_uint64)
    valid_idx = [i for i, geom in enumerate(geometries) if geom is not None]
    df_valid = df.iloc[valid_idx].copy()

    gdf = gpd.GeoDataFrame(df_valid, geometry=[geometries[i] for i in valid_idx], crs="EPSG:4326")

    return gdf

# =====================================================
# PRECALCOLO GEOMETRIE (CHIAVE DELLA PERFORMANCE)
# =====================================================
@st.cache_data(show_spinner="Costruzione geometrie H3...")
def build_all_gdfs(datasets):

    gdfs = {}

    for name, df in datasets.items():
        gdfs[name] = h3_to_gdf(df, "H3_hex_8")

    return gdfs


# =====================================================
# MAPPA BASE
# =====================================================
def create_map(center=[42.23, 12.97], zoom=5):
    return folium.Map(location=center, zoom_start=zoom)


def add_gdf_to_map(m, gdf, color):

    for _, row in gdf.iterrows():
        folium.GeoJson(
            row.geometry.__geo_interface__,
            tooltip=row.get("Name", ""),
            style_function=lambda x, c=color: {
                "fillColor": c,
                "color": c,
                "weight": 0.7,
                "fillOpacity": 0.4,
            },
        ).add_to(m)

    return m


# =====================================================
# LOAD + PRECALCOLO (UNA VOLTA SOLA)
# =====================================================
DATASETS = load_data()
ALL_GDFS = build_all_gdfs(DATASETS)

# =====================================================
# TABS (MEGLIO DI RADIO)
# =====================================================
tab1, tab2 = st.tabs(
    ["Porti e piattaforme", "Poligoni H3 da coordinate"]
)

# =====================================================
# TAB 1
# =====================================================
with tab1:

    st.subheader("Visualizzazione porti e piattaforme")

    dataset_choice = st.selectbox(
        "Seleziona dataset",
        list(ALL_GDFS.keys()),
        key="tab1_dataset"
    )

    gdf = ALL_GDFS[dataset_choice]

    # filtro dinamico SOLO per world
    if dataset_choice == "No italian ports (v3)":

        country = st.selectbox(
            "Seleziona Paese",
            sorted(gdf["Country"].dropna().unique())
        )

        gdf = gdf[gdf["Country"] == country]

        port = st.selectbox(
            "Seleziona Porto",
            sorted(gdf["Name"].dropna().unique())
        )

        gdf = gdf[gdf["Name"] == port]

    m1 = create_map()
    add_gdf_to_map(m1, gdf, "blue")

    folium.LayerControl().add_to(m1)
    st_folium(m1, width=900, height=600)


# =====================================================
# TAB 2
# =====================================================
with tab2:

    st.subheader("Generazione poligoni H3 da coordinate")

    dataset_choice = st.selectbox(
        "Dataset",
        list(ALL_GDFS.keys()),
        key="tab2_dataset"
    )

    gdf_data = ALL_GDFS[dataset_choice]

    if dataset_choice == "No italian ports (v3)":

        country = st.selectbox(
            "Seleziona Paese",
            sorted(gdf_data["Country"].dropna().unique())
        )

        gdf_data = gdf_data[gdf_data["Country"] == country]

        port = st.selectbox(
            "Seleziona Porto",
            sorted(gdf_data["Name"].dropna().unique())
        )

        gdf_data = gdf_data[gdf_data["Name"] == port]

    # ---------------- INPUT ----------------
    col1, col2, col3, col4 = st.columns(4)

    lat = col1.number_input("Latitudine", value=42.0, format="%.6f")
    lon = col2.number_input("Longitudine", value=12.0, format="%.6f")
    resolution = col3.slider("Risoluzione H3", 0, 10, 8)
    k_ring = col4.slider("Ring k", 1, 5, 1)

    if st.button("Genera poligoni H3"):

        # punto
        gdf_point = gpd.GeoDataFrame(
            geometry=gpd.points_from_xy([lon], [lat]),
            crs="EPSG:4326"
        )

        df_h3 = hrpv.geodataframe_to_cells(
            gdf_point,
            resolution=resolution
        )

        h3_ring = grid_disk(
            [df_h3["cell"].iloc[0]],
            k=k_ring,
            flatten=True
        )

        geometries = hrpv.cells_to_polygons(h3_ring)
        gdf_ring = gpd.GeoDataFrame(
            geometry=geometries,
            crs="EPSG:4326"
        )

        # mappa
        m2 = create_map([lat, lon], 6)

        add_gdf_to_map(m2, gdf_data, "blue")
        add_gdf_to_map(m2, gdf_ring, "red")

        folium.LayerControl().add_to(m2)
        st_folium(m2, width=900, height=600)