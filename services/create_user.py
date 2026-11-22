"""
create_user.py
--------------
Manage reviewer accounts from the command line (run from services/).

  python create_user.py add ketki --role admin    # create, or reset password
  python create_user.py add alex                  # viewer by default
  python create_user.py deactivate alex           # revoke access immediately
  python create_user.py activate alex
  python create_user.py list
"""

import sys
import getpass
import argparse
from dotenv import load_dotenv

load_dotenv()

import db
from auth import hash_password, ROLES


def main():
    parser = argparse.ArgumentParser(description="Manage BugAnalyzer reviewer accounts")
    sub    = parser.add_subparsers(dest="cmd", required=True)

    add = sub.add_parser("add", help="create a user or reset their password")
    add.add_argument("username")
    add.add_argument("--role", choices=ROLES, default="viewer")

    for name in ("deactivate", "activate"):
        sub.add_parser(name).add_argument("username")

    sub.add_parser("list")

    args = parser.parse_args()
    db.init_db()

    if args.cmd == "add":
        username = args.username.strip().lower()
        password = getpass.getpass("Password (10–72 characters): ")
        if not 10 <= len(password.encode()) <= 72:
            sys.exit("Password must be 10–72 characters.")
        if password != getpass.getpass("Confirm password: "):
            sys.exit("Passwords do not match.")
        db.create_user(username, hash_password(password), args.role)
        print(f"✓ {username} saved with role '{args.role}'")

    elif args.cmd in ("deactivate", "activate"):
        username = args.username.strip().lower()
        ok = db.set_user_active(username, args.cmd == "activate")
        print(f"✓ {username} {args.cmd}d" if ok else f"✗ No user named {username}")

    elif args.cmd == "list":
        users = db.list_users()
        if not users:
            print("No users yet.")
        for u in users:
            status = "active" if u["is_active"] else "INACTIVE"
            print(f"{u['username']:20} {u['role']:7} {status:9} {u['created_at'][:10]}")


if __name__ == "__main__":
    main()