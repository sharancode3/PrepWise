import argparse
import json
from pathlib import Path
from alembic import command
from alembic.config import Config
from app.core.config import BACKEND_ROOT, Settings
from app.db.session import Database
from app.features.curriculum.service import seed_curriculum


def main():
    parser = argparse.ArgumentParser(description="LearnNova local foundation tools")
    parser.add_argument("action", choices=["migrate", "seed", "export-openapi", "check-models", "setup-demo", "reset-demo"])
    args = parser.parse_args()
    if args.action == "migrate":
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        command.upgrade(config, "head")
    elif args.action == "seed":
        db = Database(Settings().resolved_database_url)
        if not db.ready():
            raise SystemExit("Run python -m app.cli migrate first")
        with db.sessions.begin() as session:
            print(json.dumps(seed_curriculum(session)))
        db.engine.dispose()
    elif args.action == "export-openapi":
        from app.main import create_app
        (BACKEND_ROOT / "openapi.json").write_text(json.dumps(create_app().openapi(), indent=2) + "\n", encoding="utf-8")
        print("Exported backend/openapi.json")
    elif args.action == "setup-demo":
        from app.features.demo.setup import setup_demo_scenario
        res = setup_demo_scenario(force_reset=False)
        print(json.dumps(res, indent=2))
    elif args.action == "reset-demo":
        from app.features.demo.setup import setup_demo_scenario
        res = setup_demo_scenario(force_reset=True)
        print(json.dumps(res, indent=2))
    else:
        from app.providers.gateway import OllamaGateway
        print(json.dumps(OllamaGateway(Settings()).capabilities(), indent=2))


if __name__ == "__main__":
    main()
