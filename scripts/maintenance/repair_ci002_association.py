"""
Maintenance Repair Script for Production Master Issue CI-002.

PURPOSE:
Associates the 3 existing I108 student complaints with Master Issue CI-002
("No Drinking Water in Room I108", assigned staff: Ramesh) and removes the
superseded auto-created CI-001 once empty.

DO NOT EXECUTE AUTOMATICALLY DURING TESTS.
Execute manually against production only after administrator review.
Usage:
    python scripts/maintenance/repair_ci002_association.py
"""
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.database.db import get_db_connection
from backend.services.common_issue_service import (
    associate_matching_complaints_to_master_issue,
    get_common_issue_with_stats,
    get_common_issue_complaints
)


def repair_ci002():
    conn = get_db_connection()
    try:
        ci2 = conn.execute("SELECT * FROM common_issues WHERE id = 2").fetchone()
        if not ci2:
            print("Master Issue CI-002 (id=2) not found in database.")
            return

        print(f"Repairing Master Issue #{ci2['id']} ({ci2.get('issue_code', 'CI-002')}): {ci2['title']}")
        print(f"Location: {ci2['hostel']}, Category: {ci2['category']}, Assigned: {ci2['assigned_to']}")

        linked_count = associate_matching_complaints_to_master_issue(2, conn)
        conn.commit()

        stats = get_common_issue_with_stats(2, conn)
        complaints = get_common_issue_complaints(2, conn)

        print(f"\nRepair completed successfully!")
        print(f"Total Linked Complaints: {stats['linked_complaints']}")
        print(f"Total Unique Students: {stats['affected_count']}")
        print("\nAssociated Complaints:")
        for c in complaints:
            print(f" - #{c['id']} | {c['student_name']} (Room: {c['student_room_no']}) | Status: {c['status']} | Assigned: {c['assigned_to']}")

    finally:
        conn.close()


if __name__ == "__main__":
    confirm = input("Are you sure you want to repair CI-002 associations in the active database? (yes/no): ").strip().lower()
    if confirm in {"yes", "y"}:
        repair_ci002()
    else:
        print("Repair canceled.")
