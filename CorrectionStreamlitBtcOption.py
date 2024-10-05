import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px  # For Plotly visualizations

# Deribit API base URL
base_url = "https://www.deribit.com/api/v2/public"

# Function to get book summary for a specific instrument
def get_book_summary(instrument_name):
    endpoint = f"{base_url}/get_book_summary_by_instrument"
    params = {'instrument_name': instrument_name}
    response = requests.get(endpoint, params=params)
    
    try:
        return response.json()
    except ValueError:
        st.error(f"Error decoding JSON response for {instrument_name}: {response.text}")
        return None

# Function to get all Bitcoin option instruments (both calls and puts, all strikes)
def get_all_btc_options():
    endpoint = f"{base_url}/get_instruments"
    params = {
        'currency': 'BTC',    # For Bitcoin options
        'kind': 'option',      # Type: options
        'expired': 'false'     # Only active options (string value)
    }
    response = requests.get(endpoint, params=params)
    
    try:
        data = response.json()
        if 'result' in data:
            return data['result']
        else:
            st.error(f"Error in response: {data}")
            return []
    except ValueError:
        st.error(f"Error decoding JSON response: {response.text}")
        return []

# Filter options with weekly expiry (within the next 7 days)
def filter_weekly_expiry_options(options):
    weekly_options = []
    current_time = datetime.utcnow()
    one_week_later = current_time + timedelta(days=7)
    
    for option in options:
        expiry_timestamp = option['expiration_timestamp'] / 1000  # Convert from milliseconds to seconds
        expiry_date = datetime.utcfromtimestamp(expiry_timestamp)
        
        if current_time <= expiry_date <= one_week_later:
            weekly_options.append(option)
    
    return weekly_options

def identify_writers_with_iv(row):
    price_change = row['Price Change'] if pd.notnull(row['Price Change']) else 0
    iv_change = row['IV Change'] if pd.notnull(row['IV Change']) else 0
    open_interest = row['Open Interest'] if pd.notnull(row['Open Interest']) else 0
    
    if row['Option Type'] == 'Call':
        if price_change < 0 and iv_change < 0 and open_interest > 0:
            return 'Call Writers (IV Falling)'
        elif price_change > 0 and iv_change > 0 and open_interest < 0:
            return 'Call Buyers (IV Rising)'
    elif row['Option Type'] == 'Put':
        if price_change > 0 and iv_change < 0 and open_interest > 0:
            return 'Put Writers (IV Falling)'
        elif price_change < 0 and iv_change > 0 and open_interest < 0:
            return 'Put Buyers (IV Rising)'
    return 'Neutral'

# Function to create a dataframe with relevant data for weekly options
def create_options_df(options):
    data = []
    
    for option in options:
        instrument_name = option['instrument_name']
        expiry_timestamp = option['expiration_timestamp'] / 1000
        expiry_date = datetime.utcfromtimestamp(expiry_timestamp).strftime('%Y-%m-%d')
        
        # Get book summary to fetch open interest and other data like IV, price change
        summary = get_book_summary(instrument_name)
        if summary and 'result' in summary:
            result = summary['result'][0] if len(summary['result']) > 0 else {}
            open_interest = result.get('open_interest', None)
            iv_change = result.get('iv', None)  # Assuming the API provides IV change
            price_change = result.get('last', None)  # Assuming the API provides price change
            
            data.append({
                'Instrument': instrument_name,
                'Expiry': expiry_date,
                'Strike Price': option['strike'],
                'Option Type': 'Call' if option['option_type'] == 'call' else 'Put',
                'Open Interest': open_interest,
                'IV Change': iv_change,
                'Price Change': price_change,
            })
    
    # Convert data to DataFrame
    df = pd.DataFrame(data)
    
    # Apply the function to identify writers
    df['Writer Type'] = df.apply(identify_writers_with_iv, axis=1)
    
    return df

# Streamlit dashboard
st.title("Bitcoin Weekly Options Dashboard (Deribit)")

# Fetch all Bitcoin options (calls and puts)
btc_options = get_all_btc_options()

if btc_options:
    # Filter weekly options (expiring in the next 7 days)
    weekly_options = filter_weekly_expiry_options(btc_options)
    
    if len(weekly_options) > 0:
        # Create a dataframe for the weekly options data
        options_df = create_options_df(weekly_options)

        # Display data as a table
        st.subheader("Weekly Expiring Bitcoin Options (Calls & Puts)")
        st.dataframe(options_df)

        # Visualization: Bar chart of Open Interest by Instrument using Plotly
        st.subheader("Open Interest by Instrument")
        bar_fig = px.bar(options_df, x='Instrument', y='Open Interest', title='Open Interest by Instrument')
        st.plotly_chart(bar_fig)

        # Visualization: Pie chart for Call vs Put distribution using Plotly
        st.subheader("Call vs Put Distribution")
        call_put_distribution = options_df['Option Type'].value_counts().reset_index()
        call_put_distribution.columns = ['Option Type', 'count']  # Rename columns to match what Plotly expects
        pie_fig = px.pie(call_put_distribution, names='Option Type', values='count', title='Call vs Put Distribution')
        st.plotly_chart(pie_fig)

        # Additional: Pie chart for Writers vs Buyers using Plotly
        st.subheader("Call/Put Writers vs Buyers")
        writer_buyer_distribution = options_df['Writer Type'].value_counts().reset_index()
        writer_buyer_distribution.columns = ['Writer Type', 'count']  # Rename columns to match what Plotly expects
        writer_pie_fig = px.pie(writer_buyer_distribution, names='Writer Type', values='count', title='Call/Put Writers vs Buyers')
        st.plotly_chart(writer_pie_fig)

    else:
        st.warning("No weekly expiring options found.")
else:
    st.error("Failed to fetch BTC options from Deribit.")
