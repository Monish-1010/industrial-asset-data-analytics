"""Rebuild the entire synthetic portfolio case study from a fixed seed."""
from pathlib import Path
from src.pipeline import run_pipeline

if __name__ == "__main__":
    metrics = run_pipeline(Path(__file__).resolve().parent)
    print("Synthetic industrial asset analysis complete.")
    for key, value in metrics.items():
        print(f"{key}: {value}")
