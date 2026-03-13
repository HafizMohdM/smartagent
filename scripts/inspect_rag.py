"""
CLI Utility to inspect the Semantic Data Layer and RAG contents.
"""

import asyncio
import json
import os
from backend.semantic.service import SemanticManager

async def inspect():
    # Initialize manager (points to ./vector_store/semantic by default)
    manager = SemanticManager()
    
    print("\n=== [ AI Agent Semantic Layer Inspection ] ===")
    
    # 1. Metrics
    print(f"\n1. Metrics ({len(manager.metrics)} found):")
    if not manager.metrics:
        print("   (Empty - run ingestion/dbt parser first)")
    for name, metric in manager.metrics.items():
        print(f"   - {name}: {metric.description[:100]}...")
        
    # 2. Entities
    print(f"\n2. Entities ({len(manager.entities)} found):")
    if not manager.entities:
        print("   (Empty)")
    for name, entity in manager.entities.items():
        print(f"   - {name} ({entity.table_name})")
        
    # 3. Join Relationships
    print(f"\n3. Relationships ({len(manager.relationships)} found):")
    if not manager.relationships:
        print("   (Empty)")
    for rel in manager.relationships:
        print(f"   - {rel.source_entity} <-> {rel.target_entity} (Type: {rel.type})")
        
    print("\n=== [ End of Inspection ] ===\n")

if __name__ == "__main__":
    asyncio.run(inspect())
