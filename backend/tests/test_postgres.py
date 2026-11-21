import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from conftest import PASSWORD, count_tables
from PIL import Image
from sqlalchemy import func, inspect, select, text

from tennisfans.core.config import Settings
from tennisfans.db.base import now
from tennisfans.db.competition import Fixture
from tennisfans.db.runtime import check_schema, engine_for, migrate
from tennisfans.modules import storage, tournaments

API = "/api/v1"


def login(app, username, password=PASSWORD):
    response = app.post(API + "/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return identity(response)


def identity(response):
    value = response.json()
    return value["user"]["id"], {
        "X-CSRF-Token": value["csrf"],
        "Cookie": f"tennisfans_session={response.cookies['tennisfans_session']}",
    }


def register(app, username):
    response = app.post(API + "/auth/register", json={"username": username, "password": PASSWORD})
    assert response.status_code == 201, response.text
    return identity(response)


def post(app, path, actor, body=None, key=None, expected=200):
    headers = {**actor, **({"Idempotency-Key": str(key or uuid4())})}
    response = app.post(API + path, headers=headers, json=body)
    assert response.status_code == expected, response.text
    return response


def pub(app, path):
    response = app.get(API + "/public" + path)
    assert response.status_code == 200, response.text
    assert response.headers["x-tennisfans-public"] == "1"
    return response.json()


def score(winner=0, outcome="COMPETITIVE", days=0):
    return {
        "played_at": (now() - timedelta(days=days, milliseconds=10)).isoformat(),
        "score": {
            "winner": winner,
            "outcome": outcome,
            "sets": ([{"a": 6, "b": 4}] if winner == 0 else [{"a": 4, "b": 6}])
            if outcome == "COMPETITIVE"
            else [],
        },
    }


def tour_request(**fields):
    return {
        "title": "Serve and volley",
        "discipline": "SINGLES",
        "format": "ROUND_ROBIN",
        "capacity": 2,
        "starts_at": (now() - timedelta(minutes=2)).isoformat(),
        "rules": {"format": "SINGLE_SET"},
        **fields,
    }


def make_tour(app, admin, **fields):
    return post(app, "/tournaments", admin, tour_request(**fields), expected=201).json()["id"]


def maintain(app):
    tournaments.reconcile_due(app.app.state.runtime.db)


def png():
    content = BytesIO()
    Image.new("RGB", (20, 12), "orange").save(content, format="PNG")
    return content.getvalue()


def test_schema_migration_and_bootstrap_cli(settings: Settings, clean_schema: None):
    engine = engine_for(settings)
    assert inspect(engine).get_table_names() == []
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: migrate(engine, replay_k=settings.elo_k), [1, 2]))
    assert len(inspect(engine).get_table_names()) == count_tables(settings)
    check_schema(engine)
    env = {
        "TENNISFANS_DATABASE_URL": settings.database_url.get_secret_value(),
        "TENNISFANS_SESSION_SECRET": settings.session_secret.get_secret_value(),
    }
    args = [
        sys.executable,
        "-c",
        "from tennisfans.cli import main; main()",
        "admin",
        "create",
        "root-admin",
        "--password-stdin",
    ]
    first = subprocess.run(  # noqa: S603
        args, input=PASSWORD + "\n", env=env, capture_output=True, text=True, check=True
    )
    assert first.stdout.strip() == "Administrator created"
    duplicate = subprocess.run(  # noqa: S603
        args, input=PASSWORD + "\n", env=env, capture_output=True, text=True, check=False
    )
    assert duplicate.returncode == 1 and "already exists" in duplicate.stderr
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'unknown'"))
    with pytest.raises(RuntimeError, match="revision differs"):
        migrate(engine)
    engine.dispose()


def test_partial_schema_is_rejected(settings, clean_schema):
    engine = engine_for(settings)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE unrelated (id int PRIMARY KEY)"))
    with pytest.raises(RuntimeError, match="missing or ambiguous"):
        migrate(engine)
    engine.dispose()


