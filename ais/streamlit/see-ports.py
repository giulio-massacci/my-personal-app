import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import geopandas as gpd
import h3ronpy.pandas.vector as hrpv
from h3ronpy import grid_disk
from h3ronpy.vector import coordinates_to_cells

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
        sep=";"
    )

    no_ita_ports = pd.read_csv(
        "https://raw.githubusercontent.com/istat-methodology/istat-ais-lib/refs/heads/main/data/porti_WORLD_NO_ITA_K3_RES8_NO_DUP_v3.csv",
        sep=";"
    )

    offshore_platforms = pd.read_csv(
        "https://raw.githubusercontent.com/istat-methodology/istat-ais-lib/refs/heads/main/data/OFFSHORE_PLATFORM.csv",
        sep=";"
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
    h3_indexes = df[h3_column].apply(lambda x: int(x, 16)).values
    geometries = hrpv.cells_to_polygons(h3_indexes)
    valid_idx = [i for i, g in enumerate(geometries) if g is not None]
    df_valid = df.iloc[valid_idx].copy()
    gdf = gpd.GeoDataFrame(
        df_valid,
        geometry=[geometries[i] for i in valid_idx],
        crs="EPSG:4326"
    )
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
    m = folium.Map(location=center, zoom_start=zoom)
    m.get_root().html.add_child(folium.Element("""
        <style>
        .leaflet-container {
            cursor: default !important;
        }
        </style>
    """))
    return m

def add_gdf_to_map(m, gdf, color):
    gdf_c = gdf.copy()
    gdf_c["H3_int_index_8"] = gdf_c["H3_int_index_8"].astype(str)
    folium.GeoJson(
        gdf_c,
        tooltip=folium.GeoJsonTooltip(
            fields=["Name", "H3_hex_8", "H3_int_index_8"],
            aliases=["Nome:", "H3 Hex:", "H3 Int:"],
            localize=True,
            labels=True,
            sticky=False,
        ),
        popup=folium.GeoJsonPopup(
            fields=["Name", "H3_hex_8", "H3_int_index_8"],
            aliases=["Nome:", "H3 Hex:", "H3 Int:"],
        ),
        style_function=lambda feature: {
            "fillColor": color,
            "color": color,
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
# INIZIALIZZA SESSION_STATE
# =====================================================
if "tab1_click_polygons" not in st.session_state:
    st.session_state.tab1_click_polygons = []

if "tab2_polygons" not in st.session_state:
    st.session_state.tab2_polygons = []

# =====================================================
# TABS
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

    # Aggiungi poligoni cliccati precedentemente
    for gdf_saved in st.session_state.tab1_click_polygons:
        add_gdf_to_map(m1, gdf_saved, "red")

    folium.LayerControl().add_to(m1)
    map_data = st_folium(m1, width=900, height=600, key="tab1_map", returned_objects=["last_clicked"])

    # Aggiungi nuovo poligono se cliccato
    if map_data and map_data.get("last_clicked"):
        lat_click = map_data["last_clicked"]["lat"]
        lon_click = map_data["last_clicked"]["lng"]
        int_cells = coordinates_to_cells(latarray=[lat_click], lngarray=[lon_click], resarray=8)
        h3_int = int(int_cells[0].as_py())
        h3_hex = format(h3_int, "x")

        geometries = hrpv.cells_to_polygons(int_cells)
        gdf_hex = gpd.GeoDataFrame(
            {
                "Name": ["New Hexagon"],
                "H3_hex_8": [h3_hex],
                "H3_int_index_8": [h3_int]
            },
            geometry=geometries,
            crs="EPSG:4326"
        )

        # Salva in session_state
        st.session_state.tab1_click_polygons.append(gdf_hex)

        st.success(f"📍 Coordinate cliccate: Lat: {lat_click}, Lon: {lon_click}, H3 Hex: {h3_hex}, H3 Int: {h3_int}")

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
        int_cells = coordinates_to_cells(latarray=[lat], lngarray=[lon], resarray=resolution)
        h3_int = int(int_cells[0].as_py())
        h3_ring = grid_disk([h3_int], k=k_ring, flatten=True)
        geometries = hrpv.cells_to_polygons(h3_ring)

        gdf_ring = gpd.GeoDataFrame(
            {
                "Name": ["Ring"] * len(h3_ring),
                "H3_hex_8": [format(cell.as_py(), "x") for cell in h3_ring],
                "H3_int_index_8": [int(cell.as_py()) for cell in h3_ring]
            },
            geometry=geometries,
            crs="EPSG:4326"
        )

        # Salva in session_state
        st.session_state.tab2_polygons.append(gdf_ring)

    # mappa
    m2 = create_map([lat, lon], 6)
    add_gdf_to_map(m2, gdf_data, "blue")
    for gdf_saved in st.session_state.tab2_polygons:
        add_gdf_to_map(m2, gdf_saved, "red")
    folium.LayerControl().add_to(m2)
    st_folium(m2, width=900, height=600, key="tab2_map", returned_objects=["last_clicked"])