"""Criptografia: AES-256-GCM com chaves derivadas por Argon2id e hashes SHA-256."""

from __future__ import annotations

import hashlib
import os
import secrets
import string
import struct
from dataclasses import dataclass
from pathlib import Path

from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .errors import AuthenticationError, InvalidInputError

KEY_LEN = 32  # 256 bits
SALT_LEN = 16
NONCE_LEN = 12  # recomendado para GCM
TAG_LEN = 16

# Limites de sanidade para parâmetros lidos de arquivos (evita DoS por parâmetros forjados)
_MAX_TIME_COST = 20
_MAX_MEMORY_KIB = 1024 * 1024  # 1 GiB
_MAX_PARALLELISM = 16


@dataclass(frozen=True)
class KdfParams:
    """Parâmetros do Argon2id."""

    time_cost: int = 3
    memory_kib: int = 64 * 1024
    parallelism: int = 4

    STRUCT = struct.Struct(">BIB")  # time(1) memória KiB(4) paralelismo(1)

    def pack(self) -> bytes:
        return self.STRUCT.pack(self.time_cost, self.memory_kib, self.parallelism)

    @classmethod
    def unpack(cls, data: bytes) -> "KdfParams":
        t, m, p = cls.STRUCT.unpack(data)
        params = cls(t, m, p)
        params.validate()
        return params

    def validate(self) -> None:
        if not (1 <= self.time_cost <= _MAX_TIME_COST):
            raise InvalidInputError("Parâmetro de tempo do Argon2id fora do limite.")
        if not (8 * self.parallelism <= self.memory_kib <= _MAX_MEMORY_KIB):
            raise InvalidInputError("Parâmetro de memória do Argon2id fora do limite.")
        if not (1 <= self.parallelism <= _MAX_PARALLELISM):
            raise InvalidInputError("Parâmetro de paralelismo do Argon2id fora do limite.")


KDF_PROFILES: dict[str, KdfParams] = {
    "rapido": KdfParams(time_cost=2, memory_kib=19 * 1024, parallelism=1),
    "padrao": KdfParams(time_cost=3, memory_kib=64 * 1024, parallelism=4),
    "alto": KdfParams(time_cost=4, memory_kib=256 * 1024, parallelism=4),
}
KDF_PROFILE_LABELS = {
    "rapido": "Rápido (19 MiB, 2 iterações)",
    "padrao": "Padrão (64 MiB, 3 iterações) – recomendado",
    "alto": "Alto (256 MiB, 4 iterações)",
}


def derive_key(password: str, salt: bytes, params: KdfParams) -> bytes:
    """Deriva uma chave de 256 bits a partir da senha com Argon2id."""
    if not isinstance(password, str) or password == "":
        raise InvalidInputError("A senha não pode ser vazia.")
    if len(salt) != SALT_LEN:
        raise InvalidInputError("Salt inválido.")
    params.validate()
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=params.time_cost,
        memory_cost=params.memory_kib,
        parallelism=params.parallelism,
        hash_len=KEY_LEN,
        type=Type.ID,
    )


def new_salt() -> bytes:
    return os.urandom(SALT_LEN)


def new_nonce() -> bytes:
    return os.urandom(NONCE_LEN)


def aes_gcm_encrypt(key: bytes, nonce: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """Cifra com AES-256-GCM. Retorna ciphertext || tag (16 bytes)."""
    if len(key) != KEY_LEN:
        raise InvalidInputError("Chave AES-256 inválida.")
    return AESGCM(key).encrypt(nonce, plaintext, aad or None)


def aes_gcm_decrypt(key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes = b"") -> bytes:
    """Decifra AES-256-GCM, levantando AuthenticationError se a tag não conferir."""
    if len(key) != KEY_LEN:
        raise InvalidInputError("Chave AES-256 inválida.")
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, aad or None)
    except InvalidTag as exc:
        raise AuthenticationError() from exc


def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def constant_time_equals(a: bytes, b: bytes) -> bool:
    return secrets.compare_digest(a, b)


# ---------------------------------------------------------------------------
# Senhas
# ---------------------------------------------------------------------------

def generate_password(length: int = 20, use_symbols: bool = True) -> str:
    """Gera uma senha forte com o gerador criptográfico do sistema."""
    if length < 8 or length > 256:
        raise InvalidInputError("O tamanho da senha deve estar entre 8 e 256.")
    alphabet = string.ascii_letters + string.digits
    symbols = "!@#$%&*()-_=+[]{};:,.?/"
    if use_symbols:
        alphabet += symbols
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        has_classes = (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and (not use_symbols or any(c in symbols for c in pwd))
        )
        if has_classes:
            return pwd


@dataclass(frozen=True)
class PasswordStrength:
    score: int  # 0..4
    label: str
    entropy_bits: float
    hints: tuple[str, ...]


_COMMON = {
    "123456", "12345678", "123456789", "password", "senha", "senha123", "qwerty",
    "abc123", "111111", "000000", "admin", "iloveyou", "123123", "brasil",
}


def evaluate_password(password: str) -> PasswordStrength:
    """Estimativa simples (offline) da força de uma senha."""
    import math

    if not password:
        return PasswordStrength(0, "Vazia", 0.0, ("Informe uma senha.",))
    pool = 0
    hints: list[str] = []
    if any(c.islower() for c in password):
        pool += 26
    else:
        hints.append("Use letras minúsculas.")
    if any(c.isupper() for c in password):
        pool += 26
    else:
        hints.append("Use letras maiúsculas.")
    if any(c.isdigit() for c in password):
        pool += 10
    else:
        hints.append("Use números.")
    if any(not c.isalnum() for c in password):
        pool += 33
    else:
        hints.append("Use símbolos.")
    if len(password) < 12:
        hints.append("Use pelo menos 12 caracteres.")
    unique_ratio = len(set(password)) / len(password)
    entropy = len(password) * math.log2(max(pool, 1)) * min(1.0, 0.5 + unique_ratio)
    if password.lower() in _COMMON:
        entropy = min(entropy, 10.0)
        hints.insert(0, "Senha muito comum.")
    if entropy < 28:
        score, label = 0, "Muito fraca"
    elif entropy < 40:
        score, label = 1, "Fraca"
    elif entropy < 60:
        score, label = 2, "Razoável"
    elif entropy < 80:
        score, label = 3, "Forte"
    else:
        score, label = 4, "Muito forte"
    return PasswordStrength(score, label, round(entropy, 1), tuple(hints))
