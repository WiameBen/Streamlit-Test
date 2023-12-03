import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import folium_static
from folium.plugins import MarkerCluster
from shapely.geometry import Point, box
import subprocess
import leafmap.foliumap as leafmap
import io
import base64
import matplotlib.pyplot as plt
import rasterio
import folium
import os
from rasterio.plot import reshape_as_image
import cv2
import  imageio
import geemap
from folium.features import DivIcon
from reportlab.pdfgen import canvas
from io import BytesIO

gdf = gpd.read_parquet("synthetic_dataset_with_morocco.parquet")

st.title("Geospatial Data Visualization")

visualization_choice = st.sidebar.radio(
    "Choose Visualization",
    ["Cartographie du jour J", "Slider", "Timelapse", "SplitMap", "PopUp", "Filtered Data","Recherche par Coordonnées"],
)

def interpolate_data(input_file, output_file):
    gdal_grid_command = (
        f"gdal_grid -a_srs EPSG:4326 -a invdist:power=2.0:smoothing=1.0 -ot Float64 "
        f"-of GTiff -l input_layer -zfield value -outsize 1000 1000 -a_nodata -9999.0 "
        f"{input_file} {output_file}"
    )
    subprocess.run(gdal_grid_command, shell=True)

def create_folium_map(gdf, attribute, day, search_coordinates=None):
    m = folium.Map(location=(30, -8), zoom_start=2.3, tiles="cartodb positron")

    attribute_column = f'{attribute}Jour{day}'
    marker_cluster = MarkerCluster().add_to(m)

    for index, row in gdf.iterrows():
        size_factor = row[attribute_column] / gdf[attribute_column].max()
        marker_size = int(size_factor * 20) + 5
        folium.CircleMarker(
            [row.latitude, row.longitude],
            radius=marker_size,
            fill=True,
            fill_color='blue',
            fill_opacity=0.7,
        ).add_to(marker_cluster)

    if search_coordinates:
        # Add a marker for the searched coordinates
        folium.Marker(
            search_coordinates, 
            popup=f"Searched Coordinates: {search_coordinates}", 
            icon=folium.Icon(color='red')
        ).add_to(m)

    folium_static(m)

def display_filtered_data(filtered_gdf):
    st.subheader("Filtered Data")
    st.write(filtered_gdf)

if visualization_choice == "Cartographie du jour J":
    attribut = st.selectbox('Choisir l\'attribut', ('LOLM', 'VALOM', 'PUBGM'))
    jour = st.selectbox('Choisir le jour', ('0', '1', '2', '3', '4', '5', '6'))
    create_folium_map(gdf, attribut, jour)


elif visualization_choice == "Recherche par Coordonnées":
    st.subheader("Search Point by Coordinates")
    latitude = st.number_input("Enter Latitude:", min_value=gdf['latitude'].min(), max_value=gdf['latitude'].max())
    longitude = st.number_input("Enter Longitude:", min_value=gdf['longitude'].min(), max_value=gdf['longitude'].max())
    attribut = st.selectbox('Choisir l\'attribut', ('LOLM', 'VALOM', 'PUBGM'))
    jour = st.selectbox('Choisir le jour', ('0', '1', '2', '3', '4', '5', '6'))
    if st.button("Search"):
        search_coordinates = [latitude, longitude]
        create_folium_map(gdf, attribut, jour, search_coordinates)


