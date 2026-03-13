"""
Core data models for the Semantic Data Layer.
Includes Metric Definitions, Entities, and Relationships.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class MetricDefinition(BaseModel):
    """Represents a business metric (e.g., Gross Revenue)."""
    name: str = Field(..., description="Unique business name of the metric")
    description: str = Field(..., description="Business definition/semantic meaning")
    sql_snippet: str = Field(..., description="The SQL calculation logic (e.g., SUM(price))")
    underlying_tables: List[str] = Field(default_factory=list, description="Tables involved in this metric")
    dimensions: List[str] = Field(default_factory=list, description="Allowable dimensions for grouping")
    is_derived: bool = False
    dependencies: List[str] = Field(default_factory=list, description="Other metrics this depends on")

class EntityDefinition(BaseModel):
    """Represents a business entity (e.g., Customer, Product)."""
    name: str
    description: str
    primary_table: str
    primary_key: str
    attributes: List[str] = Field(default_factory=list)

class Relationship(BaseModel):
    """Represents a join relationship between two entities."""
    source_entity: str
    target_entity: str
    join_type: str = "LEFT JOIN"
    join_on: str = "source.id = target.id"
    description: Optional[str] = None
