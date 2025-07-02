import streamlit as st
import pandas as pd
import firebase_admin
from firebase_admin import credentials, db
import os
from streamlit_autorefresh import st_autorefresh
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import requests
from pytz import timezone



# --- CONFIG & HEADER ---
st.set_page_config(page_title="Smart Agriculture Dashboard", layout="wide")

st.markdown("""
    <style>
        body {
            background-color: #f4f8fb;
        }
        .st-emotion-cache-1r4qj8v {
            background-color: #f4f8fb;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
    <div style="display:flex; align-items:center; justify-content: space-between;
                background-color:#005f73; padding: 15px 20px; border-radius: 8px;">
        <h2 style="margin:0; color: white;">🌿 Smart Agriculture Dashboard</h2>
        <img src="https://img.icons8.com/fluency/48/plant-under-sun.png" width="40"/>
    </div>
""", unsafe_allow_html=True)

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    cred = credentials.Certificate(os.path.join(os.path.dirname(__file__), "serviceAccountKey.json"))
    firebase_admin.initialize_app(cred, {
        "databaseURL": "https://sensor-data-90987-default-rtdb.firebaseio.com"
    })

st_autorefresh(interval=10 * 1000, key="refresh")
st.toast("🔄 Auto-refreshed every 10 seconds", icon="⏱️")

