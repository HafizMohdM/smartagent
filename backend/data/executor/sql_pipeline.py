"""
Schema-Aware SQL Pipeline — the central AI Decision System.

Replaces all inline SQL logic with a single, structured pipeline:

  User Input → Intent Classification → Synonym Expansion → Schema Mapping
  → SQL Generation → Column Validation → Execution → Auto-Repair → Chart-Safe Output

Both DatabaseTool (single-DB) and MultiDBQueryOrchestrator (multi-DB)
delegate to this pipeline instead of maintaining their own SQL logic.
"""

import logging
import time
import asyncio
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple, Set

from backend.data.executor.intent_classifier import HybridIntentClassifier, Intent
from backend.data.executor.synonym_resolver import TenantAwareSynonymResolver, ResolvedQuery
from backend.data.executor.column_resolver import EmbeddingColumnResolver
from backend.data.executor.column_validator import ColumnValidator
from backend.data.executor.domain_detector import DomainDetector
from backend.data.executor.chart_enforcer import ChartSafeEnforcer, ChartReadyData
from backend.data.executor.generator import SQLGenerator, normalize_query, remove_limit
from backend.data.executor.validator import SQLValidator
from backend.data.executor.executor import SQLExecutor
from backend.agent.utils.sql_parser import SQLParser
from backend.rag.embeddings.service import EmbeddingService

from backend.data.executor.contract import validate_db_result, get_error_fallback

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

MAX_REPAIR_RETRIES = 2
_INTENT_LLM_THRESHOLD = 0.7
PER_DB_TIMEOUT = 5.0
MAX_FALLBACK_COLUMNS = 5

# Security Patterns
SAFE_PATTERNS = ["id", "name", "email", "status", "created", "first", "last"]
SENSITIVE_PATTERNS = ["salary", "ssn", "phone", "mobile", "dob", "aadhaar", "tax", "contact", "birth"]

# ── Output contracts ────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    """Strict output contract for the SQL pipeline."""
    success: bool
    intent: str
    sql: Optional[str] = None
    rows: List[Dict[str, Any]] = field(default_factory=list)
    columns: List[str] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)
    chart_ready: Optional[ChartReadyData] = None
    error_message: Optional[str] = None
    domain: str = "generic"
    repairs_applied: int = 0
    is_fallback: bool = False

    def to_tool_data(self) -> Dict[str, Any]:
        return {"rows": self.rows, "columns": self.columns, "meta": self.meta}

def _safe_error(raw_error: str) -> str:
    error_str = str(raw_error).upper()
    if "UNDEFINEDTABLE" in error_str: return "The requested table does not exist."
    if "UNDEFINEDCOLUMN" in error_str: return "One or more columns do not match the database schema."
    if "TIMEOUT" in error_str: return "The query took too long to execute (limit: 5s)."
    return "An error occurred while processing your request. Please try rephrasing."

def _normalize_term(term: str) -> str:
    return term.lower().replace("_", "").replace(" ", "")

def _is_sensitive(col: str) -> bool:
    norm = _normalize_term(col)
    return any(p in norm for p in SENSITIVE_PATTERNS)

def _is_safe(col: str) -> bool:
    norm = _normalize_term(col)
    return any(p in norm for p in SAFE_PATTERNS)

# ── Pipeline ────────────────────────────────────────────────────────────────

