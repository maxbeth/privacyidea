# -*- coding: utf-8 -*-
#
#  privacyIDEA
#  Aug 12, 2014 Cornelius Kölbel
#  License:  AGPLv3
#  contact:  http://www.privacyidea.org
#
#  2020-10-16 Cornelius Kölbel <cornelius.koelbel@netknights.it>
#             Add attestation certificate functionality
#  2016-04-26 Cornelius Kölbel <cornelius@privacyidea.org>
#             Add the possibility to create key pair on server side
#             Provide download for pkcs12 file
#
#  2015-05-15 Adapt during migration to flask
#             Cornelius Kölbel <cornelius@privacyidea.org>
#
# This code is free software; you can redistribute it and/or
# modify it under the terms of the GNU AFFERO GENERAL PUBLIC LICENSE
# License as published by the Free Software Foundation; either
# version 3 of the License, or any later version.
#
# This code is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU AFFERO GENERAL PUBLIC LICENSE for more details.
#
# You should have received a copy of the GNU Affero General Public
# License along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
"""
This file contains the definition of the CertificateToken class.

The code is tested in test_lib_tokens_certificate.py.
"""

import logging

from privacyidea.lib.utils import to_unicode, b64encode_and_unicode, to_byte_string
from privacyidea.lib.tokenclass import TokenClass
from privacyidea.lib.log import log_with
from privacyidea.api.lib.utils import getParam
from privacyidea.lib.caconnector import get_caconnector_object
from privacyidea.lib.user import get_user_from_param
from privacyidea.lib.utils import determine_logged_in_userparams
from OpenSSL import crypto
from cryptography.x509 import load_pem_x509_certificate, load_pem_x509_csr
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding
from privacyidea.lib.decorators import check_token_locked
from privacyidea.lib import _
from privacyidea.lib.policy import SCOPE, ACTION as BASE_ACTION, GROUP, Match
from privacyidea.lib.error import privacyIDEAError

optional = True
required = False

log = logging.getLogger(__name__)

YUBICO_ATTESTATION_ROOT_CERT = """-----BEGIN CERTIFICATE-----
MIIDFzCCAf+gAwIBAgIDBAZHMA0GCSqGSIb3DQEBCwUAMCsxKTAnBgNVBAMMIFl1
YmljbyBQSVYgUm9vdCBDQSBTZXJpYWwgMjYzNzUxMCAXDTE2MDMxNDAwMDAwMFoY
DzIwNTIwNDE3MDAwMDAwWjArMSkwJwYDVQQDDCBZdWJpY28gUElWIFJvb3QgQ0Eg
U2VyaWFsIDI2Mzc1MTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAMN2
cMTNR6YCdcTFRxuPy31PabRn5m6pJ+nSE0HRWpoaM8fc8wHC+Tmb98jmNvhWNE2E
ilU85uYKfEFP9d6Q2GmytqBnxZsAa3KqZiCCx2LwQ4iYEOb1llgotVr/whEpdVOq
joU0P5e1j1y7OfwOvky/+AXIN/9Xp0VFlYRk2tQ9GcdYKDmqU+db9iKwpAzid4oH
BVLIhmD3pvkWaRA2H3DA9t7H/HNq5v3OiO1jyLZeKqZoMbPObrxqDg+9fOdShzgf
wCqgT3XVmTeiwvBSTctyi9mHQfYd2DwkaqxRnLbNVyK9zl+DzjSGp9IhVPiVtGet
X02dxhQnGS7K6BO0Qe8CAwEAAaNCMEAwHQYDVR0OBBYEFMpfyvLEojGc6SJf8ez0
1d8Cv4O/MA8GA1UdEwQIMAYBAf8CAQEwDgYDVR0PAQH/BAQDAgEGMA0GCSqGSIb3
DQEBCwUAA4IBAQBc7Ih8Bc1fkC+FyN1fhjWioBCMr3vjneh7MLbA6kSoyWF70N3s
XhbXvT4eRh0hvxqvMZNjPU/VlRn6gLVtoEikDLrYFXN6Hh6Wmyy1GTnspnOvMvz2
lLKuym9KYdYLDgnj3BeAvzIhVzzYSeU77/Cupofj093OuAswW0jYvXsGTyix6B3d
bW5yWvyS9zNXaqGaUmP3U9/b6DlHdDogMLu3VLpBB9bm5bjaKWWJYgWltCVgUbFq
Fqyi4+JE014cSgR57Jcu3dZiehB6UtAPgad9L5cNvua/IWRmm+ANy3O2LH++Pyl8
SREzU8onbBsjMg9QDiSf5oJLKvd/Ren+zGY7
-----END CERTIFICATE-----"""