# --- LOAD DATA ---
@st.cache_data(ttl=10)
def load_data():
    ref = db.reference("sensor_data")
    data = ref.get()
    all_records = []
    if data:
        for date_folder in data:
            entries = data[date_folder]
            for timestamp_key, value in entries.items():
                try:
                    ts = int(timestamp_key)
                    timestamp = datetime.fromtimestamp(ts, tz=timezone("Asia/Kolkata"))
                    value["timestamp"] = timestamp.replace(tzinfo=None)
                    all_records.append(value)
                except:
                    continue
        df = pd.DataFrame(all_records)
        df = df.dropna(subset=["timestamp"])
        df.sort_values("timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)
        df["formatted_time"] = df["timestamp"].dt.strftime("%d-%m-%Y %H:%M:%S")
        return df
    return pd.DataFrame()

df = load_data()

# --- SIDEBAR ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/128/10130/10130571.png", width=64)
st.sidebar.title("🌱 Navigation")
page = st.sidebar.radio("Go to", ["Weather", "Soil & Sensors", "Sensor Logs"])

st.sidebar.markdown("---")
st.sidebar.subheader("⏳ Filters & Alerts")
hours = st.sidebar.slider("Show data from last N hours", 0, 24, 1)
chart_type = st.sidebar.selectbox("Chart Type", ["Line", "Bar", "Area"], index=0)
sensor_options = st.sidebar.multiselect("Sensors to Visualize:", ["temperature", "ph", "tds", "turbidity"],
                                        default=["temperature", "ph", "tds", "turbidity"])
show_gauges = st.sidebar.checkbox("Show Gauges", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("🚨 Alert Thresholds")
temp_max = st.sidebar.slider("Temperature Max (°C)", 40, 100, 60)
temp_min = st.sidebar.slider("Temperature Min (°C)", 0, 40, 10)
ph_min = st.sidebar.slider("pH Min", 0.0, 14.0, 5.5)
ph_max = st.sidebar.slider("pH Max", 0.0, 14.0, 8.5)
tds_threshold = st.sidebar.slider("TDS Max", 100, 1200, 800)
tds_min = st.sidebar.slider("TDS Min (ppm)", 100, 1200, 200)
tds_max = st.sidebar.slider("TDS Max (ppm)", 100, 1200, 800)
turbidity_threshold = st.sidebar.slider("Turbidity Max (NTU)", 0.0, 10.0, 6.0)
turbidity_min = st.sidebar.slider("Turbidity Min (NTU)", 0.0, 10.0, 1.0)

now = datetime.now()
filtered_df = df[df["timestamp"] > now - timedelta(hours=hours)]

# --- PAGE 1: Weather ---
if page == "Weather":
    st.subheader("🌦️ Live Weather at Farm Location")
    try:
        lat, lon = 21.1458, 79.0882
        weather_api_key = "YOUR-WEATHER-API-KEY"
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={weather_api_key}&units=metric"
        res = requests.get(url).json()
        weather = {
            "🌡️ Temp": f"{res['main']['temp']} °C",
            "☁️ Condition": res['weather'][0]['description'].title(),
            "💧 Humidity": f"{res['main']['humidity']}%",
            "🌬️ Wind": f"{res['wind']['speed']} m/s"
        }
        st.success("✅ Weather data fetched successfully.")
        st.info("\n".join([f"**{k}**: {v}" for k, v in weather.items()]))
    except:
        st.warning("⚠️ Weather API unavailable.")

# --- PAGE 2: Soil & Sensors ---
elif page == "Soil & Sensors":
    if filtered_df.empty:
        st.warning("⚠️ No data for the selected time window.")
    else:
        latest = filtered_df.iloc[-1]
        st.subheader("📟 Latest Sensor Readings")

        # Alerts
        if latest["temperature"] > temp_max:
            st.error("🚨 High Temperature!")
        if latest["temperature"] < temp_min:
            st.error("🚨 Low Temperature!")
        if not ph_min <= latest["ph"] <= ph_max:
            st.error("🚨 Abnormal pH Level!")
        if latest["tds"] > tds_max:
            st.error("🚨 High TDS Detected!")
        if latest["tds"] < tds_min:
            st.error("🚨 Low TDS Detected!")
        if latest["turbidity"] > turbidity_threshold:
            st.error("🚨 High Turbidity Detected!")
        elif latest["turbidity"] < turbidity_min:
            st.error("🚨 Low Turbidity Detected!")


        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🌡️ Temperature (°C)", f"{latest['temperature']:.2f}")
        col2.metric("🧪 pH", f"{latest['ph']:.2f}")
        col3.metric("💧 TDS (ppm)", f"{latest['tds']}")
        col4.metric("🌫️ Turbidity (NTU)", f"{latest['turbidity']:.2f}")

        # --- Sensor Trend Charts with Custom Colors ---
        st.markdown("## 📈 Sensor Trends")

        sensor_colors = {
            "temperature": "#ef476f",  # red-pink
            "ph": "#ffd166",           # yellow
            "tds": "#06d6a0",          # teal
            "turbidity": "#118ab2"     # blue
        }

        for sensor in sensor_options:
            st.subheader(f"{sensor.capitalize()} Trend")
            line_color = sensor_colors.get(sensor, "#00b4d8")

            if chart_type == "Line":
                fig = px.line(filtered_df, x="timestamp", y=sensor, markers=True)
                fig.update_traces(line=dict(color=line_color))
            elif chart_type == "Bar":
                fig = px.bar(
                    filtered_df, x="timestamp", y=sensor,
                    color_discrete_sequence=[line_color]
                )
            elif chart_type == "Area":
                fig = px.area(
                    filtered_df, x="timestamp", y=sensor,
                    color_discrete_sequence=[line_color]
                )

            fig.update_layout(
                margin=dict(l=10, r=10, t=30, b=30),
                height=300
            )
            st.plotly_chart(fig, use_container_width=True)

        # --- Gauges ---
        if show_gauges:
            st.markdown("## 🎯 Real-Time Gauges")
            g1, g2, g3, g4 = st.columns(4)
            with g1:
                st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=latest["temperature"],
                    title={'text': "Temperature"}, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#ef476f"}})), use_container_width=True)
            with g2:
                st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=latest["ph"],
                    title={'text': "pH"}, gauge={'axis': {'range': [0, 14]}, 'bar': {'color': "#ffd166"}})), use_container_width=True)
            with g3:
                st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=latest["tds"],
                    title={'text': "TDS"}, gauge={'axis': {'range': [0, 1000]}, 'bar': {'color': "#06d6a0"}})), use_container_width=True)
            with g4:
                st.plotly_chart(go.Figure(go.Indicator(mode="gauge+number", value=latest["turbidity"],
                    title={'text': "Turbidity"}, gauge={'axis': {'range': [0, 10]}, 'bar': {'color': "#118ab2"}})), use_container_width=True)


# --- PAGE 3: Sensor Logs ---
elif page == "Sensor Logs":
    st.subheader("🗂️ Sensor Data Logs")
    if filtered_df.empty:
        st.warning("⚠️ No recent data available.")
    else:
        st.download_button("⬇️ Download CSV", data=filtered_df.to_csv(index=False), file_name="sensor_data.csv", mime="text/csv")
        st.dataframe(filtered_df[["formatted_time"] + sensor_options], use_container_width=True)

# --- FOOTER ---
st.markdown("---")
st.caption("🚀 Built by Dhananjay Kharkar")
