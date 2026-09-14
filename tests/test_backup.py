import datetime as dt
import re

import pytest


@pytest.fixture()
def backup_module(client):
    # Imported lazily (depending on `client`) rather than at module level:
    # the client fixture is what sets DATA_DIR before app.backup's module-
    # level BACKUP_DIR.mkdir() runs. A top-level import here would run
    # against whatever DATA_DIR defaults to on the machine running pytest.
    from app import backup

    return backup


def _add(client, name, portions):
    return client.post("/items", data={"name": name, "portions": portions})


def test_create_backup_writes_dated_file(client, backup_module):
    path = backup_module.create_backup()
    assert path.exists()
    assert path.name == f"freezerbags-{dt.date.today().isoformat()}.db"


def test_create_backup_twice_does_not_error(client, backup_module):
    backup_module.create_backup()
    path = backup_module.create_backup()
    assert path.exists()


def test_restore_brings_back_a_discarded_item(client, backup_module):
    resp = _add(client, "Lasagne", 3)
    assert "Lasagne" in resp.text

    today = dt.date.today()
    backup_module.create_backup(today=today)

    # Discard it -- item should disappear from the live list.
    html = client.get("/").text
    item_id = int(re.search(r"eat-dialog-(\d+)", html[html.index("Lasagne"):]).group(1))
    client.post(f"/items/{item_id}/discard")
    assert "Lasagne" not in client.get("/").text

    backup_module.restore_backup(today)
    assert "Lasagne" in client.get("/").text


def test_restore_unknown_date_raises(client, backup_module):
    with pytest.raises(FileNotFoundError):
        backup_module.restore_backup(dt.date(2000, 1, 1))


def test_prune_removes_only_old_backups(client, backup_module):
    today = dt.date.today()
    old = today - dt.timedelta(days=backup_module.RETENTION_DAYS + 5)
    recent = today - dt.timedelta(days=1)

    backup_module.create_backup(today=today)  # also creates today's + prunes
    (backup_module.BACKUP_DIR / f"freezerbags-{old.isoformat()}.db").write_bytes(b"x")
    (backup_module.BACKUP_DIR / f"freezerbags-{recent.isoformat()}.db").write_bytes(b"x")

    removed = backup_module.prune_old_backups(today=today)

    assert any(old.isoformat() in str(p) for p in removed)
    assert not any(recent.isoformat() in str(p) for p in removed)
    remaining = {d.isoformat() for d in backup_module.list_backup_dates()}
    assert old.isoformat() not in remaining
    assert recent.isoformat() in remaining
    assert today.isoformat() in remaining


def test_restore_route_requires_correct_token(client):
    today = dt.date.today().isoformat()

    resp = client.post("/internal/restore", json={"date": today})
    assert resp.status_code == 403

    resp = client.post(
        "/internal/restore", json={"date": today}, headers={"X-Restore-Token": "wrong"}
    )
    assert resp.status_code == 403


def test_restore_route_unknown_date_is_404(client):
    resp = client.post(
        "/internal/restore",
        json={"date": "2000-01-01"},
        headers={"X-Restore-Token": "test-token"},
    )
    assert resp.status_code == 404
    assert "available" in resp.json()["detail"]


def test_restore_route_success(client):
    # App startup already took a backup before this test added anything, so
    # restoring "today" should roll back to that empty state -- a more
    # meaningful check than just the status code.
    resp = _add(client, "Fish pie", 2)
    assert "Fish pie" in resp.text
    today = dt.date.today().isoformat()

    resp = client.post(
        "/internal/restore",
        json={"date": today},
        headers={"X-Restore-Token": "test-token"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "restored", "date": today}
    assert "Fish pie" not in client.get("/").text
