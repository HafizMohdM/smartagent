
import bcrypt

hashed = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj4oiHV.5gy6"
password = "admin123"

if bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8")):
    print("Match!")
else:
    print("No match.")
