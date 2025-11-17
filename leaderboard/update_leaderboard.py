import json
import sys
from datetime import datetime
from pathlib import Path

def update_leaderboard(username, score, test_set='public'):
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
  with open(json_file, 'w') as f:
    json.dump(scores, f, indent=2)
  sorted_scores = sorted(scores.items(), key=lambda x: x[1]['best_score'], reverse=True)
  with open(md_file, 'w') as f:
    f.write(f"# Public Test Leaderboard\n\n")
    f.write(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n\n")
    f.write("| Rank | Username | Best F1 Score | Submissions |\n")
    f.write("|------|----------|---------------|-------------|\n")
    for rank, (user, data) in enumerate(sorted_scores, 1):
      f.write(f"| {rank} | {user} | {data['best_score']:.4f} | {len(data['submissions'])} |\n")

if __name__ == "__main__":
  if len(sys.argv) != 4:
    print("Usage: python update_leaderboard.py <username> <score> <test_set>")
    sys.exit(1)
  update_leaderboard(sys.argv[1], sys.argv[2], sys.argv[3])