def test_sessions_reset_and_origin(app):
    admin_id, admin = login(app, "admin")
    player_id, player = register(app, "Celia")
    assert (
        app.post(
            API + "/auth/register", json={"username": "cELIA", "password": PASSWORD}
        ).status_code
        == 409
    )
    session = app.get(API + "/auth/session", headers=player)
    assert session.json()["user"]["id"] == player_id
    assert session.headers["Cache-Control"] == "no-store"
    assert "password_hash" not in session.text
    assert (
        app.patch(
            API + "/account",
            headers={**player, "Origin": "https://example.invalid"},
            json={"display_name": "New"},
        ).json()["code"]
        == "invalid_origin"
    )
    assert (
        app.patch(
            API + "/account",
            headers={**player, "X-CSRF-Token": "mismatch"},
            json={"display_name": "New"},
        ).json()["code"]
        == "invalid_csrf"
    )
    assert (
        app.patch(
            API + "/account", headers=player, json={"display_name": "New", "role": "ADMIN"}
        ).status_code
        == 422
    )
    assert (
        app.patch(
            API + f"/admin/users/{admin_id}",
            headers=player,
            json={
                "display_name": "New",
                "username": "admin",
                "active": True,
                "role": "ADMIN",
            },
        ).status_code
        == 403
    )
    preflight = app.options(
        API + "/account",
        headers={
            "Origin": "https://example.invalid",
            "Access-Control-Request-Method": "PATCH",
        },
    )
    assert "access-control-allow-origin" not in preflight.headers
    assert (
        app.patch(API + "/account", headers=player, json={"display_name": "Celia New"}).status_code
        == 200
    )
    reset = post(app, f"/admin/users/{player_id}/reset", admin).json()
    assert app.get(API + "/auth/session", headers=player).json() is None
    assert (
        app.post(API + "/auth/login", json={"username": "Celia", "password": PASSWORD}).status_code
        == 401
    )
    _, temp = login(app, "CELIA", reset["temporary_password"])
    assert app.get(API + "/auth/session", headers=temp).json()["password_change_required"]
    assert app.patch(API + "/account", headers=temp, json={"display_name": "No"}).status_code == 403
    assert (
        app.post(
            API + "/auth/login", json={"username": "Celia", "password": reset["temporary_password"]}
        ).status_code
        == 401
    )
    changed = post(app, "/auth/password", temp, {"new_password": "another durable password"})
    _, valid = identity(changed)
    assert app.get(API + "/auth/session", headers=temp).json() is None
    assert not app.get(API + "/auth/session", headers=valid).json()["password_change_required"]
    assert (
        app.post(
            API + "/auth/password",
            headers=valid,
            json={"old_password": "wrong", "new_password": PASSWORD},
        ).status_code
        == 422
    )
    post(app, "/auth/logout", valid, expected=204)
    assert app.get(API + "/auth/session", headers=valid).json() is None


