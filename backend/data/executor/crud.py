"""
Saved Query CRUD operations.
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from backend.models.saved_query import SavedQuery

async def list_saved_queries(db: AsyncSession, user_id: str) -> List[SavedQuery]:
    """Retrieve all saved queries for a specific user."""
    result = await db.execute(
        select(SavedQuery).where(SavedQuery.user_id == user_id)
    )
    return list(result.scalars().all())

async def save_query(
    db: AsyncSession,
    user_id: str,
    connection_id: str,
    query_name: str,
    natural_language_query: str,
    generated_sql: str,
    query_result_snapshot: Optional[list] = None,
    execution_time_ms: Optional[int] = None,
    row_count: Optional[int] = None
) -> SavedQuery:
    """Save a new executed query."""
    query = SavedQuery(
        user_id=user_id,
        connection_id=connection_id,
        query_name=query_name,
        natural_language_query=natural_language_query,
        generated_sql=generated_sql,
        query_result_snapshot=query_result_snapshot,
        execution_time_ms=execution_time_ms,
        row_count=row_count
    )
    db.add(query)
    await db.commit()
    await db.refresh(query)
    return query

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
