
import bcrypt

hashed = "$2b$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2.uBlmle/Je"
password = "user123"

if bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8")):
    print("Match!")
else:
    print("No match.")
