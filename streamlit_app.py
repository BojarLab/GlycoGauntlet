import streamlit as st
import pandas as pd
import requests
import os
from io import StringIO
import sys
import base64
import re
from datetime import datetime
sys.path.append('validation')
sys.path.append('evaluation')
from check_format import validate_df, parse_gwp, expected_submission_files
from evaluate_submission import evaluate_predictions

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_OWNER = os.environ.get('REPO_OWNER', 'BojarLab')
REPO_NAME = os.environ.get('REPO_NAME', 'GlycoGauntlet')

def read_upload(file):
  file.seek(0)
  if file.name.endswith('.gwp'):
    df = parse_gwp(file)
    return file.name[:-4].removesuffix('_submission') + '_submission.csv', df, df.to_csv(index=True).encode()
  df = pd.read_csv(file, encoding='utf-8-sig')
  return file.name, df, file.getvalue()

st.set_page_config(page_title="GlycoGauntlet Submission", page_icon="🍬", layout="wide")
st.title("🍬 GlycoGauntlet Submission Portal")
st.markdown("Submit your glycan structure predictions without needing a GitHub account!")

with st.expander("ℹ️ Submission Format Requirements"):
  st.markdown("""
  Your CSV files must contain these columns:
  - **m/z**: mass-to-charge ratio (float)
  - **RT**: retention time in minutes (float)
  - **charge**: signed charge, e.g., -1 for negative mode (integer)
  - **top1_pred**: predicted glycan structure in IUPAC-condensed notation (string)
  
  File names must match the test files exactly, replacing `_solution.csv` with `_submission.csv`.
  """)

username = st.text_input("Your name or model name (for leaderboard)", placeholder="JohnDoe_ManualAnnotation")

test_type = st.radio("Which test set are you submitting?", ["Public Test (immediate evaluation)", "Private Test (final evaluation only)", "Both"], horizontal=True)

public_files = None
private_files = None

if test_type in ["Public Test (immediate evaluation)", "Both"]:
  st.subheader("📊 Public Test Predictions")
  public_files = st.file_uploader("Upload your public test CSV or GlycoWorkbench files", type=['csv', 'gwp'], accept_multiple_files=True, key="public")

if test_type in ["Private Test (final evaluation only)", "Both"]:
  st.subheader("🔒 Private Test Predictions")
  private_files = st.file_uploader("Upload your private test CSV or GlycoWorkbench files", type=['csv', 'gwp'], accept_multiple_files=True, key="private")

if st.button("Preview public score (does not submit)", disabled=not public_files):
  with st.spinner("Scoring against the public solutions..."):
    solution_files = sorted(f for f in os.listdir('data/public_test') if f.endswith('_solution.csv'))
    uploaded = {}
    for file in public_files:
      name, df, _ = read_upload(file)
      errors = validate_df(df, name)
      if name.replace('_submission.csv', '_solution.csv') not in solution_files:
        errors.append(f"{name}: not a public test file name")
      for error in errors:
        st.write(f"❌ {error}")
      if not errors:
        uploaded[name.replace('_submission.csv', '_solution.csv')] = df
    rows = []
    for solution_file in solution_files:
      if solution_file in uploaded:
        f1, precision, recall, _, _, tp, fp, fn, _ = evaluate_predictions(uploaded[solution_file], pd.read_csv(f'data/public_test/{solution_file}', encoding='utf-8-sig'))
        rows.append({'File': solution_file.replace('_solution.csv', ''), 'F1': f1, 'Precision': precision, 'Recall': recall, 'False positives': f"{fp:.0f}", 'False negatives': f"{fn:.1f}"})
      else:
        rows.append({'File': solution_file.replace('_solution.csv', ''), 'F1': 0.0, 'Precision': 0.0, 'Recall': 0.0, 'False positives': '-', 'False negatives': '-'})
    preview = pd.DataFrame(rows)
    st.metric("Projected overall F1", f"{preview['F1'].mean():.4f}")
    st.caption("Mean over all public test files. Files not uploaded here count as 0, unless you submitted them earlier under the same name.")
    st.dataframe(preview.style.format({'F1': '{:.4f}', 'Precision': '{:.4f}', 'Recall': '{:.4f}'}), hide_index=True)

