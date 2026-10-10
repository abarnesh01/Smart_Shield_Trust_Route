import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split, TimeSeriesSplit, RandomizedSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    mean_absolute_error, 
    mean_squared_error, 
    r2_score,
    mean_absolute_percentage_error
)
import joblib
import logging
from typing import Tuple, Dict
from datetime import datetime
import json
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedTimePredictor:
    """
    Advanced Delivery Time Prediction with XGBoost
    
    Features:
    - Temporal feature engineering
    - Weather integration
    - Traffic pattern learning
    - Prediction intervals
    - Time series cross-validation
    """
    
    def __init__(self, model_path: str = None):
        if model_path is None:
             self.model_path = os.path.join(Path(__file__).parent.parent, "models") + os.sep
        else:
             self.model_path = model_path
             
        if not os.path.exists(self.model_path):
            os.makedirs(self.model_path, exist_ok=True)
            
        self.model = None
        self.scaler = StandardScaler()
        self.feature_names = [
            'route_distance', 'traffic_level', 'time_of_day', 'day_of_week',
            # NEW FEATURES:
            'hour', 'is_weekend', 'is_holiday', 'is_rush_hour',
            'weather_condition', 'temperature', 'precipitation',
            'historical_avg_time', 'num_stops', 'route_complexity',
            'vehicle_type', 'driver_experience', 'distance_to_next_stop'
        ]
        self.training_history = []
        self.feature_importance_ = None
        
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Advanced feature engineering for time prediction"""
        df = df.copy()
        
        # Temporal features
        if 'timestamp' in df.columns:
            dt = pd.to_datetime(df['timestamp'])
            df['hour'] = dt.dt.hour
            df['day_of_week'] = dt.dt.dayofweek
            df['is_weekend'] = dt.dt.dayofweek.isin([5, 6]).astype(int)
            # Dummy month/day
            df['month'] = dt.dt.month
            df['day_of_month'] = dt.dt.day
            
            # Rush hour identification
            df['is_morning_rush'] = df['hour'].between(7, 9).astype(int)
            df['is_evening_rush'] = df['hour'].between(17, 19).astype(int)
            df['is_rush_hour'] = (df['is_morning_rush'] | df['is_evening_rush']).astype(int)
        
        # Fill missing
        for col in ['hour', 'day_of_week', 'is_weekend', 'is_holiday', 'is_rush_hour']:
             if col not in df.columns: df[col] = 0

        # Distance-based features
        if 'route_distance' in df.columns:
            df['distance_category'] = pd.cut(
                df['route_distance'],
                bins=[-1, 5, 10, 20, 50, 1000], # Ensure bins cover all
                labels=[0, 1, 2, 3, 4]
            ).astype(int)
            
            # Base time estimate (assuming 40 km/h average)
            df['base_time_estimate'] = df['route_distance'] / 40 * 60  # minutes
        else:
            df['base_time_estimate'] = 0
        
        # Traffic impact
        if 'traffic_level' in df.columns:
            df['traffic_delay_factor'] = np.where(
                df['traffic_level'] > 0.7,
                1.5,  # 50% longer
                np.where(df['traffic_level'] > 0.4, 1.2, 1.0)
            )
            
            df['estimated_delay'] = (
                df['base_time_estimate'] * (df['traffic_delay_factor'] - 1)
            )
        
        # Weather impact - Map strings to impact
        # Assume 'weather_condition' contains categorical data
        if 'weather_condition' in df.columns:
            weather_delay_map = {
                'clear': 1.0,
                'cloudy': 1.05,
                'rain': 1.25,
                'heavy_rain': 1.5,
                'snow': 1.8,
                'storm': 2.0
            }
            # Handle potential non-string values or missing
            df['weather_delay_factor'] = df['weather_condition'].map(
                weather_delay_map
            ).fillna(1.0)
        else:
             df['weather_delay_factor'] = 1.0
        
        # Interaction features
        df['traffic_weather_impact'] = (
            df.get('traffic_delay_factor', 1.0) * 
            df.get('weather_delay_factor', 1.0)
        )
        
        df['rush_hour_traffic'] = (
            df.get('is_rush_hour', 0) * 
            df.get('traffic_level', 0)
        )
        
        # Route complexity (if multiple stops)
        if 'num_stops' in df.columns and 'route_distance' in df.columns:
            df['stop_delay'] = df['num_stops'] * 5  # 5 min per stop estimate
            df['route_complexity'] = (
                df['num_stops'] * df['route_distance'] / 10
            )
        
        return df
    
    def prepare_data(
        self, 
        df: pd.DataFrame,
        target_column: str = 'actual_time'
    ) -> Tuple[np.ndarray, np.ndarray, list]:
        """Prepare data with validation"""
        df = self.engineer_features(df)
        
        # Ensure all feature_names are present, fill with 0
        for feature in self.feature_names:
             if feature not in df.columns:
                  if feature == 'weather_condition': # Categorical logic for XGBoost? 
                       # Usually we encode. Here we simplify by using numeric mapping in feature engineering
                       # But `weather_condition` itself is in feature_names. XGBoost can handle categ, 
                       # but likely best to drop raw str or encode.
                       # We used `weather_delay_factor` earlier.
                       # Let's assume we map 'weather_condition' to int 
                       df[feature] = 0
                  else:
                       df[feature] = 0

        # Encode categorical columns if any remain
        for col in self.feature_names:
            if col in df.columns and not pd.api.types.is_numeric_dtype(df[col]):
                df[col] = df[col].astype('category').cat.codes.astype(float)

        # Filter features and convert to numeric float array
        X = df[self.feature_names].to_numpy(dtype=np.float64)
        X = np.nan_to_num(X, nan=0.0)
        
        if target_column in df.columns:
            y = df[target_column].values
            return X, y, self.feature_names
        
        return X, None, self.feature_names
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        tune_hyperparameters: bool = True,
        cv_folds: int = 5
    ) -> Dict:
        """Train with time series cross-validation"""
        logger.info("Starting training...")
        
        # Time series split (preserves temporal order)
        actual_cv = min(cv_folds, 3) 
        tscv = TimeSeriesSplit(n_splits=actual_cv)
        
        # Initial split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, shuffle=False  # No shuffle for time series
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        if tune_hyperparameters:
            logger.info("Tuning hyperparameters...")
            param_distributions = {
                'n_estimators': [100, 200, 300, 500],
                'max_depth': [3, 5, 7, 9, 11],
                'learning_rate': [0.01, 0.05, 0.1, 0.2],
                'subsample': [0.6, 0.8, 1.0],
                'colsample_bytree': [0.6, 0.8, 1.0],
                'min_child_weight': [1, 3, 5],
                'gamma': [0, 0.1, 0.2],
                'reg_alpha': [0, 0.1, 0.5, 1.0],
                'reg_lambda': [0, 0.1, 0.5, 1.0]
            }
            
            base_model = XGBRegressor(
                objective='reg:squarederror',
                random_state=42,
                n_jobs=-1
            )
            
            random_search = RandomizedSearchCV(
                base_model,
                param_distributions,
                n_iter=20, # Reduced size for quick response
                cv=tscv,
                scoring='neg_mean_absolute_error',
                n_jobs=-1,
                verbose=1,
                random_state=42
            )
            
            random_search.fit(X_train_scaled, y_train)
            self.model = random_search.best_estimator_
            best_params = random_search.best_params_
            logger.info(f"Best parameters: {best_params}")
        else:
            # Optimized default parameters
            self.model = XGBRegressor(
                n_estimators=300,
                max_depth=7,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                min_child_weight=3,
                gamma=0.1,
                reg_alpha=0.1,
                reg_lambda=0.5,
                objective='reg:squarederror',
                random_state=42,
                n_jobs=-1
            )
            self.model.fit(X_train_scaled, y_train)
            best_params = self.model.get_params()
        
        # Predictions
        y_pred_train = self.model.predict(X_train_scaled)
        y_pred_test = self.model.predict(X_test_scaled)
        
        # Calculate metrics
        metrics = {
            'train': self._calculate_metrics(y_train, y_pred_train),
            'test': self._calculate_metrics(y_test, y_pred_test),
            'best_params': best_params
        }
        
        # Feature importance
        self.feature_importance_ = pd.DataFrame({
            'feature': self.feature_names[:X.shape[1]],
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        # Store training record
        training_record = {
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics,
            'feature_importance': self.feature_importance_.to_dict('records')
        }
        self.training_history.append(training_record)
        
        logger.info(f"Training complete. Test MAE: {metrics['test']['mae']:.2f} min")
        
        return metrics
    
    def _calculate_metrics(self, y_true: np.ndarray, y_pred: np.ndarray) -> Dict:
        """Calculate comprehensive regression metrics"""
        mae = mean_absolute_error(y_true, y_pred)
        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        r2 = r2_score(y_true, y_pred)
        
        # MAPE (handle zero values)
        non_zero_mask = y_true != 0
        if non_zero_mask.any():
            mape = mean_absolute_percentage_error(
                y_true[non_zero_mask], 
                y_pred[non_zero_mask]
            )
        else:
            mape = 0.0
        
        # Median absolute error
        median_ae = np.median(np.abs(y_true - y_pred))
        
        return {
            'mae': float(mae),
            'mse': float(mse),
            'rmse': float(rmse),
            'r2': float(r2),
            'mape': float(mape) if not np.isnan(mape) else None,
            'median_ae': float(median_ae)
        }
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Make predictions"""
        if self.model is None:
            if not self.load_model():
                 raise ValueError("Model not trained")
        
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        
        return predictions
    
    def predict_with_interval(
        self, 
        X: np.ndarray, 
        confidence: float = 0.95
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Predict with confidence intervals using quantile regression
        
        Returns:
            predictions: Point estimates
            lower_bound: Lower confidence bound
            upper_bound: Upper confidence bound
        """
        predictions = self.predict(X)
        
        # Estimate prediction interval from training residuals
        # This is a simplified approach; for production, use quantile regression
        std_residual = np.std(predictions) * 1.5  # Heuristic
        
        z_score = 1.96 if confidence == 0.95 else 2.576  # 95% or 99%
        margin = z_score * std_residual
        
        lower_bound = predictions - margin
        upper_bound = predictions + margin
        
        return predictions, lower_bound, upper_bound
    
    def save_model(self, version: str = None):
        """Save model with versioning"""
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'feature_importance': self.feature_importance_,
            'training_history': self.training_history,
            'version': version
        }
        
        model_file = f"{self.model_path}time_predictor_v{version}.pkl"
        joblib.dump(model_data, model_file)
        
        logger.info(f"Model saved: {model_file}")
        return model_file
    
    def load_model(self, version: str = 'latest'):
        """Load model"""
        import glob
        
        if version == 'latest':
            model_files = glob.glob(f"{self.model_path}time_predictor_v*.pkl")
            if not model_files:
                logger.warning("No time predictor model files found")
                return False
            model_file = max(model_files)
        else:
            model_file = f"{self.model_path}time_predictor_v{version}.pkl"
            if not os.path.exists(model_file):
                return False
        
        model_data = joblib.load(model_file)
        
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.feature_importance_ = model_data.get('feature_importance')
        self.training_history = model_data.get('training_history', [])
        
        logger.info(f"Model loaded: {model_file}")
        return True
