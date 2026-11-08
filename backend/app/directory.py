import ssl
import time
from dataclasses import dataclass
from ldap3 import Server, Connection, Tls, NONE, BASE, SUBTREE
from ldap3.core.exceptions import LDAPException
from ldap3.core.tls import check_hostname
from ldap3.utils.conv import escape_filter_chars, escape_bytes
from app.errors import DirectoryDenied, DirectoryUnavailable

class ClosingTls(Tls):
    """ldap3 2.9.1 assigns its socket only after hostname validation.
    Adopt it before the handshake so failures can always close it. Certificate
    validation remains OpenSSL CERT_REQUIRED; names use ldap3's own checker.
    """
    def wrap_socket(self, connection, do_handshake=False):
        try:
            super().wrap_socket(connection, do_handshake=False)
            if do_handshake:
                connection.socket.do_handshake()
                if self.validate in (ssl.CERT_REQUIRED, ssl.CERT_OPTIONAL):
                    check_hostname(connection.socket, connection.server.host, self.valid_names)
        except BaseException:
            if connection.socket is not None:
                connection.socket.close()
            raise

@dataclass(frozen=True)
class Principal:
    guid: str
    dn: str
    username: str
    role: str

class LdapDirectory:
    def __init__(self, ca_file):
        self.ca_file = ca_file

    def _server(self, cfg, host):
        tls = ClosingTls(validate=ssl.CERT_REQUIRED, version=ssl.PROTOCOL_TLS_CLIENT,
                  ca_certs_file=self.ca_file, valid_names=[host], sni=host)
        return Server(host, port=cfg.port, use_ssl=True, tls=tls,
                      get_info=NONE, connect_timeout=cfg.connect_timeout)

    def _connection(self, server, user, password, cfg):
        return Connection(server, user=user, password=password, auto_referrals=False,
                          read_only=True, receive_timeout=cfg.receive_timeout,
                          raise_exceptions=False)

    @staticmethod
    def _close(connection):
        try:
            connection.unbind()
        except (LDAPException, OSError):
            pass
        finally:
            transport=getattr(connection,"socket",None)
            if transport is not None:
                try:
                    transport.close()
                except OSError:
                    pass

    def _run(self, cfg, bind_password, operation, only_host=None):
        for host in ([only_host] if only_host else cfg.servers):
            connection = None
            try:
                connection = self._connection(self._server(cfg, host), cfg.bind_user, bind_password, cfg)
                if not connection.bind():
                    if connection.result.get("result") in (51, 52):
                        continue
                    raise DirectoryUnavailable()
                return operation(connection, host)
            except (LDAPException, OSError, ssl.SSLError):
                continue
            finally:
                if connection is not None:
                    self._close(connection)
        raise DirectoryUnavailable()

    @staticmethod
    def _search(connection, base, query, scope=SUBTREE, attributes=None):
        connection.search(base, query, search_scope=scope,
                          attributes=attributes or ["distinguishedName"], size_limit=2)
        if connection.result.get("result") != 0:
            raise DirectoryUnavailable()
        rows = [x for x in connection.response if x.get("type") == "searchResEntry"]
        if len(rows) != 1:
            raise DirectoryDenied()
        return rows[0]

    @staticmethod
    def _principal(entry, cfg):
        raw = {k.lower():v for k,v in entry.get("raw_attributes", {}).items()}
        def number(name, required=False):
            values = raw.get(name.lower(), [])
            if not values:
                if required:
                    raise DirectoryDenied()
                return 0
            try:
                return int(values[0])
            except (ValueError, TypeError):
                raise DirectoryDenied() from None
        uac = number("userAccountControl", True)
        computed = number("msDS-User-Account-Control-Computed", True)
        expires = number("accountExpires")
        if uac & 2 or computed & (16 | 8388608):
            raise DirectoryDenied()
        if expires not in (0, 9223372036854775807) and expires <= int((time.time()+11644473600)*10000000):
            raise DirectoryDenied()
        guid_values = raw.get("objectguid", [])
        if len(guid_values)!=1 or len(guid_values[0])!=16:
            raise DirectoryDenied()
        attrs = {k.lower():v for k,v in entry.get("attributes", {}).items()}
        groups = attrs.get("memberof", [])
        if isinstance(groups, str):
            groups = [groups]
        groups = {str(x).casefold() for x in groups}
        role = "admin" if cfg.admin_group.casefold() in groups else "reader" if cfg.reader_group.casefold() in groups else None
        if role is None:
            raise DirectoryDenied()
        names = attrs.get("samaccountname", [])
        name = names[0] if isinstance(names, list) and names else names
        if not isinstance(name, str) or not name:
            raise DirectoryDenied()
        return Principal(guid_values[0].hex(), entry["dn"], name, role)

    def _lookup(self, connection, cfg, query):
        entry = self._search(connection, cfg.search_base, query, attributes=[
            "objectGUID", "sAMAccountName", "memberOf", "userAccountControl",
            "msDS-User-Account-Control-Computed", "accountExpires"])
        return entry, self._principal(entry, cfg)

    def authenticate(self, cfg, bind_password, username, password):
        if not password:
            raise DirectoryDenied()
        escaped = escape_filter_chars(username)
        query = "(&(objectCategory=person)(objectClass=user)(|(sAMAccountName="+escaped+")(userPrincipalName="+escaped+")))"
        def operation(connection, host):
            entry, principal = self._lookup(connection, cfg, query)
            user_connection = self._connection(connection.server, entry["dn"], password, cfg)
            try:
                # A bind may already have reached AD when a transport error occurs.
                # After starting it, never resend credentials through _run failover.
                try:
                    bound=user_connection.bind()
                except (LDAPException, OSError):
                    raise DirectoryUnavailable() from None
                if not bound:
                    if user_connection.result.get("result") in (51, 52):
                        raise DirectoryUnavailable()
                    raise DirectoryDenied()
            finally:
                self._close(user_connection)
            return principal
        return self._run(cfg, bind_password, operation)

    def revalidate(self, cfg, bind_password, guid):
        try:
            binary = bytes.fromhex(guid)
        except ValueError:
            raise DirectoryDenied() from None
        if len(binary)!=16:
            raise DirectoryDenied()
        query = "(&(objectCategory=person)(objectClass=user)(objectGUID="+escape_bytes(binary)+"))"
        return self._run(cfg, bind_password, lambda connection,host:self._lookup(connection,cfg,query)[1])

    def validate(self, cfg, bind_password):
        # Every configured server and both exact direct-role group DNs must work.
        for host in cfg.servers:
            def operation(connection, selected):
                for group in (cfg.admin_group, cfg.reader_group):
                    self._search(connection, group, "(objectClass=group)", BASE)
                return True
            self._run(cfg, bind_password, operation, only_host=host)
