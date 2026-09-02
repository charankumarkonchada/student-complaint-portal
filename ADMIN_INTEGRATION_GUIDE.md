# Admin & Integration Owner Workflow Guide

**ADMIN / INTEGRATION OWNER: K. Charankumar (`0221168`)**

As the Project Administrator and Integration Owner, you are the single gatekeeper for the `main` branch. This guide defines your standard operating procedure for reviewing, validating, testing, and merging Pull Requests submitted by the other 5 team members.

---

## 1. 12-Step Pull Request Review & Integration Protocol

```text
[ PR Submitted ] ──► Step 1: Open PR on GitHub
                  ──► Step 2: Inspect "Files changed"
                  ──► Step 3: Confirm Member Ownership
                  ──► Step 4: Verify Zero Cross-Feature / Shared File Contamination
                  ──► Step 5: Conduct Code Quality & Security Review
                  ──► Step 6: Fetch & Test Branch Locally
                  ──► Step 7: Test the Affected Feature Manually
                  ──► Step 8: Confirm Clean Merge Status (No Conflicts)
                  ──► Step 9: Merge Pull Request on GitHub
                  ──► Step 10: Pull Updated `main` Locally (`git pull origin main`)
                  ──► Step 11: Run Complete Application Locally
                  ──► Step 12: Verify Entire End-to-End System Health
```

---

## 2. Detailed Step Instructions

### Step 1: Check Pull Request
Open the Pull Request on GitHub. Ensure the PR checklist has been completed by the collaborator.

### Step 2: Inspect Changed Files
Click the **"Files changed"** tab on GitHub to see every line of added, modified, or deleted code.

### Step 3: Confirm Ownership
Cross-reference the files changed against [TEAM_OWNERSHIP.md](TEAM_OWNERSHIP.md):
- **Charan:** Allowed ONLY in `routes/charan/`, `templates/charan/`, `static/css/charan/`, `static/js/charan/`
- **Jagan:** Allowed ONLY in `routes/jagan/`, `templates/jagan/`, `static/css/jagan/`, `static/js/jagan/`
- **Raghunitha:** Allowed ONLY in `routes/raghunitha/`, `templates/raghunitha/`, `static/css/raghunitha/`, `static/js/raghunitha/`
- **Deepthi:** Allowed ONLY in `routes/deepthi/`, `templates/deepthi/`, `static/css/deepthi/`, `static/js/deepthi/`
- **Vennela:** Allowed ONLY in `routes/vennela/`, `templates/vennela/`, `static/css/vennela/`, `static/js/vennela/`

### Step 4: Check for Unrelated / Shared Files
Ensure the PR does **NOT** touch:
- `app.py`, `config.py`, `database/`, `services/`, `ml_engine.py`, or `templates/base.html`
- `.env`, cache files (`__pycache__`), virtual environments (`.venv`), or another member's folder.

### Step 5: Review Code Quality & Security
Verify that:
- Code does not contain hardcoded passwords or API tokens.
- SQL queries use parameter substitution (`?`) rather than string concatenation to prevent SQL injection.
- Template links use dynamic `url_for(...)`.

### Step 6: Fetch & Test the Branch Locally
Before merging, pull down the collaborator's branch to your machine:
```bash
git fetch origin <member-branch>
git checkout <member-branch>
```

### Step 7: Test the Affected Feature
Start the application locally and click through the collaborator's feature in your browser:
```bash
python3 app.py
```
- Verify HTML renders properly without template errors.
- Verify CSS styling and responsiveness.
- Verify JavaScript event handlers and console output.

### Step 8: Check for Conflicts
Ensure GitHub states: **"This branch has no conflicts with the base branch"**.

### Step 9: Merge Pull Request
On GitHub, click **"Merge pull request"** and select **"Confirm merge"**. (Delete the remote branch if desired).

### Step 10: Pull Updated `main` Locally
Return to your local `main` branch and pull the newly merged code:
```bash
git checkout main
git pull origin main
```

### Step 11: Run the Complete Application
Run the full application from your updated `main` branch:
```bash
python3 app.py
```

### Step 12: Test the Complete Application
Verify that existing features and other members' views continue to function seamlessly without regressions.

---

## 3. Handling Accidental Edits & Conflicts

### Scenario A: Member modified a shared file or another member's file
*Example:* B. Jagan modified `routes/jagan/add_complaint.py` (Valid), but also modified `services/auth_service.py` or `templates/base.html` (Invalid).

**Action:**
1. Do **NOT** merge the PR.
2. In the PR review on GitHub, click **"Request changes"**.
3. Comment:
   > *"Hi Jagan, `services/auth_service.py` is part of shared infrastructure and cannot be modified directly. Please revert changes to `services/auth_service.py` on your branch and push an update."*
4. The collaborator can revert the file locally and push:
   ```bash
   git checkout origin/main -- services/auth_service.py
   git commit -m "revert: restore shared auth_service.py"
   git push origin jagan-work
   ```
5. Once the PR contains **ONLY** their assigned files, approve and merge.

### Scenario B: Merge Conflict on `main`
If a PR cannot be cleanly merged:
1. Instruct the collaborator to sync their branch locally:
   ```bash
   git checkout <member-branch>
   git fetch origin
   git merge origin/main
   ```
2. Resolve conflicts within their assigned files.
3. Commit and push:
   ```bash
   git commit -m "merge: resolve merge conflicts with main"
   git push origin <member-branch>
   ```
