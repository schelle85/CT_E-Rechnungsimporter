"""One attachment operation; no mailbox actions, scheduling, or API activation."""
from dataclasses import dataclass
from sqlalchemy.exc import SQLAlchemyError
from app.storage_files import StorageCollision
from app.storage_plan import StorageError


@dataclass(frozen=True)
class StorageResult:
    action_key: str
    status: str
    target: str | None = None
    reason: str | None = None


def store_attachment(store, files, request, input_file):
    if store.destination_key != files.destination_key:
        return StorageResult(request.key, "failed", reason="storage_destination_conflict")
    try:
        row = store.claim(request)
    except StorageError as error:
        return StorageResult(request.key, "failed", reason=error.code)
    except SQLAlchemyError:
        return StorageResult(request.key, "failed", reason="storage_persistence_failed")
    mode, owner = row["mode"], row["owner"]
    if mode == "done":
        return StorageResult(request.key, row["state"], row["target"])
    if mode in ("busy", "operator_required"):
        return StorageResult(request.key, mode, reason="storage_first_operation_pending")
    publication_reserved = mode == "reconcile"
    known_rejected = bool(row["publication_rejected"])
    try:
        if mode == "reconcile":
            # An existing foreign target is insufficient while our stage still exists.
            if (row["publication_attempts"] and not known_rejected and not files.stage_exists(row["stage_name"])
                    and files.matches(row["target"], request)):
                store.finish(request.key, owner, "stored")
                return StorageResult(request.key, "stored", row["target"])
            raise StorageError("storage_publication_uncertain")
        files.stage(row["stage_name"], input_file, request)
        for attempt in range(2):
            publication_reserved = True  # Even a lost DB commit acknowledgement is uncertain.
            store.begin_publication(request.key, owner)
            known_rejected = False
            try:
                files.publish(row["stage_name"], row["target"])
                break
            except StorageCollision:
                known_rejected = True
                if attempt:
                    raise StorageError("storage_path_conflict") from None
                row["target"] = store.collision(request, owner)
        store.finish(request.key, owner, "stored")
        return StorageResult(request.key, "stored", row["target"])
    except (StorageError, OSError, SQLAlchemyError) as error:
        reason = error.code if isinstance(error, StorageError) else (
            "storage_persistence_failed" if isinstance(error, SQLAlchemyError) else "storage_io_failed")
        try:
            store.finish(request.key, owner, "operator_required", error=reason, rejected=known_rejected)
        except (StorageError, SQLAlchemyError):
            pass  # Keep the prior durable reservation; no second external effect.
        return StorageResult(request.key, "operator_required" if publication_reserved else "failed", reason=reason)
