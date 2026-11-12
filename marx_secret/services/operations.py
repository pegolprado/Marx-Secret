"""Operações de alto nível do MARX SECRET (usadas pela interface e pela CLI).

Cada operação é cronometrada e registrada no histórico com metadados não
secretos. Senhas e conteúdos nunca são persistidos.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, TypeVar

from ..core import analysis, compare, crypto, imageio, payload, pngchunk, stego
from ..core.errors import (
    AuthenticationError,
    CorruptedDataError,
    IntegrityError,
    InvalidInputError,
    MarxSecretError,
    PayloadTooLargeError,
)
from ..core.payload import Payload, PayloadKind
from ..core.secure_delete import secure_delete
from ..data.database import (
    STATUS_FAILURE,
    STATUS_SUCCESS,
    Database,
    OperationRecord,
)

log = logging.getLogger("marx_secret")
T = TypeVar("T")


@dataclass
class HideOptions:
    password: str | None = None
    bits_per_channel: int = 1
    scattered: bool = True
    compress: bool = True
    kdf_profile: str = "padrao"
    max_payload_bytes: int = payload.DEFAULT_MAX_PAYLOAD
    min_password_length: int = 8
    require_password: bool = True
    mode: str = "auto"  # "auto" | "lsb" | "estendido"


MODE_LABELS = {
    "auto": "Automático (LSB quando couber; senão capacidade estendida)",
    "lsb": "LSB nos pixels – máxima discrição, capacidade limitada",
    "estendido": "Capacidade estendida – bloco PNG criptografado, sem limite de resolução",
}


@dataclass
class HideResult:
    output_path: str
    payload_size: int
    container_size: int
    capacity: int
    usage_pct: float
    encrypted: bool
    compressed: bool
    bits_per_channel: int
    scattered: bool
    output_sha256: str
    payload_sha256: str
    duration_ms: int
    mode: str = "lsb"


@dataclass
class ExtractResult:
    payload: Payload
    encrypted: bool
    compressed: bool
    bits_per_channel: int
    scattered: bool
    payload_sha256: str
    integrity_ok: bool
    duration_ms: int
    mode: str = "lsb"


@dataclass
class CapacityEstimate:
    capacity: int
    required: int
    fits: bool
    usage_pct: float


def container_overhead(encrypted: bool, filename: str = "") -> int:
    base = 2 + 3 + len(filename.encode("utf-8")) + 8 + 32
    if encrypted:
        base += crypto.KdfParams.STRUCT.size + crypto.SALT_LEN + crypto.NONCE_LEN + crypto.TAG_LEN
    return base


class MarxSecretService:
    def __init__(self, db: Database | None):
        self.db = db

    # ------------------------------------------------------------------
    def _history_enabled(self) -> bool:
        return self.db is not None and bool(self.db.get_setting("history_enabled", True))

    def _record(self, rec: OperationRecord) -> None:
        if self._history_enabled():
            try:
                self.db.add_operation(rec)  # type: ignore[union-attr]
            except Exception:  # o histórico nunca deve derrubar a operação
                log.exception("Falha ao gravar histórico")

    def _run(self, rec: OperationRecord, fn: Callable[[], T]) -> T:
        start = time.perf_counter()
        try:
            result = fn()
        except MarxSecretError as exc:
            rec.status = STATUS_FAILURE
            rec.message = str(exc)
            rec.duration_ms = int((time.perf_counter() - start) * 1000)
            self._record(rec)
            raise
        except Exception as exc:
            log.exception("Erro inesperado em %s", rec.operation)
            rec.status = STATUS_FAILURE
            rec.message = f"Erro inesperado: {type(exc).__name__}"
            rec.duration_ms = int((time.perf_counter() - start) * 1000)
            self._record(rec)
            raise MarxSecretError(f"Erro inesperado: {exc}") from exc
        rec.status = STATUS_SUCCESS
        rec.duration_ms = int((time.perf_counter() - start) * 1000)
        self._record(rec)
        return result

    @staticmethod
    def _check_password(opts: HideOptions) -> None:
        if opts.require_password and not opts.password:
            raise InvalidInputError("Informe uma senha para proteger o conteúdo.")
        if opts.password and len(opts.password) < opts.min_password_length:
            raise InvalidInputError(
                f"A senha deve ter pelo menos {opts.min_password_length} caracteres."
            )
        if opts.scattered and not opts.password:
            raise InvalidInputError("A distribuição dispersa exige uma senha.")

    # ------------------------------------------------------------------
    # Capacidade
    # ------------------------------------------------------------------
    def estimate(self, cover_path: str, payload_size: int, bits_per_channel: int,
                 encrypted: bool, filename: str = "") -> CapacityEstimate:
        info = imageio.image_info(cover_path)
        cap = stego.capacity_for_size(info.width, info.height, bits_per_channel)
        required = payload_size + container_overhead(encrypted, filename)
        return CapacityEstimate(cap, required, required <= cap,
                                100.0 * required / cap if cap else 100.0)

    # ------------------------------------------------------------------
    # Ocultação
    # ------------------------------------------------------------------
    def hide(self, cover_path: str, output_path: str, data: Payload,
             opts: HideOptions) -> HideResult:
        op = "ocultar_mensagem" if data.kind == PayloadKind.TEXT else "ocultar_arquivo"
        rec = OperationRecord(
            operation=op, status=STATUS_FAILURE, input_path=str(cover_path),
            output_path=str(output_path), payload_kind=data.kind.label,
            payload_size=len(data.data), encrypted=bool(opts.password),
            bits_per_channel=opts.bits_per_channel, scattered=opts.scattered,
        )

        def work() -> HideResult:
            t0 = time.perf_counter()
            self._check_password(opts)
            imageio.validate_output_path(output_path)
            if os.path.abspath(cover_path) == os.path.abspath(output_path):
                raise InvalidInputError("A imagem de saída deve ser diferente da original.")
            rec.input_sha256 = crypto.sha256_file(cover_path)
            img = imageio.load_image(cover_path)
            kdf = crypto.KDF_PROFILES.get(opts.kdf_profile, crypto.KDF_PROFILES["padrao"])
            container = payload.build_container(
                data, opts.password or None, opts.compress, kdf, opts.max_payload_bytes
            )
            info = payload.inspect_container(container)
            rec.compressed = info.compressed
            lsb_cap = stego.capacity_bytes(img, opts.bits_per_channel)
            mode = opts.mode
            if mode == "auto":
                mode = "lsb" if len(container) <= lsb_cap else "estendido"
            if mode == "estendido":
                if Path(output_path).suffix.lower() != ".png":
                    raise InvalidInputError(
                        "A capacidade estendida exige saída em PNG. Altere a extensão do "
                        "arquivo de saída para .png.")
                # pixels idênticos ao original; contêiner em blocos PNG privados
                imageio.save_image(img, output_path)
                pngchunk.embed(output_path, container)
                recovered = pngchunk.extract(output_path)
                imageio.load_image(output_path)  # confirma que o PNG continua válido
                cap = payload.HARD_MAX_PAYLOAD
                rec.bits_per_channel = 0
                rec.scattered = False
            else:
                out_img = stego.embed(img, container, opts.bits_per_channel, opts.scattered,
                                      opts.password)
                imageio.save_image(out_img, output_path)
                # verificação pós-gravação: relê o arquivo e confirma o conteúdo
                check_img = imageio.load_image(output_path)
                recovered, _ = stego.extract(check_img, opts.password)
                cap = lsb_cap
            if not crypto.constant_time_equals(recovered, container):
                raise MarxSecretError("Falha na verificação pós-gravação da imagem.")
            out_sha = crypto.sha256_file(output_path)
            rec.output_sha256 = out_sha
            if mode == "estendido":
                rec.message = (f"Capacidade estendida (bloco PNG): {len(container)} bytes "
                               f"armazenados")
            else:
                rec.message = (
                    f"LSB: {len(container)} de {cap} bytes utilizados "
                    f"({100.0 * len(container) / cap:.2f}%)"
                )
            return HideResult(
                output_path=str(output_path),
                payload_size=len(data.data),
                container_size=len(container),
                capacity=cap,
                usage_pct=100.0 * len(container) / cap,
                encrypted=info.encrypted,
                compressed=info.compressed,
                bits_per_channel=opts.bits_per_channel if mode == "lsb" else 0,
                scattered=opts.scattered if mode == "lsb" else False,
                output_sha256=out_sha,
                payload_sha256=data.sha256,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                mode=mode,
            )

        return self._run(rec, work)

    def hide_message(self, cover_path: str, output_path: str, message: str,
                     opts: HideOptions) -> HideResult:
        return self.hide(cover_path, output_path, Payload.from_text(message), opts)

    def hide_file(self, cover_path: str, output_path: str, file_path: str,
                  opts: HideOptions) -> HideResult:
        data = Payload.from_file(file_path, opts.max_payload_bytes)
        return self.hide(cover_path, output_path, data, opts)

    # ------------------------------------------------------------------
    # Extração
    # ------------------------------------------------------------------
    def extract(self, image_path: str, password: str | None = None,
                expected: PayloadKind | None = None,
                max_payload_bytes: int = payload.DEFAULT_MAX_PAYLOAD) -> ExtractResult:
        op = "recuperar_arquivo" if expected == PayloadKind.FILE else "extrair_mensagem"
        rec = OperationRecord(operation=op, status=STATUS_FAILURE, input_path=str(image_path))

        def work() -> ExtractResult:
            t0 = time.perf_counter()
            imageio.validate_image_path(image_path)
            rec.input_sha256 = crypto.sha256_file(image_path)
            header = None
            mode = "lsb"
            if pngchunk.has_extended(image_path):
                container = pngchunk.extract(image_path)
                mode = "estendido"
            else:
                img = imageio.load_image(image_path)
                container, header = stego.extract(img, password or None)
                rec.bits_per_channel = header.layout.bits_per_channel
                rec.scattered = header.layout.scattered
            try:
                data, info = payload.open_container(container, password or None,
                                                    max_payload_bytes)
            except (CorruptedDataError, IntegrityError, PayloadTooLargeError) as exc:
                # No modo disperso, senha errada leva a posições erradas e dados aleatórios.
                if header is not None and header.layout.scattered:
                    raise AuthenticationError() from exc
                raise
            rec.operation = (
                "recuperar_arquivo" if data.kind == PayloadKind.FILE else "extrair_mensagem"
            )
            rec.payload_kind = data.kind.label
            rec.payload_size = len(data.data)
            rec.encrypted = info.encrypted
            rec.compressed = info.compressed
            rec.message = ("Integridade SHA-256 verificada"
                           + (" · capacidade estendida" if mode == "estendido" else ""))
            return ExtractResult(
                payload=data,
                encrypted=info.encrypted,
                compressed=info.compressed,
                bits_per_channel=header.layout.bits_per_channel if header else 0,
                scattered=header.layout.scattered if header else False,
                payload_sha256=data.sha256,
                integrity_ok=True,
                duration_ms=int((time.perf_counter() - t0) * 1000),
                mode=mode,
            )

        return self._run(rec, work)

    @staticmethod
    def unique_path(directory: str | Path, filename: str) -> Path:
        d = Path(directory)
        name = payload.sanitize_filename(filename or "arquivo_recuperado.bin")
        candidate = d / name
        stem, suffix = candidate.stem, candidate.suffix
        i = 1
        while candidate.exists():
            candidate = d / f"{stem} ({i}){suffix}"
            i += 1
        return candidate

    def save_payload(self, data: Payload, destination: str | Path) -> Path:
        """Grava um arquivo recuperado. ``destination`` pode ser pasta ou arquivo."""
        dest = Path(destination)
        if dest.is_dir():
            dest = self.unique_path(dest, data.filename)
        if not dest.parent.exists():
            raise InvalidInputError("A pasta de destino não existe.")
        tmp = dest.with_name(dest.name + ".tmp-marx")
        with open(tmp, "wb") as fh:
            fh.write(data.data)
        os.replace(tmp, dest)
        if crypto.sha256_file(dest) != data.sha256:
            raise MarxSecretError("Falha na verificação SHA-256 do arquivo gravado.")
        return dest

    # ------------------------------------------------------------------
    # Criptografia de arquivos (.mxs)
    # ------------------------------------------------------------------
    def encrypt_file(self, src: str, dst: str, password: str, kdf_profile: str = "padrao",
                     compress: bool = True, min_password_length: int = 8,
                     max_payload_bytes: int = payload.DEFAULT_MAX_PAYLOAD) -> str:
        rec = OperationRecord(operation="criptografar_arquivo", status=STATUS_FAILURE,
                              input_path=src, output_path=dst, encrypted=True,
                              payload_kind="Arquivo")

        def work() -> str:
            if not password or len(password) < min_password_length:
                raise InvalidInputError(
                    f"A senha deve ter pelo menos {min_password_length} caracteres.")
            if os.path.abspath(src) == os.path.abspath(dst):
                raise InvalidInputError("O destino deve ser diferente do arquivo original.")
            data = Payload.from_file(src, max_payload_bytes)
            rec.payload_size = len(data.data)
            rec.input_sha256 = data.sha256
            kdf = crypto.KDF_PROFILES.get(kdf_profile, crypto.KDF_PROFILES["padrao"])
            blob = payload.encrypt_file_bytes(data, password, kdf, compress, max_payload_bytes)
            rec.compressed = payload.inspect_container(blob[4:]).compressed
            tmp = dst + ".tmp-marx"
            with open(tmp, "wb") as fh:
                fh.write(blob)
            os.replace(tmp, dst)
            rec.output_sha256 = crypto.sha256_file(dst)
            return dst

        return self._run(rec, work)

    def decrypt_file(self, src: str, destination: str, password: str,
                     max_payload_bytes: int = payload.DEFAULT_MAX_PAYLOAD) -> Path:
        rec = OperationRecord(operation="descriptografar_arquivo", status=STATUS_FAILURE,
                              input_path=src, output_path=str(destination), encrypted=True,
                              payload_kind="Arquivo")

        def work() -> Path:
            if not os.path.isfile(src):
                raise InvalidInputError("O arquivo criptografado não foi encontrado.")
            if os.path.getsize(src) > payload.HARD_MAX_PAYLOAD + 1024:
                raise InvalidInputError("O arquivo excede o limite de tamanho permitido.")
            rec.input_sha256 = crypto.sha256_file(src)
            with open(src, "rb") as fh:
                blob = fh.read()
            data, info = payload.decrypt_file_bytes(blob, password, max_payload_bytes)
            rec.payload_size = len(data.data)
            rec.compressed = info.compressed
            out = self.save_payload(data, destination)
            rec.output_path = str(out)
            rec.output_sha256 = data.sha256
            rec.message = "Integridade SHA-256 verificada"
            return out

        return self._run(rec, work)

    # ------------------------------------------------------------------
    # Análise / comparação / utilidades
    # ------------------------------------------------------------------
    def analyze(self, image_path: str) -> analysis.AnalysisResult:
        rec = OperationRecord(operation="analisar_imagem", status=STATUS_FAILURE,
                              input_path=image_path)

        def work():
            r = analysis.analyze_image(image_path)
            rec.input_sha256 = r.file_sha256
            rec.message = (f"Suspeita {r.suspicion_label} ({r.suspicion_score}/100); "
                           f"assinatura {'detectada' if r.signature.detected else 'ausente'}")
            return r

        return self._run(rec, work)

    def compare(self, original: str, processed: str) -> compare.ComparisonResult:
        rec = OperationRecord(operation="comparar_imagens", status=STATUS_FAILURE,
                              input_path=original, output_path=processed)

        def work():
            r = compare.compare_images(original, processed)
            psnr = "∞" if r.identical else f"{r.psnr:.2f} dB"
            rec.message = f"PSNR {psnr}; SSIM {r.ssim:.5f}; {r.changed_pixels} pixels alterados"
            return r

        return self._run(rec, work)

    def secure_delete(self, path: str, passes: int = 3) -> None:
        rec = OperationRecord(operation="exclusao_segura", status=STATUS_FAILURE,
                              input_path=path)
        self._run(rec, lambda: secure_delete(path, passes))

    def verify_integrity(self, path: str, expected_sha256: str) -> bool:
        rec = OperationRecord(operation="verificar_integridade", status=STATUS_FAILURE,
                              input_path=path)

        def work() -> bool:
            if not os.path.isfile(path):
                raise InvalidInputError("Arquivo não encontrado.")
            actual = crypto.sha256_file(path)
            rec.input_sha256 = actual
            ok = actual.lower() == expected_sha256.strip().lower()
            rec.message = "Hash confere" if ok else "Hash NÃO confere"
            return ok

        return self._run(rec, work)

    def log_report(self, path: str, kind: str) -> None:
        self._record(OperationRecord(operation="gerar_relatorio", status=STATUS_SUCCESS,
                                     output_path=path, message=kind))
