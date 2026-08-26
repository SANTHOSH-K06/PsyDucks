"""
train_model.py
Train a Machine Learning Model on the Patient Clinical Dataset.
Predicts Patient Readmission Risk and Length of Stay using Scikit-Learn.
Generates evaluation metrics and serializes the model to disk.
"""

import os
import joblib
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, classification_report

def train_and_save_models(csv_path: str = "data/patient_dataset.csv", model_output_path: str = "data/triage_ml_model.pkl"):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset file not found at: {csv_path}")

    print(f"Loading patient dataset from: {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"Dataset loaded successfully with {len(df)} records.")

    # Data Cleaning & Feature Preparation
    df['Readmission_Label'] = df['Readmission'].map({'Yes': 1, 'No': 0})
    
    # Feature columns
    feature_cols = ['Age', 'Gender', 'Condition', 'Procedure', 'Cost', 'Length_of_Stay']
    X = df[feature_cols]
    y = df['Readmission_Label']

    categorical_cols = ['Gender', 'Condition', 'Procedure']
    numeric_cols = ['Age', 'Cost', 'Length_of_Stay']

    # Define Preprocessor
    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), numeric_cols),
            ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False), categorical_cols)
        ]
    )

    # Split dataset into Train and Test sets
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("\nTraining Random Forest Classifier for Readmission Risk...")
    rf_pipeline = Pipeline([
        ('preprocessor', preprocessor),
        ('classifier', RandomForestClassifier(n_estimators=100, random_state=42, max_depth=6))
    ])

    rf_pipeline.fit(X_train, y_train)
    y_pred = rf_pipeline.predict(X_test)
    y_prob = rf_pipeline.predict_proba(X_test)[:, 1]

    # Calculate Evaluation Metrics
    acc = accuracy_score(y_test, y_pred)
    prec = precision_score(y_test, y_pred, zero_division=0)
    rec = recall_score(y_test, y_pred, zero_division=0)
    f1 = f1_score(y_test, y_pred, zero_division=0)
    auc = roc_auc_score(y_test, y_prob)

    print("\n=== MODEL EVALUATION METRICS ===")
    print(f"Accuracy : {acc:.4f} ({acc*100:.2f}%)")
    print(f"Precision: {prec:.4f}")
    print(f"Recall   : {rec:.4f}")
    print(f"F1-Score : {f1:.4f}")
    print(f"ROC-AUC  : {auc:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=['No Readmission', 'Readmission']))

    # Feature Importances
    ohe_feature_names = rf_pipeline.named_steps['preprocessor'].named_transformers_['cat'].get_feature_names_out(categorical_cols)
    all_feature_names = list(numeric_cols) + list(ohe_feature_names)
    importances = rf_pipeline.named_steps['classifier'].feature_importances_

    feature_imp_df = pd.DataFrame({
        'feature': all_feature_names,
        'importance': importances
    }).sort_values(by='importance', ascending=False)

    print("\nTop 5 Most Important Features for Risk Prediction:")
    print(feature_imp_df.head(5).to_string(index=False))

    # Save Model Artifacts
    model_data = {
        'pipeline': rf_pipeline,
        'metrics': {
            'accuracy': float(acc),
            'precision': float(prec),
            'recall': float(rec),
            'f1_score': float(f1),
            'roc_auc': float(auc),
            'dataset_size': len(df),
            'test_size': len(y_test)
        },
        'feature_importances': feature_imp_df.to_dict(orient='records'),
        'trained_at': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    os.makedirs(os.path.dirname(model_output_path), exist_ok=True)
    joblib.dump(model_data, model_output_path)
    print(f"\nTrained ML Model and metrics successfully saved to: {model_output_path}")

    return model_data

if __name__ == "__main__":
    train_and_save_models()
