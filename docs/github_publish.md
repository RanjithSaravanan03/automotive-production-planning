# Upload the project and publish the dashboard

Suggested repository: `automotive-production-planning`.

## Create the repository

1. Sign in to the intended GitHub account.
2. Visit https://github.com/new.
3. Use repository name `automotive-production-planning`.
4. Description: `Python–SQLite automotive production planning simulation with shortage diagnosis, scenario analysis and an interactive dashboard.`
5. Choose **Public** for a recruiter-facing portfolio and GitHub Pages on GitHub Free. Choose Private if that is your preference; Pages availability depends on your plan.
6. Initialize with a README, then create the repository. An initial commit also allows the connected GitHub tools to upload the prepared files as a subsequent commit.
7. Share the resulting repository URL with the assistant for upload. A successful upload must be confirmed from GitHub; this prepared package does not by itself publish anything.

## Upload using Git on Windows (alternative)

Extract the release ZIP. Use its inner `automotive-production-planning` folder as the repository root; `README.md`, `src`, `data`, `reports` and `docs` must be directly inside that root.

After creating the initialized repository above, clone it to a fresh folder using Git for Windows or GitHub Desktop. Copy the **contents** of the prepared release folder into the clone, preserving its existing `.git` folder. Review the staged changes, commit them, then push. Do not upload the ZIP as the sole repository file, and do not copy an old virtual environment.

## Enable the live visualization

Once the files have reached GitHub:

1. Open repository **Settings → Pages**.
2. Source: **Deploy from a branch**.
3. Branch: **main**. Folder: **/docs**.
4. Click **Save** and wait for the Pages deployment to succeed.
5. Open the URL shown by GitHub Pages. It should display the same three scenario options and Day-64 values as the local dashboard.

For the suggested account/repository combination, the expected URL after successful deployment is:

`https://ranjithsaravanan03.github.io/automotive-production-planning/`

This is an expected address, not confirmation that a site is already live.

The package includes `docs/index.html`, `docs/.nojekyll` and screenshot assets. The page embeds simulation snapshots and needs no Python server. Reference: https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site.

## Refresh a published dashboard

Regenerate the scenario reports as required, then run:

```powershell
.\.venv\Scripts\python.exe .\src\prepare_dashboard_data.py
.\.venv\Scripts\python.exe .\src\build_planning_dashboard.py
Copy-Item .\reports\dashboard\index.html .\docs\index.html -Force
```

Commit and push the updated files. Check the deployment and open the live page again.
