# Career Radar

Career Radar scans selected company career sites, filters relevant hardware and semiconductor jobs, remembers job history, and helps you triage jobs as saved, applied, or dismissed.

## Local App

Milestone 11 adds a local web app for daily use on Windows. The app is a thin UI over the existing scanners, ranking, history, email digest, scan health, and triage services. Existing CLI commands still work.

Framework choice: the local app uses Flask because it is a small Python server-rendered framework with no Node.js, Electron, frontend build, public hosting, or separate REST API requirement. It keeps the UI testable while adding only one dependency.

## Windows First Run

1. Clone or pull the repository:

   ```powershell
   git clone https://github.com/avishailevi/career-radar.git
   cd career-radar
   ```

   If you already have the repository:

   ```powershell
   cd C:\Projects\AI-Job-Agent
   git pull
   ```

2. Create and activate a Python environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install Python dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. Install Playwright browser dependencies:

   ```powershell
   python -m playwright install
   ```

5. Optional email digest setup:

   Configure these environment variables only if you want email notifications:

   ```powershell
   $env:CAREER_RADAR_EMAIL_ENABLED="true"
   $env:CAREER_RADAR_SMTP_HOST="smtp.example.com"
   $env:CAREER_RADAR_SMTP_PORT="587"
   $env:CAREER_RADAR_SMTP_USERNAME="your-user"
   $env:CAREER_RADAR_SMTP_PASSWORD="your-password"
   $env:CAREER_RADAR_EMAIL_FROM="from@example.com"
   $env:CAREER_RADAR_EMAIL_TO="to@example.com"
   ```

6. Start the local app:

   Double-click `start_career_radar.bat`.

   The launcher starts the local server, waits until it is ready, and opens Career Radar in your default browser.

7. Stop the application safely:

   Close the browser tab, then go to the `Career Radar Server` command window and press `Ctrl+C`. If asked to terminate the batch job, type `Y` and press Enter.

## Daily Use

1. Open the app with `start_career_radar.bat`.
2. Click `Scan Now`.
3. Wait for the status to show the scan completed.
4. Review New Jobs.
5. Open job links directly from the app.
6. Mark jobs as Saved, Applied, or Dismissed.
7. Use Saved, Applied, Dismissed, and Scan Health tabs without running another scan.

Dismissed jobs are hidden from the New Jobs view. History is stored locally in `data/job_history.json` and remains available after closing and reopening the app.

## CLI Compatibility

The original command line workflow remains available:

```powershell
python main.py
python main.py Apple
python main.py Apple NVIDIA
python main.py saved
python main.py applied
python main.py dismissed
python main.py mark <job_id> <saved|dismissed|applied>
```

## Validation

Run automated checks:

```powershell
python -m unittest discover -s tests
python -m compileall .
```
