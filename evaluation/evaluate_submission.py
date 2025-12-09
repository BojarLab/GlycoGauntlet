import pandas as pd
import numpy as np
import sys
import os
from pathlib import Path
from scipy.spatial.distance import cosine
from glycowork.motif.graph import compare_glycans, get_possible_topologies, graph_to_string
from glycowork.motif.annotate import annotate_dataset

MASS_TOLERANCE = 0.5
RT_TOLERANCE = 1.0

def get_glycan_similarity(glycan1, glycan2):
  fp = annotate_dataset([glycan1, glycan2], feature_set=['known', 'exhaustive', 'terminal'])
  return 1 - cosine(fp.iloc[0].values, fp.iloc[1].values)

def match_spectra(array1, array2, mass_threshold=MASS_TOLERANCE, rt_threshold=RT_TOLERANCE, array2_alt=None):
  matches = []
  used_predictions = set()
  for i, (mass1, rt1) in enumerate(array1):
    mass_diffs = np.abs(array2[:, 0] - mass1)
    potential_matches = np.where(mass_diffs <= mass_threshold)[0]
    if array2_alt is not None:
      mass_diffs_alt = np.abs(array2_alt[:, 0] - mass1)
      potential_alt = np.where(mass_diffs_alt <= mass_threshold)[0]
      potential_matches = list(set(list(potential_matches) + list(potential_alt)))
    potential_matches = [j for j in potential_matches if j not in used_predictions]
    if len(potential_matches) == 0:
      continue
    if len(potential_matches) == 1:
      j = potential_matches[0]
      if abs(rt1 - array2[j, 1]) <= rt_threshold:
        matches.append((i, j))
        used_predictions.add(j)
    else:
      rt_diffs = np.abs(array2[potential_matches, 1] - rt1)
      best_match = potential_matches[np.argmin(rt_diffs)]
      if rt_diffs[np.argmin(rt_diffs)] <= rt_threshold:
        matches.append((i, best_match))
        used_predictions.add(best_match)
  return matches

def add_pred_column(df_in, col_name, matches, pred_df, rt_col):
  df_in = df_in.copy()
  df_in[col_name] = None
  df_in['in_ground_truth'] = True
  for gt_idx, pred_idx in matches:
    df_in.at[gt_idx, col_name] = pred_df.iloc[pred_idx, :]['top1_pred']
  extra_preds = pred_df[~(pred_df.index.isin([x[1] for x in matches]))][['m/z', 'RT', 'top1_pred']].rename(columns={'m/z': 'Mass', 'top1_pred': col_name, 'RT': rt_col})
  extra_preds['in_ground_truth'] = False
  extra_preds['glycan'] = None
  df_in = pd.concat([df_in, extra_preds]).sort_values(['Mass', rt_col])
  return df_in

