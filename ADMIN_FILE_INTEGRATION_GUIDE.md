# Admin File Integration Guide

**ADMIN / INTEGRATION OWNER: K. Charankumar (`0221168`)**

This guide documents the exact procedure for receiving completed files from each team member, copying them into the main project, running safety checks, and creating separate, dedicated Git commits on the `main` branch.

---

## 1. High-Level Integration Flow

```text
       K. Charankumar (Admin)
                 │
                 ▼
       Sends assigned files from
       `TEAM_FILE_DISTRIBUTION/<MEMBER>/`
                 │
                 ▼
          Team Member
      (Modifies files locally)
                 │
                 ▼
  Team Member returns completed files
                 │
                 ▼
       K. Charankumar (Admin)
   Copies files into main project
                 │
                 ▼
           `git status`
   (Verify ONLY that member's files changed)
                 │
                 ▼
         Test application
                 │
                 ▼
    `git add` & `git commit`
     (Member-specific commit)
                 │
                 ▼
       `git push origin main`
```

Repeat this cycle separately for each of the 5 team members so that each member's contributions appear as an isolated, distinct commit in GitHub history.

---

## 2. Step-by-Step Integration & Commit Commands

---

### Step 1: Integrating R. Charan Kumar's Work (`0210894`)

1. **Receive completed files** from Charan.
2. **Copy files** into the main project:
   - `routes/charan/*` &rarr; `routes/charan/`
   - `templates/charan/*` &rarr; `templates/charan/`
   - `static/css/charan/*` &rarr; `static/css/charan/`
   - `static/js/charan/*` &rarr; `static/js/charan/`
3. **Verify Git Status:**
   ```bash
   git status
   ```
   *Safety Check:* Confirm that **ONLY** files inside `charan/` folders are modified or added. If unrelated or shared files appear, do **NOT** commit.
4. **Test the Application:**
   ```bash
   python3 app.py
   ```
   Verify Admin Login (`/admin_login`), Manage Complaints (`/manage_complaints`), Update Status (`/update_status/<id>`), and 404 page (`/404`).
5. **Stage and Commit:**
   ```bash
   git add routes/charan/ templates/charan/ static/css/charan/ static/js/charan/
   git commit -m "feat(charan): integrate admin login and complaint management"
   git push origin main
   ```

---

### Step 2: Integrating B. Jagan's Work (`0221078`)

1. **Receive completed files** from Jagan.
2. **Copy files** into the main project:
   - `routes/jagan/*` &rarr; `routes/jagan/`
   - `templates/jagan/*` &rarr; `templates/jagan/`
   - `static/css/jagan/*` &rarr; `static/css/jagan/`
   - `static/js/jagan/*` &rarr; `static/js/jagan/`
3. **Verify Git Status:**
   ```bash
   git status
   ```
   *Safety Check:* Confirm that **ONLY** files inside `jagan/` folders are modified.
4. **Test the Application:**
   ```bash
   python3 app.py
   ```
   Verify Home page (`/`), Add Complaint (`/add_complaint`), AI live preview (`/api/ai_analyze`), Complaint History (`/complaints`), and View Complaint (`/complaint/<id>`).
5. **Stage and Commit:**
   ```bash
   git add routes/jagan/ templates/jagan/ static/css/jagan/ static/js/jagan/
   git commit -m "feat(jagan): integrate complaint submission and history features"
   git push origin main
   ```

---

### Step 3: Integrating M. Raghunitha's Work (`0220917`)

1. **Receive completed files** from Raghunitha.
2. **Copy files** into the main project:
   - `routes/raghunitha/*` &rarr; `routes/raghunitha/`
   - `templates/raghunitha/*` &rarr; `templates/raghunitha/`
   - `static/css/raghunitha/*` &rarr; `static/css/raghunitha/`
   - `static/js/raghunitha/*` &rarr; `static/js/raghunitha/`
3. **Verify Git Status:**
   ```bash
   git status
   ```
   *Safety Check:* Confirm that **ONLY** files inside `raghunitha/` folders are modified.
4. **Test the Application:**
   ```bash
   python3 app.py
   ```
   Verify Student Registration (`/register` with O/N/R/S IDs), Edit Complaint (`/edit_complaint/<id>`), Delete Complaint, and Student Profile (`/profile`).
