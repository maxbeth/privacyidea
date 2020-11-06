"""
This test file tests the lib.tokens.certificatetoken
"""

from .base import MyTestCase, FakeFlaskG, FakeAudit
from privacyidea.lib.tokens.certificatetoken import CertificateTokenClass
from privacyidea.models import Token
from privacyidea.lib.caconnector import save_caconnector
from privacyidea.lib.token import get_tokens, remove_token
from privacyidea.lib.error import ParameterError, privacyIDEAError
from privacyidea.lib.utils import int_to_hex
from privacyidea.lib.tokens.certificatetoken import parse_chainfile, verify_certificate_path, ACTION
import os
from OpenSSL import crypto


CERT = """-----BEGIN CERTIFICATE-----
MIIGXDCCBUSgAwIBAgITYwAAAA27DqXl0fVdOAAAAAAADTANBgkqhkiG9w0BAQsF
ADBCMRMwEQYKCZImiZPyLGQBGRYDb3JnMRkwFwYKCZImiZPyLGQBGRYJYXV0aC10
ZXN0MRAwDgYDVQQDEwdDQTJGMDAxMB4XDTE1MDIxMTE2NDE1M1oXDTE2MDIxMTE2
NDE1M1owgYExEzARBgoJkiaJk/IsZAEZFgNvcmcxGTAXBgoJkiaJk/IsZAEZFglh
dXRoLXRlc3QxDjAMBgNVBAMTBVVzZXJzMRowGAYDVQQDExFDb3JuZWxpdXMgS29l
bGJlbDEjMCEGCSqGSIb3DQEJARYUY29ybmVsaXVzQGJhbGZvby5uZXQwggEiMA0G
CSqGSIb3DQEBAQUAA4IBDwAwggEKAoIBAQCN5xYqSoKhxKgywdWOjZTgOobPN5lN
DbSKQktdiG7asH0/Bzg8DIyd+k6wj5yncNhHKBhDJC/cAz3YAYY+KJj/tECLyt5V
AqZLuf3sTA/Ak/neHzXwrlo9PB67JxY4tgJcaR0Cml5oSx4ofRowOCrXv60Asfkl
+3lMRaNyEpQiSVdqIzGZAM1FIy0chwknMB8PfQhlC3v60rGiWoG65Rl5zuGl9lJC
nR990FGSIUW2GLCtI57QCCdBVHIBL+M0WNbdonk9qYSHm8ArFeoftsw2UxHQazM9
KftS7osJnQWOeNw+iIQIgZxLlyC9CBeKBCj3gIwLMEZRz6y951A9nngbAgMBAAGj
ggMJMIIDBTAOBgNVHQ8BAf8EBAMCBLAwHQYDVR0OBBYEFGFYluib3gs1BQQNB25A
FyEvQuoxMB8GA1UdIwQYMBaAFO9tVOusjflOf/y1lJuQ0YZej3vuMIHHBgNVHR8E
gb8wgbwwgbmggbaggbOGgbBsZGFwOi8vL0NOPUNBMkYwMDEsQ049Z2FuZGFsZixD
Tj1DRFAsQ049UHVibGljJTIwS2V5JTIwU2VydmljZXMsQ049U2VydmljZXMsQ049
Q29uZmlndXJhdGlvbixEQz1hdXRoLXRlc3QsREM9b3JnP2NlcnRpZmljYXRlUmV2
b2NhdGlvbkxpc3Q/YmFzZT9vYmplY3RDbGFzcz1jUkxEaXN0cmlidXRpb25Qb2lu
dDCBuwYIKwYBBQUHAQEEga4wgaswgagGCCsGAQUFBzAChoGbbGRhcDovLy9DTj1D
QTJGMDAxLENOPUFJQSxDTj1QdWJsaWMlMjBLZXklMjBTZXJ2aWNlcyxDTj1TZXJ2
aWNlcyxDTj1Db25maWd1cmF0aW9uLERDPWF1dGgtdGVzdCxEQz1vcmc/Y0FDZXJ0
aWZpY2F0ZT9iYXNlP29iamVjdENsYXNzPWNlcnRpZmljYXRpb25BdXRob3JpdHkw
PQYJKwYBBAGCNxUHBDAwLgYmKwYBBAGCNxUIheyJB4SuoT6EjYcBh+WGHoXd8y83
g7DpBYPZgFwCAWQCAQgwKQYDVR0lBCIwIAYKKwYBBAGCNxQCAgYIKwYBBQUHAwIG
CCsGAQUFBwMEMDUGCSsGAQQBgjcVCgQoMCYwDAYKKwYBBAGCNxQCAjAKBggrBgEF
BQcDAjAKBggrBgEFBQcDBDBEBgNVHREEPTA7oCMGCisGAQQBgjcUAgOgFQwTY29y
bnlAYXV0aC10ZXN0Lm9yZ4EUY29ybmVsaXVzQGJhbGZvby5uZXQwRAYJKoZIhvcN
AQkPBDcwNTAOBggqhkiG9w0DAgICAIAwDgYIKoZIhvcNAwQCAgCAMAcGBSsOAwIH
MAoGCCqGSIb3DQMHMA0GCSqGSIb3DQEBCwUAA4IBAQCVI9ULYQgLxOcDWAlWPE4g
ZRcbg65oCNdB0MBzTFhQZC/YFlSTNAGU2gUhnW+LoQ4N4sVnwxPbCRpsiA0ImqFU
hh/qcIV4JYthUGYdYkGjsc1YQjdLpYsg0GRUXTQHYjMQo6gvg1z/iMhzCCU8DbjT
DkTm/0JYVCt+vpvpigX/XWLWeHLHzPHFYAdBVAYgnwbTV4hgNIO98YRiMWsXOAIR
S/IreZ58alclwJJRIGTuOTKSCd+uE7QMALztDty7cjtpMANGrz1k/uUWg9T+UgQs
czZ68tF258iaWLPbsdRWqO160iy7eDSKWFFMR4HnfLHX/UPRSpBNGSHmvT1hbkUr
-----END CERTIFICATE-----"""

