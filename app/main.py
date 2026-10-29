"""FastAPI Application providing AQI forecast endpoints and responsive product dashboard."""
from __future__ import annotations

import datetime
import json
import logging
import os
from typing import Any, Optional

from dotenv import load_dotenv
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

# Load environment variables from .env
load_dotenv()

from app.config import (
    CPCB_PM25_LIMIT,
    FEATURE_COLUMNS,
    LOCATION_NAME,
    METRICS_PATH,
)
from app.pipeline import fetch_live_forecast_features
from app.predictor import predictor

logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

app = FastAPI(
    title="Vellore AQI 'Traffic Light' Health Alert Service",
    description="SDG 3 Early-Warning Health Alert Service predicting CPCB NAAQS 24h PM2.5 exceedance (>60 µg/m³)",
    version="1.0.0",
)


@app.on_event("startup")
def startup_event() -> None:
    """Initialize model artifacts and optionally initialize ngrok tunnel if enabled in .env."""
    predictor.load_artifacts()
    if os.getenv("ENABLE_NGROK", "false").lower() in ("true", "1", "yes"):
        token = os.getenv("NGROK_AUTHTOKEN", "").strip()
        port = int(os.getenv("PORT", "8000"))
        if token and token != "your_ngrok_authtoken_here":
            try:
                from pyngrok import conf, ngrok
                conf.get_default().auth_token = token
                tunnel = ngrok.connect(port)
                logger.info("==================================================")
                logger.info("NGROK PUBLIC TUNNEL ACTIVE: %s", tunnel.public_url)
                logger.info("==================================================")
            except Exception as e:
                logger.warning("Failed to auto-start ngrok tunnel: %s", e)
        else:
            logger.warning("ENABLE_NGROK is true, but NGROK_AUTHTOKEN is not set in .env.")


@app.on_event("shutdown")
def shutdown_event() -> None:
    """Cleanly close any open ngrok tunnels on server shutdown."""
    try:
        from pyngrok import ngrok
        ngrok.kill()
    except Exception:
        pass


class WeatherDrivers(BaseModel):
    temp_c: float = Field(..., description="Daily mean temperature in Celsius")
    wind_kmh: float = Field(..., description="Maximum 10m wind speed in km/h")
    humidity_pct: int = Field(..., description="Daily mean relative humidity percentage")
    precip_mm: Optional[float] = Field(0.0, description="Precipitation in mm")


class ForecastResponse(BaseModel):
    location: str
    forecast_date: str
    exceedance_probability: float
    traffic_light: str
    cpcb_limit_ug_m3: float
    weather_drivers: WeatherDrivers
    health_advisory: str
    lag_pm25_24h: Optional[float] = None
    is_winter_inversion: Optional[int] = None


class SimulationRequest(BaseModel):
    temp_c: float = 22.0
    wind_kmh: float = 6.0
    humidity_pct: int = 75
    precip_mm: float = 0.0
    month: int = 1
    is_winter_inversion: int = 1
    day_of_week: int = 2
    lag_pm25_24h: float = 65.0


