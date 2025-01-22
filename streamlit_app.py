import streamlit as st
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import zipfile
import os
import pytz
from datetime import datetime

# Define the zip file and the dataset file names
zip_file_path = "hyderabad_uber_dataset_r.zip"
dataset_file_name = "hyderabad_uber_dataset_r.csv"  # Replace with the exact file name inside the zip

# Check if the dataset is already extracted; if not, extract it
if not os.path.exists(dataset_file_name):
    with zipfile.ZipFile(zip_file_path, 'r') as z:
        z.extractall()  # Extracts all files in the current directory
        print(f"Extracted {dataset_file_name} from {zip_file_path}")

# Load the dataset
data = pd.read_csv(dataset_file_name)  # Load the dataset into the DataFrame

# Strip whitespace from column names (if any)
data.columns = data.columns.str.strip()

# Convert Pickup_datetime to datetime
data['Pickup_datetime'] = pd.to_datetime(data['Pickup_datetime'], errors='coerce')

# Convert Pickup_datetime to India timezone if not already timezone-aware
india_timezone = pytz.timezone('Asia/Kolkata')
data['Pickup_datetime'] = data['Pickup_datetime'].dt.tz_localize('UTC').dt.tz_convert(india_timezone)

# Extract the hour from the Pickup_datetime
data['Hour_of_day'] = data['Pickup_datetime'].dt.hour

# Calculate demand and supply per hour and area
demand_per_hour_area = data.groupby(['Pickup_location', 'Hour_of_day', 'Vehicle_mode']).size().reset_index(name='Demand')
supply_per_hour_area = data[data['Ride_status'] == 'Completed'].groupby(
    ['Pickup_location', 'Hour_of_day', 'Vehicle_mode']
).size().reset_index(name='Supply')

# Pivot tables for demand and supply
pivot_demand_area = demand_per_hour_area.pivot_table(
    index=['Pickup_location', 'Vehicle_mode'], columns='Hour_of_day', values='Demand', fill_value=0
)
pivot_supply_area = supply_per_hour_area.pivot_table(
    index=['Pickup_location', 'Vehicle_mode'], columns='Hour_of_day', values='Supply', fill_value=0
)

# Get the current hour
current_hour = datetime.now(india_timezone).hour

# Initialize Streamlit session state for login status
if 'is_logged_in' not in st.session_state:
    st.session_state.is_logged_in = False
    st.session_state.driver_id = None
    st.session_state.driver_email = None
    st.session_state.selected_area = None

# Streamlit app title
st.title("UBER Driver Login Page")

# Check if the driver is logged in
if not st.session_state.is_logged_in:
    # Ask the user to enter their Driver ID and Email Address
    driver_id_input = st.text_input("Enter your Driver ID (e.g., 2111)")
    email_input = st.text_input("Enter your Email Address")

    if st.button("Login"):
        if driver_id_input and email_input:
            try:
                driver_id_input_int = int(driver_id_input)  # Convert Driver ID to integer
            except ValueError:
                st.error("Please enter a valid numeric Driver ID.")
            else:
                # Check if Driver ID and Email match
                driver_data = data[(data['Driver_id'] == driver_id_input_int) & (data['Email'] == email_input)]
                if not driver_data.empty:
                    # Mark the driver as logged in
                    st.session_state.is_logged_in = True
                    st.session_state.driver_id = driver_id_input_int
                    st.session_state.driver_email = email_input
                else:
                    st.error("Driver ID and Email do not match. Please check your details and try again.")
else:
    # Driver is logged in, show their details
    driver_id = st.session_state.driver_id
    email = st.session_state.driver_email

    st.success(f"Login successful!")

    # Filter data for the driver
    driver_data = data[data['Driver_id'] == driver_id]

    # Count the number of completed rides by vehicle type
    completed_rides = driver_data[driver_data['Ride_status'] == 'Completed']
    ride_counts = completed_rides['Vehicle_mode'].value_counts()

    # Display congratulatory message for each vehicle type
    for vehicle, count in ride_counts.items():
        st.success(f"Congratulations! You have completed a total of {count} rides on {vehicle}.")

    # Sidebar for visualizing the top 3 demand areas
    st.sidebar.title("Top Demand and Supply Areas")

    # Merge demand and supply data
    demand_supply_summary = (
        demand_per_hour_area.merge(
            supply_per_hour_area, 
            on=['Pickup_location', 'Hour_of_day', 'Vehicle_mode'], 
            how='left'
        )
        .fillna(0)  # Fill missing supply values with 0
    )

    # Filter demand and supply for the current hour and driver's vehicle mode
    current_hour_demand_supply = demand_supply_summary[
        (demand_supply_summary['Hour_of_day'] == current_hour) & 
        (demand_supply_summary['Vehicle_mode'].isin(ride_counts.index))
    ]

    # Aggregate by Pickup_location to get total demand and supply
    area_summary = (
        current_hour_demand_supply.groupby('Pickup_location')[['Demand', 'Supply']]
        .sum()
        .reset_index()
        .sort_values(by='Demand', ascending=False)
    )

    # Sidebar visualization for the top 3 areas
    formatted_current_hour = f"{current_hour % 12 or 12} {'AM' if current_hour < 12 else 'PM'}"
    st.sidebar.success(f"### Top 3 Areas with Highest Demand and Supply at {formatted_current_hour}")
    for index, row in area_summary.head(3).iterrows():
        st.sidebar.success(
            f"**{row['Pickup_location']}**: {row['Demand']} demand, {row['Supply']} supply"
        )

    # Display all demand and supply counts on the main page
    st.write("### Rides Demand and Supply Across All Areas in Current Hour")
    for index, row in area_summary.iterrows():
        st.write(
            f"**{row['Pickup_location']}**: {row['Demand']} demand, {row['Supply']} supply"
        )

    # Analyze demand and supply for the selected area
    areas = data['Pickup_location'].unique()  # Extract unique areas from the dataset
    selected_area = st.selectbox(
        "Select the area you are currently in:",
        ["Select an area"] + list(areas),  # Add a placeholder as the first option
        index=0
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
