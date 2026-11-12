"""Explicit actions only. No scan-to-action or success/classification automation."""
from urllib.parse import quote
from app.graph import GraphError
from app.graph_mail import Mailbox, identifier

FOLDERS = ("Success", "Failed", "Nachfragen", "Zahlungsavis", "unzugeordnet")


class GraphActions:
    def __init__(self, client, store):
        self.client, self.store, self.mailbox = client, store, Mailbox(client)

    def folders(self):
        inbox = self.mailbox.inbox_id()
        collection = self.client.root + "/mailFolders/inbox/childFolders"
        names = {n.casefold(): n for n in FOLDERS}
        result, seen = {}, {}
        for row in self.mailbox._pages(collection,
                {"$select": "id,displayName,parentFolderId,isHidden", "$top": "100", "includeHiddenFolders": "true"}, 1000):
            name = row.get("displayName")
            if not isinstance(name, str):
                raise GraphError("graph_invalid_folder")
            if name.casefold() not in names:
                continue
            folder_id = identifier(row.get("id"))
            identity = (name, row.get("parentFolderId"), row.get("isHidden"))
            if folder_id in seen:
                if seen[folder_id] != identity:
                    raise GraphError("graph_folder_changed")
                continue
            seen[folder_id] = identity
            if row.get("parentFolderId") != inbox or row.get("isHidden") is not False:
                raise GraphError("graph_invalid_folder")
            canonical = names[name.casefold()]
            if canonical in result:
                raise GraphError("graph_ambiguous_folder")
            result[canonical] = folder_id
        return result

    def _run(self, kind, resource, target, desired, mutate):
        key, owner, may_send = self.store.claim(self.client.config.mailbox, kind, resource, target)
        mutation_started = False
        try:
            result = desired()
            if result is None:
                if not may_send:
                    raise GraphError("graph_action_operator_required", uncertain=True)
                mutation_started = True
                mutate()
                result = desired()
                if result is None:
                    raise GraphError("graph_action_not_observed", uncertain=True)
            self.store.finish(key, owner, "done", result=result)
            return result
        except GraphError as error:
            if mutation_started:
                try:
                    result = desired()
                except GraphError:
                    result = None
                if result is not None:
                    try:
                        self.store.finish(key, owner, "done", result=result)
                    except GraphError as confirmation_error:
                        raise GraphError(confirmation_error.code, confirmation_error.status, uncertain=True) from None
                    return result
            terminal = error.code in ("graph_before_cutoff", "graph_invalid_received_time", "graph_invalid_source_folder",
                                      "graph_existing_completed_flag", "graph_action_operator_required", "graph_ambiguous_folder")
            try:
                self.store.finish(key, owner, "operator_required" if terminal else "unknown", error=error.code)
            except GraphError as persistence_error:
                raise GraphError(persistence_error.code, persistence_error.status,
                                 uncertain=error.uncertain or mutation_started or not may_send) from None
            raise GraphError(error.code, error.status,
                             uncertain=error.uncertain or mutation_started or not may_send) from None

    def ensure_folders(self):
        result = {}
        for name in FOLDERS:
            def desired(name=name):
                return self.folders().get(name)
            def mutate(name=name):
                # Reconcile again immediately before the one permitted POST.
                if name not in self.folders():
                    self.client._write("POST", self.client.root + "/mailFolders/inbox/childFolders",
                                       {"displayName": name, "isHidden": False}, expected=201)
            result[name] = self._run("folder", name, name, desired, mutate)
        return result

    def _allowed_message(self, message_id, folders):
        current = self.mailbox.message(message_id)  # Real receivedDateTime; no caller timestamp.
        if current.parent_id not in {self.mailbox.inbox_id(), *folders.values()}:
            raise GraphError("graph_invalid_source_folder")
        return current

    def flag(self, message_id):
        message_id = identifier(message_id)
        def desired():
            current = self._allowed_message(message_id, self.folders())
            if current.flag == "complete":
                raise GraphError("graph_existing_completed_flag")
            return current.id if current.flag == "flagged" else None
        def mutate():
            current = self._allowed_message(message_id, self.folders())
            if current.flag == "complete":
                raise GraphError("graph_existing_completed_flag")
            if current.flag != "flagged":
                self.client._write("PATCH", self.client.root + "/messages/" + quote(current.id, safe=""),
                                   {"flag": {"flagStatus": "flagged"}}, expected=200)
        return self._run("flag", message_id, "flagged", desired, mutate)

    def move(self, message_id, destination):
        message_id = identifier(message_id)
        if destination not in FOLDERS:
            raise GraphError("graph_invalid_destination")
        def state():
            folders = self.folders()
            target = folders.get(destination)
            if target is None:
                raise GraphError("graph_destination_missing")
            current = self._allowed_message(message_id, folders)
            if current.parent_id not in (self.mailbox.inbox_id(), target):
                raise GraphError("graph_invalid_source_folder")
            return current, target
        def desired():
            current, target = state()
            return current.id if current.parent_id == target else None
        def mutate():
            current, target = state()
            if current.parent_id != target:
                self.client._write("POST", self.client.root + "/messages/" + quote(current.id, safe="") + "/move",
                                   {"destinationId": target}, expected=201)
        return self._run("move", message_id, destination, desired, mutate)
