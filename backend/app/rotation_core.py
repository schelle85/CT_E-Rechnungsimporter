"""AP12 registration core only. Never activate credentials, retire warnings or mail."""
from app.graph import GraphError
from app.notification_certificate import certificate_client
from app.rotation_model import checked_candidate, records_hash


def reconcile_registration(journal, operation, records):
    state = journal.state(operation)
    if state is None or state["phase"] not in {"registration_started", "registration_unknown", "registered", "candidate_verified"}:
        raise GraphError("rotation_transition_invalid")
    if state["phase"] in {"registered", "candidate_verified"}:
        journal.record_created(operation)
        return state
    material = journal.material(operation)
    matches = [item for item in records if item.get("fingerprint") == material.fingerprint
        and item.get("not_before") == material.not_before and item.get("expires_at") == material.expires_at]
    baseline = set(state["baseline"])
    current = {item["key_id"] for item in records}
    if (len(matches) != 1 or not baseline.issubset(current)
            or records_hash([item for item in records if item["key_id"] in baseline]) != state["baseline_hash"]
            or matches[0]["key_id"] in baseline
            or state["response_key_id"] not in {None, matches[0]["key_id"]}):
        return journal.transition(operation, "registration_unknown")
    state = journal.transition(operation, "registered", registered_key_id=matches[0]["key_id"])
    journal.record_created(operation)
    return state


def register(journal, operation, graph):
    """Exactly one durable send permission; every resumed entry is read-only."""
    state = journal.state(operation)
    if state is None:
        raise GraphError("rotation_journal_missing")
    if graph.binding.scope != journal.binding.scope:
        raise GraphError("rotation_scope_changed")
    if state["phase"] in {"registered", "candidate_verified", "registration_rejected"}:
        if state["phase"] != "registration_rejected":
            journal.record_created(operation)
        return state
    if state["phase"] != "prepared":
        return reconcile_registration(journal, operation, graph.read())
    # Fail closed before consuming the permission if application/signer changed.
    records = graph.read()
    if (state["baseline_hash"] != records_hash(records)
            or not any(item["fingerprint"] == state["old_fingerprint"] for item in records)
            or graph.signer.fingerprint != state["old_fingerprint"]
            or graph.binding.scope != journal.binding.scope):
        raise GraphError("rotation_baseline_changed")
    material = journal.material(operation)
    checked_candidate(material, int(graph.wall()))
    journal.transition(operation, "registration_started")  # fsync before token/POST.
    try:
        returned = graph.add(material)
    except GraphError as error:
        if not error.uncertain and error.status in {400,401,403,404,405,413,415,422,429}:
            try:
                after = graph.read()
            except GraphError:
                return journal.transition(operation, "registration_unknown")
            if (not any(item["fingerprint"] == material.fingerprint for item in after)
                    and records_hash(after) == state["baseline_hash"]):
                return journal.transition(operation, "registration_rejected")
            return journal.transition(operation, "registration_unknown")
        try:
            after = graph.read()
        except GraphError:
            return journal.transition(operation, "registration_unknown")
        return reconcile_registration(journal, operation, after)
    # Capture the service-assigned ID before the selected GET. Lost persistence is
    # still registration_started and can only reconcile, never send again.
    journal.transition(operation, "registration_unknown", response_key_id=returned)
    try:
        after = graph.read()
    except GraphError:
        return journal.state(operation)
    return reconcile_registration(journal, operation, after)


def verify_candidate(journal, operation, *, deadline, client_factory=certificate_client):
    """Fresh credential from the exact stored bytes; never AP07 observe()/proof."""
    state = journal.state(operation)
    if state is None or state["phase"] not in {"registered", "candidate_verified"}:
        raise GraphError("rotation_transition_invalid")
    material = journal.material(operation)
    with client_factory(journal.binding.config, material) as client:
        client.deadline = deadline
        result = client.probe()
    if result != {"mailbox_access": "ok"}:
        raise GraphError("rotation_candidate_probe_failed")
    return journal.transition(operation, "candidate_verified") if state["phase"] == "registered" else state