YUBICO_ATTESTATION_INTERMEDIATE = """-----BEGIN CERTIFICATE-----
MIIC+jCCAeKgAwIBAgIJAIZ3F+AdGSsmMA0GCSqGSIb3DQEBCwUAMCsxKTAnBgNV
BAMMIFl1YmljbyBQSVYgUm9vdCBDQSBTZXJpYWwgMjYzNzUxMCAXDTE2MDMxNDAw
MDAwMFoYDzIwNTIwNDE3MDAwMDAwWjAhMR8wHQYDVQQDDBZZdWJpY28gUElWIEF0
dGVzdGF0aW9uMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAxVuN6bk8
U2mCiP7acPxciHhBJaIde4SOkzatZytMq0W+suDVnBuhaNVr+GNcg8uDOGK3ZK6D
NzeOyGCA5gH4daqu9m6n1XbFwSWtqp6d3LV+6Y4qtD+ZDfefIKAooJ+zsSJfrzj7
c0b0x5Mw3frQhuDJxnKZr/sklwWHh91hRW+BhspDCNzeBKOm1qYglknKDI/FnacL
kCyNaYlb5JdnUEx+L8iq2SWkAg57UPOIT0Phz3RvxXCguMj+BWsSAPVhv5lnABha
L0b/y7V4OprZKfkSolVuYHS5YqRVnDepJ7IylEpdMpEW4/7rOHSMqocIEB8SPt2T
jibBrZvzkcoJbwIDAQABoykwJzARBgorBgEEAYLECgMDBAMFAQIwEgYDVR0TAQH/
BAgwBgEB/wIBADANBgkqhkiG9w0BAQsFAAOCAQEABVe3v1pBdPlf7C7SuHgm5e9P
6r9aZMnPBn/KjAr8Gkcc1qztyFtUcgCfuFmrcyWy1gKjWYMxae7BXz3yKxsiyrb8
+fshMp4I8whUbckmEEIIHTy18FqxmNRo3JHx05FUeqA0i/Zl6xOfOhy/Q8XR0DMj
xiWgTOTpqlmA2AIesBBfuOENDDAccukRMLTXDY97L2luDFTJ99NaHKjjhCOLHmTS
BuCSS5h/F6roSi7rjh2bEOaErLG+G1hVWAzfBNXgrsUuirWRk0WKhJKeUrfNPILh
CzYH/zLEaIsLjRg+tnmKJu2E4IdodScri7oGVhVyhUW5DrcX+/8CPqnoBpd7zQ==
-----END CERTIFICATE-----
"""

VERIFY_CERTIFICATE_CHAIN = True
DEFAULT_CA_PATH = ["/etc/privacyidea/trusted_attestation_ca"]


class ACTION(BASE_ACTION):
    __doc__ = """This is the list of special certificate actions."""
    TRUSTED_CA_PATH = "trusted_Attestation_CA_path"
    REQUIRE_ATTESTATION = "require_attestation"


def _verify_cert(parent, child):
    ca = load_pem_x509_certificate(to_byte_string(parent), default_backend())
    cert = load_pem_x509_certificate(to_byte_string(child), default_backend())
    ca.public_key().verify(
        cert.signature,
        cert.tbs_certificate_bytes,
        padding.PKCS1v15(),
        cert.signature_hash_algorithm
    )


def verify_certificate_path(certificate, trusted_ca_paths):
    """
    Verify a certificate against the list of directories each containing files with
    a certificate chain.

    :param certificate: The PEM certificate to verify
    :param trusted_ca_paths: A list of directories
    :return: True or False
    """
    from os import listdir
    from os.path import isfile, join, isdir
    verified = False
    for capath in trusted_ca_paths:
        if isdir(capath):
            chainfiles = [join(capath, f) for f in listdir(capath) if isfile(join(capath, f))]
            for chainfile in chainfiles:
                chain = parse_chainfile(chainfile)
                try:
                    verify_certificate(to_byte_string(certificate), chain)
                    verified = True
                except Exception as exx:
                    log.debug(u"Can not verify attestation certificate against chain {0!s}.".format(chain))
        else:
            log.warning("The configured attestation CA directory does not exist.")
    return verified