CAKEY = "cakey.pem"
CACERT = "cacert.pem"
OPENSSLCNF = "openssl.cnf"
WORKINGDIR = "tests/testdata/ca"
REQUEST = """-----BEGIN CERTIFICATE REQUEST-----
MIICmTCCAYECAQAwVDELMAkGA1UEBhMCREUxDzANBgNVBAgMBkhlc3NlbjEUMBIG
A1UECgwLcHJpdmFjeWlkZWExHjAcBgNVBAMMFXJlcXVlc3Rlci5sb2NhbGRvbWFp
bjCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAM2+FE/6zgE/QiIbHZyv
3ZLSf9tstz45Q0NrEwPxBfQHdLx2aSgLrxmO1/zjzcZY8sp/CG1T/AcCRCTGtDRM
jAT+Mw5A4iC6AnNa9/VPY27MxrbfVB03OX1RNiZfvdw/qItroq62ndYh599BuHoo
KmhIyqgt7eHpRl5acm20hDiHkf2UEQsohMbCLyr7Afk2egl10TOIPHNBW8i/lIlw
ofDAuS5QUx6xF2Rp9C2B4KkNDjLpulWKhfEbb0l5tH+Iww0+VIibPR84jATz7mpj
K/XG27SDqsR4QTp9S+HIPnHKG2FZ6sbEyjJeyem/EinmxsNj/qBV2nrxYJhNJu36
cC0CAwEAAaAAMA0GCSqGSIb3DQEBCwUAA4IBAQB7uJC6I1By0T29IZ0B1ue5YNxM
NDPbqCytRPMQ9awJ6niMMIQRS1YPhSFPWyEWrGKWAUvbn/lV0XHH7L/tvHg6HbC0
AjLc8qPH4Xqkb1WYV1GVJYr5qyEFS9QLZQLQDC2wk018B40MSwZWtsv14832mPu8
gP5WP+mj9LRgWCP1MdAR9pcNGd9pZMcCHQLxT76mc/eol4kb/6/U6yxBmzaff8eB
oysLynYXZkm0wFudTV04K0aKlMJTp/G96sJOtw1yqrkZSe0rNVcDs9vo+HAoMWO/
XZp8nprZvJuk6/QIRpadjRkv4NElZ2oNu6a8mtaO38xxnfQm4FEMbm5p+4tM
-----END CERTIFICATE REQUEST-----"""

