"""
Hardcoded table metadata for the initial in-memory implementation.
"""

TABLE_METADATA = [
    {
        "table_name": "employee_employee",
        "columns": ["id", "first_name", "last_name", "department"],
        "description": "stores employee personal and professional details",
        "synonyms": ["employee", "staff", "person", "worker"]
    },
    {
        "table_name": "attendance_attendance",
        "columns": ["employee_id", "attendance_date", "hours"],
        "description": "stores employee attendance and working hours",
        "synonyms": ["attendance", "login", "working hours", "presence"]
    }
]