class SchemaAwareSQLPipeline:
    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        self._generator = SQLGenerator()
        self._syntax_validator = SQLValidator()
        self._column_validator = ColumnValidator()
        self._intent_classifier = HybridIntentClassifier()
        self._synonym_resolver = TenantAwareSynonymResolver()
        self._embedding_service = embedding_service
        self._column_resolver = EmbeddingColumnResolver(embedding_service)
        self._domain_detector = DomainDetector()
        self._chart_enforcer = ChartSafeEnforcer()

    async def run(
        self,
        query: str,
        schema: Dict[str, Any],
        connector: Any,
        connection_id: Optional[str] = None,
        report_mode: bool = False,
        db_name: Optional[str] = None,
        all_db_names: Optional[List[str]] = None,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        t0 = time.monotonic()
        ctx = trace_context or {}
        telemetry: Dict[str, Any] = {"pipeline_start": time.time(), "db_name": db_name, **ctx}

        # 1. Intent & Domain
        intent, confidence = self._intent_classifier.classify(query)
        if confidence < _INTENT_LLM_THRESHOLD:
            try: intent, _ = await self._intent_classifier.classify_async(query)
            except Exception: pass
        
        domain, _ = self._domain_detector.detect(schema)
        telemetry["intent"] = intent.value
        telemetry["domain"] = domain.value

        # 2. Handlers for Non-SQL intents
        if intent == Intent.METADATA: return self._handle_metadata(schema, domain, telemetry, t0)
        if intent == Intent.LOOKUP: return self._handle_lookup(query, schema, domain, telemetry, t0)

        # 3. SQL Generation
        resolved = self._synonym_resolver.resolve(normalize_query(query), schema)
        try:
            sql_raw = await self._generator.generate(
                user_query=resolved.expanded_query,
                schema=schema,
                connection_id=connection_id,
                report_mode=report_mode,
                db_name=db_name,
                domain_hint=self._domain_detector.get_domain_hints(domain),
                resolved_columns_hint="\n".join([f"- {c}" for c in resolved.resolved_columns])
            )
        except Exception as e:
            return await self._handle_pipeline_failure(query, schema, connector, intent, domain, telemetry, t0, str(e))

        # 4. Extraction & Validation
        pure_sql = SQLParser.extract_sql(sql_raw)
        if not pure_sql:
            return await self._handle_pipeline_failure(query, schema, connector, intent, domain, telemetry, t0, "No SQL extracted")

        # 5. Schema-Level Validation (sqlglot)
        is_safe, safety_reason = self._syntax_validator.validate(pure_sql)
        is_valid, schema_reason = self._syntax_validator.validate_schema(pure_sql, schema)
        
        if not is_safe or not is_valid:
            logger.warning(f"[Pipeline] Validation failed: {safety_reason if not is_safe else schema_reason}")
            return await self._handle_pipeline_failure(query, schema, connector, intent, domain, telemetry, t0, schema_reason)

        # 6. Execute with Repair
        return await self._execute_with_repair(
            sql=pure_sql, schema=schema, connector=connector, 
            user_query=query, intent=intent, domain=domain, 
            report_mode=report_mode, telemetry=telemetry, t0=t0, db_name=db_name,
            connection_id=connection_id
        )

    async def _execute_with_repair(self, **kwargs) -> PipelineResult:
        sql = kwargs['sql']
        schema = kwargs['schema']
        connector = kwargs['connector']
        telemetry = kwargs['telemetry']
        t0 = kwargs['t0']
        
        executor = SQLExecutor(connector)
        seen_sql = {hashlib.md5(sql.encode()).hexdigest()}
        current_sql = SQLParser.ensure_limit(sql)
        repairs = 0

        for attempt in range(1 + MAX_REPAIR_RETRIES):
            try:
                # Execution with timeout
                result = await asyncio.wait_for(
                    executor.execute(current_sql, trace_context=telemetry),
                    timeout=PER_DB_TIMEOUT
                )
                
                rows = result.get("rows", [])
                cols = result.get("columns", [])
                
                # Tag results for Multi-DB merging
                if kwargs.get("db_name"):
                    for r in rows: r["_source_db"] = kwargs["db_name"]
                
                return PipelineResult(
                    success=True, intent=kwargs['intent'].value, sql=current_sql,
                    rows=rows, columns=cols, domain=kwargs['domain'].value,
                    meta=self._finalize_telemetry(telemetry, t0), repairs_applied=repairs
                )

            except Exception as e:
                logger.warning(f"[Pipeline] Attempt {attempt+1} failed: {e}")
                repairs += 1
                if attempt >= MAX_REPAIR_RETRIES: break
                
                # Repair logic
                try:
                    repaired_raw = await self._generator.generate(
                        user_query=kwargs['user_query'],
                        schema=schema,
                        connection_id=kwargs.get('connection_id'),
                        error_context=str(e),
                        report_mode=kwargs['report_mode'],
                        db_name=kwargs.get('db_name')
                    )
                    repaired_sql = SQLParser.extract_sql(repaired_raw)
                    if repaired_sql:
                        h = hashlib.md5(repaired_sql.encode()).hexdigest()
                        if h not in seen_sql:
                            seen_sql.add(h)
                            current_sql = SQLParser.ensure_limit(repaired_sql)
                            continue
                except Exception: pass

        # Fallback Trigger
        return await self._handle_pipeline_failure(
            kwargs['user_query'], schema, connector, kwargs['intent'], 
            kwargs['domain'], telemetry, t0, "Repair exhausted"
        )

    async def _handle_pipeline_failure(self, query, schema, connector, intent, domain, telemetry, t0, error) -> PipelineResult:
        """Deterministic Safe Fallback Implementation."""
        logger.info(f"[Pipeline] Triggering safe fallback due to: {error}")
        
        best_table = await SQLParser.select_best_table(query, schema, self._embedding_service)
        if not best_table:
            return PipelineResult(success=False, intent=intent.value, error_message=_safe_error(error), meta=self._finalize_telemetry(telemetry, t0))
        
        # Safe Column Selection (Strict SENSITIVE-FIRST)
        table_cols = [c.get("name") if isinstance(c, dict) else str(c) for c in schema[best_table].get("columns", [])]
        safe_cols = []
        for c in table_cols:
            if _is_sensitive(c): continue
            if _is_safe(c): safe_cols.append(c)
            if len(safe_cols) >= MAX_FALLBACK_COLUMNS: break
        
        if not safe_cols: safe_cols = [table_cols[0]] # Absolute minimum

        cols_str = ", ".join(safe_cols)
        fallback_sql = f"SELECT {cols_str} FROM {best_table} LIMIT 50"
        
        # Security Assertion
        assert "*" not in fallback_sql, "Security Breach: SELECT * detected in fallback!"
        
        try:
            executor = SQLExecutor(connector)
            result = await executor.execute(fallback_sql)
            rows = result["rows"]
            cols = result["columns"]
            
            # Source tagging
            if telemetry.get("db_name"):
                for r in rows: r["_source_db"] = telemetry["db_name"]

            return PipelineResult(
                success=True, intent=intent.value, sql=fallback_sql,
                rows=rows, columns=cols, is_fallback=True,
                domain=domain.value, meta=self._finalize_telemetry(telemetry, t0)
            )
        except Exception as e:
            return PipelineResult(success=False, intent=intent.value, error_message=_safe_error(e), meta=self._finalize_telemetry(telemetry, t0))

    def _handle_metadata(self, schema, domain, telemetry, t0):
        rows = [{"table_name": t} for t in sorted(schema.keys())]
        return PipelineResult(success=True, intent="metadata", rows=rows, columns=["table_name"], domain=domain.value, meta=self._finalize_telemetry(telemetry, t0))

    def _handle_lookup(self, query, schema, domain, telemetry, t0):
        return PipelineResult(success=True, intent="lookup", rows=[], domain=domain.value, meta=self._finalize_telemetry(telemetry, t0))

    @staticmethod
    def _finalize_telemetry(telemetry, t0):
        telemetry["duration_ms"] = int((time.monotonic() - t0) * 1000)
        return telemetry


# ── Output contracts ────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    """
    Strict output contract for the SQL pipeline.
    All downstream consumers (DatabaseTool, MultiDB, chart node) read this.
    """
    success: bool
    intent: str                                    # metadata | lookup | data_query | etc.
    sql: Optional[str] = None                      # Pure SQL if generated
    rows: List[Dict[str, Any]] = field(default_factory=list)  # Row data
    columns: List[str] = field(default_factory=list)          # Column names
    meta: Dict[str, Any] = field(default_factory=dict)        # Execution metadata
    chart_ready: Optional[ChartReadyData] = None   # Guaranteed chart-safe format
    error_message: Optional[str] = None            # User-safe error
    domain: str = "generic"                        # Detected business domain
    repairs_applied: int = 0                       # Number of auto-repairs

    def to_tool_data(self) -> Dict[str, Any]:
        """Convert to the strict contract format expected by DatabaseTool."""
        return {
            "rows": self.rows,
            "columns": self.columns,
            "meta": self.meta
        }

    def to_multi_db_format(self) -> Dict[str, Any]:
        """Convert to the strict contract format expected by MultiDBQueryOrchestrator."""
        return {
            "rows": self.rows,
            "columns": self.columns,
            "meta": self.meta
        }


# ── User-safe error messages ───────────────────────────────────────────────

_USER_ERROR_MAP = {
    "UndefinedTableError": "The requested table does not exist in this database.",
    "UndefinedColumn": "One or more columns in the query do not match the database schema.",
    "SyntaxError": "There was a syntax issue in the generated query. Please try rephrasing.",
    "PermissionDenied": "You do not have permission to access this data.",
    "ConnectionError": "Unable to connect to the database. Please check the connection.",
    "TimeoutError": "The query took too long to execute. Try a simpler request.",
}


def _safe_error(raw_error: str) -> str:
    """Convert raw database errors into user-friendly messages."""
    error_upper = str(raw_error).upper()
    for key, user_msg in _USER_ERROR_MAP.items():
        if key.upper() in error_upper:
            return user_msg
    # Fallback: generic message (never expose raw error)
    return "An error occurred while processing your request. Please try rephrasing your question."


# ── Pipeline ────────────────────────────────────────────────────────────────

class SchemaAwareSQLPipeline:
    """
    Central SQL intelligence — the AI Decision System.

    Replaces all inline SQL generation/validation/execution across
    DatabaseTool and MultiDBQueryOrchestrator.
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
    ):
        self._generator = SQLGenerator()
        self._syntax_validator = SQLValidator()
        self._column_validator = ColumnValidator()
        self._intent_classifier = HybridIntentClassifier()
        self._synonym_resolver = TenantAwareSynonymResolver()
        self._column_resolver = EmbeddingColumnResolver(embedding_service)
        self._domain_detector = DomainDetector()
        self._chart_enforcer = ChartSafeEnforcer()

    async def run(
        self,
        query: str,
        schema: Dict[str, Any],
        connector: Any,              # DatabaseConnector instance
        connection_id: Optional[str] = None,
        report_mode: bool = False,
        db_name: Optional[str] = None,
        all_db_names: Optional[List[str]] = None,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        Full pipeline execution with auto-repair and strict contract enforcement.

        Args:
            query:          Natural-language user query.
            schema:         Database schema dict {table_name: {columns: [...]}}.
            connector:      Connected DatabaseConnector instance.
            connection_id:  Connection UUID string.
            report_mode:    When True, strips LIMIT and favours aggregation.
            db_name:        Database name (for multi-DB context).
            all_db_names:   All selected database names (for multi-DB context).
            trace_context:  Request-level tracing (ids).

        Returns:
            PipelineResult with strict output schema.
        """
        t0 = time.monotonic()
        ctx = trace_context or {}
        telemetry: Dict[str, Any] = {
            "pipeline_start": time.time(),
            **ctx
        }

        # ── Step 1: Intent Classification ───────────────────────────────
        intent, confidence = self._intent_classifier.classify(query)
        telemetry["intent"] = intent.value
        telemetry["intent_confidence"] = confidence

        # Low-confidence: try async LLM classification
        if confidence < _INTENT_LLM_THRESHOLD:
            try:
                intent, confidence = await self._intent_classifier.classify_async(query)
                telemetry["intent"] = intent.value
                telemetry["intent_confidence"] = confidence
                telemetry["intent_source"] = "llm"
            except Exception as e:
                logger.warning(f"Async intent classification failed: {e}")
                telemetry["intent_source"] = "rules_fallback"
        else:
            telemetry["intent_source"] = "rules"

        logger.info(f"[Pipeline] Intent: {intent.value} (confidence={confidence:.2f})")

        # ── Step 2: Domain Detection ────────────────────────────────────
        domain, domain_confidence = self._domain_detector.detect(schema)
        domain_hints = self._domain_detector.get_domain_hints(domain)
        telemetry["domain"] = domain.value
        telemetry["domain_confidence"] = domain_confidence

        # ── Step 3: Handle non-SQL intents directly ─────────────────────
        if intent == Intent.METADATA:
            return self._handle_metadata(schema, domain, telemetry, t0)

        if intent == Intent.LOOKUP:
            return self._handle_lookup(query, schema, domain, telemetry, t0)

        if intent == Intent.CLARIFICATION:
            return PipelineResult(
                success=False,
                intent=intent.value,
                error_message=(
                    "I need more context to understand your request. "
                    "Could you provide more details about what data you're looking for?"
                ),
                domain=domain.value,
                meta=self._finalize_telemetry(telemetry, t0),
            )

        # ── Step 4: Synonym Resolution ──────────────────────────────────
        normalized_query = normalize_query(query)
        resolved = self._synonym_resolver.resolve(normalized_query, schema)
        telemetry["synonym_categories"] = resolved.categories_matched
        telemetry["synonym_columns_resolved"] = len(resolved.resolved_columns)

        enriched_query = resolved.expanded_query
        logger.info(
            f"[Pipeline] Synonym resolution: {len(resolved.resolved_columns)} "
            f"columns resolved, categories={resolved.categories_matched}"
        )

        # ── Step 5: SQL Generation ──────────────────────────────────────
        resolved_columns_hint = "\n".join([
            f"- {col_name}"
            for col_name in resolved.resolved_columns
        ]) if resolved.resolved_columns else "  (no specific column mappings resolved)"

        try:
            sql_raw = await self._generator.generate(
                user_query=enriched_query,
                schema=schema,
                connection_id=connection_id,
                report_mode=report_mode,
                db_name=db_name,
                all_db_names=all_db_names,
                domain_hint=domain_hints,
                resolved_columns_hint=resolved_columns_hint,
            )
        except Exception as e:
            logger.error(f"[Pipeline] SQL generation failed: {e}")
            return PipelineResult(
                success=False,
                intent=intent.value,
                error_message=_safe_error(str(e)),
                domain=domain.value,
                meta=self._finalize_telemetry(telemetry, t0),
            )

        # ── Step 6: Parse generator output ──────────────────────────────
        # Handle intent-based responses from the LLM
        upper_sql = sql_raw.lstrip().upper()

        if upper_sql.startswith("TYPE: METADATA") or upper_sql.startswith("TYPE: LOOKUP"):
            return self._handle_type_response(sql_raw, intent, domain, telemetry, t0)

        if upper_sql.startswith("TYPE: ERROR") or upper_sql.startswith("TYPE: CLARIFICATION"):
            parts = sql_raw.split("MESSAGE:") if "MESSAGE:" in sql_raw else sql_raw.split("DATA:")
            msg = parts[1].strip() if len(parts) > 1 else sql_raw.split('\n', 1)[-1].strip()
            return PipelineResult(
                success=False,
                intent="clarification",
                error_message=msg,
                domain=domain.value,
                meta=self._finalize_telemetry(telemetry, t0),
            )

        # Extract pure SQL
        pure_sql = SQLParser.extract_sql(sql_raw)
        if not pure_sql:
            return PipelineResult(
                success=False,
                intent=intent.value,
                error_message="I couldn't generate a valid query for your request. Please try rephrasing.",
                domain=domain.value,
                meta=self._finalize_telemetry(telemetry, t0),
            )

        # Report mode: strip LIMIT
        if report_mode:
            pure_sql = remove_limit(pure_sql)

        # ── Step 7: Syntax Validation ───────────────────────────────────
        is_valid, reason = self._syntax_validator.validate(pure_sql)
        if not is_valid:
            return PipelineResult(
                success=False,
                intent=intent.value,
                sql=pure_sql,
                error_message=f"Query validation failed: {reason}",
                domain=domain.value,
                meta=self._finalize_telemetry(telemetry, t0),
            )

        # ── Step 8: Column Validation ───────────────────────────────────
        col_validation = self._column_validator.validate(pure_sql, schema)
        telemetry["column_validation"] = {
            "is_valid": col_validation.is_valid,
            "missing": col_validation.missing_columns,
        }

        if not col_validation.is_valid:
            if col_validation.fixed_sql:
                logger.info(
                    f"[Pipeline] Column auto-fix applied: "
                    f"{col_validation.suggested_fixes}"
                )
                pure_sql = col_validation.fixed_sql
                telemetry["column_auto_fixed"] = True
            else:
                # Try embedding-based resolution for missing columns
                try:
                    for missing_col in col_validation.missing_columns:
                        resolved_col = await self._column_resolver.resolve_column(
                            missing_col, schema, connection_id
                        )
                        if resolved_col:
                            import re
                            pure_sql = re.sub(
                                rf'\b{re.escape(missing_col)}\b',
                                resolved_col,
                                pure_sql,
                                flags=re.IGNORECASE,
                             )
                            telemetry.setdefault("embedding_fixes", {})[missing_col] = resolved_col
                            logger.info(
                                f"[Pipeline] Embedding fix: '{missing_col}' → '{resolved_col}'"
                            )
                except Exception as e:
                    logger.warning(f"Embedding column resolution failed: {e}")

        # ── Step 9: Execute with Repair ─────────────────────────────────
        return await self._execute_with_repair(
            sql=pure_sql,
            schema=schema,
            connector=connector,
            connection_id=connection_id,
            user_query=enriched_query,
            intent=intent,
            domain=domain,
            report_mode=report_mode,
            telemetry=telemetry,
            t0=t0,
            db_name=db_name,
            all_db_names=all_db_names,
            trace_context=ctx,
        )

    # ── Core repair loop ────────────────────────────────────────────────

    async def _execute_with_repair(
        self,
        sql: str,
        schema: Dict[str, Any],
        connector: Any,
        connection_id: Optional[str],
        user_query: str,
        intent: Intent,
        domain: Any,
        report_mode: bool,
        telemetry: Dict[str, Any],
        t0: float,
        max_retries: int = MAX_REPAIR_RETRIES,
        db_name: Optional[str] = None,
        all_db_names: Optional[List[str]] = None,
        trace_context: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        The core execute-with-repair loop.
        """
        executor = SQLExecutor(connector)
        current_sql = sql
        repairs = 0
        ctx = trace_context or {}

        for attempt in range(1 + max_retries):
            try:
                # executor.execute now returns the strict contract
                result = await executor.execute(current_sql, trace_context=ctx)
                
                # If the executor returned a fallback (error in meta)
                if result["meta"].get("error"):
                    raise Exception(result["meta"]["error"])

                rows = result["rows"]
                columns = result["columns"]

                telemetry.update(result["meta"])
                telemetry["attempts"] = attempt + 1
                telemetry["repairs_applied"] = repairs

                # ── Chart-safe enforcement ──────────────────────────────
                chart_ready = None
                if rows and columns:
                    chart_ready = self._chart_enforcer.enforce(
                        rows=rows,
                        columns=columns,
                        chart_type="bar",  # Default
                    )

                return PipelineResult(
                    success=True,
                    intent=intent.value,
                    sql=current_sql,
                    rows=rows,
                    columns=columns,
                    meta=self._finalize_telemetry(telemetry, t0),
                    chart_ready=chart_ready,
                    domain=domain.value,
                    repairs_applied=repairs,
                )

            except Exception as exec_error:
                error_str = str(exec_error)
                logger.warning(
                    f"[Pipeline] Execution failed (attempt {attempt + 1}): {error_str}"
                )

                if attempt >= max_retries:
                    # Exhausted retries: Return a strict contract failure
                    return PipelineResult(
                        success=False,
                        intent=intent.value,
                        sql=current_sql,
                        error_message=_safe_error(error_str),
                        domain=domain.value,
                        repairs_applied=repairs,
                        meta=self._finalize_telemetry(telemetry, t0),
                    )

                # ── Repair: regenerate SQL with error context ───────────
                repairs += 1
                logger.info(
                    f"[Pipeline] Auto-repair attempt {repairs}/{max_retries}..."
                )

                # Construct hints for repair as well
                domain_hints = self._domain_detector.get_domain_hints(domain)
                resolved = self._synonym_resolver.resolve(user_query, schema)
                resolved_columns_hint = "\n".join([
                    f"- {col_name}"
                    for col_name in resolved.resolved_columns
                ]) if resolved.resolved_columns else ""

                try:
                    repaired_raw = await self._generator.generate(
                        user_query=user_query,
                        schema=schema,
                        connection_id=connection_id,
                        error_context=error_str,
                        report_mode=report_mode,
                        db_name=db_name,
                        all_db_names=all_db_names,
                        domain_hint=domain_hints,
                        resolved_columns_hint=resolved_columns_hint,
                    )
                    repaired_sql = SQLParser.extract_sql(repaired_raw)
                    if repaired_sql:
                        if report_mode:
                            repaired_sql = remove_limit(repaired_sql)

                        # Validate repaired SQL
                        is_valid, _ = self._syntax_validator.validate(repaired_sql)
                        if is_valid:
                            current_sql = repaired_sql
                            telemetry[f"repair_{repairs}_sql"] = repaired_sql
                            continue

                except Exception as repair_error:
                    logger.error(
                        f"[Pipeline] Repair generation failed: {repair_error}"
                    )

        # Should not reach here, but safety net
        return PipelineResult(
            success=False,
            intent=intent.value,
            sql=current_sql,
            error_message=_safe_error("Maximum retry limit reached."),
            domain=domain.value,
            repairs_applied=repairs,
            meta=self._finalize_telemetry(telemetry, t0),
        )

    # ── Intent handlers ─────────────────────────────────────────────────

    def _handle_metadata(
        self,
        schema: Dict[str, Any],
        domain: Any,
        telemetry: Dict[str, Any],
        t0: float,
    ) -> PipelineResult:
        """Handle METADATA intent: return list of tables."""
        tables = sorted(schema.keys())
        rows = [{"table_name": t} for t in tables]
        return PipelineResult(
            success=True,
            intent="metadata",
            rows=rows,
            columns=["table_name"],
            domain=domain.value,
            meta=self._finalize_telemetry(telemetry, t0),
        )

    def _handle_lookup(
        self,
        query: str,
        schema: Dict[str, Any],
        domain: Any,
        telemetry: Dict[str, Any],
        t0: float,
    ) -> PipelineResult:
        """Handle LOOKUP intent: find the best matching table."""
        query_lower = query.lower()
        best_table = None
        best_score = 0

        for table_name in schema:
            table_lower = table_name.lower()
            score = sum(1 for word in query_lower.split() if word in table_lower)
            if score > best_score:
                best_score = score
                best_table = table_name

        if best_table:
            cols = [
                _col_name(c)
                for c in schema[best_table].get("columns", [])
            ]
            rows = [{"table_name": best_table, "columns": ", ".join(cols)}]
        else:
            rows = [{"result": "No matching table found."}]

        return PipelineResult(
            success=True,
            intent="lookup",
            rows=rows,
            columns=list(rows[0].keys()) if rows else [],
            domain=domain.value,
            meta=self._finalize_telemetry(telemetry, t0),
        )

    def _handle_type_response(
        self,
        sql_raw: str,
        intent: Intent,
        domain: Any,
        telemetry: Dict[str, Any],
        t0: float,
    ) -> PipelineResult:
        """Handle TYPE: METADATA / TYPE: LOOKUP responses from the LLM."""
        parts = sql_raw.split("DATA:")
        items = []
        if len(parts) > 1:
            raw_items = parts[1].strip().split('\n')
            items = [item.strip("*- \t") for item in raw_items if item.strip()]

        rows = [{"Result": item} for item in items]
        return PipelineResult(
            success=True,
            intent=intent.value,
            rows=rows,
            columns=["Result"],
            domain=domain.value,
            meta=self._finalize_telemetry(telemetry, t0),
        )

    # ── Helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _finalize_telemetry(telemetry: Dict[str, Any], t0: float) -> Dict[str, Any]:
        """Add total pipeline duration and version to telemetry."""
        telemetry["pipeline_duration_ms"] = int((time.monotonic() - t0) * 1000)
        telemetry["version"] = "v1"
        return telemetry


def _col_name(col: Any) -> str:
    """Extract column name from either a dict or a plain string."""
    if isinstance(col, dict):
        return col.get("name", "")
    return str(col)
