"""Real loopback TLS handshakes using synthetic CA/keys; no LDAP/customer secrets."""
import gc
import warnings
import datetime
import socket
import ssl
import tempfile
import threading
import unittest
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID
from ldap3 import Server,NONE
from ldap3.core.exceptions import LDAPException
from app.directory import LdapDirectory
from app.settings import LdapSettings

class RealTlsTests(unittest.TestCase):
    def test_real_hostname_and_ca_validation_without_insecure_fallback(self):
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter("always", ResourceWarning)
            now=datetime.datetime.now(datetime.timezone.utc)
            ca_key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            ca_name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"Synthetic test CA")])
            ca=(x509.CertificateBuilder().subject_name(ca_name).issuer_name(ca_name)
                .public_key(ca_key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=1))
                .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
                .sign(ca_key,hashes.SHA256()))
            key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,"dc1.example.invalid")])
            cert=(x509.CertificateBuilder().subject_name(name).issuer_name(ca_name)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now-datetime.timedelta(minutes=1)).not_valid_after(now+datetime.timedelta(days=1))
                .add_extension(x509.SubjectAlternativeName([x509.DNSName("dc1.example.invalid")]),critical=False)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
                .sign(ca_key,hashes.SHA256()))
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory)
                (root/"ca.pem").write_bytes(ca.public_bytes(serialization.Encoding.PEM))
                (root/"cert.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
                (root/"key.pem").write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
                context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(root/"cert.pem",root/"key.pem")
                listener=socket.socket();listener.bind(("127.0.0.1",0));listener.listen()
                listener.settimeout(0.2)
                port=listener.getsockname()[1];stop=threading.Event()
                def serve():
                    while not stop.is_set():
                        try:
                            raw,_=listener.accept()
                        except socket.timeout:
                            continue
                        except OSError:
                            break
                        try:
                            raw.settimeout(1)
                            with context.wrap_socket(raw,server_side=True) as stream:
                                stream.recv(4096)
                        except (OSError,ssl.SSLError):
                            raw.close()
                thread=threading.Thread(target=serve,daemon=True);thread.start()
                cfg=LdapSettings(servers=["dc1.example.invalid"],port=port,search_base="DC=example,DC=invalid",
                    bind_user="ldap@example.invalid",admin_group="CN=Admins,DC=example,DC=invalid",
                    reader_group="CN=Readers,DC=example,DC=invalid",connect_timeout=2,receive_timeout=2)
                def connection(ca_file,hostname):
                    adapter=LdapDirectory(str(ca_file))
                    # Transport loopback; the actual production Tls object retains FQDN/SNI/CA policy.
                    tls=adapter._server(cfg,hostname).tls
                    server=Server("127.0.0.1",port=port,use_ssl=True,tls=tls,get_info=NONE,connect_timeout=2)
                    return adapter._connection(server,"synthetic","synthetic",cfg)
                try:
                    good=connection(root/"ca.pem","dc1.example.invalid")
                    good.open(read_server_info=False)
                    self.assertFalse(good.closed)
                    good.unbind()
                    for ca_file,hostname in ((root/"ca.pem","dc2.example.invalid"),("/etc/ssl/certs/ca-certificates.crt","dc1.example.invalid")):
                        with self.subTest(ca=str(ca_file),host=hostname):
                            bad=connection(ca_file,hostname)
                            try:
                                bad.open(read_server_info=False)
                            except LDAPException:
                                pass
                            else:
                                self.assertTrue(bad.closed,"TLS accepted invalid hostname/trust")
                            finally:
                                bad.unbind()
                finally:
                    stop.set();listener.close();thread.join(timeout=3)
            gc.collect()
            self.assertFalse([w for w in observed if issubclass(w.category,ResourceWarning)], "TLS failure leaked a transport")
