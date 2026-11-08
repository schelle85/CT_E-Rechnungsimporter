import ipaddress
from pathlib import Path
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from cryptography.fernet import Fernet

def read_secret(path):
    value = Path(path).read_bytes()
    if value.endswith(b"\r\n"):
        value = value[:-2]
    elif value.endswith(b"\n"):
        value = value[:-1]
    return value.decode("utf-8")

def load_cipher(path):
    try:
        return Fernet(read_secret(path).encode("ascii"))
    except (OSError, ValueError, UnicodeError):
        raise RuntimeError("Stable configuration key unavailable.") from None

def public_origin(value):
    part = urlsplit(value)
    if part.scheme != "https" or not part.hostname or part.username or part.password or part.path not in ("", "/") or part.query or part.fragment:
        raise RuntimeError("PUBLIC_ORIGIN must be one HTTPS origin.")
    return "https://" + part.netloc.lower()

class LdapSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    servers: list[str] = Field(min_length=1, max_length=3)
    port: int = Field(default=636, ge=1, le=65535)
    search_base: str = Field(min_length=1, max_length=2048)
    bind_user: str = Field(min_length=1, max_length=512)
    admin_group: str = Field(min_length=1, max_length=2048)
    reader_group: str = Field(min_length=1, max_length=2048)
    connect_timeout: int = Field(default=3, ge=1, le=5)
    receive_timeout: int = Field(default=5, ge=1, le=5)

    @field_validator("servers")
    @classmethod
    def hostnames(cls, values):
        import re
        result = []
        for value in values:
            host = value.encode("idna").decode("ascii").lower()
            try:
                ipaddress.ip_address(host)
            except ValueError:
                pass
            else:
                raise ValueError("FQDN required")
            if len(host)>253 or "." not in host or not all(re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x) for x in host.split(".")):
                raise ValueError("FQDN required")
            if host in result:
                raise ValueError("Duplicate server")
            result.append(host)
        return result

    @field_validator("search_base", "bind_user", "admin_group", "reader_group")
    @classmethod
    def no_controls(cls, value):
        if any(ord(c)<32 for c in value):
            raise ValueError("Control characters forbidden")
        return value

class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=1024)

class ConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    settings: LdapSettings
    bind_password: SecretStr | None = Field(default=None, min_length=1, max_length=1024)
