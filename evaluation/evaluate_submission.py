import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path
from scipy.spatial.distance import cosine
from scipy.optimize import linear_sum_assignment
from glycowork.motif.processing import canonicalize_iupac
from glycowork.motif.graph import compare_glycans, get_possible_topologies, graph_to_string
from glycowork.motif.annotate import annotate_dataset
from glycowork.motif.tokenization import PROTON_MASS

MASS_TOLERANCE = 0.5
RT_TOLERANCE = 1.0

def get_glycan_similarity(glycan1, glycan2):
  fp = annotate_dataset([glycan1, glycan2], feature_set=['known', 'exhaustive', 'terminal'])
  return 1 - cosine(fp.iloc[0].values, fp.iloc[1].values)

def match_spectra(array1, array2, mass_threshold=MASS_TOLERANCE, rt_threshold=RT_TOLERANCE, array1_alt=None, array2_alt=None):
  array1_alt = array1 if array1_alt is None else array1_alt
  array2_alt = array2 if array2_alt is None else array2_alt
  # fmin, so a row without a charge (NaN singly charged equivalent) still matches on its m/z
  mass_diffs = np.fmin(np.abs(array1[:, None, 0] - array2[None, :, 0]), np.abs(array1_alt[:, None, 0] - array2_alt[None, :, 0]))
  rt_diffs = np.abs(array1[:, None, 1] - array2[None, :, 1])
  feasible = (mass_diffs <= mass_threshold) & (rt_diffs <= rt_threshold)
  rows, cols = linear_sum_assignment(np.where(feasible, mass_diffs / mass_threshold + rt_diffs / rt_threshold, 1e6))
  return [(i, j) for i, j in zip(rows, cols) if feasible[i, j]]

def add_pred_column(df_in, col_name, matches, pred_df, rt_col):
  df_in = df_in.copy()
  df_in[col_name] = None
  df_in['in_ground_truth'] = True
  for gt_idx, pred_idx in matches:
    df_in.at[gt_idx, col_name] = pred_df.iloc[pred_idx, :]['top1_pred']
  extra_preds = pred_df[~(pred_df.index.isin([x[1] for x in matches]))][['m/z', 'RT', 'top1_pred']].rename(columns={'top1_pred': col_name, 'RT': rt_col})
  extra_preds['in_ground_truth'] = False
  extra_preds['top1_pred'] = None
  df_in = pd.concat([df_in, extra_preds]).sort_values(['m/z', rt_col])
  return df_in

