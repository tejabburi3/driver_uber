import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import zipfile
import os
import pytz
from datetime import datetime

zip_file_path = "hyderabad_uber_dataset_r.zip"
dataset_file_name = "hyderabad_uber_dataset_r.csv"  # Replace with the exact file name inside the zip

# Check if the dataset is already extracted; if not, extract it
if not os.path.exists(dataset_file_name):
    with zipfile.ZipFile(zip_file_path, 'r') as z:
        z.extractall()  # Extracts all files in the current directory
        print(f"Extracted {dataset_file_name} from {zip_file_path}")

# Load the dataset
data = pd.read_csv(dataset_file_name)

# Convert Pickup_datetime to datetime and handle timezone conversion
data['Pickup_datetime'] = pd.to_datetime(data['Pickup_datetime'], errors='coerce')
india_timezone = pytz.timezone('Asia/Kolkata')
data['Pickup_datetime'] = data['Pickup_datetime'].dt.tz_localize('UTC').dt.tz_convert(india_timezone)

# Extract additional columns for analysis
data['Hour_of_day'] = data['Pickup_datetime'].dt.hour
data['Day_of_week'] = data['Pickup_datetime'].dt.day_name()

# Get the current day and time
current_day_of_week = datetime.now(india_timezone).strftime('%A')
current_hour = datetime.now(india_timezone).hour

# Filter the dataset for the current day of the week
current_day_data = data[data['Day_of_week'] == current_day_of_week]

# Calculate demand and supply per hour and area for the current day
current_day_demand_per_hour_area = current_day_data.groupby(
    ['Pickup_location', 'Hour_of_day', 'Vehicle_mode']
).size().reset_index(name='Demand')

current_day_supply_per_hour_area = current_day_data[
    current_day_data['Ride_status'] == 'Completed'
].groupby(['Pickup_location', 'Hour_of_day', 'Vehicle_mode']).size().reset_index(name='Supply')

# Merge demand and supply data
demand_supply_summary = pd.merge(
    current_day_demand_per_hour_area,
    current_day_supply_per_hour_area,
    on=['Pickup_location', 'Hour_of_day', 'Vehicle_mode'],
    how='left'
).fillna(0)  # Fill missing supply values with 0

# Initialize Streamlit session state for login status
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False
    st.session_state.driver_id = None
    st.session_state.driver_email = None
    st.session_state.selected_area = None

# Streamlit app title
st.title("UBER Driver Login Page")

# Login logic
if not st.session_state.is_logged_in:
    driver_id_input = st.text_input("Enter your Driver ID (e.g., 2111)")
    email_input = st.text_input("Enter your Email Address")

    if st.button("Login"):
        if driver_id_input and email_input:
            try:
                driver_id_input_int = int(driver_id_input)  # Convert Driver ID to integer
            except ValueError:
                st.error("Please enter a valid numeric Driver ID.")
            else:
                driver_data = data[(data['Driver_id'] == driver_id_input_int) & (data['Email'] == email_input)]
                if not driver_data.empty:
                    st.session_state.is_logged_in = True
                    st.session_state.driver_id = driver_id_input_int
                    st.session_state.driver_email = email_input
                else:
                    st.error("Driver ID and Email do not match. Please check your details and try again.")
else:
    driver_id = st.session_state.driver_id
    email = st.session_state.driver_email
    st.success(f"🛣 Logged in successfully 😊!")

    driver_data = data[data['Driver_id'] == driver_id]
    completed_rides = driver_data[driver_data['Ride_status'] == 'Completed']
    ride_counts = completed_rides['Vehicle_mode'].value_counts()

    for vehicle, count in ride_counts.items():
        st.success(f"Congratulations! You have completed a total of {count} rides on {vehicle}.")

    st.sidebar.title("Top Demand Areas")
    current_hour_demand = demand_supply_summary[
        (demand_supply_summary['Hour_of_day'] == current_hour) &
        (demand_supply_summary['Vehicle_mode'].isin(ride_counts.index))
    ]
    top_areas = current_hour_demand.groupby('Pickup_location').agg({'Demand': 'sum', 'Supply': 'sum'}).reset_index()
    top_areas = top_areas.sort_values(by='Demand', ascending=False)

    st.sidebar.success(f"### Top 3 Areas with Highest Demand on {current_day_of_week}s at {current_hour}:00")
    for _, row in top_areas.head(3).iterrows():
        st.sidebar.success(f"{row['Pickup_location']}: {row['Demand']} rides booked, {row['Supply']} rides completed")

    st.write(f"### Demand and Supply for {current_day_of_week} in the Current Hour")
    for index, row in top_areas.iterrows():
        st.write(
            f"**{row['Pickup_location']}**: {row['Demand']} demand, {row['Supply']} supply"
        )


    areas = data['Pickup_location'].unique()
    selected_area = st.selectbox("Select the area you are currently in:", ["Select an area"] + list(areas), index=0)
    pivot_demand_area = current_day_demand_per_hour_area.pivot_table(
    index=['Pickup_location', 'Vehicle_mode'],
    columns='Hour_of_day',
    values='Demand',
    fill_value=0
)

pivot_supply_area = current_day_supply_per_hour_area.pivot_table(
    index=['Pickup_location', 'Vehicle_mode'],
    columns='Hour_of_day',
    values='Supply',
    fill_value=0
)

    if selected_area != "Select an area":
        st.session_state.selected_area = selected_area
        st.success(f"Your current location is: {selected_area}")

        filtered_demand = pivot_demand_area.loc[(selected_area, vehicle)]
        filtered_supply = pivot_supply_area.loc[(selected_area, vehicle)]

        max_demand_hour = filtered_demand.idxmax()
        max_demand = filtered_demand[max_demand_hour]
        max_supply = filtered_supply[max_demand_hour]

        # Format the hour to 12-hour format with AM/PM for the max demand
        formatted_max_demand_hour = f"{max_demand_hour % 12 or 12} {'AM' if max_demand_hour < 12 else 'PM'}"
        
        st.write(f"**Highest Demand of {vehicle} in {selected_area}:** {max_demand} rides at {formatted_max_demand_hour}.")
        st.write(f"**Supply at this time:** {max_supply} rides.")
