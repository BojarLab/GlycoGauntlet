import pandas as pd
import sys
import os
from pathlib import Path

def validate_submission(submission_dir, test_dir="data/public_test"):
  test_files = [f.replace("_solution", "_submission") for f in os.listdir(test_dir) if f.endswith('.csv')]
  submission_files = [f for f in os.listdir(submission_dir) if f.endswith('.csv')]
  errors = []
  if set(test_files) != set(submission_files):
    missing = set(test_files) - set(submission_files)
    extra = set(submission_files) - set(test_files)
    if missing:
      errors.append(f"Missing predictions for: {missing}")
    if extra:
      errors.append(f"Extra files not in test set: {extra}")
  for filename in submission_files:
    filepath = os.path.join(submission_dir, filename)
    try:
      df = pd.read_excel(filepath)
    except Exception as e:
      errors.append(f"{filename}: Cannot read Excel file - {e}")
      continue
    required_cols = ['m/z', 'RT', 'charge', 'top1_pred']
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
      errors.append(f"{filename}: Missing required columns: {missing_cols}")
      continue
    if not pd.api.types.is_numeric_dtype(df['m/z']):
      errors.append(f"{filename}: m/z must be numeric")
    if not pd.api.types.is_numeric_dtype(df['RT']):
      errors.append(f"{filename}: RT must be numeric")
    if not pd.api.types.is_integer_dtype(df['charge']):
      errors.append(f"{filename}: charge must be integer")
    if df['top1_pred'].isna().all():
      errors.append(f"{filename}: top1_pred column is empty")
    if len(df) == 0:
      errors.append(f"{filename}: File is empty")
  if errors:
    print("VALIDATION FAILED:\n")
    for error in errors:
      print(f"  ❌ {error}")
    sys.exit(1)
  else:
    print(f"✓ All {len(submission_files)} files validated successfully")
    sys.exit(0)

if __name__ == "__main__":
  if len(sys.argv) != 2:
    print("Usage: python check_format.py <submission_directory>")
    sys.exit(1)
  validate_submission(sys.argv[1])
