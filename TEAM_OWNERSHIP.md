# Team 15: Module Ownership & File Distribution Matrix

This document defines the strict feature assignment, directory ownership, and file distribution model for the **IntelliHostel Student Complaint Portal**.

---

## 1. Feature & Folder Ownership Table

| Member | ID | Features | Route Folder | Template Folder | CSS Folder | JS Folder | Shared Files |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **R. Charan Kumar** | `0210894` | • Admin Login<br>• Admin Logout<br>• Manage Complaints<br>• Update Status<br>• 404 Error Page | `routes/charan/` | `templates/charan/` | `static/css/charan/` | `static/js/charan/` | Read / Use only (Not distributed) |
| **K. Charankumar**<br>*(Project Admin & Integration Owner)* | `0221168` | • Admin Dashboard<br>• Analytics Dashboard<br>• Export Reports (PDF/Excel)<br>• **Central Integration & Infrastructure** | `routes/charankumar/` | `templates/charankumar/` | `static/css/charankumar/` | `static/js/charankumar/` | **Sole Owner & Maintainer** |
| **B. Jagan** | `0221078` | • Home Page<br>• Add Complaint<br>• Complaint History<br>• View Complaint Details | `routes/jagan/` | `templates/jagan/` | `static/css/jagan/` | `static/js/jagan/` | Read / Use only (Not distributed) |
| **M. Raghunitha** | `0220917` | • Student Registration<br>• Edit Complaint<br>• Delete Complaint<br>• Student Profile | `routes/raghunitha/` | `templates/raghunitha/` | `static/css/raghunitha/` | `static/js/raghunitha/` | Read / Use only (Not distributed) |
| **K. Deepthi** | `0220836` | • Student Login<br>• Student Logout<br>• Forgot Password<br>• Verify Reset OTP<br>• Reset Password<br>• Password Change<br>• Notifications | `routes/deepthi/` | `templates/deepthi/` | `static/css/deepthi/` | `static/js/deepthi/` | Read / Use only (Not distributed) |
| **K. Vennela** | `0210785` | • Student Dashboard<br>• Recent Activity<br>• 500 Error Page | `routes/vennela/` | `templates/vennela/` | `static/css/vennela/` | `static/js/vennela/` | Read / Use only (Not distributed) |

---

## 2. File Distribution & Admin Integration Model

Under this workflow:
1. **No Member Branches on GitHub:** Collaborators do not clone the repository, create branches, or open Pull Requests.
2. **Distribution Copies:** K. Charankumar distributes assigned files from `TEAM_FILE_DISTRIBUTION/<MEMBER_NAME>/`.
3. **Local Editing:** Collaborators edit only their assigned files locally and send them back to K. Charankumar.
4. **Integration & Separate Commits:** K. Charankumar copies the completed files into the main project and creates separate, distinct commits representing each member on the `main` branch.

---

## 3. Dedicated Commit Messages

| Member | Assigned Folders | Commit Message (Executed by K. Charankumar) |
| :--- | :--- | :--- |
| **R. Charan Kumar** | `routes/charan/`<br>`templates/charan/`<br>`static/css/charan/`<br>`static/js/charan/` | `feat(charan): integrate admin login and complaint management` |
| **B. Jagan** | `routes/jagan/`<br>`templates/jagan/`<br>`static/css/jagan/`<br>`static/js/jagan/` | `feat(jagan): integrate complaint submission and history features` |
| **M. Raghunitha** | `routes/raghunitha/`<br>`templates/raghunitha/`<br>`static/css/raghunitha/`<br>`static/js/raghunitha/` | `feat(raghunitha): integrate registration editing and profile features` |
| **K. Deepthi** | `routes/deepthi/`<br>`templates/deepthi/`<br>`static/css/deepthi/`<br>`static/js/deepthi/` | `feat(deepthi): integrate authentication password reset and notifications` |
| **K. Vennela** | `routes/vennela/`<br>`templates/vennela/`<br>`static/css/vennela/`<br>`static/js/vennela/` | `feat(vennela): integrate student dashboard and activity features` |
| **K. Charankumar** | `routes/charankumar/`<br>`templates/charankumar/`<br>`static/css/charankumar/`<br>`static/js/charankumar/`<br>+ Shared Infrastructure | `feat(admin): admin dashboard, analytics, exports and integration` |