def parse_chainfile(chainfile):
    """
    Parse a text file, that contains a list of CA files.
    The topmost being the trusted Root CA followed by intermediate

    :param chainfile: The filename to parse
    :return: A list of PEM certificates
    """
    cacerts = []
    cacert = ""
    with open(chainfile) as f:
        lines = f.readlines()
    for line in lines:
        if line.startswith("-----BEGIN CERTIFICATE-----"):
            cacert = line
        elif line.startswith("-----END CERTIFICATE-----"):
            cacert += line
            # End of certificate
            cacerts.append(cacert)
        elif line.startswith("#") or line == "":
            # Empty line or comment
            pass
        else:
            cacert += line
    return cacerts


def verify_certificate(certificate, chain):
    """
    Verify a certificate against the certificate chain, which can be of any length

    The certificate chain starts with the root certificate and contains further
    intermediate certificates

    :param certificate: The certificate
    :type certificate: PEM encoded string
    :param chain: A list of PEM encoded certificates
    :type chain: list
    :return: raises an exception
    """
    # first reverse the list, since it can be popped better
    chain = list(reversed(chain))
    if not chain:
        raise privacyIDEAError("Can not verify certificate against an empty chain.")
    # verify chain
    while chain:
        signer = chain.pop()
        if chain:
            # There is another element in the list, so we check the intermediate:
            signee = chain.pop()
            _verify_cert(signer, signee)
            signer = signee

    # This was the last certificate in the chain, so we check the certificate
    _verify_cert(signer, certificate)


