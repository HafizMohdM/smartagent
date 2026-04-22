"""
Domain Detector — infers the business domain from schema table/column patterns.
Provides domain-specific hints to the SQL generator for more accurate query generation.

Supported domains: HR, Finance, Retail, Healthcare, Education, Generic.
"""

import logging
import re
from enum import Enum
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class Domain(Enum):
    HR = "hr"
    FINANCE = "finance"
    RETAIL = "retail"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    GENERIC = "generic"


# ── Domain signal definitions ───────────────────────────────────────────────

DOMAIN_SIGNALS: Dict[Domain, Dict[str, List[str]]] = {
    Domain.HR: {
        "tables": [
            "employee", "department", "attendance", "payroll", "leave",
            "salary", "designation", "shift", "overtime", "appraisal",
            "benefits", "onboarding", "offboarding", "personnel",
        ],
        "columns": [
            "hire_date", "designation", "reporting_to", "department_id",
            "employee_id", "emp_id", "leave_balance", "shift_id",
            "manager_id", "joining_date", "termination_date",
        ],
    },
    Domain.FINANCE: {
        "tables": [
            "transaction", "account", "ledger", "invoice", "payment",
            "budget", "expense", "revenue", "tax", "journal",
            "receivable", "payable", "asset", "liability",
        ],
        "columns": [
            "amount", "balance", "debit", "credit", "fiscal_year",
            "account_number", "transaction_date", "invoice_number",
            "tax_rate", "currency", "exchange_rate",
        ],
    },
    Domain.RETAIL: {
        "tables": [
            "product", "order", "customer", "inventory", "cart",
            "category", "supplier", "warehouse", "shipment",
            "promotion", "coupon", "wishlist", "review",
        ],
        "columns": [
            "sku", "unit_price", "quantity", "discount", "shipping",
            "order_date", "delivery_date", "stock_level",
            "reorder_point", "customer_id", "product_id",
        ],
    },
    Domain.HEALTHCARE: {
        "tables": [
            "patient", "diagnosis", "prescription", "appointment",
            "doctor", "ward", "lab_result", "treatment", "insurance",
            "pharmacy", "nurse", "medical_record",
        ],
        "columns": [
            "icd_code", "dosage", "blood_type", "admission_date",
            "discharge_date", "patient_id", "doctor_id",
            "diagnosis_code", "vital_signs", "allergy",
        ],
    },
    Domain.EDUCATION: {
        "tables": [
            "student", "course", "enrollment", "grade", "faculty",
            "semester", "classroom", "assignment", "exam",
            "scholarship", "curriculum", "attendance",
        ],
        "columns": [
            "gpa", "credit_hours", "enrollment_date", "major",
            "student_id", "course_id", "semester_id",
            "grade_point", "academic_year", "faculty_id",
        ],
    },
}


# ── Domain-specific SQL generation hints ────────────────────────────────────

DOMAIN_HINTS: Dict[Domain, str] = {
    Domain.HR: (
        "This is an HR/People database. "
        "For 'people' or 'staff' queries, prefer employee/personnel tables. "
        "For 'attendance' queries, look for attendance/timesheet tables. "
        "For salary queries, look for payroll/salary/compensation tables. "
        "Names are typically split into first_name/last_name columns."
    ),
    Domain.FINANCE: (
        "This is a Finance/Accounting database. "
        "For monetary queries, use SUM/AVG on amount/balance columns. "
        "For period queries, use fiscal_year or transaction_date. "
        "Debit/credit entries may need NET calculation (debit - credit)."
    ),
    Domain.RETAIL: (
        "This is a Retail/E-commerce database. "
        "For sales queries, join orders with products. "
        "For revenue, use SUM(unit_price * quantity). "
        "For inventory, check stock_level and reorder_point."
    ),
    Domain.HEALTHCARE: (
        "This is a Healthcare/Medical database. "
        "For patient queries, join patient with diagnosis/prescription. "
        "Use ICD codes for diagnosis categorization. "
        "Be careful with PHI (Protected Health Information) columns."
    ),
    Domain.EDUCATION: (
        "This is an Education/Academic database. "
        "For student performance, use GPA or grade tables. "
        "For enrollment queries, join student with course via enrollment. "
        "Academic periods are tracked by semester/academic_year."
    ),
    Domain.GENERIC: (
        "Business domain could not be determined from the schema. "
        "Use general best practices for SQL generation."
    ),
}


def _col_name(col: Any) -> str:
    """Extract column name from either a dict or a plain string."""
    if isinstance(col, dict):
        return col.get("name", "")
    return str(col)


class DomainDetector:
    """Infers business domain from schema table/column patterns."""

    def detect(self, schema: Dict[str, Any]) -> Tuple[Domain, float]:
        """
        Score each domain by signal frequency → return best match.

        Args:
            schema: Database schema dict {table_name: {columns: [...], ...}}

        Returns:
            Tuple of (detected_domain, confidence_score 0.0-1.0)
        """
        if not schema:
            return Domain.GENERIC, 0.0

        table_names_lower = {t.lower() for t in schema.keys()}
        all_columns_lower = set()
        for table_info in schema.values():
            for col in table_info.get("columns", []):
                all_columns_lower.add(_col_name(col).lower())

        scores: Dict[Domain, float] = {}

        for domain, signals in DOMAIN_SIGNALS.items():
            table_score = 0
            col_score = 0

            # Score table matches (weighted 2x)
            signal_tables = signals.get("tables", [])
            for sig_table in signal_tables:
                for actual_table in table_names_lower:
                    if sig_table in actual_table:
                        table_score += 2
                        break

            # Score column matches (weighted 1x)
            signal_cols = signals.get("columns", [])
            for sig_col in signal_cols:
                for actual_col in all_columns_lower:
                    if sig_col in actual_col or actual_col in sig_col:
                        col_score += 1
                        break

            total_signals = len(signal_tables) * 2 + len(signal_cols)
            raw_score = table_score + col_score
            scores[domain] = raw_score / total_signals if total_signals > 0 else 0.0

        if not scores:
            return Domain.GENERIC, 0.0

        best_domain = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_domain]

        # Require minimum 15% signal match to declare a domain
        if best_score < 0.15:
            logger.info(
                f"Domain detection: no strong match (best={best_domain.value}, "
                f"score={best_score:.2f}). Defaulting to GENERIC."
            )
            return Domain.GENERIC, best_score

        logger.info(
            f"Domain detected: {best_domain.value} (confidence={best_score:.2f})"
        )
        return best_domain, best_score

    def get_domain_hints(self, domain: Domain) -> str:
        """Return domain-specific SQL generation hints for prompt injection."""
        return DOMAIN_HINTS.get(domain, DOMAIN_HINTS[Domain.GENERIC])

    def detect_and_hint(self, schema: Dict[str, Any]) -> Tuple[Domain, str]:
        """Convenience: detect domain and return hints in one call."""
        domain, _ = self.detect(schema)
        return domain, self.get_domain_hints(domain)
