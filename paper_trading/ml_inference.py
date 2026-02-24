"""
Simple ML inference wrapper used by paper trading orchestrator.
Provides a small stable API around a sklearn-style classifier with predict_proba.
"""
from typing import Optional
import os
import pandas as pd

try:
    import joblib
except Exception:
    joblib = None


class MLInference:
    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.feature_names = None
        if model_path:
            self.load_model(model_path)

    def load_model(self, model_path: str):
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found: {model_path}")
        if joblib:
            self.model = joblib.load(model_path)
        else:
            import pickle
            with open(model_path, 'rb') as f:
                self.model = pickle.load(f)
        # Attempt to load metadata.json in same directory to know expected features
        meta_path = os.path.join(os.path.dirname(model_path), 'metadata.json')
        if os.path.exists(meta_path):
            try:
                import json
                with open(meta_path, 'r') as mf:
                    meta = json.load(mf)
                self.feature_names = meta.get('features')
            except Exception:
                self.feature_names = None
        # Fallback to sklearn attribute if available
        if self.feature_names is None:
            try:
                self.feature_names = list(getattr(self.model, 'feature_names_in_', [])) or None
            except Exception:
                self.feature_names = None

        # Runtime PSI gating: if monitoring is available, run a quick PSI check
        try:
            from monitoring.psi import run_model_psi_check
            model_dir = os.path.dirname(model_path)
            res = run_model_psi_check(model_dir)
            if isinstance(res, dict) and res.get('overall_status') == 'ALERT':
                # Send alert and prevent model from being used in runtime
                try:
                    from monitoring.alerts import send_telegram_alert
                    send_telegram_alert(f"Runtime model load gated due to PSI ALERT: {model_dir}")
                except Exception:
                    pass
                raise RuntimeError(f"Model gated due to PSI ALERT: {model_dir}")
        except RuntimeError:
            raise
        except Exception:
            # If monitoring not available or fails, do not block model load
            pass

    def predict_score(self, df_row: pd.DataFrame) -> float:
        """
        Accepts a single-row DataFrame with columns matching training features.
        Returns a float probability in [0,1].
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        # Ensure input is DataFrame with shape (1, n_features)
        if isinstance(df_row, pd.Series):
            df_row = df_row.to_frame().T

        # If we know expected feature names, select/reorder them and fill missing with 0
        X = df_row
        if self.feature_names:
            # Create a DataFrame with exactly the expected columns
            cols = list(self.feature_names)
            # If any expected column missing, add with zeros
            missing = [c for c in cols if c not in X.columns]
            if missing:
                for c in missing:
                    X[c] = 0
            # Select in the original training order
            X = X[cols]
        else:
            # If we don't know expected features, try to let the model handle it
            X = df_row

        try:
            prob = self.model.predict_proba(X)[:, 1][0]
        except Exception:
            # Fallback: use predict and map {0->0.0,1->1.0}
            p = self.model.predict(X)[0]
            prob = float(p)

        # Clip to [0,1]
        return max(0.0, min(1.0, float(prob)))
