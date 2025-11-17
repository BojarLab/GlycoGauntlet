# GlycoGauntlet

Predict glycan structures from mass spectrometry glycomics data. Beat our deep learning model (CandyCrunch) or provide expert manual annotations.

## Task

Given Excel files containing LC-MS/MS glycomics runs (thousands of spectra per file), predict the glycan structure for each detected peak (Alternatively, raw files are available here: XXX). Input files contain m/z, retention time, and intensity data. Your job is to output glycan structures in (preferably) IUPAC-condensed notation, as well as where they're found (m/z + retention time).

## Evaluation

Your predictions are matched to ground truth spectra using mass (±0.5 Da) and retention time (±1.0 min) tolerance. Scoring uses a soft F1 metric where exact structural matches get 1.0 and partial matches get cosine similarity based on motif fingerprints. False positives and false negatives are penalized. See `evaluation/evaluate_submission.py` for the exact implementation.

## Data

**Training**: Full annotated dataset at https://zenodo.org/records/10997110 (multiple glycomics runs, hundreds of thousands of annotated spectra)

**Public Test**: Files in `data/public_test/` with ground truths as `_solution.csv` files

**Private Test**: Hidden, scored only at competition end

## Submission Format

Your predictions must be Excel files matching the input filenames, with this exact structure:

| Column | Type | Description |
|--------|------|-------------|
| m/z | float | Observed mass-to-charge ratio |
| charge | float | Signed charge (e.g., -1 for negative mode) |
| RT | float | Retention time in minutes |
| top1_pred | str | Predicted glycan in IUPAC-condensed notation |

Index should be integer row numbers. Additional columns (confidence scores, alternative predictions) are allowed but ignored.

**Example row:**
```
m/z: 1235.19, charge: -1, RT: 17.63, top1_pred: Man(a1-3)[Man(a1-6)]Man(a1-6)[Man(a1-3)]Man(b1-4)GlcNAc(b1-4)GlcNAc
```

## How to Participate

1. Fork this repository
2. Run your model or manually annotate the files in `data/public_test/`
3. Save predictions as Excel files in `submissions/{your_github_username}/public/`
4. Ensure filenames match the test files exactly (e.g., if test file is `sample_001.xlsx`, prediction must be `sample_001_submission.csv`)
5. Run `python validation/check_format.py submissions/{your_github_username}/public/` to verify format
6. Open a pull request

GitHub Actions will automatically evaluate your submission on the public test set and update the leaderboard. You can submit multiple times; only your best score counts.

## Baseline

CandyCrunch (our model) achieves F1=0.XX on public test. Code: https://github.com/BojarLab/CandyCrunch

To generate baseline predictions:
```python
from candycrunch.prediction import wrap_inference
preds = wrap_inference("data/public_test/example.xlsx", glycan_class='N')
preds.to_csv("submissions/baseline/public/example_submission.csv")
```

## Leaderboard

See `leaderboard/public.md` for current rankings on public test set.

Final rankings on private test set will be revealed after competition closes on [DATE].

## Manual Annotation

You don't need code. Annotate spectra in Excel, format as above, submit. Many of the best glycomics annotations come from expert knowledge, not algorithms.

## Questions

Open an issue or see the full evaluation code in `evaluation/`.