"""
Hybrid Intent Classifier — deterministic rule-based classification with LLM fallback.

Tier 1: Regex pattern matching (<1ms, handles 80%+ of queries)
Tier 2: LLM classification (for genuinely ambiguous queries)

Intents:
  METADATA     — "show tables", "list schemas"
  LOOKUP       — "which table has salary data"
  DATA_QUERY   — "show employees in dept 5"
  AGGREGATE    — "total sales by region", "how many employees"
  SEARCH       — "find John Smith"
  CLARIFICATION — ambiguous, need more context
"""

import logging
import re
from enum import Enum
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class Intent(Enum):
    METADATA = "metadata"
    LOOKUP = "lookup"
    DATA_QUERY = "data_query"
    AGGREGATE = "aggregate"
    SEARCH = "search"
    CLARIFICATION = "clarification"


# ── Tier 1: Deterministic rule patterns ─────────────────────────────────────

_RULE_PATTERNS = {
    Intent.METADATA: [
        re.compile(
            r"\b(show|list|what|display|describe|get)\s+(me\s+)?(all\s+)?"
            r"(the\s+)?(tables?|schema|database|columns?|fields?|structure)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\btables?\s+(in|for|of|available)\b", re.IGNORECASE),
        re.compile(r"\bwhat\s+(are|is)\s+(the\s+)?(tables?|schema)\b", re.IGNORECASE),
        re.compile(r"\bdescribe\s+(the\s+)?database\b", re.IGNORECASE),
    ],
    Intent.LOOKUP: [
        re.compile(r"\b(which|what)\s+table\s+(has|contains|stores?|holds?)\b", re.IGNORECASE),
        re.compile(r"\bfind\s+(the\s+)?table\s+(for|with|that)\b", re.IGNORECASE),
        re.compile(r"\bwhere\s+is\s+(\w+)\s+(stored|saved|kept)\b", re.IGNORECASE),
        re.compile(r"\btable\s+for\s+\w+\b", re.IGNORECASE),
    ],
    Intent.AGGREGATE: [
        re.compile(
            r"\b(count|total|sum|average|avg|how\s+many|breakdown|"
            r"distribution|per\s+\w+|group\s+by|statistics|stats|"
            r"percentage|percent|ratio|comparison|compare|trend)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b(top|bottom|highest|lowest|most|least|max|min)\s+\d*\b", re.IGNORECASE),
    ],
    Intent.SEARCH: [
        re.compile(
            r"\b(find|search|look\s*up|where\s+is|locate)\b.*"
            r"\b(named?|called|employee|person|user|staff|customer|patient|student)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(info|information|details?|data|record)\s+(for|of|about|on)\s+",
            re.IGNORECASE,
        ),
        re.compile(r"\bwho\s+(is|are)\b", re.IGNORECASE),
    ],
    Intent.DATA_QUERY: [
        re.compile(
            r"\b(show|get|fetch|display|list|give|retrieve|select|pull)\s+(me\s+)?"
            r"(all\s+)?(the\s+)?\w+\s*(from|in|of|for|where|with)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\b(all|every)\s+(employees?|records?|rows?|entries?|items?)\b", re.IGNORECASE),
        re.compile(
            r"\b(attendance|salary|leave|order|transaction|invoice|grade)\s+"
            r"(of|for|data|records?|report)\b",
            re.IGNORECASE,
        ),
    ],
}

# Priority ordering: METADATA > LOOKUP > AGGREGATE > SEARCH > DATA_QUERY
_PRIORITY_ORDER = [
    Intent.METADATA,
    Intent.LOOKUP,
    Intent.AGGREGATE,
    Intent.SEARCH,
    Intent.DATA_QUERY,
]

# ── Confidence thresholds ───────────────────────────────────────────────────

_RULE_CONFIDENCE = 0.90       # High confidence for rule matches
_LLM_FALLBACK_THRESHOLD = 0.7  # Below this, fall back to LLM


