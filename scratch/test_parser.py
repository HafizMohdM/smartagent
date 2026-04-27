import sys
import os
sys.path.append(os.getcwd())
try:
    from backend.agent.utils.sql_parser import SQLParser
    print("SQLParser imported successfully")
    print(f"Attributes: {dir(SQLParser)}")
except Exception as e:
    print(f"Import failed: {e}")
