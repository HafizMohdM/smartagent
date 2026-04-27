import re

def _extract_identifiers(text):
    columns = set()
    tokens = re.findall(r'(?:(\w+)\.)?(\w+)', text)
    for _table_prefix, col in tokens:
        columns.add(col)
    return columns

sql_fragment = "DATE_TRUNC('month', a.attendance_date) AS month"
print(f"Fragment: {sql_fragment}")
print(f"Identifiers: {_extract_identifiers(sql_fragment)}")

sql_fragment_2 = "ON a.id = b.id"
print(f"Fragment: {sql_fragment_2}")
print(f"Identifiers: {_extract_identifiers(sql_fragment_2)}")

sql_fragment_4 = "a.attendance_date a, m.total_attendance m"
print(f"Fragment: {sql_fragment_4}")
print(f"Identifiers: {_extract_identifiers(sql_fragment_4)}")

sql_fragment_5 = "COUNT(*) total"
print(f"Fragment: {sql_fragment_5}")
print(f"Identifiers: {_extract_identifiers(sql_fragment_5)}")