def evaluate_predictions(predictions, gt, rt_col='RT'):
  if len(predictions) == 0:
    return 0.0, 0, 0, 0, 0, 0, 0, 0, 0
  if 'charge' not in predictions.columns:
    predictions['charge'] = -1
  predictions['converted_masses'] = [m_z * abs(charge) + (abs(charge) - 1) for m_z, charge in zip(predictions.reset_index()['m/z'], predictions['charge'])]
  pairs = predictions.reset_index()[['m/z', 'RT']].round(2).values
  pairs_converted = predictions[['converted_masses', 'RT']].round(2).values
  gt_pairs = gt.reset_index()[['Mass', rt_col]].round(2).values
  matched_pairs = match_spectra(gt_pairs, pairs, mass_threshold=MASS_TOLERANCE, rt_threshold=RT_TOLERANCE, array2_alt=pairs_converted)
  merge_df = gt[['Mass', rt_col, 'glycan']].reset_index(drop=True)
  new_md = add_pred_column(merge_df, 'batch_pred', matched_pairs, predictions.reset_index(), rt_col)
  similarity_scores = []
  for gt_glycan, pred_glycan in zip(new_md['glycan'], new_md['batch_pred']):
    if not (isinstance(gt_glycan, str) and isinstance(pred_glycan, str)):
      similarity_scores.append(0.0)
      continue
    if '{' in gt_glycan:
      possible_structures = [graph_to_string(x) for x in get_possible_topologies(gt_glycan)]
      similarity_scores.append(max([1.0 if compare_glycans(p, pred_glycan) else get_glycan_similarity(p, pred_glycan) for p in possible_structures]))
    else:
      if compare_glycans(gt_glycan, pred_glycan):
        similarity_scores.append(1.0)
      else:
        similarity_scores.append(get_glycan_similarity(gt_glycan, pred_glycan))
  new_md['similarity_score'] = similarity_scores
  unevaluable = len(np.where((new_md['in_ground_truth'])&(new_md['glycan'].isnull())&(new_md['batch_pred'].notnull()))[0])
  fp = len(np.where((~new_md['in_ground_truth'])&(new_md['batch_pred'].notnull()))[0])
  tp = new_md[new_md['glycan'].notnull()]['similarity_score'].sum() + 0.5 * unevaluable
  empty_glycan_not_predicted = len(np.where((new_md['in_ground_truth'])&(new_md['glycan'].isnull())&(new_md['batch_pred'].isnull()))[0])
  fn = (new_md[new_md['glycan'].notnull()]['similarity_score'].apply(lambda x: 1-x)).sum() + empty_glycan_not_predicted
  peaks_not_picked = len(np.where((new_md['in_ground_truth'])&(new_md['batch_pred'].isnull()))[0])
  incorrect_predictions = len(np.where((new_md['glycan'].notnull()) & (new_md['batch_pred'].notnull()) & (new_md['similarity_score'] < 1.0))[0])
  precision = tp / (tp + fp + 1e-8)
  recall = tp / (tp + fn + 1e-8)
  f1_score = 2 * (precision * recall) / (precision + recall + 1e-8)
  return f1_score, precision, recall, peaks_not_picked, incorrect_predictions, tp, fp, fn, unevaluable

def evaluate_submission(submission_dir, test_dir="data/public_test"):
  test_files = [f for f in os.listdir(test_dir) if f.endswith('.csv') and '_solution' in f]
  results = {}
  for test_file in test_files:
    if not os.path.exists(os.path.join(test_dir, test_file)):
      print(f"Warning: No solution file for {test_file}")
      continue
    submission_file = test_file.replace('_solution.csv', '_submission.csv')
    submission_path = os.path.join(submission_dir, submission_file)
    if not os.path.exists(submission_path):
      print(f"Warning: Missing submission file {test_file}")
      continue
    predictions = pd.read_csv(submission_path)
    gt = pd.read_csv(os.path.join(test_dir, test_file))
    rt_col = 'RT' if 'RT' in gt.columns else test_file.split('.')[0] + '_RT'
    f1, precision, recall, peaks_not_picked, incorrect, tp, fp, fn, unevaluable = evaluate_predictions(predictions, gt, rt_col)
    results[test_file] = {'F1': f1, 'Precision': precision, 'Recall': recall, 'TP': tp, 'FP': fp, 'FN': fn, 'Unevaluable': unevaluable}
    print(f"{test_file}: F1={f1:.4f}, Precision={precision:.4f}, Recall={recall:.4f}, TP={tp:.1f}, FP={fp}, FN={fn:.1f}, Unevaluable={unevaluable}")
  avg_f1 = np.mean([r['F1'] for r in results.values()])
  print(f"\nAverage F1: {avg_f1:.4f}")
  return avg_f1, results

if __name__ == "__main__":
  if len(sys.argv) != 2:
    print("Usage: python evaluate_submission.py <submission_directory>")
    sys.exit(1)
  avg_f1, results = evaluate_submission(sys.argv[1])