5. **Stage and Commit:**
   ```bash
   git add routes/raghunitha/ templates/raghunitha/ static/css/raghunitha/ static/js/raghunitha/
   git commit -m "feat(raghunitha): integrate registration editing and profile features"
   git push origin main
   ```

---

### Step 4: Integrating K. Deepthi's Work (`0220836`)

1. **Receive completed files** from Deepthi.
2. **Copy files** into the main project:
   - `routes/deepthi/*` &rarr; `routes/deepthi/`
   - `templates/deepthi/*` &rarr; `templates/deepthi/`
   - `static/css/deepthi/*` &rarr; `static/css/deepthi/`
   - `static/js/deepthi/*` &rarr; `static/js/deepthi/`
3. **Verify Git Status:**
   ```bash
   git status
   ```
   *Safety Check:* Confirm that **ONLY** files inside `deepthi/` folders are modified.
4. **Test the Application:**
   ```bash
   python3 app.py
   ```
   Verify Student Login (`/login`), Logout (`/logout`), Forgot Password (`/forgot-password`), Verify Reset OTP (`/verify-reset-otp`), Reset Password (`/reset-password`), Change Password (`/change_password`), and Notifications (`/notifications`).
5. **Stage and Commit:**
   ```bash
   git add routes/deepthi/ templates/deepthi/ static/css/deepthi/ static/js/deepthi/
   git commit -m "feat(deepthi): integrate authentication password reset and notifications"
   git push origin main
   ```

---

### Step 5: Integrating K. Vennela's Work (`0210785`)

1. **Receive completed files** from Vennela.
2. **Copy files** into the main project:
   - `routes/vennela/*` &rarr; `routes/vennela/`
   - `templates/vennela/*` &rarr; `templates/vennela/`
   - `static/css/vennela/*` &rarr; `static/css/vennela/`
   - `static/js/vennela/*` &rarr; `static/js/vennela/`
3. **Verify Git Status:**
   ```bash
   git status
   ```
   *Safety Check:* Confirm that **ONLY** files inside `vennela/` folders are modified.
4. **Test the Application:**
   ```bash
   python3 app.py
   ```
   Verify Student Dashboard (`/dashboard`), Recent Activity (`/activity`), and 500 error page (`/500`).
5. **Stage and Commit:**
   ```bash
   git add routes/vennela/ templates/vennela/ static/css/vennela/ static/js/vennela/
   git commit -m "feat(vennela): integrate student dashboard and activity features"
   git push origin main
   ```

---

## 3. Desired GitHub History

After performing these individual commits, your GitHub `main` branch commit log will cleanly reflect each member's contributions:

```text
main
│
├── feat(charan): integrate admin login and complaint management
│
├── feat(jagan): integrate complaint submission and history features
│
├── feat(raghunitha): integrate registration editing and profile features
│
├── feat(deepthi): integrate authentication password reset and notifications
│
└── feat(vennela): integrate student dashboard and activity features
```

> [!IMPORTANT]
> **Do NOT Squash Commits:** Keep these commits as separate entries in git history. Do not squash or rebase them into a single monolithic commit.

---

## 4. Understanding Git Authorship vs GitHub Committer

Because you (K. Charankumar) are executing the commits locally and pushing from your GitHub account:
1. **Default Git Behavior:** GitHub will display your account as the committer. The commit message explicitly designates the author (e.g., `feat(jagan): ...`).
2. **Configuring Co-Authored-By (Recommended for GitHub UI Attribution):**
   If you want GitHub's UI to link the member's GitHub profile alongside yours, add a `Co-authored-by:` trailer in the commit message:
   ```bash
   git commit -m "feat(jagan): integrate complaint submission and history features

   Co-authored-by: B Jagan <jagan_github_email@example.com>"
   ```
3. **Configuring Git `--author` Flag:**
   If you want Git's author metadata to record the team member's name and email while keeping you as the committer:
   ```bash
   git commit --author="B. Jagan <jagan_email@example.com>" -m "feat(jagan): integrate complaint submission and history features"
   ```
*Note:* Simply pushing a commit from your GitHub account without the `--author` or `Co-authored-by` flag will record your account as the author. Use one of the two methods above if profile-level contributor credit is required.
