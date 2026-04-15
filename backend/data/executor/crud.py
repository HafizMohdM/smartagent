"""
Saved Query CRUD operations.
"""
from typing import List, Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.saved_query import SavedQuery
from backend.agent.utils.sql_parser import SQLParser

async def list_saved_queries(db: AsyncSession, user_id: str) -> List[SavedQuery]:
    """Retrieve all saved queries for a specific user."""
    result = await db.execute(
        select(SavedQuery).where(SavedQuery.user_id == user_id)
    )
    return list(result.scalars().all())

async def save_query(
    db: AsyncSession,
    user_id: str,
    username: str,
    tenant_id: str,
    connection_id: str,
    database_name: str,
    title: str,
    natural_language_query: str,
    query: str,
    query_result_snapshot: Optional[Any] = None,
    execution_time_ms: Optional[int] = None,
    row_count: Optional[int] = None
) -> SavedQuery:
    # Determine response type and appropriate content to save
    from backend.agent.utils.sql_parser import SQLParser
    rtype = SQLParser.get_response_type(query)
    
    if rtype == "sql":
        pure_sql = SQLParser.extract_sql(query)
        if not pure_sql and SQLParser.is_valid_query(query):
            pure_sql = query.strip()
        
        if not pure_sql:
            raise ValueError("No valid SQL found in response. Saving blocked.")
        content_to_save = pure_sql
    elif rtype in ["metadata", "lookup"]:
        # Save the full text response for non-SQL intents
        content_to_save = query.strip()
    else:
        # For ERROR or UNKNOWN, we still try to extract SQL as a fallback
        pure_sql = SQLParser.extract_sql(query)
        if pure_sql:
            content_to_save = pure_sql
        else:
            raise ValueError(f"Cannot save response of type '{rtype}' without valid SQL.")

    saved_query = SavedQuery(
        user_id=user_id,
        username=username,
        tenant_id=tenant_id,
        connection_id=connection_id,
        database_name=database_name,
        title=title,
        natural_language_query=natural_language_query,
        query=content_to_save, # Store pure SQL or formatted text
        query_result_snapshot=query_result_snapshot,
        execution_time_ms=execution_time_ms,
        row_count=row_count
    )
    db.add(saved_query)
    await db.commit()
    await db.refresh(saved_query)
    return saved_query

async def get_query(db: AsyncSession, query_id: str, user_id: str) -> Optional[SavedQuery]:
    """Retrieve a specific saved query if it belongs to the user."""
    result = await db.execute(
        select(SavedQuery)
        .where(SavedQuery.id == query_id)
        .where(SavedQuery.user_id == user_id)
    )
    return result.scalars().first()

async def delete_query(db: AsyncSession, query_id: str, user_id: str) -> bool:
    """Delete a user's saved query."""
    query = await get_query(db, query_id, user_id)
    if query:
        await db.delete(query)
        await db.commit()
        return True
    return False

async def update_query(
    db: AsyncSession,
    query_id: str,
    user_id: str,
    **updates
) -> Optional[SavedQuery]:
    """Partially update a saved query."""
    query_obj = await get_query(db, query_id, user_id)
    if not query_obj:
        return None
    
    for key, value in updates.items():
        if hasattr(query_obj, key) and value is not None:
            # If updating the query, extract pure SQL
            if key == "query":
                value = SQLParser.extract_sql(value) or value.strip()
            setattr(query_obj, key, value)
    
    await db.commit()
    await db.refresh(query_obj)
    return query_obj
