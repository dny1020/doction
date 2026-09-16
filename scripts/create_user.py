#!/usr/bin/env python3
"""Creates a doction user from the command line, bypassing web registration.

Uses the same DATABASE_URL as the app, so point it at the real database.

    # in a local checkout
    uv run python -m scripts.create_user alice@example.com
    DATABASE_URL=postgresql://doction:doction@localhost:5432/doction \\
        uv run python -m scripts.create_user bob@corp.io

    # inside the deployed container
    docker exec -it doction python -m scripts.create_user alice@example.com
"""

import argparse
import getpass
import sys

from app import db, seed
from app.auth import hash_password


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a doction user.")
    parser.add_argument("email")
    parser.add_argument("--password", help="si se omite, se pide de forma interactiva")
    parser.add_argument("--no-seed", action="store_true", help="no crear las páginas de ejemplo")
    args = parser.parse_args()

    email = args.email.strip().lower()
    if "@" not in email:
        print("error: email inválido", file=sys.stderr)
        return 2

    db.init_db()
    if db.get_user_by_email(email) is not None:
        print(f"error: ya existe un usuario con {email}", file=sys.stderr)
        return 1

    password = args.password or getpass.getpass("Password (8+ caracteres): ")
    if len(password) < 8:
        print("error: la contraseña debe tener al menos 8 caracteres", file=sys.stderr)
        return 2

    user_id = db.create_user(email, hash_password(password))
    workspace = db.ensure_default_workspace(user_id)
    if not args.no_seed:
        for title, content in seed.SEED_PAGES:
            db.create_page(user_id, int(workspace.id), title, content)
    print(f"ok: usuario {email} creado (id={user_id}, workspace='{workspace.slug}')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
