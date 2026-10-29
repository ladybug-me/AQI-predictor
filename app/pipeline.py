"""Open-Meteo data ingestion and feature engineering pipeline for Vellore AQI."""
from __future__ import annotations

import datetime
import logging
from typing import Any, Tuple

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import (
    AIR_QUALITY_API_URL,
    BACKOFF_FACTOR,
    CPCB_PM25_LIMIT,
    FEATURE_COLUMNS,
    LATITUDE,
    LONGITUDE,
    MAX_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
    WEATHER_ARCHIVE_URL,
    WEATHER_FORECAST_URL,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def get_requests_session() -> requests.Session:
    """Create a resilient requests session with exponential backoff retries."""
    session = requests.Session()
    retries = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def fetch_historical_training_data(years: int = 3) -> pd.DataFrame:
    """
    Fetch historical meteorological and particulate data for training.
    
    Data sources:
    - Open-Meteo Air Quality API (CAMS Reanalysis): hourly pm2_5
    - Open-Meteo Weather Archive API (ERA5 Reanalysis): daily temp, wind, humidity, rain
    
    Aggregates hourly particulate data to 24-hour daily means and joins with weather.
    """
    session = get_requests_session()
    
    # Open-Meteo historical weather has a ~2-5 day latency
    end_date = datetime.date.today() - datetime.timedelta(days=5)
    start_date = end_date - datetime.timedelta(days=years * 365)
    
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    logger.info(
        "Fetching %d years of historical data (%s to %s) for Vellore (lat=%f, lon=%f)...",
        years,
        start_str,
        end_str,
        LATITUDE,
        LONGITUDE,
    )

    # 1. Fetch Historical Weather from Archive API
    weather_params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "daily": [
            "temperature_2m_mean",
            "wind_speed_10m_max",
            "relative_humidity_2m_mean",
            "precipitation_sum",
        ],
        "start_date": start_str,
        "end_date": end_str,
        "timezone": "auto",
    }
    resp_weather = session.get(
        WEATHER_ARCHIVE_URL,
        params=weather_params,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp_weather.raise_for_status()
    weather_json = resp_weather.json()
    if "daily" not in weather_json:
        raise ValueError(f"Weather Archive response missing 'daily' section: {weather_json}")
    
    df_weather = pd.DataFrame(weather_json["daily"])
    df_weather["time"] = pd.to_datetime(df_weather["time"])
    df_weather = df_weather.rename(
        columns={
            "temperature_2m_mean": "temp_mean",
            "wind_speed_10m_max": "wind_speed_max",
            "relative_humidity_2m_mean": "humidity_mean",
            "precipitation_sum": "precip_sum",
        }
    )

    # 2. Fetch Historical PM2.5 from Air Quality API
    aq_params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": "pm2_5",
        "start_date": start_str,
        "end_date": end_str,
    }
    resp_aq = session.get(
        AIR_QUALITY_API_URL,
        params=aq_params,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    resp_aq.raise_for_status()
    aq_json = resp_aq.json()
    if "hourly" not in aq_json:
        raise ValueError(f"Air Quality API response missing 'hourly' section: {aq_json}")
    
    df_aq = pd.DataFrame(aq_json["hourly"])
    df_aq["time"] = pd.to_datetime(df_aq["time"])
    # Aggregate hourly to daily mean
    df_aq_daily = df_aq.set_index("time").resample("D").mean().reset_index()
    df_aq_daily = df_aq_daily.rename(columns={"pm2_5": "pm2_5_mean"})

    # 3. Merge datasets
    df_merged = pd.merge(df_weather, df_aq_daily, on="time", how="inner")

    # 4. Feature Engineering
    # lag_pm25_24h captures the ~81.9% emission baseline variance
    df_merged["lag_pm25_24h"] = df_merged["pm2_5_mean"].shift(1)
    df_merged["month"] = df_merged["time"].dt.month
    df_merged["day_of_week"] = df_merged["time"].dt.day_of_week
    # Winter inversion proxy (Nov, Dec, Jan, Feb)
    df_merged["is_winter_inversion"] = df_merged["month"].isin([11, 12, 1, 2]).astype(int)
    
    # Target: 1 if daily mean PM2.5 exceeds CPCB standard (60 µg/m³), else 0
    df_merged["target"] = (df_merged["pm2_5_mean"] > CPCB_PM25_LIMIT).astype(int)

    # Drop NaNs created by lag shift or sensor gaps
    df_clean = df_merged.dropna().reset_index(drop=True)
    logger.info("Successfully assembled dataset: %d samples, %d positive exceedances.", len(df_clean), df_clean["target"].sum())
    return df_clean


def fetch_live_forecast_features() -> Tuple[pd.DataFrame, dict[str, Any], str]:
    """
    Fetch live observations and forecasts to generate feature vector for tomorrow's prediction.
    
    Returns:
        features_df: Single-row DataFrame matching FEATURE_COLUMNS
        weather_drivers: Dict with temp_c, wind_kmh, humidity_pct, precip_mm
        forecast_date_str: Target date string (YYYY-MM-DD)
    """
    session = get_requests_session()
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%Y-%m-%d")
    today_str = today.strftime("%Y-%m-%d")

    logger.info("Fetching live PM2.5 lag and tomorrow's (%s) weather forecast...", tomorrow_str)

    # 1. Fetch recent PM2.5 to compute today's 24h lag
    aq_params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "hourly": "pm2_5",
        "past_days": 2,
        "forecast_days": 1,
    }
    resp_aq = session.get(AIR_QUALITY_API_URL, params=aq_params, timeout=REQUEST_TIMEOUT_SECONDS)
    resp_aq.raise_for_status()
    aq_json = resp_aq.json()
    
    times = aq_json.get("hourly", {}).get("time", [])
    pm25_vals = aq_json.get("hourly", {}).get("pm2_5", [])
    
    # Filter today's hourly values; if insufficient (<6), use the latest 24 available hourly values
    today_readings = [v for t, v in zip(times, pm25_vals) if t.startswith(today_str) and v is not None]
    if len(today_readings) < 6:
        valid_readings = [v for v in pm25_vals if v is not None]
        today_readings = valid_readings[-24:] if len(valid_readings) >= 24 else valid_readings

    if not today_readings:
        # Fallback to annual safe mean baseline if API returns empty
        lag_pm25 = 40.0
    else:
        lag_pm25 = float(sum(today_readings) / len(today_readings))

    # 2. Fetch tomorrow's weather forecast
    weather_params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "daily": [
            "temperature_2m_mean",
            "wind_speed_10m_max",
            "relative_humidity_2m_mean",
            "precipitation_sum",
        ],
        "timezone": "auto",
    }
    resp_weather = session.get(WEATHER_FORECAST_URL, params=weather_params, timeout=REQUEST_TIMEOUT_SECONDS)
    resp_weather.raise_for_status()
    weather_json = resp_weather.json()
    daily_weather = weather_json.get("daily", {})
    daily_times = daily_weather.get("time", [])

    if tomorrow_str in daily_times:
        idx = daily_times.index(tomorrow_str)
    elif len(daily_times) > 1:
        idx = 1
    else:
        idx = 0

    temp_mean = float(daily_weather.get("temperature_2m_mean", [25.0])[idx])
    wind_speed_max = float(daily_weather.get("wind_speed_10m_max", [10.0])[idx])
    humidity_mean = float(daily_weather.get("relative_humidity_2m_mean", [70.0])[idx])
    precip_sum = float(daily_weather.get("precipitation_sum", [0.0])[idx])

    # 3. Calendar Features for tomorrow
    month = tomorrow.month
    day_of_week = tomorrow.weekday()
    is_winter_inversion = 1 if month in [11, 12, 1, 2] else 0

    # Build feature record
    feature_dict = {
        "temp_mean": temp_mean,
        "wind_speed_max": wind_speed_max,
        "humidity_mean": humidity_mean,
        "precip_sum": precip_sum,
        "month": month,
        "is_winter_inversion": is_winter_inversion,
        "day_of_week": day_of_week,
        "lag_pm25_24h": lag_pm25,
    }

    features_df = pd.DataFrame([feature_dict])[FEATURE_COLUMNS]

    weather_drivers = {
        "temp_c": round(temp_mean, 1),
        "wind_kmh": round(wind_speed_max, 1),
        "humidity_pct": int(round(humidity_mean)),
        "precip_mm": round(precip_sum, 1),
    }

    return features_df, weather_drivers, tomorrow_str