def test_friendly_replay_idempotency_disputes_and_media(app):
    _, admin = login(app, "admin")
    alice, a = register(app, "alice")
    bob, b = register(app, "bobby")
    charlie, c = register(app, "charlie")
    dana, _ = register(app, "dana")
    rules = {"format": "SINGLE_SET"}
    body = {"discipline": "SINGLES", "rules": rules, "a": [alice], "b": [bob], **score()}
    post(app, "/matches/friendly", c, body, expected=403)
    post(app, "/matches/friendly", a, {**body, "b": [alice]}, expected=422)
    client_key = uuid4()
    with ThreadPoolExecutor(max_workers=2) as pool:
        refs = list(
            pool.map(
                lambda _: post(
                    app, "/matches/friendly", a, body, key=client_key, expected=201
                ).json(),
                [0, 1],
            )
        )
    assert refs[0] == refs[1]
    first = refs[0]["id"]
    post(app, "/matches/friendly", a, {**body, **score(days=1)}, key=client_key, expected=409)
    assert pub(app, f"/users/{alice}")["player"]["rating"] == 1516
    second = post(
        app,
        "/matches/friendly",
        a,
        {
            "discipline": "DOUBLES",
            "rules": rules,
            "a": [alice, dana],
            "b": [charlie, bob],
            **score(winner=1, days=3),
        },
        expected=201,
    ).json()["id"]
    before = pub(app, f"/users/{alice}")
    assert [point["match_id"] for point in before["history"]] == [second, first]
    assert before["player"]["rating"] > 1500
    path = f"/matches/{first}"
    match = pub(app, path)
    post(
        app,
        path + "/disputes",
        a,
        {"version": match["version"], "reason": "Own submission"},
        expected=403,
    )
    post(
        app,
        path + "/disputes",
        c,
        {"version": match["version"], "reason": "Unrelated player"},
        expected=403,
    )
    post(
        app,
        path + "/disputes",
        b,
        {"version": match["version"], "reason": "Wrong score"},
        expected=204,
    )
    disputed = pub(app, path)
    assert disputed["status"] == "DISPUTED" and disputed["rating"] == []
    assert pub(app, f"/users/{alice}")["player"]["rating"] == 1484
    resolution = {
        "version": disputed["version"],
        "reason": "Official decision",
        "decision": "UPHOLD",
    }
    post(app, path + "/resolution", b, resolution, expected=403)
    resolve_key = uuid4()
    post(app, path + "/resolution", admin, resolution, key=resolve_key)
    post(app, path + "/resolution", admin, resolution, key=resolve_key)
    assert pub(app, f"/users/{alice}")["history"] == before["history"]
    assert app.get(API + "/account/notifications", headers=a).json()["total"] == 1
    files = [
        ("files", ("court.png", png(), "image/png")),
        ("files", ("ball.png", png(), "image/png")),
    ]
    route = API + f"/media/match/{first}"
    assert app.post(route, headers=c, files=files).status_code == 403
    assert app.post(API + f"/media/user/{bob}", headers=a, files=files[:1]).status_code == 403
    assert (
        app.post(
            route, headers=a, files=[("files", ("image.svg", b"<svg/>", "image/svg+xml"))]
        ).status_code
        == 422
    )
    assert (
        app.post(
            route, headers=a, files=[("files", ("large.png", b"x" * 4200, "image/png"))]
        ).status_code
        == 413
    )
    assert (
        app.post(
            route, headers=a, files=[("files", ("large.png", b"x" * 9000, "image/png"))]
        ).status_code
        == 413
    )
    photos = app.post(route, headers=a, files=files)
    assert photos.status_code == 201, photos.text
    ids = [item["id"] for item in photos.json()["items"]]
    assert len(ids) == 2
    for photo_id in ids:
        assert app.get(API + f"/public/media/{photo_id}/thumb").content.startswith(b"\x89PNG")
    admin_delete = "/admin" + path + "/delete"
    current = pub(app, path)
    body = {"version": current["version"], "reason": "Remove invalid fixture"}
    preview = post(app, admin_delete, admin, body, expected=409).json()
    assert preview["code"] == "cascade_confirmation"
    post(app, admin_delete, admin, {**body, "confirmation": preview["context"]["confirmation"]})
    assert app.get(API + "/public" + path).status_code == 404
    assert pub(app, f"/users/{alice}")["player"]["rating"] == 1484
    runtime = app.app.state.runtime
    storage.cleanup_pending(runtime.db, runtime.storage)
    for photo_id in ids:
        assert app.get(API + f"/public/media/{photo_id}/full").status_code == 404
    assert list(runtime.storage.root.iterdir()) == []


