import os
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest
from conftest import ORIGIN
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_postgres import API, png, register

from tennisfans.db.runtime import engine_for
from tennisfans.main import create_app

SCRIPTS = Path(__file__).resolve().parents[2] / "deploy" / "scripts"


def run(script, *args, env, check=False):
    return subprocess.run(  # noqa: S603
        [str(SCRIPTS / script), *map(str, args)],
        env=env,
        capture_output=True,
        text=True,
        check=check,
    )


@pytest.mark.skipif(
    not all(shutil.which(cmd) for cmd in ("psql", "pg_dump", "pg_restore")),
    reason="Install PostgreSQL client tools",
)
def test_backup_and_restore_real_postgres_and_media(settings, clean_schema, tmp_path):
    if not SCRIPTS.is_dir():
        pytest.fail("Run recovery tests from the repository checkout")
    with TestClient(create_app(settings), headers={"Origin": ORIGIN}) as app:
        user, credentials = register(app, "backup-player")
        response = app.post(
            API + f"/media/user/{user}",
            headers=credentials,
            files={
                "files": ("original.png", png(), "image/png"),
            },
        )
        assert response.status_code == 201, response.text
        photo = response.json()["items"][0]["id"]
        url = API + f"/public/media/{photo}/full"
        original = app.get(url).content

    env = {
        **os.environ,
        "TENNISFANS_DATABASE_URL": settings.database_url.get_secret_value(),
        "TENNISFANS_MEDIA_ROOT": str(settings.media_root),
    }
    backup = tmp_path / "snapshot"
    run("backup", backup, env=env, check=True)
    refused = run("restore", backup, "--confirm-empty-target", env=env)
    assert refused.returncode != 0 and "populated" in refused.stderr
    engine = engine_for(settings)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    engine.dispose()
    recovery = tmp_path / "restored"
    env["TENNISFANS_MEDIA_ROOT"] = str(recovery)
    run("restore", backup, "--confirm-empty-target", env=env, check=True)
    recovered = settings.model_copy(update={"media_root": recovery})
    with TestClient(create_app(recovered), headers={"Origin": ORIGIN}) as restored:
        assert restored.get(url).content == original
        assert restored.get(API + f"/public/users/{user}").json()["player"]["avatar_id"] == photo


def executable(path: Path, source: str) -> None:
    path.write_text("#!/bin/bash\n" + source, encoding="utf-8")
    path.chmod(0o700)


def test_deployment_rollback_and_noninteractive_failure(tmp_path):
    binary = tmp_path / "bin"
    binary.mkdir()
    parent = tmp_path / "target"
    old = parent / "releases" / "old"
    old.mkdir(parents=True)
    (parent / "current").symlink_to(old, target_is_directory=True)
    path = tmp_path / "release-source"
    cli = path / "backend" / ".venv" / "bin"
    cli.mkdir(parents=True)
    executable(cli / "tennisfans", "exit 73\n")
    scripts = path / "deploy" / "scripts"
    scripts.mkdir(parents=True)
    executable(scripts / "backup", 'mkdir -- "$1"\n')
    commit = "a" * 40
    (path / "commit").write_text(commit + "\n", encoding="utf-8")
    archive = tmp_path / "bundle.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(path, arcname=".")

    executable(binary / "uv", "exit 0\n")
    executable(
        binary / "psql", 'if [[ "$*" == *to_regclass* ]]; then echo 1; else echo 0001_initial; fi\n'
    )
    executable(
        binary / "sudo",
        '[[ "$1" == "-n" ]] || exit 1\nprintf "%s\\n" "$*" >> "$SYSTEMCTL_COMMANDS"\n',
    )
    config = tmp_path / "deploy.env"
    env = {
        **os.environ,
        "PATH": str(binary) + ":" + os.environ["PATH"],
        "TENNISFANS_DEPLOY_CONFIG": str(config),
        "SYSTEMCTL_COMMANDS": str(tmp_path / "calls"),
    }
    failure = run("activate", parent, "development", archive, commit, env=env)
    assert failure.returncode != 0 and "operator" in failure.stderr
    assert (parent / "current").resolve() == old
    config.write_text(
        "BACKEND_SERVICE=api.service\nFRONTEND_SERVICE=web.service\n"
        "BACKEND_HEALTH_URL=http://127.0.0.1:8000\nFRONTEND_HEALTH_URL=http://127.0.0.1:5173\n"
        "TENNISFANS_MEDIA_ROOT=/tmp/test-media\nTENNISFANS_DATABASE_URL=postgresql+psycopg:///test\n",
        encoding="utf-8",
    )
    failure = run("activate", parent, "development", archive, commit, env=env)
    assert failure.returncode == 73
    assert "Restored the previous release" in failure.stderr
    assert (parent / "current").resolve() == old
    assert (tmp_path / "calls").read_text().endswith("-n systemctl start api.service web.service\n")
