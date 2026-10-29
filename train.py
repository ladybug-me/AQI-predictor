"""Model training pipeline for Vellore AQI PM2.5 Exceedance Classifier."""
from __future__ import annotations

import datetime
import json
import logging
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.config import (
    FEATURE_COLUMNS,
    METRICS_PATH,
    MODEL_PATH,
    MODELS_DIR,
)
from app.pipeline import fetch_historical_training_data

logger = logging.getLogger("train")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def train() -> None:
    """Fetch historical data, train LogisticRegression pipeline, evaluate, and save artifacts."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Starting historical data collection from Open-Meteo...")
    df = fetch_historical_training_data(years=3)

    if len(df) < 50:
        raise ValueError(f"Insufficient training samples collected ({len(df)} rows). Check API availability.")

    X = df[FEATURE_COLUMNS]
    y = df["target"]

    total_samples = len(df)
    positive_samples = int(y.sum())
    negative_samples = total_samples - positive_samples

    logger.info(
        "Dataset loaded: %d total days (%d exceedance days [1], %d safe days [0], baseline rate: %.2f%%).",
        total_samples,
        positive_samples,
        negative_samples,
        (positive_samples / total_samples) * 100,
    )

    # Chronological train/test split: first 80% train, final 20% test (preserving time-series order)
    split_index = int(total_samples * 0.8)
    X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
    y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]

    train_pos = int(y_train.sum())
    test_pos = int(y_test.sum())

    logger.info(
        "Chronological Split: Train=%d days (%d exceedances), Test=%d days (%d exceedances)",
        len(X_train),
        train_pos,
        len(X_test),
        test_pos,
    )

    # Scikit-learn Pipeline: StandardScaler + LogisticRegression(class_weight='balanced')
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(class_weight="balanced", random_state=42, max_iter=1000)),
    ])

    logger.info("Fitting balanced Logistic Regression pipeline...")
    pipeline.fit(X_train, y_train)

    # Evaluate on Test Set
    y_test_pred = pipeline.predict(X_test)
    y_test_prob = pipeline.predict_proba(X_test)[:, 1]

    acc = float(accuracy_score(y_test, y_test_pred))
    prec = float(precision_score(y_test, y_test_pred, zero_division=0))
    rec = float(recall_score(y_test, y_test_pred, zero_division=0))
    f1 = float(f1_score(y_test, y_test_pred, zero_division=0))

    try:
        raw_roc = roc_auc_score(y_test, y_test_prob)
        roc_auc = None if np.isnan(raw_roc) else round(float(raw_roc), 4)
    except (ValueError, TypeError):
        # Occurs if test set contains only negative samples (e.g. spring-monsoon window)
        logger.warning("Test set contains only one class. Test ROC-AUC is undefined; computing full/train baseline.")
        roc_auc = None

    # Compute training metrics for reference
    y_train_pred = pipeline.predict(X_train)
    y_train_prob = pipeline.predict_proba(X_train)[:, 1]
    train_acc = float(accuracy_score(y_train, y_train_pred))
    train_prec = float(precision_score(y_train, y_train_pred, zero_division=0))
    train_rec = float(recall_score(y_train, y_train_pred, zero_division=0))
    train_f1 = float(f1_score(y_train, y_train_pred, zero_division=0))
    train_roc = float(roc_auc_score(y_train, y_train_prob))

    # Coefficients and Feature Importance
    clf: LogisticRegression = pipeline.named_steps["classifier"]
    coeffs = clf.coef_[0].tolist()
    odds_ratios = np.exp(coeffs).tolist()
    feature_importance = {
        feat: {
            "coefficient": round(c, 4),
            "odds_ratio": round(o, 4),
        }
        for feat, c, o in zip(FEATURE_COLUMNS, coeffs, odds_ratios)
    }

    metrics_payload = {
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1_score": round(f1, 4),
        "roc_auc": round(roc_auc, 4) if roc_auc is not None else None,
        "sample_counts": {
            "total": total_samples,
            "train": len(X_train),
            "test": len(X_test),
            "train_exceedances": train_pos,
            "test_exceedances": test_pos,
        },
        "train_baseline": {
            "accuracy": round(train_acc, 4),
            "precision": round(train_prec, 4),
            "recall": round(train_rec, 4),
            "f1_score": round(train_f1, 4),
            "roc_auc": round(train_roc, 4),
        },
        "feature_importance": feature_importance,
        "trained_at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "model_type": "LogisticRegression(class_weight='balanced')",
    }

    # Save artifacts
    joblib.dump(pipeline, MODEL_PATH)
    logger.info("Saved serialized model to %s", MODEL_PATH)

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics_payload, f, indent=2)
    logger.info("Saved evaluation metrics to %s", METRICS_PATH)

    print("\n" + "=" * 60)
    print(" VELLORE AQI CLASSIFIER TRAINING SUMMARY")
    print("=" * 60)
    print(f"Total Samples:       {total_samples} days")
    print(f"Train / Test Split:  {len(X_train)} / {len(X_test)} days (80/20 chronological)")
    print(f"Test Accuracy:       {acc:.4f}")
    print(f"Test Precision:      {prec:.4f}")
    print(f"Test Recall:         {rec:.4f}")
    print(f"Test F1-Score:       {f1:.4f}")
    print(f"Test ROC-AUC:        {roc_auc if roc_auc is not None else 'N/A (Single class in test)'}")
    print(f"Train ROC-AUC:       {train_roc:.4f}")
    print("-" * 60)
    print("Feature Importance (Standardized Odds Ratios):")
    for feat, stats in sorted(feature_importance.items(), key=lambda x: abs(x[1]["coefficient"]), reverse=True):
        print(f"  {feat:<22} coef: {stats['coefficient']:>7.4f} | OR: {stats['odds_ratio']:>7.4f}")
    print("=" * 60)
    print("Artifacts generated successfully.\n")


if __name__ == "__main__":
    train()