class HybridIntentClassifier:
    """Rule-based intent classification with LLM fallback for ambiguous queries."""

    def __init__(self):
        self._llm = None  # Lazy-loaded

    def classify(self, query: str) -> Tuple[Intent, float]:
        """
        Classify user query intent using deterministic rules.

        Returns:
            Tuple of (Intent, confidence_score 0.0-1.0)
        """
        if not query or not query.strip():
            return Intent.CLARIFICATION, 0.0

        query_clean = query.strip()

        # ── Tier 1: Rule-based classification ───────────────────────────
        matches = {}
        for intent in _PRIORITY_ORDER:
            patterns = _RULE_PATTERNS.get(intent, [])
            match_count = sum(1 for p in patterns if p.search(query_clean))
            if match_count > 0:
                # Score based on proportion of patterns matched
                matches[intent] = match_count / len(patterns) if patterns else 0

        if matches:
            best_intent = max(matches, key=matches.get)  # type: ignore[arg-type]
            pattern_score = matches[best_intent]
            # Scale confidence: 1 pattern match = 0.85, 2+ = 0.95
            confidence = min(_RULE_CONFIDENCE, 0.75 + pattern_score * 0.20)

            logger.debug(
                f"Intent classified (rules): {best_intent.value} "
                f"(confidence={confidence:.2f}, matches={matches})"
            )
            return best_intent, confidence

        # ── Heuristic: Name-only input (1-3 words, no intent verbs) ─────
        words = query_clean.split()
        if len(words) <= 3 and not self._has_intent_verb(query_clean):
            logger.debug(f"Intent classified (heuristic): SEARCH — name-only input")
            return Intent.SEARCH, 0.80

        # ── Tier 2: LLM fallback not used synchronously ─────────────────
        # For queries that don't match any pattern, default to DATA_QUERY
        # The LLM fallback is available via classify_async for complex cases
        logger.debug(
            f"Intent classified (fallback): DATA_QUERY — no strong pattern match"
        )
        return Intent.DATA_QUERY, 0.60

    async def classify_async(self, query: str) -> Tuple[Intent, float]:
        """
        Async classification: tries rules first, then LLM fallback.

        Use this for uncertain queries where the sync classifier returns
        low confidence (< 0.7).
        """
        intent, confidence = self.classify(query)

        if confidence >= _LLM_FALLBACK_THRESHOLD:
            return intent, confidence

        # ── LLM Fallback ────────────────────────────────────────────────
        try:
            llm_intent, llm_confidence = await self._llm_classify(query)
            logger.info(
                f"LLM intent override: {intent.value} → {llm_intent.value} "
                f"(confidence: {confidence:.2f} → {llm_confidence:.2f})"
            )
            return llm_intent, llm_confidence
        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}. Using rule result.")
            return intent, confidence

    async def _llm_classify(self, query: str) -> Tuple[Intent, float]:
        """LLM-based classification for ambiguous queries."""
        if self._llm is None:
            from langchain_openai import ChatOpenAI
            from pydantic import SecretStr
            from backend.config.settings import settings

            self._llm = ChatOpenAI(
                model=settings.LLM_MODEL,
                api_key=SecretStr(settings.OPENAI_API_KEY),
                temperature=0,
                max_tokens=50,
            )

        from langchain_core.messages import SystemMessage, HumanMessage

        prompt = (
            "Classify this database query intent into exactly ONE category:\n"
            "- METADATA: user wants to see table/schema information\n"
            "- LOOKUP: user wants to find which table contains something\n"
            "- AGGREGATE: user wants counts, sums, averages, trends, comparisons\n"
            "- SEARCH: user wants to find specific records by name/value\n"
            "- DATA_QUERY: user wants to retrieve/list data from tables\n"
            "- CLARIFICATION: query is too vague to understand\n\n"
            "Return ONLY the category name, nothing else."
        )

        response = await self._llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=query),
        ])

        raw = str(response.content).strip().upper()

        # Map response to Intent
        intent_map = {
            "METADATA": Intent.METADATA,
            "LOOKUP": Intent.LOOKUP,
            "AGGREGATE": Intent.AGGREGATE,
            "SEARCH": Intent.SEARCH,
            "DATA_QUERY": Intent.DATA_QUERY,
            "CLARIFICATION": Intent.CLARIFICATION,
        }

        intent = intent_map.get(raw, Intent.DATA_QUERY)
        return intent, 0.85

    @staticmethod
    def _has_intent_verb(query: str) -> bool:
        """Check if query contains any action/intent verbs."""
        INTENT_VERBS = {
            "show", "get", "find", "list", "give", "fetch", "display",
            "what", "who", "how", "when", "where", "select", "count",
            "total", "sum", "average", "report", "search", "look",
            "describe", "which", "compare",
        }
        words = re.findall(r'\w+', query.lower())
        return any(w in INTENT_VERBS for w in words)
