import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, GridSearchCV, cross_val_score
from sklearn.preprocessing import StandardScaler, RobustScaler
from sklearn.metrics import (
    classification_report, 
    confusion_matrix, 
    roc_auc_score, 
    roc_curve,
    precision_recall_curve
)
import joblib
import logging
from typing import Tuple, Dict, List
from datetime import datetime
import json
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EnhancedSafetyClassifier:
    """
    Advanced Safety Classifier with proper ML practices
    
    Features:
    - Multi-class classification (Very Safe, Safe, Moderate, Unsafe, Very Unsafe)
    - Proper feature engineering and scaling
    - Cross-validation and hyperparameter tuning
    - Feature importance tracking
    - Model versioning
    - Comprehensive metrics
    """
    
    def __init__(self, model_path: str = None):
        if model_path is None:
             self.model_path = os.path.join(Path(__file__).parent.parent, "models") + os.sep
        else:
             self.model_path = model_path
             
        self.model = None
        self.scaler = RobustScaler()  # Better for outliers than StandardScaler
        self.feature_names = [
            'lighting', 'patrol_frequency', 
            'traffic_density', 'police_proximity', 'hospital_proximity',
            # NEW FEATURES:
            'time_of_day', 'day_of_week', 'is_weekend',
            'population_density', 'commercial_area', 'residential_area',
            'street_width', 'cctv_coverage', 'emergency_response_time'
        ]
        self.safety_classes = {
            0: 'Very Unsafe',
            1: 'Unsafe', 
            2: 'Moderate',
            3: 'Safe',
            4: 'Very Safe'
        }
        self.feature_importance_ = None
        self.training_history = []
        
        if not os.path.exists(self.model_path):
            os.makedirs(self.model_path, exist_ok=True)
        
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Advanced feature engineering for safety prediction
        """
        df = df.copy()
        
        # Temporal features
        if 'timestamp' in df.columns:
            df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
            df['time_of_day'] = df['hour'].apply(self._categorize_time)
            df['day_of_week'] = pd.to_datetime(df['timestamp']).dt.dayofweek
            df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
        
        # Fallback if temporal columns missing but needed for feature_names
        for col in ['time_of_day', 'day_of_week', 'is_weekend']:
            if col not in df.columns:
                df[col] = 0
                
        # Fill missing new features with defaults if strictly necessary
        for col in ['population_density', 'commercial_area', 'residential_area', 'street_width', 'cctv_coverage', 'emergency_response_time']:
            if col not in df.columns:
                df[col] = 0.5 # Neutral default

        # Interaction features (important for safety)
        df['safety_infrastructure'] = (
            df.get('lighting', 0) * 0.3 + 
            df.get('patrol_frequency', 0) * 0.4 + 
            df.get('cctv_coverage', 0) * 0.3
        )
        
        df['risk_score'] = (
            (1 / (df.get('police_proximity', 0.1) + 0.1)) * 0.4
        )
        
        # Proximity composite score
        df['emergency_accessibility'] = (
            1 / (df.get('police_proximity', 0.1) + 0.1) * 0.5 +
            1 / (df.get('hospital_proximity', 0.1) + 0.1) * 0.5
        )
        
        # Normalize traffic density impact
        if 'traffic_density' in df.columns:
            df['traffic_safety_factor'] = np.where(
                df['traffic_density'] > 0.7,
                df['traffic_density'] * 0.5,  # High traffic = slower but safer
                df['traffic_density'] * 1.2   # Low traffic = faster but less witnesses
            )
        
        return df
    
    @staticmethod
    def _categorize_time(hour: int) -> int:
        """Categorize hour into time periods"""
        if 6 <= hour < 12:
            return 1  # Morning
        elif 12 <= hour < 18:
            return 2  # Afternoon
        elif 18 <= hour < 22:
            return 3  # Evening
        else:
            return 4  # Night (highest risk)
    
    def create_safety_score(self, features: pd.DataFrame) -> np.ndarray:
        """
        Convert features to safety classes (0-4)
        This is for synthetic data generation or labeling
        """
        # Weighted safety score calculation with defaults (Removing Crime)
        safety_score = (
            features.get('lighting', 0.5) * 0.25 +
            features.get('patrol_frequency', 0.5) * 0.20 +
            features.get('safety_infrastructure', 0.5) * 0.20 +
            features.get('emergency_accessibility', 0.5) * 0.15 +
            (1 - features.get('risk_score', 0.5)) * 0.20
        )
        
        # Convert to classes
        classes = np.zeros(len(safety_score), dtype=int)
        classes[safety_score < 0.2] = 0  # Very Unsafe
        classes[(safety_score >= 0.2) & (safety_score < 0.4)] = 1  # Unsafe
        classes[(safety_score >= 0.4) & (safety_score < 0.6)] = 2  # Moderate
        classes[(safety_score >= 0.6) & (safety_score < 0.8)] = 3  # Safe
        classes[safety_score >= 0.8] = 4  # Very Safe
        
        return classes
    
    def prepare_data(
        self, 
        df: pd.DataFrame, 
        target_column: str = 'safety_class'
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare and validate data for training/prediction
        """
        # Feature engineering
        df = self.engineer_features(df)
        
        # Validate required columns
        # For training, fill any missing columns with defaults to avoid KeyErrors
        for feature in self.feature_names:
            if feature not in df.columns:
                df[feature] = 0.0 # Default fallback
            elif not pd.api.types.is_numeric_dtype(df[feature]):
                df[feature] = df[feature].astype('category').cat.codes.astype(float)
        
        X = df[self.feature_names].to_numpy(dtype=np.float64)
        
        # Handle missing values
        X = np.nan_to_num(X, nan=0.0, posinf=1.0, neginf=0.0)
        
        if target_column in df.columns:
            y = df[target_column].values
            return X, y
        
        return X, None
    
    def train(
        self, 
        X: np.ndarray, 
        y: np.ndarray,
        tune_hyperparameters: bool = True,
        cv_folds: int = 5
    ) -> Dict:
        """
        Train the model with proper validation and hyperparameter tuning
        """
        logger.info("Starting training process...")
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Hyperparameter tuning
        if tune_hyperparameters:
            logger.info("Performing hyperparameter tuning...")
            param_grid = {
                'n_estimators': [100, 200, 300],
                'max_depth': [10, 20, 30, None],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4],
                'max_features': ['sqrt', 'log2'],
                'class_weight': ['balanced', 'balanced_subsample']
            }
            
            base_model = RandomForestClassifier(random_state=42, n_jobs=-1)
            # Reduce CV folds if not enough samples
            actual_cv = min(cv_folds, 3) 
            grid_search = GridSearchCV(
                base_model, 
                param_grid, 
                cv=actual_cv, 
                scoring='f1_weighted',
                n_jobs=-1,
                verbose=1
            )
            
            grid_search.fit(X_train_scaled, y_train)
            self.model = grid_search.best_estimator_
            best_params = grid_search.best_params_
            logger.info(f"Best parameters: {best_params}")
        else:
            # Use default optimized parameters
            self.model = RandomForestClassifier(
                n_estimators=200,
                max_depth=20,
                min_samples_split=5,
                min_samples_leaf=2,
                max_features='sqrt',
                class_weight='balanced',
                random_state=42,
                n_jobs=-1
            )
            self.model.fit(X_train_scaled, y_train)
            best_params = self.model.get_params()
        
        # Cross-validation
        actual_cv = min(cv_folds, 3)
        cv_scores = cross_val_score(
            self.model, X_train_scaled, y_train, 
            cv=actual_cv, scoring='f1_weighted'
        )
        
        # Predictions
        y_pred = self.model.predict(X_test_scaled)
        y_pred_proba = self.model.predict_proba(X_test_scaled)
        
        # Calculate metrics
        metrics = self._calculate_metrics(y_test, y_pred, y_pred_proba)
        metrics['cv_scores'] = cv_scores.tolist()
        metrics['cv_mean'] = cv_scores.mean()
        metrics['cv_std'] = cv_scores.std()
        metrics['best_params'] = best_params
        
        # Feature importance
        self.feature_importance_ = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        # Store training history
        training_record = {
            'timestamp': datetime.now().isoformat(),
            'metrics': metrics,
            'feature_importance': self.feature_importance_.to_dict('records')
        }
        self.training_history.append(training_record)
        
        logger.info(f"Training complete. F1-Score: {metrics['f1_weighted']:.4f}")
        
        return metrics
    
    def _calculate_metrics(
        self, 
        y_true: np.ndarray, 
        y_pred: np.ndarray,
        y_pred_proba: np.ndarray
    ) -> Dict:
        """Calculate comprehensive evaluation metrics"""
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score, 
            f1_score, cohen_kappa_score
        )
        
        metrics = {
            'accuracy': float(accuracy_score(y_true, y_pred)),
            'precision_weighted': float(precision_score(y_true, y_pred, average='weighted', zero_division=0)),
            'recall_weighted': float(recall_score(y_true, y_pred, average='weighted', zero_division=0)),
            'f1_weighted': float(f1_score(y_true, y_pred, average='weighted', zero_division=0)),
            'cohen_kappa': float(cohen_kappa_score(y_true, y_pred)),
            'confusion_matrix': confusion_matrix(y_true, y_pred).tolist(),
            'classification_report': classification_report(
                y_true, y_pred, 
                output_dict=True,
                zero_division=0
            )
        }
        
        # ROC-AUC for multi-class
        try:
            metrics['roc_auc_ovr'] = float(roc_auc_score(
                y_true, y_pred_proba, 
                multi_class='ovr', 
                average='weighted'
            ))
        except Exception as e:
            logger.warning(f"Could not calculate ROC-AUC: {e}")
            metrics['roc_auc_ovr'] = None
        
        return metrics
    
    def predict(self, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Make predictions with confidence scores
        
        Returns:
            predictions: Class predictions (0-4)
            probabilities: Confidence probabilities for each class
        """
        if self.model is None:
            if not self.load_model():
                raise ValueError("Model not trained and could not load saved model. Call train() first.")
        
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        raw_probs = self.model.predict_proba(X_scaled)
        
        num_classes = len(self.safety_classes)
        probabilities = np.zeros((len(X), num_classes), dtype=float)
        if hasattr(self.model, "classes_"):
            for idx, cls_label in enumerate(self.model.classes_):
                if 0 <= cls_label < num_classes:
                    probabilities[:, cls_label] = raw_probs[:, idx]
        else:
            probabilities = raw_probs
        
        return predictions, probabilities
    
    def predict_safety_score(self, X: np.ndarray) -> np.ndarray:
        """
        Convert class predictions to 0-100 safety score
        """
        predictions, probabilities = self.predict(X)
        class_values = np.array([0, 25, 50, 75, 100])
        safety_scores = np.sum(probabilities * class_values, axis=1)
        return safety_scores
    
    def save_model(self, version: str = None):
        """Save model with versioning"""
        if version is None:
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'safety_classes': self.safety_classes,
            'feature_importance': self.feature_importance_,
            'training_history': self.training_history,
            'version': version
        }
        
        model_file = f"{self.model_path}safety_classifier_v{version}.pkl"
        joblib.dump(model_data, model_file)
        
        # Save metadata
        metadata_file = f"{self.model_path}safety_classifier_v{version}_metadata.json"
        metadata = {
            'version': version,
            'timestamp': datetime.now().isoformat(),
            'feature_names': self.feature_names,
            'training_history': [
                {k: v for k, v in h.items() if k != 'confusion_matrix'} 
                for h in self.training_history
            ]
        }
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        
        logger.info(f"Model saved: {model_file}")
        
        return model_file
    
    def load_model(self, version: str = 'latest'):
        """Load model with version support"""
        import glob
        
        if version == 'latest':
            model_files = glob.glob(f"{self.model_path}safety_classifier_v*.pkl")
            if not model_files:
                 # Be tolerant if no enhanced model exists, allow training fresh
                logger.warning("No enhanced model files found.")
                return False
            model_file = max(model_files)  # Latest by filename
        else:
            model_file = f"{self.model_path}safety_classifier_v{version}.pkl"
            if not os.path.exists(model_file):
                return False
        
        try:
            model_data = joblib.load(model_file)
            
            self.model = model_data['model']
            self.scaler = model_data['scaler']
            self.feature_names = model_data['feature_names']
            self.safety_classes = model_data['safety_classes']
            self.feature_importance_ = model_data.get('feature_importance')
            self.training_history = model_data.get('training_history', [])
            
            logger.info(f"Model loaded: {model_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to load model {model_file}: {e}")
            return False
    
    def get_feature_importance(self) -> pd.DataFrame:
        """Get feature importance rankings"""
        if self.feature_importance_ is None:
             # Return empty dataframe if no model
             return pd.DataFrame(columns=['feature', 'importance'])
        return self.feature_importance_
