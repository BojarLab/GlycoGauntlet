import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path
from evaluate_submission import evaluate_predictions

def evaluate_local(submission_dir, test_dir, output_file=None):
  test_files = [f for f in os.listdir(test_dir) if f.endswith('.csv') and '_solution' in f]
  results = {}
  for test_file in test_files:
    submission_file = test_file.replace('_solution.csv', '_submission.csv')
    submission_path = os.path.join(submission_dir, submission_file)
    if not os.path.exists(submission_path):
      print(f"Warning: Missing submission file {submission_file}")
      continue
    predictions = pd.read_csv(submission_path)
    gt = pd.read_csv(os.path.join(test_dir, test_file))
    rt_col = 'RT' if 'RT' in gt.columns else test_file.split('.')[0] + '_RT'
    gt_filtered = gt[gt['glycan'].notna()]
    f1, precision, recall, peaks_not_picked, incorrect, tp, fp, fn = evaluate_predictions(predictions, gt_filtered, rt_col)
    results[test_file] = {'F1': f1, 'Precision': precision, 'Recall': recall, 'TP': tp, 'FP': fp, 'FN': fn}
    print(f"{test_file}: F1={f1:.4f}, Precision={precision:.4f}, Recall={recall:.4f}, TP={tp:.1f}, FP={fp}, FN={fn:.1f}")
  avg_f1 = np.mean([r['F1'] for r in results.values()])
  print(f"\nAverage F1: {avg_f1:.4f}")
  if output_file:
    with open(output_file, 'w') as f:
      f.write(f"Private Test Evaluation\n")
      f.write(f"Average F1: {avg_f1:.4f}\n\n")
      for test_file, metrics in results.items():
        f.write(f"{test_file}: F1={metrics['F1']:.4f}\n")
  return avg_f1, results

if __name__ == "__main__":
  if len(sys.argv) < 3:
    print("Usage: python evaluate_local.py <submission_directory> <private_test_directory> [output_file]")
    sys.exit(1)
  output = sys.argv[3] if len(sys.argv) > 3 else None
  evaluate_local(sys.argv[1], sys.argv[2], output)
