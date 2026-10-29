"""Inference engine and contextual health advisory generator."""
from __future__ import annotations

import json
import logging
from typing import Any

import joblib
import pandas as pd

from app.config import (
    CPCB_PM25_LIMIT,
    LOCATION_NAME,
    METRICS_PATH,
    MODEL_PATH,
    PROB_GREEN_MAX,
    PROB_RED_MIN,
)

logger = logging.getLogger(__name__)


class AQIPredictor:
    """Manages model loading, calibrated inference, and health advisory synthesis."""

    def __init__(self) -> None:
        self.pipeline: Any | None = None
        self.metrics: dict[str, Any] = {}
        self.load_artifacts()

    def load_artifacts(self) -> bool:
        """Attempt to load serialized model pipeline and metrics from disk."""
        if MODEL_PATH.exists():
            try:
                self.pipeline = joblib.load(MODEL_PATH)
                logger.info("Successfully loaded AQI classifier model from %s", MODEL_PATH)
            except Exception as e:
                logger.error("Failed to load model from %s: %s", MODEL_PATH, e)
                self.pipeline = None
        else:
            logger.warning("Model file not found at %s. Service requires training.", MODEL_PATH)
            self.pipeline = None

        if METRICS_PATH.exists():
            try:
                with open(METRICS_PATH, "r", encoding="utf-8") as f:
                    self.metrics = json.load(f)
                logger.info("Successfully loaded metrics from %s", METRICS_PATH)
            except Exception as e:
                logger.error("Failed to load metrics from %s: %s", METRICS_PATH, e)
                self.metrics = {}
        else:
            self.metrics = {}

        return self.is_loaded

    @property
    def is_loaded(self) -> bool:
        """Return True if model pipeline is loaded and ready for inference."""
        return self.pipeline is not None

    def get_traffic_light(self, probability: float) -> str:
        """
        Map calibrated probability to Traffic Light status:
        - GREEN:  Prob < 0.35
        - YELLOW: 0.35 <= Prob < 0.65
        - RED:    Prob >= 0.65
        """
        if probability < PROB_GREEN_MAX:
            return "GREEN"
        elif probability >= PROB_RED_MIN:
            return "RED"
        else:
            return "YELLOW"

    def generate_health_advisory(
        self,
        traffic_light: str,
        weather_drivers: dict[str, Any],
        is_winter_inversion: bool,
    ) -> str:
        """Synthesize contextual health guidance based on risk level and atmospheric physics."""
        temp = weather_drivers.get("temp_c", 25.0)
        wind = weather_drivers.get("wind_kmh", 10.0)
        precip = weather_drivers.get("precip_mm", 0.0)

        # Meteorological context clauses
        meteo_notes: list[str] = []
        if is_winter_inversion:
            meteo_notes.append("Cool nocturnal surface boundary layer is suppressing convective mixing.")
        if precip > 2.0:
            meteo_notes.append("Monsoon wet deposition is actively scavenging airborne particulate matter.")
        elif wind > 14.0:
            meteo_notes.append("Stronger surface airflow is providing horizontal plume dilution.")
        elif wind < 6.0:
            meteo_notes.append("Stagnant low wind speeds are constraining horizontal dispersion.")

        context_str = " " + " ".join(meteo_notes) if meteo_notes else ""

        if traffic_light == "RED":
            advisory = (
                f"High risk of PM2.5 exceeding the CPCB safe limit (60 µg/m³).{context_str} "
                "Vulnerable groups (children, elderly, individuals with asthma or COPD) should stay indoors. "
                "Avoid morning and evening outdoor cardio workouts. Keep windows closed and consider HEPA filtration."
            )
        elif traffic_light == "YELLOW":
            advisory = (
                f"Moderate PM2.5 exceedance risk.{context_str} "
                "Air quality is acceptable for the general public, but unusually sensitive individuals should reduce prolonged heavy exertion outdoors. "
                "Students and commuters are advised to monitor evening conditions."
            )
        else:
            advisory = (
                f"Low exceedance risk.{context_str} "
                "Atmospheric dispersion is favorable; particulate concentrations are expected to remain within the safe CPCB 60 µg/m³ 24-hour limit. "
                "Normal outdoor activities and campus sports are recommended."
            )

        return advisory

    def predict(
        self,
        features_df: pd.DataFrame,
        weather_drivers: dict[str, Any],
        forecast_date: str,
    ) -> dict[str, Any]:
        """
        Run model prediction for tomorrow and format standardized response payload.
        """
        if not self.is_loaded:
            raise RuntimeError(
                "Model artifact is not loaded. Run 'uv run python train.py' to generate model artifacts."
            )

        # Calibrated probability of class 1 (pm2_5 > 60 µg/m³)
        probabilities = self.pipeline.predict_proba(features_df)
        prob_exceedance = float(probabilities[0, 1])

        traffic_light = self.get_traffic_light(prob_exceedance)
        is_winter = bool(features_df.get("is_winter_inversion", [0]).iloc[0])

        advisory = self.generate_health_advisory(traffic_light, weather_drivers, is_winter)

        # Standard weather drivers payload (temp_c, wind_kmh, humidity_pct)
        standard_drivers = {
            "temp_c": weather_drivers.get("temp_c"),
            "wind_kmh": weather_drivers.get("wind_kmh"),
            "humidity_pct": weather_drivers.get("humidity_pct"),
        }

        return {
            "location": LOCATION_NAME,
            "forecast_date": forecast_date,
            "exceedance_probability": round(prob_exceedance, 2),
            "traffic_light": traffic_light,
            "cpcb_limit_ug_m3": CPCB_PM25_LIMIT,
            "weather_drivers": standard_drivers,
            "health_advisory": advisory,
        }


# Global predictor instance
predictor = AQIPredictor()
