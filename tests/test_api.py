def _add(client, name, portions):
    return client.post("/items", data={"name": name, "portions": portions})


def _get_item_id(html: str, name: str) -> int:
    """Pull the numeric item id out of the rendered `eat-dialog-{id}` near the item's name."""
    import re

    idx = html.find(name)
    assert idx != -1, f"{name!r} not found in response"
    tail = html[idx:]
    m = re.search(r'eat-dialog-(\d+)', tail)
    assert m, "could not find item id in rendered HTML"
    return int(m.group(1))


def test_healthz(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_index_shows_heading_and_empty_state(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "FreezerBags" in resp.text
    assert "Nothing in the freezer yet" in resp.text


def test_add_item_appears_in_list(client):
    resp = _add(client, "Chilli con carne", 4)
    assert resp.status_code == 200
    assert "Chilli con carne" in resp.text
    assert "4 portions" in resp.text


def test_add_to_existing_item_is_case_insensitive_and_sums_portions(client):
    _add(client, "Chilli con carne", 4)
    resp = _add(client, "chilli con carne", 2)
    assert "6 portions" in resp.text
    # Only one row for the item, not two.
    assert resp.text.count('<li class="item">') == 1


def test_add_to_endpoint_adds_a_batch(client):
    resp = _add(client, "Bolognese", 3)
    item_id = _get_item_id(resp.text, "Bolognese")
    resp = client.post(f"/items/{item_id}/add", data={"portions": 2})
    assert "5 portions" in resp.text


def test_eat_is_fifo_and_leaves_correct_remainder(client):
    # Two batches of the same item, added on the same (test) day, so FIFO
    # order here is really just "oldest batch id first" -- verified via the
    # running total rather than distinguishing dates.
    resp = _add(client, "Soup", 4)
    item_id = _get_item_id(resp.text, "Soup")
    client.post(f"/items/{item_id}/add", data={"portions": 2})  # total 6

    resp = client.post(f"/items/{item_id}/eat", data={"portions": 5})
    assert "1 portion" in resp.text
    assert "Soup" in resp.text


def test_eating_all_portions_removes_item_from_list(client):
    resp = _add(client, "Curry", 3)
    item_id = _get_item_id(resp.text, "Curry")
    resp = client.post(f"/items/{item_id}/eat", data={"portions": 3})
    assert "Curry" not in resp.text
    assert "Nothing in the freezer yet" in resp.text


def test_eating_more_than_available_is_rejected(client):
    resp = _add(client, "Curry", 3)
    item_id = _get_item_id(resp.text, "Curry")
    resp = client.post(f"/items/{item_id}/eat", data={"portions": 5})
    assert "Only 3 portion" in resp.text
    # Item is untouched.
    assert "3 portions" in resp.text


def test_discard_removes_item(client):
    resp = _add(client, "Fish pie", 2)
    item_id = _get_item_id(resp.text, "Fish pie")
    resp = client.post(f"/items/{item_id}/discard")
    assert "Fish pie" not in resp.text


def test_empty_name_is_rejected(client):
    resp = _add(client, "   ", 2)
    assert "Please enter a food description" in resp.text


def test_portions_out_of_range_is_rejected(client):
    resp = _add(client, "Stew", 0)
    assert "Portions must be between" in resp.text

    resp = _add(client, "Stew", 500)
    assert "Portions must be between" in resp.text


def test_acting_on_discarded_item_is_rejected(client):
    resp = _add(client, "Lasagne", 2)
    item_id = _get_item_id(resp.text, "Lasagne")
    client.post(f"/items/{item_id}/discard")

    resp = client.post(f"/items/{item_id}/eat", data={"portions": 1})
    assert "no longer in the freezer" in resp.text
