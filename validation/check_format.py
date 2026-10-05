import pandas as pd
import sys
import os
from pathlib import Path
import xml.etree.ElementTree as ET
from glycowork.motif.processing import canonicalize_iupac
from glycowork.motif.tokenization import glycan_to_mass
from glycowork.motif.graph import glycan_to_nxGraph

def parse_gwp(file_obj):
  tree = ET.parse(file_obj)
  rows = []
  for scan in tree.getroot().iter('Scan'):
    name = scan.get('name', '')
    if '@' not in name:
      continue
    mz_str, rt_str = name.split('@', 1)
    try:
      mz, rt = float(mz_str), float(rt_str)
    except ValueError:
      continue
    for glycan in scan.iter('Glycan'):
      raw = glycan.get('structure', '')
      if not raw:
        continue
      try:
        iupac = canonicalize_iupac(raw)
      except Exception:
        iupac = raw
      charge = -1
      try:
        neutral = glycan_to_mass(iupac) + 1.00728
        best, best_diff = -1, float('inf')
        for n in [1, 2, 3]:
          diff = abs(mz * n + n * 1.00728 - neutral)
          if diff < best_diff:
            best_diff, best = diff, n
        charge = -best
      except Exception:
        pass
      rows.append({'m/z': mz, 'RT': rt, 'charge': charge, 'top1_pred': iupac})
      break
  return pd.DataFrame(rows)

def expected_submission_files(test_dir):
  return {f.replace('_solution.csv', '').replace('.xlsx', '') + '_submission.csv' for f in os.listdir(test_dir) if f.endswith('_solution.csv') or f.endswith('.xlsx')}

def validate_df(df, filename):
  errors = []
  required_cols = ['m/z', 'RT', 'charge', 'top1_pred']
  missing_cols = [col for col in required_cols if col not in df.columns.tolist()]
  if missing_cols:
    return [f"{filename}: Missing required columns: {missing_cols}"]
  if len(df) == 0:
    return [f"{filename}: File is empty"]
  if not pd.api.types.is_numeric_dtype(df['m/z']):
    errors.append(f"{filename}: m/z must be numeric")
  if not pd.api.types.is_numeric_dtype(df['RT']):
    errors.append(f"{filename}: RT must be numeric")
  if not pd.api.types.is_integer_dtype(df['charge']):
    errors.append(f"{filename}: charge must be integer")
  if df['top1_pred'].isna().all():
    errors.append(f"{filename}: top1_pred column is empty")
  unparseable = []
  for glycan in df['top1_pred'].dropna().astype(str).unique():
    try:
      glycan_to_nxGraph(canonicalize_iupac(glycan))
    except Exception:
      unparseable.append(f"row {df.index[df['top1_pred'].astype(str) == glycan][0] + 2}: '{glycan}'")
  if unparseable:
    errors.append(f"{filename}: {len(unparseable)} unparseable glycan(s) in top1_pred, e.g. {'; '.join(unparseable[:5])}")
  return errors

def validate_submission(submission_dir, test_dir=None):
  test_dir = test_dir or ('data/private_test' if Path(submission_dir).name == 'private' else 'data/public_test')
  test_files = expected_submission_files(test_dir)
  submission_files = [f for f in os.listdir(submission_dir) if f.endswith('.csv')]
  errors = []
  extra = set(submission_files) - set(test_files)
  if extra:
    errors.append(f"Extra files not in test set: {extra}")
  missing = set(test_files) - set(submission_files)
  if missing:
    print(f"⚠️ Warning: Partial submission - missing predictions for: {missing}")
  for filename in submission_files:
    filepath = os.path.join(submission_dir, filename)
    try:
      df = pd.read_csv(filepath, encoding='utf-8-sig')
    except Exception as e:
      errors.append(f"{filename}: Cannot read CSV file - {e}")
      continue
    errors.extend(validate_df(df, filename))
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