BOGUS_ATTESTATION = """-----BEGIN CERTIFICATE-----
MIIDozCCAougAwIBAgIUAlblMK5ormWoid9l8hM2x9VPJv4wDQYJKoZIhvcNAQEL
BQAwYTELMAkGA1UEBhMCREUxDzANBgNVBAgMBkhlc3NlbjEPMA0GA1UEBwwGS2Fz
c2VsMRQwEgYDVQQKDAtwcml2YWN5SURFQTEaMBgGA1UEAwwRYm9ndXNfYXR0ZXN0
YXRpb24wHhcNMjAxMDI2MTA1MjEyWhcNMjAxMTI1MTA1MjEyWjBhMQswCQYDVQQG
EwJERTEPMA0GA1UECAwGSGVzc2VuMQ8wDQYDVQQHDAZLYXNzZWwxFDASBgNVBAoM
C3ByaXZhY3lJREVBMRowGAYDVQQDDBFib2d1c19hdHRlc3RhdGlvbjCCASIwDQYJ
KoZIhvcNAQEBBQADggEPADCCAQoCggEBAK5Vn8fOMMtwIeKGrbaqzICwuPtmhZoT
epkdiJEEhVNEQhGItjcCegZAmnkRlPZM0qFXUoUkoIZVFihN8jDgm8tjZVwf2FPo
YJFVqSRgqwFw5nxQx8h/TBJ4X5IJtU9U+irFmsZS8Ff4j+a4SJieR64/Q/r9oV2q
dgwznse1QjV+05rQviWKK6nKYUZm+BmmCeYvFlJ1x7uY8qeN48fqomz+WQ2IAQMH
WiKM6uBJqX0S1/z4abqwSC7qExTq+L/JUnwZdDxY31T+cjF3qCeLwIaGvj2Itjum
aRUi3bbB4cCEJ7N5VBLuMUna4VKDv7ZSdYDdVAKolgPAYL7b8+UhSOECAwEAAaNT
MFEwHQYDVR0OBBYEFFWifSe1imyuEqfPQDS+dDB1MHL+MB8GA1UdIwQYMBaAFFWi
fSe1imyuEqfPQDS+dDB1MHL+MA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZIhvcNAQEL
BQADggEBABGEhd6HMaJ52mwTrixVKtaPXOS9K20MVqlNzFKA8xe91578Q0GsrP29
ZEXgpcvbG52OvzhCuafLnb4BQmhS/oEaTQLjQXPoG8Mz3l7GkqS5QLeNmgx4MGhj
BxxgoTvp8d2OQD6aXKDpr4IF8vdc+GSNZ6OC96b2EDQn9jHfxZzPSx4F5XIA9fyl
KuOsMevU9r3tE7aWPtl/d397zgxQdZ1QKvY4nogArAMpCzwAAbF7+qKoJIUrMvEx
dae+xapkTiMKISuCqhv89rmVDhZlJ098PcHuJDWn6vsvpxykHEXvAE321W/6h7C/
ZHPVHkcHIwzETqjhRuLCYhXblFmfnRo=
-----END CERTIFICATE-----
"""

