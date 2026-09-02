# Pull Request Submission Checklist

Every collaborator must copy this checklist into their GitHub Pull Request description and check off all items before requesting a review from the Integration Owner (**K. Charankumar**).

---

## Collaborator PR Checklist

```markdown
### Contributor Information
- **Name:** [Your Name]
- **Student ID:** [Your ID]
- **Branch:** [e.g. jagan-work / deepthi-work / etc.]
- **Assigned Feature(s):** [e.g. Add Complaint / Student Registration / etc.]

### Mandatory Scope & Integrity Checks
- [ ] **Assigned Files Only:** I modified ONLY files located inside my assigned feature folders (`routes/<my-name>/`, `templates/<my-name>/`, `static/css/<my-name>/`, `static/js/<my-name>/`).
- [ ] **No Cross-Feature Edits:** I did not edit, rename, move, or delete any other team member's feature files.
- [ ] **Shared Infrastructure Unchanged:** I did not modify shared infrastructure (`app.py`, `config.py`, `database/`, `services/`, `ml_engine.py`, or `base.html`) without prior written approval.
- [ ] **No Secrets Committed:** I confirmed that `.env`, passwords, API keys, and temporary tokens are NOT staged or committed (`git status` and `git diff` checked).
- [ ] **No Unrelated Files:** No build artifacts, `.DS_Store`, cache directories (`__pycache__`), or virtual environment files are included in this PR.

### Functional & UI Verification
- [ ] **Application Starts:** The Flask app launches cleanly with `python3 app.py` without syntax errors or broken imports.
- [ ] **Feature Works:** My assigned feature works end-to-end as intended.
- [ ] **Routes Tested:** All HTTP routes and view functions for my feature were tested locally.
- [ ] **HTML & Templates:** My templates extend `base.html` properly and render without Jinja errors.
- [ ] **CSS & Styling:** My feature's specific stylesheet loads properly and matches the design system.
- [ ] **JavaScript Interactions:** My feature's JavaScript executes without browser console errors.
- [ ] **Synced with Main:** I merged `origin/main` into my local branch prior to opening this PR and resolved any conflicts in my own files.
```

---

## Instructions for Submission
1. Copy the Markdown code block above.
2. Paste it into the description box when creating your Pull Request on GitHub.
3. Check each box by placing an `x` between the brackets: `[x]`.
4. Submit the Pull Request against the `main` branch.
5. Notify **K. Charankumar** (`0221168`) for review and merging.