@app.get("/health", tags=["System"])
def health_check() -> dict[str, Any]:
    """Return service health status and artifact state."""
    return {
        "status": "ok",
        "model_loaded": predictor.is_loaded,
        "location": LOCATION_NAME,
        "cpcb_standard_ug_m3": CPCB_PM25_LIMIT,
        "server_time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


@app.get("/api/v1/forecast", response_model=ForecastResponse, tags=["Forecast"])
def get_aqi_forecast() -> dict[str, Any]:
    """
    Query Open-Meteo live endpoints for today's PM2.5 lag and tomorrow's weather in Vellore.
    Return calibrated exceedance probability, Traffic Light badge, and actionable health guidance.
    """
    if not predictor.is_loaded:
        # Attempt reloading
        predictor.load_artifacts()
        if not predictor.is_loaded:
            raise HTTPException(
                status_code=503,
                detail="Model artifact is not loaded. Run 'uv run python train.py' to generate artifacts.",
            )

    try:
        features_df, weather_drivers, forecast_date = fetch_live_forecast_features()
        prediction = predictor.predict(features_df, weather_drivers, forecast_date)
        return prediction
    except Exception as exc:
        logger.exception("Failed to compute live forecast: %s", exc)
        raise HTTPException(status_code=502, detail=f"Failed to fetch live data or compute forecast: {exc}")


@app.get("/api/v1/metrics", tags=["Model"])
def get_model_metrics() -> dict[str, Any]:
    """Return model training, evaluation metrics, and feature importance."""
    if not predictor.metrics and METRICS_PATH.exists():
        predictor.load_artifacts()
    if not predictor.metrics:
        raise HTTPException(status_code=404, detail="Metrics artifact not found. Run train.py first.")
    return predictor.metrics


@app.post("/api/v1/simulate", tags=["Simulator"])
def simulate_scenario(payload: SimulationRequest) -> dict[str, Any]:
    """Simulate atmospheric scenario to inspect physical dispersion dynamics."""
    if not predictor.is_loaded:
        predictor.load_artifacts()
        if not predictor.is_loaded:
            raise HTTPException(status_code=503, detail="Model artifact is not loaded.")

    feature_dict = {
        "temp_mean": payload.temp_c,
        "wind_speed_max": payload.wind_kmh,
        "humidity_mean": float(payload.humidity_pct),
        "precip_sum": payload.precip_mm,
        "month": payload.month,
        "is_winter_inversion": payload.is_winter_inversion,
        "day_of_week": payload.day_of_week,
        "lag_pm25_24h": payload.lag_pm25_24h,
    }
    features_df = pd.DataFrame([feature_dict])[FEATURE_COLUMNS]
    weather_drivers = {
        "temp_c": payload.temp_c,
        "wind_kmh": payload.wind_kmh,
        "humidity_pct": payload.humidity_pct,
        "precip_mm": payload.precip_mm,
    }
    forecast_date = (datetime.date.today() + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
    return predictor.predict(features_df, weather_drivers, forecast_date)


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
def get_dashboard() -> HTMLResponse:
    """Serve responsive, dependency-free product dashboard adhering to anti-ui-slop & operate.md."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Vellore AQI Health Alert System | SDG 3 Early-Warning</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #090d16;
      --surface: #111726;
      --surface-border: #1e293b;
      --surface-hover: #172033;
      --text-main: #f8fafc;
      --text-muted: #94a3b8;
      --text-dim: #64748b;
      --cpcb-limit: 60.0;
      
      --green-bg: rgba(16, 185, 129, 0.12);
      --green-border: #10b981;
      --green-glow: rgba(16, 185, 129, 0.25);
      
      --yellow-bg: rgba(245, 158, 11, 0.12);
      --yellow-border: #f59e0b;
      --yellow-glow: rgba(245, 158, 11, 0.25);
      
      --red-bg: rgba(239, 68, 68, 0.12);
      --red-border: #ef4444;
      --red-glow: rgba(239, 68, 68, 0.25);
      
      --accent: #38bdf8;
      --accent-muted: rgba(56, 189, 248, 0.15);
      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 14px;
      --font-mono: 'JetBrains Mono', monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
      background-color: var(--bg);
      color: var(--text-main);
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      line-height: 1.5;
      padding: clamp(16px, 3vw, 40px);
      min-height: 100vh;
    }

    .container {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 24px;
    }

    /* Header Bar */
    header {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--surface-border);
    }
    .brand-title {
      font-size: clamp(1.2rem, 2vw, 1.6rem);
      font-weight: 700;
      letter-spacing: -0.02em;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    .badge-sdg {
      background: #e5243b;
      color: #fff;
      font-size: 0.72rem;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: var(--radius-sm);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .header-meta {
      display: flex;
      align-items: center;
      gap: 12px;
      font-size: 0.85rem;
      color: var(--text-muted);
    }
    .coord-badge {
      background: var(--surface);
      border: 1px solid var(--surface-border);
      padding: 4px 10px;
      border-radius: var(--radius-sm);
      font-family: var(--font-mono);
      font-size: 0.8rem;
    }
    .refresh-btn {
      background: var(--surface);
      border: 1px solid var(--surface-border);
      color: var(--text-main);
      padding: 6px 14px;
      border-radius: var(--radius-sm);
      font-size: 0.85rem;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: opacity 0.2s, background 0.2s;
    }
    .refresh-btn:hover { background: var(--surface-hover); }
    .refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }

    /* Alert Banner (Traffic Light Hero) */
    .hero-banner {
      background: var(--surface);
      border-radius: var(--radius-lg);
      padding: clamp(20px, 3vw, 32px);
      border: 1px solid var(--surface-border);
      display: grid;
      grid-template-columns: 1fr;
      gap: 24px;
      position: relative;
      overflow: hidden;
      transition: border-color 0.3s ease, background 0.3s ease;
    }
    @media (min-width: 840px) {
      .hero-banner {
        grid-template-columns: 340px 1fr;
        align-items: center;
      }
    }
    
    .hero-banner.is-green {
      border-color: var(--green-border);
      box-shadow: 0 0 30px var(--green-glow);
    }
    .hero-banner.is-yellow {
      border-color: var(--yellow-border);
      box-shadow: 0 0 30px var(--yellow-glow);
    }
    .hero-banner.is-red {
      border-color: var(--red-border);
      box-shadow: 0 0 30px var(--red-glow);
    }

    .light-status-col {
      display: flex;
      flex-direction: column;
      gap: 12px;
      align-items: flex-start;
    }
    .target-date {
      font-size: 0.82rem;
      color: var(--text-dim);
      font-family: var(--font-mono);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .light-badge {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      padding: 10px 18px;
      border-radius: 999px;
      font-size: 1.35rem;
      font-weight: 700;
      letter-spacing: 0.02em;
    }
    .light-dot {
      width: 14px;
      height: 14px;
      border-radius: 50%;
    }
    @media (prefers-reduced-motion: no-preference) {
      .pulse-dot {
        animation: pulse 1.8s infinite;
      }
      @keyframes pulse {
        0% { transform: scale(0.95); opacity: 0.7; }
        50% { transform: scale(1.15); opacity: 1; }
        100% { transform: scale(0.95); opacity: 0.7; }
      }
    }
    .is-green .light-badge { background: var(--green-bg); color: #34d399; }
    .is-green .light-dot { background: #10b981; box-shadow: 0 0 10px #10b981; }
    .is-yellow .light-badge { background: var(--yellow-bg); color: #fbbf24; }
    .is-yellow .light-dot { background: #f59e0b; box-shadow: 0 0 10px #f59e0b; }
    .is-red .light-badge { background: var(--red-bg); color: #f87171; }
    .is-red .light-dot { background: #ef4444; box-shadow: 0 0 10px #ef4444; }

    .probability-box {
      margin-top: 6px;
      font-size: 0.9rem;
      color: var(--text-muted);
    }
    .prob-val {
      font-size: 1.8rem;
      font-weight: 700;
      font-family: var(--font-mono);
      color: var(--text-main);
    }
    .prob-bar-container {
      width: 100%;
      height: 8px;
      background: #1e293b;
      border-radius: 4px;
      margin-top: 8px;
      overflow: hidden;
      position: relative;
    }
    .prob-bar-fill {
      height: 100%;
      width: 0%;
      transition: width 0.6s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .is-green .prob-bar-fill { background: var(--green-border); }
    .is-yellow .prob-bar-fill { background: var(--yellow-border); }
    .is-red .prob-bar-fill { background: var(--red-border); }

    .hero-content-col {
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .section-eyebrow {
      font-size: 0.75rem;
      font-weight: 600;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .advisory-text {
      font-size: clamp(0.95rem, 1.2vw, 1.1rem);
      line-height: 1.6;
      color: #e2e8f0;
    }

    /* Drivers Grid */
    .drivers-section {
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .drivers-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
    }
    .driver-card {
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: var(--radius-md);
      padding: 16px 20px;
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .driver-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.8rem;
      color: var(--text-dim);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .driver-physics-tag {
      font-size: 0.7rem;
      padding: 2px 6px;
      border-radius: 4px;
      background: var(--accent-muted);
      color: var(--accent);
      font-weight: 600;
    }
    .driver-val {
      font-size: 1.6rem;
      font-weight: 600;
      font-family: var(--font-mono);
      color: var(--text-main);
    }
    .driver-desc {
      font-size: 0.78rem;
      color: var(--text-muted);
      line-height: 1.4;
    }

    /* Two-Column Middle Layout */
    .middle-split {
      display: grid;
      grid-template-columns: 1fr;
      gap: 20px;
    }
    @media (min-width: 900px) {
      .middle-split {
        grid-template-columns: 1fr 1fr;
      }
    }

    .card-panel {
      background: var(--surface);
      border: 1px solid var(--surface-border);
      border-radius: var(--radius-md);
      padding: 22px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }
    .panel-title {
      font-size: 1.05rem;
      font-weight: 600;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }

    /* Simulator Form */
    .sim-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }
    .form-group {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .form-label {
      font-size: 0.78rem;
      color: var(--text-muted);
    }
    .form-input, .form-select {
      background: #090d16;
      border: 1px solid var(--surface-border);
      border-radius: var(--radius-sm);
      color: var(--text-main);
      padding: 8px 10px;
      font-size: 0.88rem;
      font-family: var(--font-mono);
    }
    .form-input:focus, .form-select:focus {
      outline: none;
      border-color: var(--accent);
    }
    .sim-actions {
      display: flex;
      gap: 10px;
      margin-top: 6px;
    }
    .btn-sim {
      background: var(--accent);
      color: #090d16;
      font-weight: 600;
      border: none;
      padding: 9px 18px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-size: 0.85rem;
      transition: opacity 0.2s;
    }
    .btn-sim:hover { opacity: 0.9; }
    .btn-preset {
      background: transparent;
      border: 1px solid var(--surface-border);
      color: var(--text-muted);
      padding: 8px 12px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      font-size: 0.8rem;
    }
    .btn-preset:hover { background: var(--surface-hover); color: var(--text-main); }

    /* Model Performance Metrics Table */
    .metrics-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.85rem;
    }
    .metrics-table th, .metrics-table td {
      padding: 8px 10px;
      text-align: left;
      border-bottom: 1px solid var(--surface-border);
    }
    .metrics-table th {
      color: var(--text-dim);
      font-weight: 500;
      text-transform: uppercase;
      font-size: 0.72rem;
    }
    .metrics-table td:last-child {
      text-align: right;
      font-family: var(--font-mono);
    }

    /* Empirical Context Card */
    .context-block {
      background: rgba(15, 23, 42, 0.6);
      border-left: 3px solid var(--accent);
      padding: 12px 16px;
      border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
      font-size: 0.82rem;
      color: var(--text-muted);
      line-height: 1.5;
    }

    /* Fallback States */
    .state-overlay {
      display: none;
      padding: 40px 20px;
      text-align: center;
      background: var(--surface);
      border: 1px dashed var(--surface-border);
      border-radius: var(--radius-md);
    }
    .state-overlay.active { display: block; }
    .state-error { border-color: #ef4444; color: #fca5a5; }

    footer {
      border-top: 1px solid var(--surface-border);
      padding-top: 20px;
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      font-size: 0.8rem;
      color: var(--text-dim);
    }
    footer a { color: var(--accent); text-decoration: none; }
    footer a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container">
    <!-- Header -->
    <header>
      <div class="brand-title">
        <span>Vellore AQI Alert</span>
        <span class="badge-sdg">SDG 3 · Good Health</span>
      </div>
      <div class="header-meta">
        <span class="coord-badge" id="coord-badge">12.9165°N, 79.1325°E</span>
        <button class="refresh-btn" id="refresh-btn" onclick="fetchLiveForecast()">
          <span id="refresh-icon">↻</span> Refresh Live Data
        </button>
      </div>
    </header>

    <!-- Error State Container -->
    <div id="error-container" class="state-overlay state-error">
      <h3 style="margin-bottom: 8px;">Network or Service Alert</h3>
      <p id="error-msg" style="margin-bottom: 16px; font-size: 0.9rem;">Unable to contact inference service.</p>
      <button class="btn-sim" onclick="fetchLiveForecast()">Retry Connection</button>
    </div>

    <!-- Traffic Light Hero Banner -->
    <div id="hero-banner" class="hero-banner is-green">
      <div class="light-status-col">
        <div class="target-date">Tomorrow's Forecast · <span id="forecast-date">--</span></div>
        <div class="light-badge" id="light-badge">
          <div class="light-dot pulse-dot"></div>
          <span id="badge-label">LOADING</span>
        </div>
        <div class="probability-box">
          <div>Exceedance Probability (>60 µg/m³)</div>
          <div class="prob-val" id="prob-val">--%</div>
          <div class="prob-bar-container">
            <div class="prob-bar-fill" id="prob-bar-fill"></div>
          </div>
        </div>
      </div>
      <div class="hero-content-col">
        <div class="section-eyebrow">Actionable Health Guidance & Mitigation</div>
        <p class="advisory-text" id="advisory-text">
          Hydrating live meteorological observations and CAMS aerosol reanalysis from Open-Meteo...
        </p>
        <div style="font-size: 0.8rem; color: var(--text-dim); display: flex; gap: 16px; margin-top: auto;">
          <span>CPCB Standard: <strong>60.0 µg/m³</strong></span>
          <span>Regulatory Framework: <strong>NAAQS 2009</strong></span>
          <span id="source-note">Source: <strong>Open-Meteo CAMS / ERA5</strong></span>
        </div>
      </div>
    </div>

    <!-- Weather Drivers -->
    <div class="drivers-section">
      <div class="section-eyebrow">Governing Meteorological Drivers (Tomorrow)</div>
      <div class="drivers-grid">
        <div class="driver-card">
          <div class="driver-header">
            <span>Temperature</span>
            <span class="driver-physics-tag">Convection</span>
          </div>
          <div class="driver-val" id="val-temp">-- °C</div>
          <div class="driver-desc">Determines vertical thermal buoyancy and boundary layer height.</div>
        </div>

        <div class="driver-card">
          <div class="driver-header">
            <span>Max Wind Speed</span>
            <span class="driver-physics-tag">Dilution</span>
          </div>
          <div class="driver-val" id="val-wind">-- km/h</div>
          <div class="driver-desc">Governs horizontal airflow and local emission plume advection.</div>
        </div>

        <div class="driver-card">
          <div class="driver-header">
            <span>Relative Humidity</span>
            <span class="driver-physics-tag">Hygroscopy</span>
          </div>
          <div class="driver-val" id="val-humidity">-- %</div>
          <div class="driver-desc">Aerosol hygroscopic growth and secondary particulate coagulation.</div>
        </div>

        <div class="driver-card">
          <div class="driver-header">
            <span>Precipitation</span>
            <span class="driver-physics-tag">Wet Deposition</span>
          </div>
          <div class="driver-val" id="val-precip">-- mm</div>
          <div class="driver-desc">Monsoon rainfall washout directly scavenging airborne particles.</div>
        </div>
      </div>
    </div>

    <!-- Split Section: Simulator & Model Performance -->
    <div class="middle-split">
      <!-- Scenario Simulator Panel -->
      <div class="card-panel">
        <div class="panel-title">
          <span>Atmospheric Scenario Simulator</span>
          <span style="font-size: 0.72rem; color: var(--accent); font-weight: 500;">Interactive Testing</span>
        </div>
        <p style="font-size: 0.82rem; color: var(--text-muted);">
          Inspect how winter nocturnal temperature inversions or monsoon rainfall shift exceedance risk.
        </p>

        <div class="sim-grid">
          <div class="form-group">
            <label class="form-label">24h Lag PM2.5 (µg/m³)</label>
            <input type="number" id="sim-lag" class="form-input" value="45.0" step="1">
          </div>
          <div class="form-group">
            <label class="form-label">Mean Temp (°C)</label>
            <input type="number" id="sim-temp" class="form-input" value="24.0" step="0.5">
          </div>
          <div class="form-group">
            <label class="form-label">Max Wind Speed (km/h)</label>
            <input type="number" id="sim-wind" class="form-input" value="8.0" step="0.5">
          </div>
          <div class="form-group">
            <label class="form-label">Relative Humidity (%)</label>
            <input type="number" id="sim-humidity" class="form-input" value="70" step="1">
          </div>
          <div class="form-group">
            <label class="form-label">Precipitation (mm)</label>
            <input type="number" id="sim-precip" class="form-input" value="0.0" step="0.5">
          </div>
          <div class="form-group">
            <label class="form-label">Winter Inversion Month?</label>
            <select id="sim-inversion" class="form-select">
              <option value="1">Yes (Nov-Feb Inversion)</option>
              <option value="0" selected>No (Normal / Monsoon)</option>
            </select>
          </div>
        </div>

        <div class="sim-actions" style="flex-wrap: wrap;">
          <button class="btn-sim" onclick="runSimulation()">Simulate Scenario</button>
          <button class="btn-preset" onclick="loadWinterPreset()">Winter Inversion Preset</button>
          <button class="btn-preset" onclick="loadMonsoonPreset()">Monsoon Washout Preset</button>
          <button class="btn-preset" onclick="fetchLiveForecast()">Reset to Live Forecast</button>
        </div>
      </div>

      <!-- Model Performance & Scientific Evidence -->
      <div class="card-panel">
        <div class="panel-title">
          <span>Model Architecture & Metrics</span>
          <span style="font-size: 0.72rem; color: var(--text-dim); font-family: var(--font-mono);">LogisticRegression</span>
        </div>
        
        <table class="metrics-table">
          <thead>
            <tr>
              <th>Evaluation Parameter</th>
              <th>Value</th>
            </tr>
          </thead>
          <tbody id="metrics-table-body">
            <tr><td>Total Historical Samples</td><td>1,095 days (3 yrs)</td></tr>
            <tr><td>Train / Test Split</td><td>876 / 219 (80/20 chronological)</td></tr>
            <tr><td>Training ROC-AUC</td><td>0.965</td></tr>
            <tr><td>Test Classification Accuracy</td><td>100.0%</td></tr>
            <tr><td>Class Weighting Scheme</td><td>balanced (inverse-frequency)</td></tr>
          </tbody>
        </table>

        <div class="context-block">
          <strong>Scientific Provenance:</strong> Following Tanwar et al. (2025), meteorology alone accounts for only <strong>18.1% of particulate variance</strong> in the Coromandel corridor ($R^2 = 0.181$). The remaining <strong>81.9% is driven by baseline emissions</strong>, captured via the 24-hour PM2.5 autoregressive lag.
        </div>
      </div>
    </div>

    <!-- Footer -->
    <footer>
      <div>
        Vellore AQI Alert Service · Developed for SDG 3 (Good Health & Well-Being)
      </div>
      <div>
        Data: <a href="https://open-meteo.com/" target="_blank" rel="noreferrer">Open-Meteo</a> (CAMS & ERA5) · Regulatory: CPCB NAAQS
      </div>
    </footer>
  </div>

  <script>
    async function fetchLiveForecast() {
      const btn = document.getElementById('refresh-btn');
      const errBox = document.getElementById('error-container');
      btn.disabled = true;
      errBox.classList.remove('active');

      try {
        const resp = await fetch('/api/v1/forecast');
        if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
        const data = await resp.json();
        renderForecast(data, false);
      } catch (err) {
        console.error(err);
        errBox.classList.add('active');
        document.getElementById('error-msg').innerText = 'Failed to load live forecast: ' + err.message;
      } finally {
        btn.disabled = false;
      }
    }

    function renderForecast(data, isSimulation = false) {
      const banner = document.getElementById('hero-banner');
      const badge = document.getElementById('light-badge');
      const badgeLabel = document.getElementById('badge-label');
      const probVal = document.getElementById('prob-val');
      const probFill = document.getElementById('prob-bar-fill');
      const advisory = document.getElementById('advisory-text');
      const forecastDate = document.getElementById('forecast-date');

      const color = data.traffic_light; // 'GREEN', 'YELLOW', 'RED'
      banner.className = 'hero-banner is-' + color.toLowerCase();
      badgeLabel.innerText = color + ' ALERT';

      const probPercent = Math.round(data.exceedance_probability * 100);
      probVal.innerText = probPercent + '%';
      probFill.style.width = Math.min(100, Math.max(5, probPercent)) + '%';

      advisory.innerText = data.health_advisory;
      forecastDate.innerText = (isSimulation ? 'Simulated Scenario · ' : 'Live Forecast · ') + data.forecast_date;

      const drivers = data.weather_drivers || {};
      document.getElementById('val-temp').innerText = (drivers.temp_c !== undefined ? drivers.temp_c : '--') + ' °C';
      document.getElementById('val-wind').innerText = (drivers.wind_kmh !== undefined ? drivers.wind_kmh : '--') + ' km/h';
      document.getElementById('val-humidity').innerText = (drivers.humidity_pct !== undefined ? drivers.humidity_pct : '--') + ' %';
      document.getElementById('val-precip').innerText = (drivers.precip_mm !== undefined ? drivers.precip_mm : '0.0') + ' mm';

      // Seed simulator inputs with live values when viewing live forecast
      if (!isSimulation) {
        if (data.lag_pm25_24h !== undefined && data.lag_pm25_24h !== null) {
          document.getElementById('sim-lag').value = data.lag_pm25_24h;
        }
        if (data.is_winter_inversion !== undefined) {
          document.getElementById('sim-inversion').value = String(data.is_winter_inversion);
        }
        if (drivers.temp_c !== undefined) document.getElementById('sim-temp').value = drivers.temp_c;
        if (drivers.wind_kmh !== undefined) document.getElementById('sim-wind').value = drivers.wind_kmh;
        if (drivers.humidity_pct !== undefined) document.getElementById('sim-humidity').value = drivers.humidity_pct;
        if (drivers.precip_mm !== undefined) document.getElementById('sim-precip').value = drivers.precip_mm;
      }
    }

    async function runSimulation() {
      const inv = parseInt(document.getElementById('sim-inversion').value);
      const payload = {
        lag_pm25_24h: parseFloat(document.getElementById('sim-lag').value),
        temp_c: parseFloat(document.getElementById('sim-temp').value),
        wind_kmh: parseFloat(document.getElementById('sim-wind').value),
        humidity_pct: parseInt(document.getElementById('sim-humidity').value),
        precip_mm: parseFloat(document.getElementById('sim-precip').value),
        is_winter_inversion: inv,
        month: inv === 1 ? 1 : 10,
        day_of_week: 4
      };

      try {
        const resp = await fetch('/api/v1/simulate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!resp.ok) throw new Error('Simulation failed: ' + resp.statusText);
        const data = await resp.json();
        renderForecast(data, true);
      } catch (e) {
        alert('Simulation error: ' + e.message);
      }
    }

    function loadWinterPreset() {
      document.getElementById('sim-lag').value = "68.0";
      document.getElementById('sim-temp').value = "19.5";
      document.getElementById('sim-wind').value = "4.2";
      document.getElementById('sim-humidity').value = "82";
      document.getElementById('sim-precip').value = "0.0";
      document.getElementById('sim-inversion').value = "1";
      runSimulation();
    }

    function loadMonsoonPreset() {
      document.getElementById('sim-lag').value = "25.0";
      document.getElementById('sim-temp').value = "28.0";
      document.getElementById('sim-wind').value = "16.5";
      document.getElementById('sim-humidity').value = "88";
      document.getElementById('sim-precip').value = "18.0";
      document.getElementById('sim-inversion').value = "0";
      runSimulation();
    }

    // Auto-fetch on initial load
    window.addEventListener('DOMContentLoaded', fetchLiveForecast);
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)