class CertificateTokenClass(TokenClass):
    """
    Token to implement an X509 certificate.
    The certificate can be enrolled by sending a CSR to the server or the
    keypair is created by the server. If the server creates the keypair,
    the user can download a PKCS12 file.
    The OTP PIN is used as passphrase for the PKCS12 file.

    privacyIDEA is capable of working with different CA connectors.

    Valid parameters are *request* or *certificate*, both PEM encoded.
    If you pass a *request* you also need to pass the *ca* that should be
    used to sign the request. Passing a *certificate* just uploads the
    certificate to a new token object.

    A certificate token can be created by an administrative task with the
    token/init api like this:

      **Example Initialization Request**:

        .. sourcecode:: http

           POST /auth HTTP/1.1
           Host: example.com
           Accept: application/json

           type=certificate
           user=cornelius
           realm=realm1
           request=<PEM encoded request>
           attestation=<PEM encoded attestation certificate>
           ca=<name of the ca connector>

      **Example Initialization Request, key generation on servers side**

      In this case the certificate is created on behalf of another user.

        .. sourcecode:: http

           POST /auth HTTP/1.1
           Host: example.com
           Accept: application/json

           type=certificate
           user=cornelius
           realm=realm1
           generate=1
           ca=<name of the ca connector>

      **Example response**:

           .. sourcecode:: http

               HTTP/1.1 200 OK
               Content-Type: application/json

               {
                  "detail": {
                    "certificate": "...PEM..."
                  },
                  "id": 1,
                  "jsonrpc": "2.0",
                  "result": {
                    "status": true,
                    "value": true
                  },
                  "version": "privacyIDEA unknown"
                }

    """
    using_pin = False
    hKeyRequired = False

    def __init__(self, aToken):
        TokenClass.__init__(self, aToken)
        self.set_type(u"certificate")
        self.otp_len = 0

    @staticmethod
    def get_class_type():
        return "certificate"

    @staticmethod
    def get_class_prefix():
        return "CRT"

    @staticmethod
    @log_with(log)
    def get_class_info(key=None, ret='all'):
        """
        returns a subtree of the token definition

        :param key: subsection identifier
        :type key: string
        :param ret: default return value, if nothing is found
        :type ret: user defined
        :return: subsection if key exists or user defined
        :rtype: dict or scalar
        """
        res = {'type': 'certificate',
               'title': 'Certificate Token',
               'description': _('Certificate: Enroll an x509 Certificate '
                                'Token.'),
               'init': {},
               'config': {},
               'user':  ['enroll'],
               # This tokentype is enrollable in the UI for...
               'ui_enroll': ["admin", "user"],
               'policy': {
                   SCOPE.ENROLL: {
                       ACTION.MAXTOKENUSER: {
                           'type': 'int',
                           'desc': _("The user may only have this maximum number of certificates assigned."),
                           'group': GROUP.TOKEN
                       },
                       ACTION.MAXACTIVETOKENUSER: {
                           'type': 'int',
                           'desc': _("The user may only have this maximum number of active certificates assigned."),
                           'group': GROUP.TOKEN
                       },
                       ACTION.REQUIRE_ATTESTATION: {
                           'type': 'string',
                           'desc': _("Enrolling a certificate token can require an attestation certificate. "
                                     "(Default: ignore)"),
                           'group': GROUP.TOKEN,
                           'value': [""]
                       }
                   },
                   SCOPE.USER: {
                       ACTION.TRUSTED_CA_PATH: {
                           'type': 'str',
                           'desc': _("The directory containing attestation certificate chains."),
                           'group': GROUP.TOKEN
                       }
                   },
                   SCOPE.ADMIN: {
                       ACTION.TRUSTED_CA_PATH: {
                           'type': 'str',
                           'desc': _("The directory containing attestation certificate chains."),
                           'group': GROUP.TOKEN
                       }
                   }
               }
               }
        if key:
            ret = res.get(key, {})
        else:
            if ret == 'all':
                ret = res
        return ret

    @classmethod
    def get_default_settings(cls, g, params):
        """
        This method returns a dictionary with additional settings for token
        enrollment.
        The settings that are evaluated are
        SCOPE.ADMIN|SCOPE.USER, action=trusted_Assertion_CA_path
        It sets a list of configured paths.

        The returned dictionary is added to the parameters of the API call.
        :param g: context object, see documentation of ``Match``
        :param params: The call parameters
        :type params: dict
        :return: default parameters
        """
        ret = {ACTION.TRUSTED_CA_PATH: DEFAULT_CA_PATH}
        (role, username, userrealm, adminuser, adminrealm) = determine_logged_in_userparams(g.logged_in_user,
                                                                                            params)
        # Now we fetch CA-pathes from the policies
        paths = Match.generic(g, scope=role,
                              action="{0!s}_{1!s}".format(cls.get_class_type(), ACTION.TRUSTED_CA_PATH),
                              user=username,
                              realm=userrealm,
                              adminuser=adminuser,
                              adminrealm=adminrealm).action_values(unique=False,
                                                                   allow_white_space_in_action=True)
        if paths:
            ret[ACTION.TRUSTED_CA_PATH] = list(paths)

        return ret

    def update(self, param):
        """
        This method is called during the initialization process.
        :param param: parameters from the token init
        :type param: dict
        :return: None
        """
        TokenClass.update(self, param)

        request = getParam(param, "request", optional)
        spkac = getParam(param, "spkac", optional)
        certificate = getParam(param, "certificate", optional)
        generate = getParam(param, "genkey", optional)
        template_name = getParam(param, "template", optional)
        if request or generate:
            # If we do not upload a user certificate, then we need a CA do
            # sign the uploaded request or generated certificate.
            ca = getParam(param, "ca", required)
            self.add_tokeninfo("CA", ca)
            cacon = get_caconnector_object(ca)
        if request:
            request_csr = load_pem_x509_csr(to_byte_string(request), default_backend())
            if not request_csr.is_signature_valid:
                raise privacyIDEAError("request has invalid signature.")
            # If a request is sent, we can have an attestation certificate
            attestation = getParam(param, "attestation", optional)
            if attestation:
                request_numbers = request_csr.public_key().public_numbers()
                attestation_cert = load_pem_x509_certificate(to_byte_string(attestation), default_backend())
                attestation_numbers = attestation_cert.public_key().public_numbers()
                if request_numbers != attestation_numbers:
                    log.warning("certificate request does not match attestation certificate.")
                    raise privacyIDEAError("certificate request does not match attestation certificate.")
                if VERIFY_CERTIFICATE_CHAIN:
                    verified = verify_certificate_path(attestation,
                                                       param.get(ACTION.TRUSTED_CA_PATH))
                    if not verified:
                        raise privacyIDEAError("Failed to verify certificate chain of attestation certificate.")

            # During the initialization process, we need to create the
            # certificate
            x509object = cacon.sign_request(request,
                                            options={"spkac": spkac,
                                                     "template": template_name})
            certificate = crypto.dump_certificate(crypto.FILETYPE_PEM,
                                                  x509object)
        elif generate:
            # Create the certificate on behalf of another user.
            # Now we need to create the key pair,
            # the request
            # and the certificate
            # We need the user for whom the certificate should be created
            user = get_user_from_param(param, optionalOrRequired=required)

            keysize = getParam(param, "keysize", optional, 2048)
            key = crypto.PKey()
            key.generate_key(crypto.TYPE_RSA, keysize)
            req = crypto.X509Req()
            req.get_subject().CN = user.login
            # Add email to subject
            if user.info.get("email"):
                req.get_subject().emailAddress = user.info.get("email")
            req.get_subject().organizationalUnitName = user.realm
            # TODO: Add Country, Organization, Email
            # req.get_subject().countryName = 'xxx'
            # req.get_subject().stateOrProvinceName = 'xxx'
            # req.get_subject().localityName = 'xxx'
            # req.get_subject().organizationName = 'xxx'
            req.set_pubkey(key)
            req.sign(key, "sha256")
            csr = to_unicode(crypto.dump_certificate_request(crypto.FILETYPE_PEM, req))
            x509object = cacon.sign_request(csr, options={"template": template_name})
            certificate = crypto.dump_certificate(crypto.FILETYPE_PEM,
                                                  x509object)
            # Save the private key to the encrypted key field of the token
            s = crypto.dump_privatekey(crypto.FILETYPE_PEM, key)
            self.add_tokeninfo("privatekey", s, value_type="password")

        if "pin" in param:
            self.set_pin(param.get("pin"), encrypt=True)

        if certificate:
            self.add_tokeninfo("certificate", certificate)

    @log_with(log)
    def get_init_detail(self, params=None, user=None):
        """
        At the end of the initialization we return the certificate and the
        PKCS12 file, if the private key exists.
        """
        response_detail = TokenClass.get_init_detail(self, params, user)
        params = params or {}
        certificate = self.get_tokeninfo("certificate")
        response_detail["certificate"] = certificate
        privatekey = self.get_tokeninfo("privatekey")
        # If there is a private key, we dump a PKCS12
        if privatekey:
            response_detail["pkcs12"] = b64encode_and_unicode(self._create_pkcs12_bin())

        return response_detail

    def _create_pkcs12_bin(self):
        """
        Helper function to create an encrypted pkcs12 binary for download

        :return: PKCS12 binary
        """
        certificate = self.get_tokeninfo("certificate")
        privatekey = self.get_tokeninfo("privatekey")
        pkcs12 = crypto.PKCS12()
        pkcs12.set_certificate(crypto.load_certificate(
            crypto.FILETYPE_PEM, certificate))
        pkcs12.set_privatekey(crypto.load_privatekey(crypto.FILETYPE_PEM,
                                                     privatekey))
        # TODO define a random passphrase and hand it to the user
        passphrase = self.token.get_pin()
        if passphrase == -1:
            passphrase = ""
        pkcs12_bin = pkcs12.export(passphrase=passphrase.encode('utf8'))
        return pkcs12_bin

    def get_as_dict(self):
        """
        This returns the token data as a dictionary.
        It is used to display the token list at /token/list.

        The certificate token can add the PKCS12 file if it exists

        :return: The token data as dict
        :rtype: dict
        """
        # first get the database values as dict
        token_dict = self.token.get()

        if "privatekey" in token_dict.get("info"):
            token_dict["info"]["pkcs12"] = b64encode_and_unicode(self._create_pkcs12_bin())

        return token_dict

    @check_token_locked
    def set_pin(self, pin, encrypt=False):
        """
        set the PIN of a token.
        The PIN of the certificate token is stored encrypted. It is used as
        passphrase for the PKCS12 file.

        :param pin: the pin to be set for the token
        :type pin: basestring
        :param encrypt: If set to True, the pin is stored encrypted and
                        can be retrieved from the database again
        :type encrypt: bool
        """
        storeHashed = False
        self.token.set_pin(pin, storeHashed)

    def revoke(self):
        """
        This revokes the token. We need to determine the CA, which issues the
        certificate, contact the connector and revoke the certificate

        Some token types may revoke a token without locking it.
        """
        TokenClass.revoke(self)

        # determine the CA and its connector.
        ti = self.get_tokeninfo()
        ca_specifier = ti.get("CA")
        log.debug("Revoking certificate {0!s} on CA {1!s}.".format(
            self.token.serial, ca_specifier))
        certificate_pem = ti.get("certificate")

        # call CAConnector.revoke_cert()
        ca_obj = get_caconnector_object(ca_specifier)
        revoked = ca_obj.revoke_cert(certificate_pem)
        log.info("Certificate {0!s} revoked on CA {1!s}.".format(revoked,
                                                                 ca_specifier))

        # call CAConnector.create_crl()
        crl = ca_obj.create_crl()
        log.info("CRL {0!s} created.".format(crl))

        return revoked