elif visualization_choice == "PopUp":
    def create_popup_folium_map(attribut):
        m = folium.Map(location=(30, -8), zoom_start=5, tiles="cartodb positron")
        marker_cluster = MarkerCluster().add_to(m)

        for index, row in gdf.iterrows():
            labels = ['Jour-0', 'Jour-1', 'Jour-2', 'Jour-3', 'Jour-4', 'Jour-5', 'Jour-6']
            sizes_attribut_01 = [row['LOLMJour0'], row['LOLMJour1'], row['LOLMJour2'], row['LOLMJour3'], row['LOLMJour4'], row['LOLMJour5'], row['LOLMJour6']]
            sizes_attribut_02 = [row['VALOMJour0'], row['VALOMJour1'], row['VALOMJour2'], row['VALOMJour3'], row['VALOMJour4'], row['VALOMJour5'], row['VALOMJour6']]
            sizes_attribut_03 = [row['PUBGMJour0'], row['PUBGMJour1'], row['PUBGMJour2'], row['PUBGMJour3'], row['PUBGMJour4'], row['PUBGMJour5'], row['PUBGMJour6']]

            fig, ax = plt.subplots()
            ax.plot(labels, sizes_attribut_01, label='LOLM', marker='o', linestyle='-')
            ax.plot(labels, sizes_attribut_02, label='VALM', marker='o', linestyle='-')
            ax.plot(labels, sizes_attribut_03, label='PUBGM', marker='o', linestyle='-')

            ax.set_title(f'Line Chart for {attribut}')
            ax.set_xlabel('Days')
            ax.set_ylabel('Attribute Value')
            ax.legend()

            image_stream = io.BytesIO()
            plt.savefig(image_stream, format='png')
            plt.close()

            image_stream.seek(0)
            encoded_image = base64.b64encode(image_stream.read()).decode()

            popup_html = f'<img src="data:image/png;base64,{encoded_image}">'
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=0.1,
                fill=True,
                fill_color='blue',
                fill_opacity=0.7,
                popup=folium.Popup(popup_html)
            ).add_to(marker_cluster)

        folium_static(m)

    create_popup_folium_map("Attribut")

elif visualization_choice == "Filtered Data":
    st.sidebar.subheader("Filter Data")
    attribute_filter = st.sidebar.text_input("Attribute Filter (e.g., attribute > 100):")
    spatial_filter = st.sidebar.text_input("Spatial Filter (e.g., within_box(x_min, y_min, x_max, y_max):)")

    if not attribute_filter and not spatial_filter:
        st.sidebar.text("Enter your query.")
    else:
        filtered_gdf = gdf.query(attribute_filter)

        if spatial_filter:
            x_min, y_min, x_max, y_max = map(float, spatial_filter.split(','))
            bbox = box(x_min, y_min, x_max, y_max)
            filtered_gdf = filtered_gdf[filtered_gdf.geometry.within(bbox)]

        display_filtered_data(filtered_gdf)