def evaluate_predictions(predictions, gt, rt_col='RT'):
  predictions = predictions[predictions['top1_pred'].notna()].reset_index(drop=True)
  if len(predictions) == 0:
    return 0.0, 0, 0, 0, 0, 0, 0, 0, 0
  canonical = {g: canonicalize_iupac(g) for g in predictions['top1_pred'].astype(str).unique()}
  predictions['top1_pred'] = predictions['top1_pred'].astype(str).map(canonical)
  if 'charge' not in predictions.columns:
    predictions['charge'] = -1
  gt_charges = gt['charge'] if 'charge' in gt.columns else pd.Series(-1, index=gt.index)
  # Singly charged equivalent of a z-fold charged ion (one proton per extra charge, sign-aware)
  predictions['converted_masses'] = [m_z * abs(charge) - (charge - np.sign(charge)) * PROTON_MASS for m_z, charge in zip(predictions['m/z'], predictions['charge'])]
  pairs = predictions[['m/z', 'RT']].round(2).values
  pairs_converted = predictions[['converted_masses', 'RT']].round(2).values
  gt_pairs = gt.reset_index()[['m/z', rt_col]].round(2).values
  gt_pairs_converted = np.column_stack([[m_z * abs(charge) - (charge - np.sign(charge)) * PROTON_MASS for m_z, charge in zip(gt['m/z'], gt_charges)], gt[rt_col]]).round(2)
  matched_pairs = match_spectra(gt_pairs, pairs, mass_threshold=MASS_TOLERANCE, rt_threshold=RT_TOLERANCE, array1_alt=gt_pairs_converted, array2_alt=pairs_converted)
  merge_df = gt[['m/z', rt_col, 'top1_pred']].reset_index(drop=True)
  new_md = add_pred_column(merge_df, 'batch_pred', matched_pairs, predictions.reset_index(), rt_col)
  similarity_scores = []
  for gt_glycan, pred_glycan in zip(new_md['top1_pred'], new_md['batch_pred']):
    if not (isinstance(gt_glycan, str) and isinstance(pred_glycan, str)):
      similarity_scores.append(0.0)
      continue
    if '{' in gt_glycan:
      possible_structures = [graph_to_string(x) for x in get_possible_topologies(gt_glycan, exhaustive=True)]
      similarity_scores.append(max([1.0 if compare_glycans(p, pred_glycan) else get_glycan_similarity(p, pred_glycan) for p in possible_structures]))
    else:
      if compare_glycans(gt_glycan, pred_glycan):
        similarity_scores.append(1.0)
      else:
        similarity_scores.append(get_glycan_similarity(gt_glycan, pred_glycan))
  new_md['similarity_score'] = similarity_scores
  unevaluable = len(np.where((new_md['in_ground_truth'])&(new_md['top1_pred'].isnull())&(new_md['batch_pred'].notnull()))[0])
  fp = len(np.where((~new_md['in_ground_truth'])&(new_md['batch_pred'].notnull()))[0])
  tp = new_md[new_md['top1_pred'].notnull()]['similarity_score'].sum() + 0.5 * unevaluable
  empty_glycan_not_predicted = len(np.where((new_md['in_ground_truth'])&(new_md['top1_pred'].isnull())&(new_md['batch_pred'].isnull()))[0])
  unevaluable += empty_glycan_not_predicted
  # A GT peak without a structure weighs half both ways: a prediction there earns 0.5 TP, missing it costs 0.5 FN (a miss used to cost nothing)
  fn = (new_md[new_md['top1_pred'].notnull()]['similarity_score'].apply(lambda x: 1-x)).sum() + 0.5 * empty_glycan_not_predicted
  peaks_not_picked = len(np.where((new_md['in_ground_truth'])&(new_md['batch_pred'].isnull()))[0])
  incorrect_predictions = len(np.where((new_md['top1_pred'].notnull()) & (new_md['batch_pred'].notnull()) & (new_md['similarity_score'] < 1.0))[0])
  precision = tp / (tp + fp + 1e-8)
  recall = tp / (tp + fn + 1e-8)
  f1_score = 2 * (precision * recall) / (precision + recall + 1e-8)
  return f1_score, precision, recall, peaks_not_picked, incorrect_predictions, tp, fp, fn, unevaluable

def evaluate_submission(submission_dir, test_dir="data/public_test"):
  test_files = [f for f in os.listdir(test_dir) if f.endswith('.csv') and '_solution' in f]
  results = {}
  for test_file in test_files:
    submission_file = test_file.replace('_solution.csv', '_submission.csv')
    submission_path = os.path.join(submission_dir, submission_file)
    if not os.path.exists(submission_path):
      print(f"Warning: Missing submission file {submission_file}, scored as F1=0")
      results[test_file] = {'F1': 0.0, 'Precision': 0.0, 'Recall': 0.0, 'TP': 0, 'FP': 0, 'FN': 0, 'Unevaluable': 0, 'submitted': False}
      continue
    predictions = pd.read_csv(submission_path, encoding='utf-8-sig')
    gt = pd.read_csv(os.path.join(test_dir, test_file), encoding='utf-8-sig')
    rt_col = 'RT' if 'RT' in gt.columns else test_file.split('.')[0] + '_RT'
    f1, precision, recall, peaks_not_picked, incorrect, tp, fp, fn, unevaluable = evaluate_predictions(predictions, gt, rt_col)
    results[test_file] = {'F1': f1, 'Precision': precision, 'Recall': recall, 'TP': tp, 'FP': fp, 'FN': fn, 'Unevaluable': unevaluable, 'submitted': True}
    print(f"{test_file}: F1={f1:.4f}, Precision={precision:.4f}, Recall={recall:.4f}, TP={tp:.1f}, FP={fp}, FN={fn:.1f}, Unevaluable={unevaluable}")
  if not any(r['submitted'] for r in results.values()):
    print("No matching test files found")
    sys.exit(1)
  avg_f1 = np.mean([r['F1'] for r in results.values()])
  print(f"\n{'=' * 60}")
  print(f"OVERALL F1 SCORE: {avg_f1:.4f}")
  print(f"OVERALL PRECISION: {np.mean([r['Precision'] for r in results.values()]):.4f}")
  print(f"OVERALL RECALL: {np.mean([r['Recall'] for r in results.values()]):.4f}")
  print(f"{'=' * 60}")
  return avg_f1, results

if __name__ == "__main__":
  if len(sys.argv) != 2:
    print("Usage: python evaluate_submission.py <submission_directory>")
    sys.exit(1)
  avg_f1, results = evaluate_submission(sys.argv[1])
