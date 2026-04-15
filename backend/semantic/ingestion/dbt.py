"""
dbt Ingestion Handler — Extracts semantic models from dbt manifest scripts.
"""

import json
import logging
from typing import List, Optional
from backend.semantic.models import MetricDefinition, EntityDefinition
from backend.semantic.service import SemanticManager

logger = logging.getLogger(__name__)

class DBTParser:
    """Parses dbt manifest.json to populate the Semantic Data Layer."""
    
    def __init__(self, semantic_manager: SemanticManager):
        self.manager = semantic_manager

    async def ingest_manifest(self, manifest_path: str):
        """
        Parses manifest.json (v3+ format).
        Extracts metrics and models as entities.
        """
        try:
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
            
            # 1. Ingest Metrics
            metrics = manifest.get("metrics", {})
            for m_id, m_data in metrics.items():
                metric = MetricDefinition(
                    name=m_data.get("name"),
                    description=m_data.get("description", ""),
                    sql_snippet=m_data.get("calculation_method", "SUM") + "(" + m_data.get("expression", "*") + ")",
                    underlying_tables=[m_data.get("model", "")],
                    dimensions=m_data.get("dimensions", [])
                )
                await self.manager.add_metric(metric)
            
            # 2. Ingest Models as Entities
            nodes = manifest.get("nodes", {})
            for n_id, n_data in nodes.items():
                if n_data.get("resource_type") == "model":
                    entity = EntityDefinition(
                        name=n_data.get("name"),
                        description=n_data.get("description", ""),
                        primary_table=n_data.get("alias") or n_data.get("name"),
                        primary_key=n_data.get("config", {}).get("primary_key", "id"),
                        attributes=[c for c in n_data.get("columns", {}).keys()]
                    )
                    self.manager.entities[entity.name] = entity
            
            self.manager._save_all()
            logger.info("✓ Completed dbt manifest ingestion.")
            
        except Exception as e:
            logger.error(f"✗ Failed to ingest dbt manifest: {e}")
            raise
