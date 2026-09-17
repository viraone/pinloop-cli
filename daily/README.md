# Pinloop Jobs dashboard

This folder contains the local daily job-search pipeline, tailored-resume builder,
application autofill, and dashboard.

Personal data is intentionally not tracked. Before running it in a fresh clone:

```bash
cd daily
cp resume.example.json resume.json
cp profile.example.json profile.json
cp skills.example.json skills.json
python3 -m venv .venv
.venv/bin/pip install flask openpyxl playwright reportlab
.venv/bin/playwright install chromium
```

Edit the three copied JSON files with the applicant's truthful information. Run
`./run.sh` for the pipeline or `./ui.sh` for the local dashboard.