YUBIKEY_CSR = """-----BEGIN CERTIFICATE REQUEST-----
MIICbTCCAVUCAQAwFzEVMBMGA1UEAwwMY249Y29ybmVsaXVzMIIBIjANBgkqhkiG
9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzqQ5MCVz5J3mNzuFWYPvo275g7n3SLAL1egF
QGHNxVq8ES9bTtBPuNDofwWrrSQLkNQ/YOwVtk6+jtkmq/IvfzXCpqG8UjrZiPuz
+nEguVEO+K8NFr69XbmrMNWsazy87ihKT2/UCRX3mK932zYVLh7uD9DZYK3bucQ/
xiUy+ePpULjshKDE0pz9ziWAhX46rUynQBsKWBifwl424dFE6Ua23LQoouztAvcl
eeGGjmlnUu6CIbeELcznqDlXfaMe6VBjdymr5KX/3O5MS14IK2IILXW4JmyT6/VF
6s2DWFMVRuZrQ8Ev2YhLPdX9DP9RUu1U+yctWe9MUM5xzetamQIDAQABoBEwDwYJ
KoZIhvcNAQkOMQIwADANBgkqhkiG9w0BAQsFAAOCAQEArLWY74prQRtKojwMEOsw
4efmzCwOvLoO/WXDwzrr7kgSOawQanhFzD+Z4kCwapf1ZMmobBnyWREpL4EC9PzC
YH+mgSDCI0jDj/4OSfklb31IzRhuWcCVOpV9xuiDW875WM792t09ILCpx4rayw2a
8t92zv49IcWHtJNqpo2Q8064p2fzYf1J1r4OEBKUUxEIcw2/nifIiHHTb7DqDF4+
XjcD3ygUfTVbCzPYBmLPwvt+80AxgT2Nd6E612L/fbI9clv5DsvMwnVeSvlP1wXo
5BampVY4p5CQRFLlCQa9fGWZrT+ArC9Djo0mHf32x6pEsSz0zMOlmjHrh+ChVkAs
tA==
-----END CERTIFICATE REQUEST-----"""

YUBIKEY_ATTEST = """-----BEGIN CERTIFICATE-----
MIIDIDCCAgigAwIBAgIQG9hW/ORI6D3vd8zMxQXNPjANBgkqhkiG9w0BAQsFADAh
MR8wHQYDVQQDDBZZdWJpY28gUElWIEF0dGVzdGF0aW9uMCAXDTE2MDMxNDAwMDAw
MFoYDzIwNTIwNDE3MDAwMDAwWjAlMSMwIQYDVQQDDBpZdWJpS2V5IFBJViBBdHRl
c3RhdGlvbiA5YTCCASIwDQYJKoZIhvcNAQEBBQADggEPADCCAQoCggEBAM6kOTAl
c+Sd5jc7hVmD76Nu+YO590iwC9XoBUBhzcVavBEvW07QT7jQ6H8Fq60kC5DUP2Ds
FbZOvo7ZJqvyL381wqahvFI62Yj7s/pxILlRDvivDRa+vV25qzDVrGs8vO4oSk9v
1AkV95ivd9s2FS4e7g/Q2WCt27nEP8YlMvnj6VC47ISgxNKc/c4lgIV+Oq1Mp0Ab
ClgYn8JeNuHRROlGtty0KKLs7QL3JXnhho5pZ1LugiG3hC3M56g5V32jHulQY3cp
q+Sl/9zuTEteCCtiCC11uCZsk+v1RerNg1hTFUbma0PBL9mISz3V/Qz/UVLtVPsn
LVnvTFDOcc3rWpkCAwEAAaNOMEwwEQYKKwYBBAGCxAoDAwQDBQECMBQGCisGAQQB
gsQKAwcEBgIEAKb+EDAQBgorBgEEAYLECgMIBAICATAPBgorBgEEAYLECgMJBAEB
MA0GCSqGSIb3DQEBCwUAA4IBAQDEIv9hTeLL4Eb62mh5nZVJ1epJc4GZ0PmjQPWt
V73nuAns2gkG5weJd3osVcGN0vfqfKzBIZKFRPw2bXrDylgNmMZRJqpVHJ2gfy4I
vDLhYYB9tAk0SkzoHGsQdmHq9IjZRMeEg/0gl0qpjtkDc1ypQm8BLSJqwtQlv4BX
eaGmyo8RKiihI9xu2CmcafcQPbLLLtGAllGdRDakBejkZLL2mb6FaoLcEBidTcN4
/BUNZ+7Tkb7c3iUl5Q0boM+2CKQ9LAKcdaSr8JaCrD1rp+nOCPIcq+cFrdNaLBrn
QQeweMv1LvLaxlnyRNOVbtSzbYVW7laFcEpwuEhAq+5bM6AO
-----END CERTIFICATE-----"""

