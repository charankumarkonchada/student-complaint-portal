"""Machine Learning module for IntelliHostel.
Provides complaint categorization, priority prediction, resolution estimation,
and duplicate issue detection.
"""
from ml.ml_engine import predict_complaint, find_duplicate

__all__ = ["predict_complaint", "find_duplicate"]
