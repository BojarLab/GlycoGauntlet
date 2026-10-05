import json
import sys
import numpy as np
from datetime import datetime
from pathlib import Path


def write_leaderboard_md(scores, test_set):
  sorted_scores = sorted(scores.items(), key=lambda x: x[1]['best_score'], reverse=True)
  rescored_at = [s['rescored_at'] for data in scores.values() for s in data['submissions'] if s.get('rescored')]
  with open(Path('leaderboard') / f'{test_set}.md', 'w') as f:
    f.write(f"# {test_set.capitalize()} Test Leaderboard\n\n")
    f.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
    f.write(f"Total participants: {len(scores)} | Total submissions: {sum(len([s for s in data['submissions'] if not s.get('rescored')]) for data in scores.values())}\n\n")
    if rescored_at:
      f.write(f"All scores were recomputed with the current evaluator on {max(rescored_at)[:10]}; earlier scores are kept as legacy entries in `{test_set}_scores.json`.\n\n")
    f.write("Precision and Recall are those of each participant's best-scoring submission (mean over all test files).\n\n")
    f.write("| Rank | Username | Best F1 Score | Precision | Recall | Last F1 Score | Submissions | Last Submission |\n")
    f.write("|------|----------|---------------|-----------|--------|---------------|-------------|------------------|\n")
    for rank, (user, data) in enumerate(sorted_scores, 1):
      current = [s for s in data['submissions'] if not s.get('legacy')]
      last_entry = max(current, key = lambda x: x['timestamp'])
      best_entry = max(current, key = lambda x: x['score'])
      last_sub_date = datetime.fromisoformat(last_entry['timestamp']).strftime('%Y-%m-%d')
      last_score = last_entry['score']
      precision_str = f"{best_entry['precision']:.4f}" if 'precision' in best_entry else '-'
      recall_str = f"{best_entry['recall']:.4f}" if 'recall' in best_entry else '-'
      f.write(
        f"| {rank} | {user} | {data['best_score']:.4f} | {precision_str} | {recall_str} | {last_score:.4f} | {len([s for s in data['submissions'] if not s.get('rescored')])} | {last_sub_date} |\n")


def update_leaderboard(username, score, test_set='public', precision='', recall=''):
  leaderboard_dir = Path('leaderboard')
  leaderboard_dir.mkdir(exist_ok=True)
  json_file = leaderboard_dir / f'{test_set}_scores.json'
  if json_file.exists():
    with open(json_file, 'r') as f:
      scores = json.load(f)
  else:
    scores = {}
  timestamp = datetime.now().isoformat()
  if username not in scores:
    scores[username] = {'best_score': float(score), 'submissions': []}
  else:
    if float(score) > scores[username]['best_score']:
      scores[username]['best_score'] = float(score)
  scores[username]['submissions'].append({'score': float(score), 'timestamp': timestamp})
  if precision and recall:
    scores[username]['submissions'][-1].update({'precision': float(precision), 'recall': float(recall)})
  with open(json_file, 'w') as f:
    json.dump(scores, f, indent = 2)
  write_leaderboard_md(scores, test_set)


def rescore_leaderboard(test_set = 'public'):
  sys.path.append('evaluation')
  from evaluate_submission import evaluate_submission
  json_file = Path('leaderboard') / f'{test_set}_scores.json'
  with open(json_file, 'r') as f:
    scores = json.load(f)
  for username, data in scores.items():
    submission_dir = Path('submissions') / username / test_set
    if not any(submission_dir.glob('*_submission.csv')):
      print(f"{username}: no {test_set} submission files, kept as is")
      continue
    print(f"\n### {username}")
    avg_f1, results = evaluate_submission(str(submission_dir), f'data/{test_set}_test')
    last_timestamp = max(s['timestamp'] for s in data['submissions'] if not s.get('rescored'))
    for entry in data['submissions']:
      entry['legacy'] = True
    data['submissions'].append({'score': round(float(avg_f1), 4),
                                'precision': round(float(np.mean([r['Precision'] for r in results.values()])), 4),
                                'recall': round(float(np.mean([r['Recall'] for r in results.values()])), 4),
                                'timestamp': last_timestamp, 'rescored': True,
                                'rescored_at': datetime.now().isoformat()})
    data['best_score'] = round(float(avg_f1), 4)
  with open(json_file, 'w') as f:
    json.dump(scores, f, indent = 2)
  write_leaderboard_md(scores, test_set)


if __name__ == "__main__":
  if len(sys.argv) == 3 and sys.argv[1] == '--rescore':
    rescore_leaderboard(sys.argv[2])
  elif len(sys.argv) in [4, 6]:
    update_leaderboard(*sys.argv[1:])
  else:
    print("Usage: python update_leaderboard.py <username> <score> <test_set> [precision recall]\n       python update_leaderboard.py --rescore <test_set>")
    sys.exit(1)