YUBIKEY_PUBKEY = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAzqQ5MCVz5J3mNzuFWYPv
o275g7n3SLAL1egFQGHNxVq8ES9bTtBPuNDofwWrrSQLkNQ/YOwVtk6+jtkmq/Iv
fzXCpqG8UjrZiPuz+nEguVEO+K8NFr69XbmrMNWsazy87ihKT2/UCRX3mK932zYV
Lh7uD9DZYK3bucQ/xiUy+ePpULjshKDE0pz9ziWAhX46rUynQBsKWBifwl424dFE
6Ua23LQoouztAvcleeGGjmlnUu6CIbeELcznqDlXfaMe6VBjdymr5KX/3O5MS14I
K2IILXW4JmyT6/VF6s2DWFMVRuZrQ8Ev2YhLPdX9DP9RUu1U+yctWe9MUM5xzeta
mQIDAQAB
-----END PUBLIC KEY-----"""

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

class CertificateTokenTestCase(MyTestCase):

    serial1 = "CRT0001"
    serial2 = "CRT0002"
    serial3 = "CRT0003"

    def test_001_parse_cert_chain(self):
        chain = parse_chainfile("tests/testdata/attestation/yubico.pem")
        self.assertEqual(2, len(chain))
        self.assertEqual(YUBICO_ATTESTATION_ROOT_CERT.strip(), chain[0].strip())
        self.assertEqual(YUBICO_ATTESTATION_INTERMEDIATE.strip(), chain[1].strip())

    def test_002_verify(self):
        # Verify an attestation certificate against trusted CA chain path.
        r = verify_certificate_path(YUBIKEY_ATTEST, ["tests/testdata/attestation",
                                                     "tests/testdata/feitian_non_exist"])
        self.assertTrue(r)

        # Verification against an empty chain, due to misconfiguration failes.
        r = verify_certificate_path(YUBIKEY_ATTEST, ["tests/testdata/feitian_non_exist"])
        self.assertFalse(r)

    def test_01_create_token_from_certificate(self):
        db_token = Token(self.serial1, tokentype="certificate")
        db_token.save()
        token = CertificateTokenClass(db_token)

        # just upload a ready certificate
        token.update({"certificate": CERT})
        self.assertTrue(token.token.serial == self.serial1, token)
        self.assertTrue(token.token.tokentype == "certificate",
                        token.token.tokentype)
        self.assertTrue(token.type == "certificate", token)
        class_prefix = token.get_class_prefix()
        self.assertTrue(class_prefix == "CRT", class_prefix)
        self.assertEqual(token.get_class_type(), "certificate")

        detail = token.get_init_detail()
        self.assertEqual(detail.get("certificate"), CERT)

    def test_02_create_token_from_request(self):
        cwd = os.getcwd()
        # setup ca connector
        r = save_caconnector({"cakey": CAKEY,
                              "cacert": CACERT,
                              "type": "local",
                              "caconnector": "localCA",
                              "openssl.cnf": OPENSSLCNF,
                              "CSRDir": "",
                              "CertificateDir": "",
                              "WorkingDir": cwd + "/" + WORKINGDIR})

        db_token = Token(self.serial2, tokentype="certificate")
        db_token.save()
        token = CertificateTokenClass(db_token)

        # just upload a ready certificate
        token.update({"ca": "localCA",
                      "request": REQUEST})
        self.assertTrue(token.token.serial == self.serial2, token)
        self.assertTrue(token.token.tokentype == "certificate",
                        token.token.tokentype)
        self.assertTrue(token.type == "certificate", token)
        class_prefix = token.get_class_prefix()
        self.assertTrue(class_prefix == "CRT", class_prefix)
        self.assertTrue(token.get_class_type() == "certificate", token)

        detail = token.get_init_detail()
        certificate = detail.get("certificate")
        # At each testrun, the certificate might get another serial number!
        x509obj = crypto.load_certificate(crypto.FILETYPE_PEM, certificate)
        self.assertEqual("{0!r}".format(x509obj.get_issuer()),
                         "<X509Name object '/C=DE/ST=Hessen"
                         "/O=privacyidea/CN=CA001'>")
        self.assertEqual("{0!r}".format(x509obj.get_subject()),
                         "<X509Name object '/C=DE/ST=Hessen"
                         "/O=privacyidea/CN=requester.localdomain'>")

        # Test, if the certificate is also completely stored in the tokeninfo
        # and if we can retrieve it from the tokeninfo
        token = get_tokens(serial=self.serial2)[0]
        certificate = token.get_tokeninfo("certificate")
        x509obj = crypto.load_certificate(crypto.FILETYPE_PEM, certificate)
        self.assertEqual("{0!r}".format(x509obj.get_issuer()),
                         "<X509Name object '/C=DE/ST=Hessen"
                         "/O=privacyidea/CN=CA001'>")
        self.assertEqual("{0!r}".format(x509obj.get_subject()),
                         "<X509Name object '/C=DE/ST=Hessen"
                         "/O=privacyidea/CN=requester.localdomain'>")
        remove_token(self.serial2)

    def test_02a_fail_request_with_attestation(self):
        cwd = os.getcwd()
        # setup ca connector
        r = save_caconnector({"cakey": CAKEY,
                              "cacert": CACERT,
                              "type": "local",
                              "caconnector": "localCA",
                              "openssl.cnf": OPENSSLCNF,
                              "CSRDir": "",
                              "CertificateDir": "",
                              "WorkingDir": cwd + "/" + WORKINGDIR})

        db_token = Token(self.serial2, tokentype="certificate")
        db_token.save()
        token = CertificateTokenClass(db_token)

        # A cert request will fail, since the attestation certificate does not match
        self.assertRaises(privacyIDEAError,
                          token.update,
                          {"ca": "localCA",
                           "attestation": BOGUS_ATTESTATION,
                           "request": REQUEST})
        remove_token(self.serial2)

    def test_02b_success_request_with_attestation(self):
        cwd = os.getcwd()
        # setup ca connector
        r = save_caconnector({"cakey": CAKEY,
                              "cacert": CACERT,
                              "type": "local",
                              "caconnector": "localCA",
                              "openssl.cnf": OPENSSLCNF,
                              "CSRDir": "",
                              "CertificateDir": "",
                              "WorkingDir": cwd + "/" + WORKINGDIR})

        db_token = Token(self.serial2, tokentype="certificate")
        db_token.save()
        token = CertificateTokenClass(db_token)

        # The cert request will success with a valid attestation certificate
        token.update({"ca": "localCA",
                      "attestation": YUBIKEY_ATTEST,
                      "request": YUBIKEY_CSR,
                      ACTION.TRUSTED_CA_PATH: ["tests/testdata/attestation/"]})
        class_prefix = token.get_class_prefix()
        self.assertTrue(class_prefix == "CRT", class_prefix)
        self.assertTrue(token.get_class_type() == "certificate", token)

        detail = token.get_init_detail()
        certificate = detail.get("certificate")
        # At each testrun, the certificate might get another serial number!
        x509obj = crypto.load_certificate(crypto.FILETYPE_PEM, certificate)
        self.assertEqual("{0!r}".format(x509obj.get_issuer()),
                         "<X509Name object '/C=DE/ST=Hessen"
                         "/O=privacyidea/CN=CA001'>")
        self.assertEqual("{0!r}".format(x509obj.get_subject()),
                         "<X509Name object '/CN=cn=cornelius'>")
        remove_token(self.serial2)


    def test_03_class_methods(self):
        db_token = Token.query.filter(Token.serial == self.serial1).first()
        token = CertificateTokenClass(db_token)

        info = token.get_class_info()
        self.assertTrue(info.get("title") == "Certificate Token", info)

        info = token.get_class_info("title")
        self.assertTrue(info == "Certificate Token", info)

    def test_04_create_token_on_server(self):
        self.setUp_user_realms()
        cwd = os.getcwd()
        # setup ca connector
        r = save_caconnector({"cakey": CAKEY,
                              "cacert": CACERT,
                              "type": "local",
                              "caconnector": "localCA",
                              "openssl.cnf": OPENSSLCNF,
                              "CSRDir": "",
                              "CertificateDir": "",
                              "WorkingDir": cwd + "/" + WORKINGDIR})

        db_token = Token(self.serial3, tokentype="certificate")
        db_token.save()
        token = CertificateTokenClass(db_token)

        # missing user
        self.assertRaises(ParameterError,
                          token.update, {"ca": "localCA","genkey": 1})

        token.update({"ca": "localCA", "genkey": 1,
                      "user": "cornelius"})

        self.assertEqual(token.token.serial, self.serial3)
        self.assertEqual(token.token.tokentype, "certificate")
        self.assertEqual(token.type, "certificate")

        detail = token.get_init_detail()
        certificate = detail.get("certificate")
        # At each testrun, the certificate might get another serial number!
        x509obj = crypto.load_certificate(crypto.FILETYPE_PEM, certificate)
        self.assertEqual("{0!r}".format(x509obj.get_issuer()),
                         "<X509Name object '/C=DE/ST=Hessen"
                         "/O=privacyidea/CN=CA001'>")
        self.assertEqual("{0!r}".format(x509obj.get_subject()),
                         "<X509Name object '/OU=realm1/CN=cornelius/emailAddress=user@localhost.localdomain'>")

        # Test, if the certificate is also completely stored in the tokeninfo
        # and if we can retrieve it from the tokeninfo
        token = get_tokens(serial=self.serial3)[0]
        certificate = token.get_tokeninfo("certificate")
        x509obj = crypto.load_certificate(crypto.FILETYPE_PEM, certificate)
        self.assertEqual("{0!r}".format(x509obj.get_issuer()),
                         "<X509Name object '/C=DE/ST=Hessen"
                         "/O=privacyidea/CN=CA001'>")
        self.assertEqual("{0!r}".format(x509obj.get_subject()),
                         "<X509Name object '/OU=realm1/CN=cornelius/emailAddress=user@localhost.localdomain'>")

        privatekey = token.get_tokeninfo("privatekey")
        self.assertTrue(privatekey.startswith("-----BEGIN PRIVATE KEY-----"))

        # check for pkcs12
        self.assertTrue(detail.get("pkcs12"))

        # revoke the token
        r = token.revoke()
        self.assertEqual(r, int_to_hex(x509obj.get_serial_number()))

    def test_05_get_default_settings(self):
        from privacyidea.lib.policy import set_policy, delete_policy, PolicyClass, SCOPE
        from privacyidea.lib.tokens.certificatetoken import ACTION, CertificateTokenClass

        params = {}
        g = FakeFlaskG()
        g.audit_object = FakeAudit()
        # trusted path for a user
        g.logged_in_user = {"user": "hans",
                            "realm": "default",
                            "role": "user"}
        set_policy("pol1", scope=SCOPE.USER,
                   action="certificate_{0!s}=tests/testdata/attestation/".format(ACTION.TRUSTED_CA_PATH))
        g.policy_object = PolicyClass()
        p = CertificateTokenClass.get_default_settings(g, params)
        self.assertEqual(["tests/testdata/attestation/"],
                         p.get("trusted_Attestation_CA_path"))
        delete_policy("pol1")
        # the same should work for an admin user
        g.logged_in_user = {"user": "admin",
                            "realm": "super",
                            "role": "admin"}
        set_policy("pol1", scope=SCOPE.ADMIN,
                   action="certificate_{0!s}=tests/testdata/attestation/".format(ACTION.TRUSTED_CA_PATH))
        g.policy_object = PolicyClass()
        p = CertificateTokenClass.get_default_settings(g, params)
        self.assertEqual(["tests/testdata/attestation/"],
                         p.get("trusted_Attestation_CA_path"))
        delete_policy("pol1")
        # If we have no policy, we revert to default
        g.policy_object = PolicyClass()
        p = CertificateTokenClass.get_default_settings(g, params)
        self.assertEqual(["/etc/privacyidea/trusted_attestation_ca"],
                         p.get("trusted_Attestation_CA_path"))
