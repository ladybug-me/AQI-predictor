"""Configuration parameters, API endpoints, coordinates, and regulatory limits."""
from pathlib import Path

# Geographical Coordinates for Vellore, India
LATITUDE: float = 12.9165
LONGITUDE: float = 79.1325
LOCATION_NAME: str = "Vellore, IN"

# Regulatory Baseline (CPCB NAAQS 24-Hour PM2.5 Limit)
CPCB_PM25_LIMIT: float = 60.0  # µg/m³

# Traffic Light Classification Thresholds
PROB_GREEN_MAX: float = 0.35   # Prob < 0.35 -> GREEN
PROB_RED_MIN: float = 0.65     # Prob >= 0.65 -> RED
# 0.35 <= Prob < 0.65 -> YELLOW

# Open-Meteo API Endpoints
AIR_QUALITY_API_URL: str = "https://air-quality-api.open-meteo.com/v1/air-quality"
WEATHER_ARCHIVE_URL: str = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_FORECAST_URL: str = "https://api.open-meteo.com/v1/forecast"

# Artifact Paths
BASE_DIR: Path = Path(__file__).resolve().parent.parent
MODELS_DIR: Path = BASE_DIR / "models"
MODEL_PATH: Path = MODELS_DIR / "aqi_classifier.joblib"
METRICS_PATH: Path = MODELS_DIR / "metrics.json"

# Feature Specification
FEATURE_COLUMNS: list[str] = [
    "temp_mean",
    "wind_speed_max",
    "humidity_mean",
    "precip_sum",
    "month",
    "is_winter_inversion",
    "day_of_week",
    "lag_pm25_24h",
]

# HTTP Settings
REQUEST_TIMEOUT_SECONDS: int = 15
MAX_RETRIES: int = 3
BACKOFF_FACTOR: float = 1.0
