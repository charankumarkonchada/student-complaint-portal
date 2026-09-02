# IntelliHostel — Modular Multi-Contributor Complaint Portal

An enterprise-grade, AI-assisted Student Hostel Complaint Management System designed for RGUKT. Restructured into a clean, modular 6-member team architecture operating under a **File-Distribution + Admin-Integration** workflow.

---

## 👥 Team 15 Member Assignments & Ownership

| Team Member | ID | Role / Module Ownership | Assigned Feature Folders |
| :--- | :--- | :--- | :--- |
| **R. Charan Kumar** | `0210894` | Admin Login, Admin Logout, Manage Complaints, Update Status, 404 Error Page | `routes/charan/`<br>`templates/charan/`<br>`static/css/charan/`<br>`static/js/charan/` |
| **K. Charankumar** | `0221168` | Admin Dashboard, Analytics Dashboard, Export Reports (PDF/Excel), **Project Admin & Integration Owner** | `routes/charankumar/`<br>`templates/charankumar/`<br>`static/css/charankumar/`<br>`static/js/charankumar/`<br>+ Shared Infrastructure |
| **B. Jagan** | `0221078` | Home Page, Add Complaint, Complaint History, View Complaint Details | `routes/jagan/`<br>`templates/jagan/`<br>`static/css/jagan/`<br>`static/js/jagan/` |
| **M. Raghunitha** | `0220917` | Student Registration, Edit Complaint, Delete Complaint, Student Profile | `routes/raghunitha/`<br>`templates/raghunitha/`<br>`static/css/raghunitha/`<br>`static/js/raghunitha/` |
| **K. Deepthi** | `0220836` | Student Login, Logout, Forgot Password, OTP Verification, Reset Password, Change Password, Notifications | `routes/deepthi/`<br>`templates/deepthi/`<br>`static/css/deepthi/`<br>`static/js/deepthi/` |
| **K. Vennela** | `0210785` | Student Dashboard, Recent Activity, 500 Server Error Page | `routes/vennela/`<br>`templates/vennela/`<br>`static/css/vennela/`<br>`static/js/vennela/` |

---

## 🔄 File-Distribution + Admin-Integration Workflow

Under this collaboration model:
1. **K. Charankumar distributes assigned files** to each collaborator from `TEAM_FILE_DISTRIBUTION/<MEMBER_NAME>/`.
2. Collaborators **modify only their assigned feature files** locally.
3. Collaborators do **not** push branches or open Pull Requests on GitHub.
4. Collaborators **return their completed files** to K. Charankumar.
5. K. Charankumar **copies the completed files into the main project**, runs safety checks, and creates **separate, dedicated Git commits** for each member on the `main` branch.

---

## 📚 Team Documentation Directory

| Guide | Purpose | Primary Audience |
| :--- | :--- | :--- |
| [MEMBER_FILE_INSTRUCTIONS.md](MEMBER_FILE_INSTRUCTIONS.md) | Simple instructions for members receiving, modifying, and returning their assigned files. | Team Collaborators |
| [ADMIN_FILE_INTEGRATION_GUIDE.md](ADMIN_FILE_INTEGRATION_GUIDE.md) | Step-by-step instructions for Charankumar to copy, test, and commit each member's files separately. | K. Charankumar (Admin) |
| [TEAM_OWNERSHIP.md](TEAM_OWNERSHIP.md) | Definitive feature assignment, directory ownership, and commit message matrix. | All Team Members |
| [SHARED_FILES.md](SHARED_FILES.md) | Full registry of shared infrastructure files owned exclusively by K. Charankumar. | All Team Members |
| [RUN_PROJECT.md](RUN_PROJECT.md) | Local environment setup, dependencies, `.env` config, database setup, and startup. | All Team Members |

---

## 🚀 Running the Project Locally

```bash
# 1. Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env

# 4. Initialize database
python3 database/create_db.py

# 5. Launch server
python3 app.py
```
Open `http://127.0.0.1:5000` in your web browser.