elif visualization_choice == "Slider":
    # Title of the Streamlit app
    st.title("Raster Visualization")

    # Selection of attributes using sliders
    jeu_choice = st.select_slider("Choisir l'attribut", options=('LOLM', 'VALOM', 'PUBGM'))
    day_choice = st.select_slider("Choisir le jour", options=('0', '1', '2', '3', '4', '5', '6'))

    if jeu_choice == 'LOLM' and day_choice in ('0', '1', '2', '3', '4', '5', '6'):
        # Load the raster based on the choices
        raster_path = f'LOLJour{day_choice}.tif'
        selected_raster = rasterio.open(raster_path)
        bounds = selected_raster.bounds

        # Reshape the raster data to an image
        image_data = reshape_as_image(selected_raster.read())

        # Create a Folium map centered around the middle of the raster
        m = folium.Map(location=[(bounds.bottom + bounds.top) / 2, (bounds.left + bounds.right) / 2], zoom_start=5)

        # Add the raster data as an image overlay
        folium.raster_layers.ImageOverlay(
            image_data,
            bounds=[[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
            colormap=lambda x: (0, 0, 0, x),
        ).add_to(m)

        # Display the map in the Streamlit app
        st.write(f"Visualisation de {jeu_choice} Jour {day_choice}")
        folium_static(m)


    if jeu_choice == 'VALOM' and day_choice in ('0', '1', '2', '3', '4', '5', '6'):
        # Load the raster based on the choices
        raster_path = f'VALOJour{day_choice}.tif'
        selected_raster = rasterio.open(raster_path)
        bounds = selected_raster.bounds

        # Reshape the raster data to an image
        image_data = reshape_as_image(selected_raster.read())

        # Create a Folium map centered around the middle of the raster
        m = folium.Map(location=[(bounds.bottom + bounds.top) / 2, (bounds.left + bounds.right) / 2], zoom_start=5)

        # Add the raster data as an image overlay
        folium.raster_layers.ImageOverlay(
            image_data,
            bounds=[[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
            colormap=lambda x: (0, 0, 0, x),
        ).add_to(m)

        # Display the map in the Streamlit app
        st.write(f"Visualisation de {jeu_choice} Jour {day_choice}")
        folium_static(m)


    if jeu_choice == 'PUBGM' and day_choice in ('0', '1', '2', '3', '4', '5', '6'):
        # Load the raster based on the choices
        raster_path = f'PUBGJour{day_choice}.tif'
        selected_raster = rasterio.open(raster_path)
        bounds = selected_raster.bounds

        # Reshape the raster data to an image
        image_data = reshape_as_image(selected_raster.read())

        # Create a Folium map centered around the middle of the raster
        m = folium.Map(location=[(bounds.bottom + bounds.top) / 2, (bounds.left + bounds.right) / 2], zoom_start=5)

        # Add the raster data as an image overlay
        folium.raster_layers.ImageOverlay(
            image_data,
            bounds=[[bounds.bottom, bounds.left], [bounds.top, bounds.right]],
            colormap=lambda x: (0, 0, 0, x),
        ).add_to(m)

        # Display the map in the Streamlit app
        st.write(f"Visualisation de {jeu_choice} Jour {day_choice}")
        folium_static(m)


elif  visualization_choice == "Timelapse":


    def load_geotiff_images(directory, target_width, target_height):
        image_files = sorted([f for f in os.listdir(directory) if f.lower().endswith(('.tif', '.tiff'))])
        images = []

        for image_file in image_files:
            image_path = os.path.join(directory, image_file)
            raster = rasterio.open(image_path)
            image_data = reshape_as_image(raster.read())

            # Resize the image to the target dimensions
            image_data_resized = cv2.resize(image_data, (target_width, target_height))

            images.append(image_data_resized)

        return images

    # Streamlit app
    st.header("Sélectionnez le Jeu Vidéo :")
    selected_property = st.selectbox("", ['LOLM', 'VALOM', 'PUBGM'])

    # Specify the directory and target dimensions based on the selected property
    if selected_property == "LOLM":
        image_directory = "C:\\Users\\WiWiZ\\Desktop\\projet\\GeoTiff\\LOLM"
        output_file = "output_timelapse.gif"
        target_width, target_height = 640, 480  # Adjust these values as needed
    elif selected_property == "VALOM":
        image_directory = "C:\\Users\\WiWiZ\\Desktop\\projet\\GeoTiff\\VALOM"
        output_file = "output_timelapse2.gif"
        target_width, target_height = 640, 480  # Adjust these values as needed
    elif selected_property == "PUBGM":
        image_directory = "C:\\Users\\WiWiZ\\Desktop\\projet\\GeoTiff\\PUBGM"
        output_file = "output_timelapse3.gif"
        target_width, target_height = 640, 480  # Adjust these values as needed

    # Load and resize GeoTIFF images
    geotiff_images = load_geotiff_images(image_directory, target_width, target_height)

    # Create and display the timelapse GIF
    imageio.mimsave(output_file, geotiff_images, fps=80, loop=0)
    st.image(output_file, width=target_width)


elif visualization_choice == "SplitMap":
    
    st.title("Split-panel Map")
    # First set of sliders
    col1, col2 = st.columns(2)

    with col1:
        jeu_choice = st.select_slider("Choisir l'attribut", options=('LOL', 'VALO', 'PUBG'))
        day_choice = st.select_slider("Choisir le jour", options=('0', '1', '2', '3', '4', '5', '6'))
        raster_path1 = '' 
        if jeu_choice in ('LOL', 'VALO', 'PUBG') and day_choice in ('0', '1', '2', '3', '4', '5', '6'):
            # Load the raster based on the choices
            raster_path1 = f'{jeu_choice}Jour{day_choice}.tif'

    # Second set of sliders
    with col2:
        jeu_choice2 = st.select_slider("Choisir l'attribut2", options=('LOL', 'VALO', 'PUBG'))
        day_choice2 = st.select_slider("Choisir le jour2", options=('0', '1', '2', '3', '4', '5', '6'))
        raster_path2 = ''  # Initialize raster_path2
        if jeu_choice2 in ('LOL', 'VALO', 'PUBG') and day_choice2 in ('0', '1', '2', '3', '4', '5', '6'):
            # Load the raster based on the choices
            raster_path2 = f'{jeu_choice2}Jour{day_choice2}.tif'
    m = leafmap.Map()
    m.split_map(
        left_layer= raster_path1 , right_layer= raster_path2
    )

    m.to_streamlit(height=700)





else:
    # Handle other visualizations
    pass





