import json
import sys
from datetime import datetime
from pathlib import Path

def update_leaderboard(username, score, test_set='public', precision='', recall=''):
  leaderboard_dir = Path('leaderboard')
  leaderboard_dir.mkdir(exist_ok=True)
  json_file = leaderboard_dir / f'{test_set}_scores.json'
  md_file = leaderboard_dir / f'{test_set}.md'
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
    json.dump(scores, f, indent=2)
  sorted_scores = sorted(scores.items(), key=lambda x: x[1]['best_score'], reverse=True)
  with open(md_file, 'w') as f:
    f.write(f"# {test_set.capitalize()} Test Leaderboard\n\n")
    f.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
    f.write(f"Total participants: {len(scores)} | Total submissions: {sum(len(data['submissions']) for data in scores.values())}\n\n")
    f.write("Precision and Recall are those of each participant's best-scoring submission (mean over all test files).\n\n")
    f.write("| Rank | Username | Best F1 Score | Precision | Recall | Last F1 Score | Submissions | Last Submission |\n")
    f.write("|------|----------|---------------|-----------|--------|---------------|-------------|------------------|\n")
    for rank, (user, data) in enumerate(sorted_scores, 1):
      last_entry = max(data['submissions'], key = lambda x: x['timestamp'])
      best_entry = max(data['submissions'], key = lambda x: x['score'])
      last_sub_date = datetime.fromisoformat(last_entry['timestamp']).strftime('%Y-%m-%d')
      last_score = last_entry['score']
      precision_str = f"{best_entry['precision']:.4f}" if 'precision' in best_entry else '-'
      recall_str = f"{best_entry['recall']:.4f}" if 'recall' in best_entry else '-'
      f.write(
        f"| {rank} | {user} | {data['best_score']:.4f} | {precision_str} | {recall_str} | {last_score:.4f} | {len(data['submissions'])} | {last_sub_date} |\n")

if __name__ == "__main__":
  if len(sys.argv) not in [4, 6]:
    print("Usage: python update_leaderboard.py <username> <score> <test_set> [precision recall]")
    sys.exit(1)
  update_leaderboard(*sys.argv[1:])
