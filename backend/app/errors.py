class AccessError(Exception):
    def __init__(self, status=401, detail="Anmeldung oder Sitzung nicht gültig."):
        self.status, self.detail = status, detail

class DirectoryDenied(Exception):
    pass

class DirectoryUnavailable(Exception):
    pass
