import sys
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from evaluate_submission import evaluate_submission

def evaluate_local(private_test_dir, output_file='leaderboard/private.md'):
  rows = []
  for submission_dir in sorted(Path('submissions').glob('*/private')):
    if not any(submission_dir.glob('*_submission.csv')):
      continue
    print(f"\n### {submission_dir.parent.name}")
    avg_f1, results = evaluate_submission(str(submission_dir), private_test_dir)
    rows.append((submission_dir.parent.name, avg_f1, results))
  rows.sort(key=lambda x: x[1], reverse=True)
  test_files = sorted(rows[0][2]) if rows else []
  glycan_class = pd.read_csv('data/file_metadata.csv', encoding='utf-8-sig').set_index('filename')['glycan_class'].to_dict()
  classes = sorted({glycan_class.get(t.replace('_solution.csv', '')) for t in test_files} - {None})
  with open(output_file, 'w', encoding='utf-8') as f:
    f.write(f"# Private Test Leaderboard\n\nEvaluated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | Participants: {len(rows)} | Missing files are scored as F1=0 | Precision, Recall, and class F1 are means over files\n\n")
    f.write("| Rank | Username | Overall F1 | Precision | Recall | " + " | ".join(f"{c}-glycan F1" for c in classes) + (" | " if classes else "") + " | ".join(t.replace('_solution.csv', '') for t in test_files) + " |\n")
    f.write("|" + "---|" * (len(test_files) + len(classes) + 5) + "\n")
    for rank, (user, avg_f1, results) in enumerate(rows, 1):
      class_f1 = [np.mean([results[t]['F1'] for t in test_files if glycan_class.get(t.replace('_solution.csv', '')) == c]) for c in classes]
      f.write(f"| {rank} | {user} | {avg_f1:.4f} | {np.mean([r['Precision'] for r in results.values()]):.4f} | {np.mean([r['Recall'] for r in results.values()]):.4f} | " + "".join(f"{x:.4f} | " for x in class_f1) + " | ".join(f"{results[t]['F1']:.4f}" if results[t]['submitted'] else "-" for t in test_files) + " |\n")
  print(f"\nPrivate leaderboard written to {output_file}")

if __name__ == "__main__":
  if len(sys.argv) < 2:
    print("Usage: python evaluation/evaluate_local.py <private_solution_directory> [output_file]")
    sys.exit(1)
  evaluate_local(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else 'leaderboard/private.md')