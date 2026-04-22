"""
Tenant-Aware Synonym Resolver — schema-driven synonym resolution.

No hardcoded column names. Instead, at runtime:
  1. Categorize every column in the schema by semantic meaning (regex patterns)
  2. Map user's vague terms (e.g., "basic info") to semantic categories
  3. Resolve categories → actual column names for this specific schema

This ensures the system works across tenants with wildly different column naming
conventions (e.g., "employee_first_name" vs "emp_fname" vs "given_name").
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ── Column semantic categories (regex patterns) ────────────────────────────

COLUMN_CATEGORIES: Dict[str, re.Pattern] = {
    "name": re.compile(
        r"(first.?name|last.?name|full.?name|employee.?name|emp.?name|"
        r"surname|given.?name|family.?name|middle.?name|display.?name|"
        r"person.?name|staff.?name|user.?name|personnel.?n[am]|"
        r"f.?name|l.?name|^name$)",
        re.IGNORECASE,
    ),
    "id": re.compile(
        r"(^id$|_id$|^pk$|employee.?id|emp.?id|staff.?id|user.?id|"
        r"person.?id|record.?id|serial|badge)",
        re.IGNORECASE,
    ),
    "email": re.compile(
        r"(e.?mail|email.?address|mail|contact.?email)",
        re.IGNORECASE,
    ),
    "phone": re.compile(
        r"(phone|mobile|cell|tel|contact.?number|phone.?number|"
        r"mobile.?number|fax)",
        re.IGNORECASE,
    ),
    "address": re.compile(
        r"(address|street|city|state|country|zip|postal|location|"
        r"region|province|district|area|residence)",
        re.IGNORECASE,
    ),
    "salary": re.compile(
        r"(salary|wage|pay|compensation|earnings|rate|income|"
        r"base.?pay|gross.?pay|net.?pay|ctc|annual.?pay)",
        re.IGNORECASE,
    ),
    "department": re.compile(
        r"(dept|department|division|unit|team|group|section|branch|"
        r"department.?name|dept.?name)",
        re.IGNORECASE,
    ),
    "date": re.compile(
        r"(date|created|updated|modified|hired|joined|timestamp|"
        r"_at$|_on$|birth|dob|start.?date|end.?date|join.?date|"
        r"hire.?date|termination|effective)",
        re.IGNORECASE,
    ),
    "status": re.compile(
        r"(status|state|active|enabled|flag|is_.+|has_.+|"
        r"employment.?status|current.?status)",
        re.IGNORECASE,
    ),
    "title": re.compile(
        r"(title|designation|position|role|job.?title|rank|grade)",
        re.IGNORECASE,
    ),
    "gender": re.compile(
        r"(gender|sex|salutation|prefix|mr|mrs)",
        re.IGNORECASE,
    ),
    "age": re.compile(
        r"(age|birth.?date|dob|date.?of.?birth|years)",
        re.IGNORECASE,
    ),
}


# ── User intent → column category mapping ──────────────────────────────────

INTENT_EXPANSIONS: Dict[str, List[str]] = {
    # Basic / Overview
    "basic info": ["name", "id"],
    "basic information": ["name", "id"],
    "overview": ["name", "id", "department", "status"],
    # Contact
    "contact info": ["name", "email", "phone", "address"],
    "contact information": ["name", "email", "phone", "address"],
    "contact details": ["name", "email", "phone", "address"],
    # Personal
    "personal info": ["name", "email", "phone", "gender", "age"],
    "personal information": ["name", "email", "phone", "gender", "age"],
    "personal details": ["name", "email", "phone", "gender", "age"],
    # Employment
    "employee details": ["*"],
    "employment info": ["name", "department", "title", "date", "status"],
    "employment details": ["name", "department", "title", "date", "status"],
    "job info": ["name", "title", "department"],
    "job details": ["name", "title", "department"],
    # Financial
    "salary info": ["name", "salary", "department"],
    "salary details": ["name", "salary", "department"],
    "pay info": ["name", "salary"],
    "compensation": ["name", "salary"],
    # Catch-all
    "names": ["name"],
    "details": ["*"],
    "all data": ["*"],
    "full data": ["*"],
    "full details": ["*"],
    "everything": ["*"],
    "all info": ["*"],
    "all information": ["*"],
}


@dataclass
class ResolvedQuery:
    """Result of synonym resolution."""
    original_query: str
    expanded_query: str
    resolved_columns: List[str]       # Actual column names from schema
    categories_matched: List[str]     # Semantic categories that matched
    is_select_all: bool = False       # True when "*" expansion triggered
    schema_table_hint: Optional[str] = None  # Suggested primary table


def _col_name(col: Any) -> str:
    """Extract column name from either a dict or a plain string."""
    if isinstance(col, dict):
        return col.get("name", "")
    return str(col)


class TenantAwareSynonymResolver:
    """
    Schema-driven synonym resolution — no static column name dictionaries.

    At runtime, introspects the live schema to resolve vague user terms
    into concrete column names that actually exist in the database.
    """

    def resolve(self, query: str, schema: Dict[str, Any]) -> ResolvedQuery:
        """
        Resolve vague terms in the user query to concrete column names.

        Args:
            query:  The user's natural language query.
            schema: The database schema dict {table_name: {columns: [...]}}.

        Returns:
            ResolvedQuery with concrete column names and expanded query.
        """
        query_lower = query.lower().strip()

        # 1. Categorize all columns in the schema
        column_map = self._categorize_columns(schema)

        # 2. Check for intent expansion matches
        matched_categories: List[str] = []
        is_select_all = False

        for phrase, categories in INTENT_EXPANSIONS.items():
            if phrase in query_lower:
                if "*" in categories:
                    is_select_all = True
                    matched_categories = ["*"]
                else:
                    matched_categories.extend(categories)
                break  # First match wins (most specific should be listed first)

        # 3. Resolve categories → actual column names
        resolved_columns: List[str] = []
        if is_select_all:
            # All columns across all tables
            for table_info in schema.values():
                for col in table_info.get("columns", []):
                    cn = _col_name(col)
                    if cn and cn not in resolved_columns:
                        resolved_columns.append(cn)
        elif matched_categories:
            # Specific categories → resolve to actual column names
            seen: Set[str] = set()
            for category in matched_categories:
                for col_name in column_map.get(category, []):
                    if col_name not in seen:
                        resolved_columns.append(col_name)
                        seen.add(col_name)

        # 4. Build expanded query
        expanded_query = query
        if resolved_columns and not is_select_all:
            col_list = ", ".join(resolved_columns)
            expanded_query = (
                f"{query} (USE THESE SPECIFIC COLUMNS: {col_list})"
            )

        # 5. Detect best table hint
        table_hint = self._find_best_table(query_lower, schema)

        return ResolvedQuery(
            original_query=query,
            expanded_query=expanded_query,
            resolved_columns=resolved_columns,
            categories_matched=list(set(matched_categories)),
            is_select_all=is_select_all,
            schema_table_hint=table_hint,
        )

    def _categorize_columns(self, schema: Dict[str, Any]) -> Dict[str, List[str]]:
        """
        Classify every column in the schema by semantic category using regex.

        Returns:
            Dict mapping category name → list of actual column names.
            e.g., {"name": ["employee_first_name", "employee_last_name"], ...}
        """
        category_map: Dict[str, List[str]] = {cat: [] for cat in COLUMN_CATEGORIES}

        for table_info in schema.values():
            for col in table_info.get("columns", []):
                cn = _col_name(col)
                if not cn:
                    continue
                for category, pattern in COLUMN_CATEGORIES.items():
                    if pattern.search(cn):
                        if cn not in category_map[category]:
                            category_map[category].append(cn)
                        break  # First category match wins per column

        return category_map

    def _find_best_table(self, query_lower: str, schema: Dict[str, Any]) -> Optional[str]:
        """
        Heuristically determine the most relevant table for the query.
        Uses keyword matching against table names.
        """
        # Common entity keywords and their table patterns
        entity_keywords = {
            "employee": ["employee", "emp", "staff", "personnel", "worker"],
            "attendance": ["attendance", "checkin", "timesheet", "presence"],
            "department": ["department", "dept", "division", "unit"],
            "salary": ["salary", "payroll", "wage", "compensation"],
            "leave": ["leave", "vacation", "time_off", "absence"],
            "customer": ["customer", "client", "buyer"],
            "order": ["order", "purchase", "sale"],
            "product": ["product", "item", "goods", "merchandise"],
            "student": ["student", "learner", "pupil"],
            "patient": ["patient", "admit"],
        }

        for entity, patterns in entity_keywords.items():
            if any(p in query_lower for p in patterns):
                # Find the table that matches
                for table_name in schema:
                    table_lower = table_name.lower()
                    if any(p in table_lower for p in patterns):
                        return table_name

        return None
