"""
Unit Tests – ML Models (backend.ml.models)
==========================================
Tests RandomForestIDS, XGBoostIDS, and EnsembleIDS using in-memory
synthetic data.  No disk artifacts or PostgreSQL required.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ai.models import EnsembleIDS, RandomForestIDS, XGBoostIDS

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

N_TRAIN = 120
N_VAL = 30
N_FEATURES = 10
CLASSES = ["Normal", "DDoS", "PortScan"]
FEATURE_COLS = [f"feature_{i}" for i in range(N_FEATURES)]
RNG = np.random.default_rng(42)


@pytest.fixture(scope="module")
def synthetic_dataset():
    """Return (X_train, y_train, X_val, y_val) as DataFrames/Series."""
    X_train = pd.DataFrame(
        RNG.standard_normal((N_TRAIN, N_FEATURES)), columns=FEATURE_COLS
    )
    y_train = pd.Series(
        RNG.choice(CLASSES, size=N_TRAIN), name="label"
    )
    X_val = pd.DataFrame(
        RNG.standard_normal((N_VAL, N_FEATURES)), columns=FEATURE_COLS
    )
    y_val = pd.Series(
        RNG.choice(CLASSES, size=N_VAL), name="label"
    )
    return X_train, y_train, X_val, y_val


# ---------------------------------------------------------------------------
# RandomForestIDS
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRandomForestIDS:

    def test_initialization(self):
        model = RandomForestIDS(n_estimators=5, max_depth=3)
        assert model.model_name == "RandomForest"
        assert not model.is_trained

    def test_train_sets_is_trained(self, synthetic_dataset):
        X_train, y_train, X_val, y_val = synthetic_dataset
        model = RandomForestIDS(n_estimators=5, max_depth=3)
        metrics = model.train(X_train, y_train, X_val, y_val)

        assert model.is_trained
        assert "accuracy" in metrics
        assert 0.0 <= metrics["accuracy"] <= 1.0
        assert model.feature_names == FEATURE_COLS

    def test_predict_output_shape(self, synthetic_dataset):
        X_train, y_train, X_val, y_val = synthetic_dataset
        model = RandomForestIDS(n_estimators=5, max_depth=3)
        model.train(X_train, y_train)

        preds = model.predict(X_val)
        assert len(preds) == N_VAL

    def test_predict_proba_sums_to_one(self, synthetic_dataset):
        X_train, y_train, X_val, y_val = synthetic_dataset
        model = RandomForestIDS(n_estimators=5, max_depth=3)
        model.train(X_train, y_train)

        proba = model.predict_proba(X_val)
        assert proba.shape == (N_VAL, len(CLASSES))
        assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6)

    def test_predict_untrained_raises(self):
        model = RandomForestIDS(n_estimators=5)
        X = pd.DataFrame(RNG.standard_normal((5, N_FEATURES)), columns=FEATURE_COLS)
        with pytest.raises(ValueError, match="not trained"):
            model.predict(X)


# ---------------------------------------------------------------------------
# XGBoostIDS
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestXGBoostIDS:

    def test_initialization(self):
        model = XGBoostIDS(n_estimators=5, max_depth=3)
        assert model.model_name == "XGBoost"
        assert not model.is_trained

    def test_train_sets_is_trained(self, synthetic_dataset):
        X_train, y_train, X_val, y_val = synthetic_dataset
        model = XGBoostIDS(n_estimators=5, max_depth=3)
        metrics = model.train(X_train, y_train, X_val, y_val)

        assert model.is_trained
        assert "accuracy" in metrics

    def test_predict_output_shape(self, synthetic_dataset):
        X_train, y_train, _, _ = synthetic_dataset
        X_test = pd.DataFrame(
            RNG.standard_normal((10, N_FEATURES)), columns=FEATURE_COLS
        )
        model = XGBoostIDS(n_estimators=5, max_depth=3)
        model.train(X_train, y_train)

        preds = model.predict(X_test)
        assert len(preds) == 10


# ---------------------------------------------------------------------------
# EnsembleIDS
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEnsembleIDS:

    def test_initialization(self):
        ensemble = EnsembleIDS(voting="soft")
        assert ensemble.model_name == "Ensemble"
        assert not ensemble.is_trained
        assert ensemble.models == []

    def test_add_model(self):
        ensemble = EnsembleIDS()
        rf = RandomForestIDS(n_estimators=5)
        ensemble.add_model(rf, weight=1.0)
        assert len(ensemble.models) == 1

    def test_train_ensemble(self, synthetic_dataset):
        X_train, y_train, X_val, y_val = synthetic_dataset

        rf = RandomForestIDS(n_estimators=5, max_depth=3)
        xgb_m = XGBoostIDS(n_estimators=5, max_depth=3)

        ensemble = EnsembleIDS(voting="soft")
        ensemble.add_model(rf, weight=0.5)
        ensemble.add_model(xgb_m, weight=0.5)

        metrics = ensemble.train(X_train, y_train, X_val, y_val)

        assert ensemble.is_trained
        assert "accuracy" in metrics
        assert 0.0 <= metrics["accuracy"] <= 1.0