agree = st.checkbox("I confirm my files follow the required format")

if st.button("Submit Predictions", disabled=not agree or not username or (not public_files and not private_files)):
  if not GITHUB_TOKEN:
    st.error("GitHub token not configured. Please contact the competition organizers.")
    st.stop()
  username = re.sub(r'[^A-Za-z0-9_.-]', '_', username.strip())
  with st.spinner("Validating and submitting your predictions..."):
    try:
      validation_errors = []
      uploads = {'public': [], 'private': []}
      for test_type_key, files in [('public', public_files), ('private', private_files)]:
        expected = expected_submission_files(f'data/{test_type_key}_test')
        for file in files or []:
          name, df, content = read_upload(file)
          if name not in expected:
            validation_errors.append(f"{name}: not a {test_type_key} test file name, expected one of {sorted(expected)}")
          validation_errors.extend(validate_df(df, name))
          uploads[test_type_key].append((name, base64.b64encode(content).decode('utf-8')))
      if validation_errors:
        st.error("Validation failed:")
        for error in validation_errors:
          st.write(f"❌ {error}")
        st.stop()
      headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
      branch_name = f"submission-{username.replace(' ', '-')}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
      main_response = requests.get(f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/refs/heads/main', headers=headers)
      if main_response.status_code != 200:
        st.error(f"Failed to get main branch: {main_response.text}")
        st.stop()
      main_sha = main_response.json()['object']['sha']
      ref_data = {'ref': f'refs/heads/{branch_name}', 'sha': main_sha}
      ref_response = requests.post(f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/git/refs', json=ref_data, headers=headers)
      if ref_response.status_code != 201:
        st.error(f"Failed to create branch: {ref_response.text}")
        st.stop()
      file_urls = {'public': [], 'private': []}
      for test_type_key, files in uploads.items():
        for name, content in files:
          file_path = f"submissions/{username}/{test_type_key}/{name}"
          file_data = {'message': f'Add {name}', 'content': content, 'branch': branch_name}
          existing_response = requests.get(f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}?ref={branch_name}', headers=headers)
          if existing_response.status_code == 200:
            file_data['sha'] = existing_response.json()['sha']
          file_response = requests.put(f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{file_path}', json=file_data, headers=headers)
          if file_response.status_code not in [201, 200]:
            st.error(f"Failed to upload {name}: {file_response.text}")
            st.stop()
          raw_url = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{branch_name}/{file_path}"
          file_urls[test_type_key].append(raw_url)
      issue_body = f"### GitHub Username or Model Name\n{username}\n\n### Public Test Predictions\n"
      if file_urls['public']:
        for url in file_urls['public']:
          issue_body += f"- {url}\n"
      else:
        issue_body += "None\n"
      issue_body += "\n### Private Test Predictions\n"
      if file_urls['private']:
        for url in file_urls['private']:
          issue_body += f"- {url}\n"
      else:
        issue_body += "None\n"
      issue_body += "\n### Confirmation\n- [x] Files validated via Streamlit\n- [x] CSV files follow required format"
      issue_data = {'title': f'[Submission] {username}', 'body': issue_body, 'labels': ['submission', 'streamlit']}
      response = requests.post(f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/issues', json=issue_data, headers=headers)
      if response.status_code != 201:
        st.error(f"Failed to create submission: {response.text}")
        st.stop()
      issue_number = response.json()['number']
      st.success(f"✅ Submission successful! Issue #{issue_number} created.")
      st.markdown(f"Track your submission at: https://github.com/{REPO_OWNER}/{REPO_NAME}/issues/{issue_number}")
      st.info("Your submission is being processed. Check the issue for results; validation and evaluation typically complete within a few minutes.")
    except Exception as e:
      st.error(f"Error during submission: {str(e)}")

st.markdown("---")
st.markdown(f"View the leaderboard: [Public Test Leaderboard](https://github.com/{REPO_OWNER}/{REPO_NAME}/blob/main/leaderboard/public.md)")
