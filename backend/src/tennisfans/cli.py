import argparse
import getpass
import json
import sys
from pathlib import Path

import uvicorn
from sqlalchemy import select

from tennisfans.api.contracts import Registration
from tennisfans.core.config import Settings
from tennisfans.db.accounts import User
from tennisfans.db.runtime import check_schema, engine_for, lock, migrate, session_factory
from tennisfans.domain.permissions import Role
from tennisfans.main import configure_logs, create_app
from tennisfans.modules.auth import create_user


def main() -> None:
    parser = argparse.ArgumentParser(prog="tennisfans")
    commands = parser.add_subparsers(dest="command", required=True)
    server = commands.add_parser("serve")
    server.add_argument("--host")
    server.add_argument("--port", type=int)
    db = commands.add_parser("db")
    db.add_argument("action", choices=("upgrade", "check"))
    admin = commands.add_parser("admin")
    admin.add_argument("action", choices=("create",))
    admin.add_argument("username")
    admin.add_argument("--display-name")
    admin.add_argument("--password-stdin", action="store_true")
    schema = commands.add_parser("openapi")
    schema.add_argument("path", type=Path)
    args = parser.parse_args()
    settings = Settings()
    configure_logs(settings)
    if args.command == "serve":
        uvicorn.run(
            create_app(settings),
            host=args.host or settings.backend_host,
            port=args.port or settings.backend_port,
            forwarded_allow_ips=settings.trusted_proxy_hosts,
            access_log=False,
        )
        return
    if args.command == "openapi":
        args.path.write_text(
            json.dumps(create_app(settings).openapi(), indent=2) + "\n", encoding="utf-8"
        )
        return
    engine = engine_for(settings)
    try:
        if args.command == "db":
            if args.action == "check":
                check_schema(engine)
            else:
                migrate(engine, explicit=True, replay_k=settings.elo_k)
            return
        password = (
            sys.stdin.readline().rstrip("\r\n")
            if args.password_stdin
            else getpass.getpass("Administrator password: ")
        )
        payload = Registration(
            username=args.username, password=password, display_name=args.display_name
        )
        migrate(engine, replay_k=settings.elo_k)
        with session_factory(engine).begin() as db_session:
            lock(db_session)
            if db_session.scalar(select(User.id).where(User.role == Role.ADMIN).limit(1)):
                parser.exit(
                    1,
                    "An administrator already exists. Manage additional roles in the application.\n",
                )
            create_user(
                db_session, payload.username, payload.password, payload.display_name, Role.ADMIN
            )
        print("Administrator created")
    finally:
        engine.dispose()
