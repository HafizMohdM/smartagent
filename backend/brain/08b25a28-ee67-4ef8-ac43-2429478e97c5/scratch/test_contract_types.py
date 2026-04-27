
import asyncio
import sys
import os

# Add project root to sys.path
sys.path.append(os.getcwd())

from backend.data.executor.contract import validate_db_result, get_error_fallback

def test_valid_contract():
    print("Testing valid contract...")
    valid = {
        "rows": [{"id": 1, "name": "Test"}],
        "columns": ["id", "name"],
        "meta": {"row_count": 1}
    }
    result = validate_db_result(valid, source="test")
    assert result == valid
    print("[OK] Valid contract passed.")

def test_invalid_types():
    print("Testing invalid types...")
    # rows is a dict instead of list
    invalid = {
        "rows": {"id": 1},
        "columns": ["id"],
        "meta": {}
    }
    try:
        validate_db_result(invalid, source="test")
        print("[FAIL] Should have raised ValueError/TypeError/KeyError for invalid rows type.")
    except (ValueError, TypeError, KeyError) as e:
        print(f"[OK] Caught expected error: {e}")

def test_missing_keys():
    print("Testing missing keys...")
    invalid = {
        "rows": [],
        "meta": {}
    }
    try:
        validate_db_result(invalid, source="test")
        print("[FAIL] Should have raised ValueError/TypeError/KeyError for missing 'columns'.")
    except (ValueError, TypeError, KeyError) as e:
        print(f"[OK] Caught expected error: {e}")

def test_fallback():
    print("Testing error fallback...")
    fallback = get_error_fallback("Simulated error", source="test")
    assert "rows" in fallback
    assert "columns" in fallback
    assert "meta" in fallback
    assert fallback["meta"]["error"] == "Simulated error"
    print("[OK] Error fallback verified.")

if __name__ == "__main__":
    test_valid_contract()
    test_invalid_types()
    test_missing_keys()
    test_fallback()
