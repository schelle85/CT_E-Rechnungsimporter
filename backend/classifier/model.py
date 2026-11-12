from dataclasses import asdict, dataclass


class RecognitionError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class Finding:
    status: str
    category: str | None
    format: str | None
    reason: str
    method: str = "structure"

    def result(self, digest):
        return {**asdict(self), "original_sha256": digest, "rule_version": "ap03-3"}


def failed(code):
    return Finding("failed", None, None, code)


def ignored(code="unsupported_attachment"):
    return Finding("ignored", None, None, code)
