import asyncio
import logging
from backend.data.executor.generator import SQLGenerator
from backend.agent.utils.sql_parser import SQLParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_production():
    generator = SQLGenerator()
    schema = {
        "users": {"columns": [{"name": "id"}, {"name": "name"}], "description": "Store user accounts and profiles."},
        "attendance": {"columns": [{"name": "id"}, {"name": "user_id"}, {"name": "date"}], "description": "Transaction logs for employee attendance."},
        "employee_employee": {"columns": [{"name": "id"}, {"name": "name"}], "description": "Primary table for employee records."}
    }
    
    test_cases = [
        ("list tables", "TYPE: METADATA"),
        ("employees", "TYPE: LOOKUP"),
        ("employee names", "TYPE: SQL (Forced employee_employee)"),
        ("show all users", "TYPE: SQL"),
    ]
    
    print("\n=== FINAL PRODUCTION-GRADE VERIFICATION ===\n")
    
    for query, expected_type in test_cases:
        print(f"Query: '{query}'")
        resp = await generator.generate(query, schema)
        print(f"Response Content:\n{resp}")
        
        rtype = SQLParser.get_response_type(resp)
        print(f"Identified Type: {rtype}")
        
        sql = SQLParser.extract_sql(resp)
        if sql:
            print(f"Extracted SQL: {sql[:50]}...")
        else:
            print("No SQL extracted.")
        
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(verify_production())