def test_oversubscription_and_atomic_reschedule(app):
    _, admin = login(app, "admin")
    player_a, a = register(app, "player-a")
    player_b, b = register(app, "player-b")
    player_c, c = register(app, "player-c")
    organizer, org = register(app, "organizer")
    tournament = make_tour(app, admin, participants=[player_a], organizers=[organizer])
    other = make_tour(app, admin, starts_at=(now() + timedelta(days=30)).isoformat())
    root = f"/tournaments/{tournament}"
    assert pub(app, root)["fixtures"] == []
    assert app.get(API + f"/tournaments/{other}/applications", headers=org).status_code == 403
    for player in (b, c):
        post(app, root + "/application", player, expected=204)
    assert app.get(API + root + "/applications", headers=a).status_code == 403
    assert app.get(API + root + "/applications", headers=org).json()["total"] == 2
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: maintain(app), range(4)))
    assert pub(app, root)["status"] == "ACTION_REQUIRED"

    def accept(player):
        return app.post(
            API + root + f"/roster/{player}", headers=org, json={"action": "ACCEPT"}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(accept, [player_b, player_c])) == [204, 409]
    maintain(app)
    state = pub(app, root)
    assert state["accepted"] == 2 and state["status"] == "ACTION_REQUIRED"
    config = {
        **state["config"],
        "version": state["version"],
        "starts_at": (now() - timedelta(seconds=1)).isoformat(),
    }
    assert app.put(API + root, headers=org, json=config).status_code == 403
    assert app.put(API + root, headers=admin, json=config).status_code == 204
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: maintain(app), range(4)))
    state = pub(app, root)
    assert state["status"] == "ACTIVE"
    assert len(state["fixtures"]) == 1
    with app.app.state.runtime.db() as db:
        assert db.scalar(select(func.count()).select_from(Fixture)) == 1
    assert app.delete(API + root + f"/organizers/{organizer}", headers=admin).status_code == 204
    assert app.get(API + root + "/applications", headers=org).status_code == 403
    match = state["fixtures"][0]["match"]
    assert (
        app.post(
            API + f"/media/match/{match['id']}",
            headers=org,
            files={"files": ("image.png", png(), "image/png")},
        ).status_code
        == 403
    )
    post(
        app,
        f"/matches/{match['id']}/result",
        org,
        {**score(), "version": match["version"]},
        expected=403,
    )
    post(
        app,
        f"/matches/{match['id']}/result",
        admin,
        {**score(outcome="WALKOVER"), "version": match["version"]},
    )
    assert pub(app, root)["status"] == "COMPLETED"
    assert pub(app, f"/users/{player_a}")["history"] == []
    assert app.delete(API + root, headers=admin).status_code == 204
    assert app.get(API + f"/public/matches/{match['id']}").status_code == 404


