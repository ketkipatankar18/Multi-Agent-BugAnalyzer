#!/usr/bin/env python3
"""
seed_admin.py — Create the initial admin user in PostgreSQL.
Run once:  python seed_admin.py
"""
import os
import sys
import bcrypt
import db  # services/db.py
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv()) 

USERNAME = os.environ["ADMIN_USERNAME"]
PASSWORD = os.environ["ADMIN_PASSWORD"]
ROLE     = os.environ.get("ADMIN_ROLE", "admin") 


def main() -> None:
    db.init_db()  # ensure pool is open

    existing = db.get_user(USERNAME)
    if existing:
        print(f"[skip] User '{USERNAME}' already exists (role={existing['role']}).")
        sys.exit(0)

    pw_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt()).decode()
    db.create_user(USERNAME, pw_hash, ROLE)
    print(f"[ok]   Created user '{USERNAME}' with role='{ROLE}'.")
    print(f"       Login at POST /auth/login  →  username={USERNAME}  password={PASSWORD}")


if __name__ == "__main__":
    main()