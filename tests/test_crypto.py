import pytest

from marx_secret.core import crypto
from marx_secret.core.errors import AuthenticationError, InvalidInputError

FAST = crypto.KDF_PROFILES["rapido"]


def test_key_derivation_is_deterministic_and_salted():
    salt = crypto.new_salt()
    k1 = crypto.derive_key("abc12345", salt, FAST)
    k2 = crypto.derive_key("abc12345", salt, FAST)
    k3 = crypto.derive_key("abc12345", crypto.new_salt(), FAST)
    assert k1 == k2 and len(k1) == 32
    assert k1 != k3


def test_aes_gcm_roundtrip_and_tamper_detection():
    key = crypto.derive_key("pw-123456", crypto.new_salt(), FAST)
    nonce = crypto.new_nonce()
    ct = crypto.aes_gcm_encrypt(key, nonce, b"segredo", aad=b"hdr")
    assert crypto.aes_gcm_decrypt(key, nonce, ct, aad=b"hdr") == b"segredo"
    with pytest.raises(AuthenticationError):
        crypto.aes_gcm_decrypt(key, nonce, ct, aad=b"outro")
    tampered = bytearray(ct)
    tampered[0] ^= 1
    with pytest.raises(AuthenticationError):
        crypto.aes_gcm_decrypt(key, nonce, bytes(tampered), aad=b"hdr")


def test_wrong_key_fails():
    salt = crypto.new_salt()
    nonce = crypto.new_nonce()
    ct = crypto.aes_gcm_encrypt(crypto.derive_key("correta1", salt, FAST), nonce, b"x")
    with pytest.raises(AuthenticationError):
        crypto.aes_gcm_decrypt(crypto.derive_key("errada12", salt, FAST), nonce, ct)


def test_empty_password_rejected():
    with pytest.raises(InvalidInputError):
        crypto.derive_key("", crypto.new_salt(), FAST)


def test_kdf_params_validation():
    with pytest.raises(InvalidInputError):
        crypto.KdfParams(time_cost=0).validate()
    with pytest.raises(InvalidInputError):
        crypto.KdfParams.unpack(crypto.KdfParams(3, 4 * 1024 * 1024, 4).pack())


def test_sha256_helpers(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"abc")
    expected = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert crypto.sha256_hex(b"abc") == expected
    assert crypto.sha256_file(f) == expected


def test_password_generator_and_strength():
    pwd = crypto.generate_password(24)
    assert len(pwd) == 24
    assert crypto.evaluate_password(pwd).score >= 3
    assert crypto.evaluate_password("123456").score == 0
    assert crypto.evaluate_password("").label == "Vazia"
    with pytest.raises(InvalidInputError):
        crypto.generate_password(4)