@pytest.mark.parametrize("format_", ["SINGLE_ELIMINATION", "GROUPS_THEN_PLAYOFFS"])
def test_group_or_knockout_invalidation_and_resolution(app, format_):
    _, admin = login(app, "admin")
    members = dict(register(app, f"player-{number}") for number in range(4))
    organizer_id, organizer = register(app, "nonplaying-organizer")
    id_ = make_tour(
        app,
        admin,
        capacity=4,
        participants=list(members),
        organizers=[organizer_id],
        format=format_,
    )
    maintain(app)
    root = f"/tournaments/{id_}"
    view = pub(app, root)
    assert view["status"] == "ACTIVE"
    first = [entry["match"] for entry in view["fixtures"] if entry["match"]]
    assert len(first) == 2
    for match in first:
        post(
            app,
            f"/matches/{match['id']}/result",
            members[match["a"][0]["id"]],
            {
                **score(),
                "version": match["version"],
            },
        )
    state = pub(app, root)
    final = [entry["match"] for entry in state["fixtures"] if entry["stage"] == "PLAYOFF"][-1]
    post(
        app,
        f"/matches/{final['id']}/result",
        members[final["a"][0]["id"]],
        {
            **score(),
            "version": final["version"],
        },
    )
    state = pub(app, root)
    assert state["status"] == "COMPLETED"
    assert [(item["rank"], item["rank_end"]) for item in state["placements"]] == [
        (1, 1),
        (2, 2),
        (3, 4),
        (3, 4),
    ]
    target = pub(app, f"/matches/{first[0]['id']}")
    url = f"/matches/{target['id']}"
    post(
        app,
        url + "/disputes",
        members[target["b"][0]["id"]],
        {"version": target["version"], "reason": "Incorrect winner"},
        expected=204,
    )
    assert pub(app, root)["status"] == "ACTIVE"
    assert pub(app, f"/matches/{final['id']}")["status"] == "BLOCKED"
    current = pub(app, url)
    body = {
        "version": current["version"],
        "reason": "Verified winner",
        "decision": "REPLACE",
        "replacement": score(1),
    }
    assert (
        post(app, url + "/resolution", organizer, body, expected=409).json()["code"]
        == "admin_cascade_required"
    )
    preview = post(app, url + "/resolution", admin, body, expected=409).json()
    impacts = preview["context"]["affected"]
    assert any(item["match_id"] == final["id"] and item["has_result"] for item in impacts)
    post(
        app,
        url + "/resolution",
        admin,
        {**body, "confirmation": preview["context"]["confirmation"]},
    )
    assert app.get(API + f"/public/matches/{final['id']}").status_code == 404
    assert pub(app, root)["status"] == "ACTIVE"
    replaced = pub(app, url)
    assert replaced["score"]["winner"] == 1
    revision = replaced["revisions"][0]
    assert revision["before"]["score"]["winner"] == 0
    assert revision["after"]["score"]["winner"] == 1
    assert revision["actor"]["username"] == "admin"
    assert app.delete(API + root, headers=admin).status_code == 204
    assert pub(app, "/matches")["total"] == 0
    assert all(pub(app, f"/users/{player_id}")["player"]["rating"] == 1500 for player_id in members)


def test_fixed_and_rotating_rosters(app):
    _, admin = login(app, "admin")
    members = dict(register(app, f"team-{number}") for number in range(5))
    ids = list(members)
    fixed = make_tour(
        app, admin, discipline="DOUBLES", team_mode="FIXED_TEAMS", capacity=4, participants=ids[:4]
    )
    rotating = make_tour(
        app,
        admin,
        discipline="DOUBLES",
        team_mode="ROTATING_PARTNERS",
        capacity=5,
        participants=ids,
    )
    root = f"/tournaments/{fixed}"
    assert (
        app.put(
            API + root + "/teams", headers=admin, json={"teams": [ids[:2], [ids[0], ids[3]]]}
        ).status_code
        == 422
    )
    assert (
        app.put(
            API + root + "/teams", headers=admin, json={"teams": [ids[:2], ids[2:4]]}
        ).status_code
        == 204
    )
    maintain(app)
    fixed_view = pub(app, root)
    assert len(fixed_view["fixtures"]) == 1
    assert len(fixed_view["standings"]) == 2
    assert all(len(item["players"]) == 2 for item in fixed_view["standings"])
    rotating_view = pub(app, f"/tournaments/{rotating}")
    assert len(rotating_view["fixtures"]) == 5
    assert len(rotating_view["standings"]) == 5
    assert all(len(item["players"]) == 1 for item in rotating_view["standings"])
    for fixture in rotating_view["fixtures"]:
        match = fixture["match"]
        post(
            app,
            f"/matches/{match['id']}/result",
            members[match["a"][0]["id"]],
            {
                **score(),
                "version": match["version"],
            },
        )
    assert pub(app, f"/tournaments/{rotating}")["status"] == "COMPLETED"
    assert all(row["played"] == 4 for row in pub(app, f"/tournaments/{rotating}")["standings"])
