import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import geopandas as gpd
from shapely.geometry import Polygon
import h3ronpy.pandas.vector as hrpv
from h3ronpy import grid_disk

# ----------------------------------------------------
# Caricamento dati
# ----------------------------------------------------
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
    return ita_ports, no_ita_ports, offshore_platforms

# ----------------------------------------------------
# Funzione conversione H3 → GeoDataFrame
# ----------------------------------------------------
def h3_to_gdf(df, h3_column, name_column):
    h3_indexes = df[h3_column].apply(lambda x: int(x, 16)).values
    geometries = hrpv.cells_to_polygons(h3_indexes)
    valid_idx = [i for i, geom in enumerate(geometries) if geom is not None]
    df_valid = df.iloc[valid_idx].copy()
    gdf = gpd.GeoDataFrame(df_valid, geometry=[geometries[i] for i in valid_idx], crs="EPSG:4326")
    return gdf

# ----------------------------------------------------
# Inizializza session_state per bottone H3
# ----------------------------------------------------
if "generate_h3" not in st.session_state:
    st.session_state.generate_h3 = False

# ----------------------------------------------------
# Caricamento dati
# ----------------------------------------------------
ita_ports, no_ita_ports, offshore_platforms = load_data()

# ----------------------------------------------------
# Streamlit APP con radio per selezione tab
# ----------------------------------------------------
st.title("🌍 AIS - Visualizzazione porti e H3")
selected_tab = st.radio("Seleziona Tab", ["Porti e piattaforme", "Poligoni H3 da coordinate"])

# ================= TAB 1 =================
if selected_tab == "Porti e piattaforme":
    st.markdown("### Visualizzazione porti e piattaforme")
    
    dataset_choice = st.selectbox(
        "Seleziona il dataset",
        ["Italian ports (v3)", "No italian ports (v3)", "Offshore platforms (v1)"],
        key="tab1_dataset"
    )
    
    df = []
    if dataset_choice == "Italian ports (v3)":
        df = ita_ports
    elif dataset_choice == "No italian ports (v3)":
        df = no_ita_ports
    else:
        df = offshore_platforms
    
    if dataset_choice != "No italian ports (v3)":
        df_port = df
    else:
        country_list = sorted(df["Country"].dropna().unique())
        selected_country = st.selectbox("Seleziona il Paese", country_list, key="tab1_country")
        df_country = df[df["Country"] == selected_country]

        port_list = sorted(df_country["Name"].dropna().unique())
        selected_port = st.selectbox("Seleziona il Porto", port_list, key="tab1_port")
        df_port = df_country[df_country["Name"] == selected_port]
    
    gdf_port = h3_to_gdf(df_port, "H3_hex_8", "Name")
    
    map_center = [42.233235, 12.975832]
    m1 = folium.Map(location=map_center, zoom_start=5)
    
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
        ).add_to(m1)
    
    folium.LayerControl().add_to(m1)
    st_folium(m1, width=800, height=600)

# ================= TAB 2 =================
elif selected_tab == "Poligoni H3 da coordinate":
    st.markdown("### Generazione poligoni H3 da coordinate e dataset")
    
    dataset_choice_tab2 = st.selectbox(
        "Seleziona il dataset",
        ["Italian ports (v3)", "No italian ports (v3)", "Offshore platforms (v1)"],
        key="tab2_dataset"
    )
    df_tab2 = []
    if dataset_choice_tab2 == "Italian ports (v3)":
        df_tab2 = ita_ports
    elif dataset_choice_tab2 == "No italian ports (v3)":
        df_tab2 = no_ita_ports
    else:
        df_tab2 = offshore_platforms

    # Input coordinate e H3
    lat_input = st.number_input("Latitudine", value=42.0, format="%.6f")
    lon_input = st.number_input("Longitudine", value=12.0, format="%.6f")
    resolution_input = st.slider("Risoluzione H3", min_value=0, max_value=10, value=8)
    k_ring_input = st.slider("Raggio del ring (k)", min_value=1, max_value=5, value=1)

    if st.button("Genera poligoni H3"):
        st.session_state.generate_h3 = True  # ricorda che il bottone è stato premuto

    # Genera la mappa solo se il bottone è stato premuto
    if st.session_state.generate_h3:
        gdf_point = gpd.GeoDataFrame(
            {"lat": [lat_input], "lon": [lon_input]},
            geometry=gpd.points_from_xy([lon_input], [lat_input]),
            crs="EPSG:4326"
        )
        df_h3 = hrpv.geodataframe_to_cells(gdf_point, resolution=resolution_input)
        h3_ring = grid_disk([df_h3["cell"].iloc[0]], k=k_ring_input, flatten=True)
        geometries = hrpv.cells_to_polygons(h3_ring)
        gdf_ring = gpd.GeoDataFrame(geometry=geometries, crs="EPSG:4326")

        # Converto dataset scelto in H3
        if dataset_choice_tab2 != "No italian ports (v3)":
            df_port = df_tab2
        else:
            country_list = sorted(df_tab2["Country"].dropna().unique())
            selected_country = st.selectbox("Seleziona il Paese", country_list, key="tab2_country")
            df_country = df_tab2[df_tab2["Country"] == selected_country]

            port_list = sorted(df_country["Name"].dropna().unique())
            selected_port = st.selectbox("Seleziona il Porto", port_list, key="tab2_port")
            df_port = df_country[df_country["Name"] == selected_port]
        gdf_data = h3_to_gdf(df_port, "H3_hex_8", "Name")

        # Creo mappa
        m2 = folium.Map(location=[lat_input, lon_input], zoom_start=6)

        # Poligoni dataset (blu)
        for _, row in gdf_data.iterrows():
            folium.GeoJson(
                row.geometry.__geo_interface__,
                name=row["Name"],
                tooltip=folium.Tooltip(f"{row['Name']}"),
                style_function=lambda x: {
                    "fillColor": "blue",
                    "color": "blue",
                    "weight": 0.7,
                    "fillOpacity": 0.4
                }
            ).add_to(m2)

        # Poligoni H3 (rosso)
        for _, row in gdf_ring.iterrows():
            folium.GeoJson(
                row.geometry.__geo_interface__,
                style_function=lambda x: {
                    "fillColor": "red",
                    "color": "red",
                    "weight": 0.7,
                    "fillOpacity": 0.4
                }
            ).add_to(m2)

        folium.LayerControl().add_to(m2)
        st_folium(m2, width=800, height=600)
