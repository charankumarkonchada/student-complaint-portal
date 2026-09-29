# Training Data Directory

This directory contains datasets used by the IntelliHostel machine learning engine (`ml/ml_engine.py`).

## Files
- `training_data.csv`: Synthetic historical complaint dataset used to train:
  1. **Category Classification Model** (Logistic Regression + TF-IDF)
  2. **Priority Classification Model** (Logistic Regression + TF-IDF)
  3. **Resolution Time Estimation Model** (Ridge Regression + TF-IDF)
  4. **Duplicate Detection Corpus** (Cosine similarity on TF-IDF vectors)

## Dataset Schema
| Column Name | Data Type | Description | Example |
|-------------|-----------|-------------|---------|
| `title` | Text | Short summary of student issue | "Water tap leaking in washroom" |
| `description` | Text | Detailed explanation of complaint | "Continuous water leakage from tap 2" |
| `category` | Text | Maintenance category | "Plumbing", "Electrical", "WiFi" |
| `priority` | Text | Urgency level | "Low", "Medium", "High" |
| `resolution_days` | Float | Historical turnaround time in days | 1.5 |
