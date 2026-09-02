# GitHub Team Collaboration Workflow Guide

**Project:** IntelliHostel — Student Complaint Portal  
**Project Admin & Integration Owner:** K. Charankumar (`0221168`)

This guide explains the exact step-by-step Git & GitHub workflow for all collaborators. Follow these instructions strictly to ensure zero merge conflicts, secure secrets management, and safe integration.

---

## 1. High-Level Collaboration Flow

```text
       [ K. Charankumar: Complete Working Project ]
                           │
                           ▼
                  GitHub `main` branch
                           │
    ┌──────────────────────┼──────────────────────┐
    ▼                      ▼                      ▼
R. Charan Kumar         B. Jagan             M. Raghunitha  ... (Deepthi & Vennela)
(charan-work)         (jagan-work)         (raghunitha-work)
    │                      │                      │
    ▼                      ▼                      ▼
Modifies ONLY          Modifies ONLY          Modifies ONLY
assigned files         assigned files         assigned files
    │                      │                      │
    ▼                      ▼                      ▼
Commit & Push          Commit & Push          Commit & Push
`charan-work`          `jagan-work`           `raghunitha-work`
    │                      │                      │
    └──────────────────────┼──────────────────────┘
                           │
                           ▼
               GitHub Pull Request (PR)
                           │
                           ▼
         K. Charankumar reviews, tests & merges
                           │
                           ▼
                 Updated `main` branch
```

---

## 2. Core Rules for Every Collaborator

1. **Never Push Directly to `main`**:
   - `git push origin main` is **STRICTLY PROHIBITED**.
   - You must push ONLY to your dedicated branch: `git push -u origin <your-branch>`.
2. **Modify ONLY Your Assigned Folders**:
   - Touch only the files inside your designated subdirectories under `routes/`, `templates/`, `static/css/`, and `static/js/`.
   - Never edit another member's feature files or shared infrastructure (`app.py`, `config.py`, `database/`, `services/`, `ml_engine.py`, `base.html`).
3. **No File Swapping via WhatsApp or ZIPs**:
   - Do NOT send modified ZIPs, email attachments, or WhatsApp files.
   - All collaboration happens transparently through Git branches and GitHub Pull Requests.
4. **Never Commit Secrets**:
   - Never commit `.env` or files containing API keys, passwords, or credentials.

---

## 3. Dedicated Member Commands

Use `<YOUR_GITHUB_REPOSITORY_URL>` as the repository URL when cloning.

---

### Member 1: R. Charan Kumar (`0210894`)
- **Branch Name:** `charan-work`
- **Assigned Feature Folders:**
  - `routes/charan/`
  - `templates/charan/`
  - `static/css/charan/`
  - `static/js/charan/`

#### Step-by-Step Commands:
```bash
# 1. Clone the complete repository
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd SE

# 2. Create and switch to your feature branch
git checkout -b charan-work

# 3. Work ONLY on your assigned files (e.g. routes/charan/, templates/charan/, etc.)

# 4. Check changed files to ensure no other files were touched
git status

# 5. Stage ONLY your assigned files
git add routes/charan/ templates/charan/ static/css/charan/ static/js/charan/

# 6. Commit with a meaningful message
git commit -m "feat(admin): update admin complaint status and 404 page styling"

# 7. Push your branch to GitHub
git push -u origin charan-work

# 8. Open GitHub and create a Pull Request from 'charan-work' into 'main'
```

---

### Member 2: K. Charankumar (`0221168`) — Admin & Integration Owner
- **Branch:** `main` (or integration branches)
- **Role:** Reviews, tests, and merges all Pull Requests. Maintains shared infrastructure (`app.py`, `config.py`, `database/`, `services/`, `ml_engine.py`, `base.html`).

---

### Member 3: B. Jagan (`0221078`)
- **Branch Name:** `jagan-work`
- **Assigned Feature Folders:**
  - `routes/jagan/`
  - `templates/jagan/`
  - `static/css/jagan/`
  - `static/js/jagan/`

#### Step-by-Step Commands:
```bash
# 1. Clone the complete repository
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd SE

# 2. Create and switch to your feature branch
git checkout -b jagan-work

# 3. Work ONLY on your assigned files (e.g. routes/jagan/, templates/jagan/, etc.)

# 4. Check changed files
git status

# 5. Stage ONLY your assigned files
git add routes/jagan/ templates/jagan/ static/css/jagan/ static/js/jagan/

# 6. Commit with a meaningful message
git commit -m "feat(complaints): enhance complaint submission and history view"

# 7. Push your branch to GitHub
git push -u origin jagan-work

# 8. Open GitHub and create a Pull Request from 'jagan-work' into 'main'
```

