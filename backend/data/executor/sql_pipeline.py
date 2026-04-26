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
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from backend.data.executor.intent_classifier import HybridIntentClassifier, Intent
from backend.data.executor.synonym_resolver import TenantAwareSynonymResolver
from backend.data.executor.column_resolver import EmbeddingColumnResolver
from backend.data.executor.column_validator import ColumnValidator
from backend.data.executor.domain_detector import DomainDetector
from backend.data.executor.chart_enforcer import ChartSafeEnforcer, ChartReadyData
from backend.data.executor.generator import SQLGenerator, normalize_query, remove_limit
from backend.data.executor.validator import SQLValidator
from backend.data.executor.executor import SQLExecutor
from backend.agent.utils.sql_parser import SQLParser
from backend.rag.embeddings.service import EmbeddingService

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────────────

MAX_REPAIR_RETRIES = 2
_INTENT_LLM_THRESHOLD = 0.7
PER_DB_TIMEOUT = 5.0
MAX_FALLBACK_COLUMNS = 5

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
        tenant_id: Optional[str] = None,
        report_mode: bool = False,
        db_name: Optional[str] = None,
        all_db_names: Optional[List[str]] = None,
        trace_context: Optional[Dict[str, Any]] = None,
        semantic_context: str = "",
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

        # 3. Synonym Resolution
        normalized_query = normalize_query(query)
        resolved = self._synonym_resolver.resolve(normalized_query, schema)
        enriched_query = resolved.expanded_query

        # 4. SQL Generation
        resolved_columns_hint = "\n".join([f"- {c}" for c in resolved.resolved_columns])
        try:
            sql_raw = await self._generator.generate(
                user_query=enriched_query,
                schema=schema,
                tenant_id=tenant_id,
                connection_id=connection_id,
                report_mode=report_mode,
                db_name=db_name,
                all_db_names=all_db_names,
                domain_hint=self._domain_detector.get_domain_hints(domain),
                resolved_columns_hint=resolved_columns_hint,
                semantic_context=semantic_context,
            )
        except Exception as e:
            return PipelineResult(success=False, intent=intent.value, error_message=_safe_error(e), meta=self._finalize_telemetry(telemetry, t0))

        # 5. Extraction & Validation
        pure_sql = SQLParser.extract_sql(sql_raw)
        if not pure_sql:
            return PipelineResult(success=False, intent=intent.value, error_message="No SQL generated.", meta=self._finalize_telemetry(telemetry, t0))

        # 6. Syntax & Column Validation
        is_valid, reason = self._syntax_validator.validate(pure_sql)
        if not is_valid:
            return PipelineResult(success=False, intent=intent.value, sql=pure_sql, error_message=reason, meta=self._finalize_telemetry(telemetry, t0))

        col_validation = self._column_validator.validate(pure_sql, schema)
        if not col_validation.is_valid:
            if col_validation.fixed_sql:
                pure_sql = col_validation.fixed_sql
            else:
                # Try embedding fix
                for missing in col_validation.missing_columns:
                    resolved_col = await self._column_resolver.resolve_column(missing, schema, connection_id)
                    if resolved_col:
                        import re
                        pure_sql = re.sub(rf'\b{re.escape(missing)}\b', resolved_col, pure_sql, flags=re.IGNORECASE)

        # 7. Execute with Repair
        return await self._execute_with_repair(
            sql=pure_sql, schema=schema, connector=connector, 
            connection_id=connection_id, tenant_id=tenant_id,
            user_query=enriched_query, intent=intent, domain=domain, 
            report_mode=report_mode, telemetry=telemetry, t0=t0, db_name=db_name,
            all_db_names=all_db_names, trace_context=ctx
        )

    async def _execute_with_repair(self, **kwargs) -> PipelineResult:
        sql = kwargs['sql']
        schema = kwargs['schema']
        connector = kwargs['connector']
        telemetry = kwargs['telemetry']
        t0 = kwargs['t0']
        
        executor = SQLExecutor(connector)
        current_sql = sql
        repairs = 0

        for attempt in range(1 + MAX_REPAIR_RETRIES):
            try:
                result = await asyncio.wait_for(
                    executor.execute(current_sql, trace_context=telemetry),
                    timeout=PER_DB_TIMEOUT
                )
                
                rows = result.get("rows", [])
                cols = result.get("columns", [])
                
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
                
                try:
                    repaired_raw = await self._generator.generate(
                        user_query=kwargs['user_query'],
                        schema=schema,
                        tenant_id=kwargs.get('tenant_id'),
                        connection_id=kwargs.get('connection_id'),
                        error_context=str(e),
                        failed_sql=current_sql,
                        report_mode=kwargs['report_mode'],
                        db_name=kwargs.get('db_name')
                    )
                    repaired_sql = SQLParser.extract_sql(repaired_raw)
                    if repaired_sql:
                        current_sql = repaired_sql
                        continue
                except Exception: pass

        return PipelineResult(
            success=False, intent=kwargs['intent'].value, sql=current_sql,
            error_message=_safe_error("Query failed after repair attempts."),
            meta=self._finalize_telemetry(telemetry, t0)
        )

    def _handle_metadata(self, schema, domain, telemetry, t0):
        rows = [{"table_name": t} for t in sorted(schema.keys())]
        return PipelineResult(success=True, intent="metadata", rows=rows, columns=["table_name"], domain=domain.value, meta=self._finalize_telemetry(telemetry, t0))

    def _handle_lookup(self, query, schema, domain, telemetry, t0):
        return PipelineResult(success=True, intent="lookup", rows=[], domain=domain.value, meta=self._finalize_telemetry(telemetry, t0))

    @staticmethod
    def _finalize_telemetry(telemetry, t0):
        telemetry["duration_ms"] = int((time.monotonic() - t0) * 1000)
        return telemetry
