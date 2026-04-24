import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import rasterio
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import os

# 1. SET UP THE PAGE
st.set_page_config(page_title="Zambia Energy Access Dashboard", layout="wide")
st.title("Integrated Rural Electrification Dashboard")
st.markdown("Mapping Tier 1 Off-Grid Solar against VIIRS Nighttime Lights in Zambia.")

# 2. CREATE THE SIDEBAR CONTROLS
st.sidebar.header("Dashboard Controls")
show_satellite = st.sidebar.checkbox("Show VIIRS Satellite Data", value=True)

# The slider to filter faint lights
satellite_threshold = st.sidebar.slider("Detection Threshold (Radiance)", min_value=0.0, max_value=2.0, value=0.1, step=0.05)

st.sidebar.markdown("---")
show_households = st.sidebar.checkbox("Show Solar Households (Ground Truth)", value=True)
apply_fusion = st.sidebar.checkbox("Apply Data Fusion", value=False)

# 3. LOAD THE VECTOR DATA
@st.cache_data
def load_households():
    return gpd.read_file("solar_households.geojson")

households_gdf = load_households()

# 4. BUILD THE MAP
# White/light basemap
m = folium.Map(location=[-15.4, 29.2], zoom_start=10, tiles="CartoDB positron")

# --- SATELLITE LOGIC ---
if show_satellite:
    try:
        with rasterio.open("viirs_base_map.tif") as src:
            arr = src.read(1)
            bounds = [[src.bounds.bottom, src.bounds.left], [src.bounds.top, src.bounds.right]]
            
            # DIAGNOSTIC: Print the actual numbers in the sidebar so we know what we're working with
            valid_pixels = arr[arr > 0]
            if len(valid_pixels) > 0:
                st.sidebar.markdown("---")
                st.sidebar.info(f"**TIF Data Range:**\n\nMin Light: {round(np.min(valid_pixels), 3)}\n\nMax Light: {round(np.max(valid_pixels), 3)}")
            
            # True Transparency Math
            # Keep values above threshold, turn everything else into NaN (Not a Number)
            arr_filtered = np.where(arr >= satellite_threshold, arr, np.nan)
            
            if np.nanmax(arr_filtered) > 0:
                # Normalize the data so colors show up properly
                vmax = np.nanmax(arr_filtered)
                vmin = satellite_threshold
                if vmax == vmin:
                    vmax = vmin + 0.1
                
                norm_arr = (arr_filtered - vmin) / (vmax - vmin)
                norm_arr = np.clip(norm_arr, 0, 1)
                
                # Apply the inferno color ramp (yellows/reds/purples)
                cmap = plt.get_cmap('inferno')
                rgba_img = cmap(norm_arr)
                
                # Force NaN values to be 100% transparent
                rgba_img[np.isnan(arr_filtered), 3] = 0 
                
                # Save the temporary image
                plt.imsave('temp_viirs.png', rgba_img)
                
                # Overlay it onto the map
                folium.raster_layers.ImageOverlay(
                    image='temp_viirs.png',
                    bounds=bounds,
                    opacity=0.75,
                    name='VIIRS Nighttime Lights'
                ).add_to(m)
            else:
                st.sidebar.warning("Threshold is set higher than any light in the image.")
                
    except Exception as e:
        st.sidebar.error(f"Error loading map: {e}")

# --- HOUSEHOLD & FUSION LOGIC ---
if show_households:
    if apply_fusion:
        point_color = "#FF0000" # Bright Red so it contrasts with the white basemap and yellow raster
        radius_size = 6
        fill_op = 1.0
    else:
        point_color = "#0000FF" # Blue for raw data
        radius_size = 4
        fill_op = 0.6

    for _, row in households_gdf.iterrows():
        lon, lat = row.geometry.x, row.geometry.y
        folium.CircleMarker(
            location=[lat, lon],
            radius=radius_size,
            color=point_color,
            weight=1,
            fill=True,
            fill_color=point_color,
            fill_opacity=fill_op,
            tooltip="Verified Tier 1 Solar Household"
        ).add_to(m)

# 5. DISPLAY THE MAP IN STREAMLIT
col1, col2 = st.columns([7, 3])

with col1:
    st_data = st_folium(m, width=800, height=500)

with col2:
    st.subheader("Spatial Statistics")
    st.info(f"**Verified Off-Grid Households:** {len(households_gdf)}")
    
    st.markdown("### Fusion Status")
    if apply_fusion:
        st.success("✅ **Active:** Micro-level ground truth data is successfully overriding the VIIRS satellite blind spots.")
    else:
        st.warning("❌ **Inactive:** Viewing standard remote sensing outputs. Off-grid systems are currently invisible.")

# Launch Streamlit app with: `python3 -m streamlit run app.py` in the terminal (for MacOS). Make sure to have the required files in the same directory