---

### Member 4: M. Raghunitha (`0220917`)
- **Branch Name:** `raghunitha-work`
- **Assigned Feature Folders:**
  - `routes/raghunitha/`
  - `templates/raghunitha/`
  - `static/css/raghunitha/`
  - `static/js/raghunitha/`

#### Step-by-Step Commands:
```bash
# 1. Clone the complete repository
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd SE

# 2. Create and switch to your feature branch
git checkout -b raghunitha-work

# 3. Work ONLY on your assigned files (e.g. routes/raghunitha/, templates/raghunitha/, etc.)

# 4. Check changed files
git status

# 5. Stage ONLY your assigned files
git add routes/raghunitha/ templates/raghunitha/ static/css/raghunitha/ static/js/raghunitha/

# 6. Commit with a meaningful message
git commit -m "feat(registration): verify multi-campus ID formats and profile view"

# 7. Push your branch to GitHub
git push -u origin raghunitha-work

# 8. Open GitHub and create a Pull Request from 'raghunitha-work' into 'main'
```

---

### Member 5: K. Deepthi (`0220836`)
- **Branch Name:** `deepthi-work`
- **Assigned Feature Folders:**
  - `routes/deepthi/`
  - `templates/deepthi/`
  - `static/css/deepthi/`
  - `static/js/deepthi/`

#### Step-by-Step Commands:
```bash
# 1. Clone the complete repository
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd SE

# 2. Create and switch to your feature branch
git checkout -b deepthi-work

# 3. Work ONLY on your assigned files (e.g. routes/deepthi/, templates/deepthi/, etc.)

# 4. Check changed files
git status

# 5. Stage ONLY your assigned files
git add routes/deepthi/ templates/deepthi/ static/css/deepthi/ static/js/deepthi/

# 6. Commit with a meaningful message
git commit -m "feat(auth): refine student login, password reset flow and notifications"

# 7. Push your branch to GitHub
git push -u origin deepthi-work

# 8. Open GitHub and create a Pull Request from 'deepthi-work' into 'main'
```

---

### Member 6: K. Vennela (`0210785`)
- **Branch Name:** `vennela-work`
- **Assigned Feature Folders:**
  - `routes/vennela/`
  - `templates/vennela/`
  - `static/css/vennela/`
  - `static/js/vennela/`

#### Step-by-Step Commands:
```bash
# 1. Clone the complete repository
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd SE

# 2. Create and switch to your feature branch
git checkout -b vennela-work

# 3. Work ONLY on your assigned files (e.g. routes/vennela/, templates/vennela/, etc.)

# 4. Check changed files
git status

# 5. Stage ONLY your assigned files
git add routes/vennela/ templates/vennela/ static/css/vennela/ static/js/vennela/

# 6. Commit with a meaningful message
git commit -m "feat(dashboard): update student KPI widgets, activity log and 500 error"

# 7. Push your branch to GitHub
git push -u origin vennela-work

# 8. Open GitHub and create a Pull Request from 'vennela-work' into 'main'
```

---

## 4. How to Sync Your Branch with `main`

Before starting new work or submitting a Pull Request, always pull the latest changes from `main` into your local branch:

```bash
# 1. Fetch latest changes from GitHub
git fetch origin

# 2. Ensure you are on your feature branch
git checkout <your-branch>

# 3. Merge origin/main into your branch
git merge origin/main
```

### Resolving Merge Conflicts:
If Git reports a conflict:
1. Run `git status` to see conflicting files.
2. If the conflict is in your assigned feature file, open the file, resolve the conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`), save the file, and run:
   ```bash
   git add <conflicted-file>
   git commit -m "merge: sync branch with latest main"
   ```
3. If the conflict is in a shared file or another member's folder, **STOP** immediately and contact K. Charankumar. Do **NOT** overwrite the file.

---

## 5. Pull Request (PR) Creation & Review Workflow

1. Push your branch to GitHub:
   ```bash
   git push -u origin <your-branch>
   ```
2. Navigate to your repository on GitHub. You will see a banner: **"Compare & pull request"**. Click it.
3. Set the base branch to `main` and the compare branch to your feature branch (`<your-branch>`).
4. Fill out the PR title and description summarizing your changes.
5. Review the **"Files changed"** tab on GitHub:
   - Confirm that **ONLY** your assigned feature files appear.
   - Confirm that **NO** shared files or `.env` files appear.
6. Submit the Pull Request and notify K. Charankumar.
7. **Members must NOT merge their own Pull Requests.** The Integration Owner will review, test, and merge it.
