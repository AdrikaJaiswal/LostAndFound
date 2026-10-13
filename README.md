# Lost & Found Management System

A secure, role-based web application designed to streamline the reporting, tracking, claim verification, and return lifecycle of lost items across campus.

---

## Project Overview:

Managing lost property on campus often relies on disorganized bulletin boards or informal messaging channels. This project provides a centralized, authenticated platform with Role-Based Access Control (RBAC) connecting Students, Faculty, and Administrators through a structured workflow: **Report → Search → Claim → Faculty Verification → Secure Return**.

---

## Key Features & Architectural Modules:

### 1. Authentication, Security & Core Backend
* **11-Table Relational Schema:** Built on PostgreSQL (Supabase) with foreign keys, constraints, and optimized composite B-Tree indexes.
* **Bcrypt Password Hashing:** Salted password encryption ensuring credentials are never stored in plain text.
* **Role-Based Access Control (RBAC):** Custom decorators (`@login_required`, `@role_required`) protecting administrative and faculty verification routes.
* **Media & File Validation:** Enforces MIME/header integrity, a 5 MB file cap, and a 5-image upload maximum using Pillow.
* **Notification Engine:** Dispatches automated updates across status changes and claim reviews.

### 2. Student & Public Module
* Public-facing landing pages (Home, About, Contact).
* Item reporting interface (`upload.html`) supporting multi-image uploads.
* Student dashboard to track personal reports, claims, and status updates.
* Claim submission modal collecting ownership descriptions and verification details.

### 3. Faculty Verification Module
* Multi-parameter Smart Search (filter by category, location, status, and date).
* Item detail views with claim review queues.
* Faculty claim approval and rejection workflows.
* Formal return logging capturing receiver registration number, phone, academic programme, and optional notes.

The Faculty/Admin portal is available at `/api/faculty/portal` after login. It
uses the existing Flask session and Faculty/Admin role guard for its pages and
data endpoints. Receiver details are entered at handover and are not
independently verified by the form; the source and verification policy for
academic programme still require team confirmation. Return recording depends
on approval and deployment of the separate database migration and its
least-privilege RPC permission decision. Competing claims are not automatically
changed when an item is returned.

### 4. Admin, Analytics & Reporting Module
* Administrative control panel for user and category management.
* Visual metrics dashboards (e.g., monthly item trends, return rates).
* System activity logs tracking key platform actions for data auditability.
* CSV/PDF report generation for system audits and analytics.

---

## Database Architecture:

The system utilizes an 11-table relational schema designed in 3NF:
1. `roles` (Student, Faculty, Admin)
2. `users` (User profiles & salted password hashes)
3. `categories` (Item classification)
4. `locations` (Campus buildings and zones)
5. `items` (Reported lost and found items)
6. `item_images` (Media attachments per item)
7. `claims` (Item ownership claims & proof)
8. `returned_items` (Faculty-verified return audit logs)
9. `notifications` (User status change alerts)
10. `announcements` (Campus-wide broadcasts)
11. `activity_logs` (System administrative audit trail)

---

## Tech Stack:

* **Backend:** Python, Flask
* **Database:** PostgreSQL (Supabase)
* **Security & Auth:** Bcrypt, Flask Sessions, Custom RBAC Decorators
* **File Processing:** Pillow (PIL)
* **Frontend:** HTML5, CSS3, JavaScript, Bootstrap

---

## Getting Started

### 1. Prerequisites
* Python 3.10+ installed
* Git installed

### 2. Clone the Repository
```bash
git clone https://github.com/AdrikaJaiswal/LostAndFound.git
cd LostAndFound
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory:
```env
SUPABASE_URL="your-supabase-url"
SUPABASE_KEY="your-supabase-anon-key"
SECRET_KEY="your-flask-secret-key"
```

### 5. Run the Application
```bash
py -3 app.py
```
Open http://127.0.0.1:5000. After signing in with a Faculty or Admin account,
open http://127.0.0.1:5000/api/faculty/portal for claim review, smart search,
return recording, and return history.

### 6. Run the Tests
```bash
py -3 -m unittest discover -s tests -v
```

The Faculty route tests mock Supabase and do not validate database permissions
or PostgreSQL behavior. The return workflow migration in
`database/migrations/20261013_001_record_item_return.sql` is a draft only.
Before enabling return recording, review the permission and credential
decisions in `database/migrations/README.md` and test the migration against a
disposable local Supabase/PostgreSQL instance. Do not use a shared database
for the initial integration test. The portal records receiver details as
entered; claimant identity and academic programme provenance have not been
independently verified. Other claims are not automatically changed after a
return.

---

## Git & Branching Strategy

* `main`: Protected production-ready branch.
* Feature Branches: Team members work on descriptive feature branches and merge via Pull Requests:
  * `feature/student-public-module`
  * `feature/faculty-verification`
  * `feature/admin-analytics`

---

## Team Roles & Responsibilities

| Role | Module | Focus Area |
| :--- | :--- | :--- |
| Adrika Jaiswal(Project Lead) | Backend Core & Database | DB Architecture, Auth, Sessions, RBAC Decorators, Media/Notification Services |
| Shruthika Santhosh | Student & Public Module | Base Layouts, Upload Form, Claim Submission, Student Dashboard |
| Prithvi Vijay | Faculty & Verification | Smart Search, Claim Approvals, Return Verification Logging |
| Kashish Arora | Admin & Analytics | Dashboards, Category/User Management, Activity Logs, CSV/PDF Reports |
