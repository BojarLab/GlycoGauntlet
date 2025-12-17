import streamlit as st
import pandas as pd
import requests
import os
from io import StringIO
import sys
sys.path.append('validation')
from check_format import validate_submission

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
REPO_OWNER = os.environ.get('REPO_OWNER', 'BojarLab')
REPO_NAME = os.environ.get('REPO_NAME', 'GlycoGauntlet')

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
  public_files = st.file_uploader("Upload your public test CSV files", type=['csv'], accept_multiple_files=True, key="public")

if test_type in ["Private Test (final evaluation only)", "Both"]:
  st.subheader("🔒 Private Test Predictions")
  private_files = st.file_uploader("Upload your private test CSV files", type=['csv'], accept_multiple_files=True, key="private")

agree = st.checkbox("I confirm my files follow the required format")

if st.button("Submit Predictions", disabled=not agree or not username or (not public_files and not private_files)):
  if not GITHUB_TOKEN:
    st.error("GitHub token not configured. Please contact the competition organizers.")
    st.stop()
  with st.spinner("Validating and submitting your predictions..."):
    try:
      validation_errors = []
      if public_files:
        for file in public_files:
          df = pd.read_csv(file)
          required_cols = ['m/z', 'RT', 'charge', 'top1_pred']
          missing_cols = [col for col in required_cols if col not in df.columns]
          if missing_cols:
            validation_errors.append(f"{file.name}: Missing columns {missing_cols}")
          if not pd.api.types.is_numeric_dtype(df['m/z']):
            validation_errors.append(f"{file.name}: m/z must be numeric")
          if not pd.api.types.is_numeric_dtype(df['RT']):
            validation_errors.append(f"{file.name}: RT must be numeric")
          if not pd.api.types.is_integer_dtype(df['charge']):
            validation_errors.append(f"{file.name}: charge must be integer")
          if df['top1_pred'].isna().all():
            validation_errors.append(f"{file.name}: top1_pred column is empty")
          if len(df) == 0:
            validation_errors.append(f"{file.name}: File is empty")
      if validation_errors:
        st.error("Validation failed:")
        for error in validation_errors:
          st.write(f"❌ {error}")
        st.stop()
      headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
      import base64
      issue_body = f"### GitHub Username or Model Name\n{username}\n\n### Public Test Predictions\n"
      if public_files:
        for file in public_files:
          file.seek(0)
          content = base64.b64encode(file.read()).decode('utf-8')
          issue_body += f"\n**{file.name}**:\n```csv-base64\n{content}\n```\n"
      else:
        issue_body += "None\n"
      issue_body += "\n### Private Test Predictions\n"
      if private_files:
        for file in private_files:
          file.seek(0)
          content = base64.b64encode(file.read()).decode('utf-8')
          issue_body += f"\n**{file.name}**:\n```csv-base64\n{content}\n```\n"
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
      st.info("Your files will be processed by our automated workflow within a few minutes.")
    except Exception as e:
      st.error(f"Error during submission: {str(e)}")

st.markdown("---")
st.markdown(f"View the leaderboard: [Public Test Leaderboard](https://github.com/{REPO_OWNER}/{REPO_NAME}/blob/main/leaderboard/public.md)")
