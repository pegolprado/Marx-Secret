"""Banco de dados local SQLite: histórico de operações e configurações.

Política de privacidade: o histórico guarda apenas metadados técnicos
(caminhos, tamanhos, hashes, parâmetros). Senhas e conteúdos secretos nunca
são gravados. Nomes de arquivos ocultos também não são registrados.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1

OPERATION_LABELS = {
    "ocultar_mensagem": "Ocultar mensagem",
    "extrair_mensagem": "Extrair mensagem",
    "ocultar_arquivo": "Ocultar arquivo",
    "recuperar_arquivo": "Recuperar arquivo",
    "criptografar_arquivo": "Criptografar arquivo",
    "descriptografar_arquivo": "Descriptografar arquivo",
    "analisar_imagem": "Análise de imagem",
    "comparar_imagens": "Comparação de imagens",
    "exclusao_segura": "Exclusão segura",
    "gerar_relatorio": "Geração de relatório",
    "verificar_integridade": "Verificação de integridade",
}

STATUS_SUCCESS = "sucesso"
STATUS_FAILURE = "falha"

DEFAULT_SETTINGS: dict[str, Any] = {
    "theme": "escuro",
    "output_dir": "",
    "bits_per_channel": 1,
    "scattered": True,
    "compress": True,
    "kdf_profile": "padrao",
    "require_password": True,
    "min_password_length": 8,
    "max_payload_mb": 256,
    "embed_mode": "auto",
    "secure_delete_passes": 3,
    "confirm_secure_delete": True,
    "history_enabled": True,
    "animations": True,
    "clear_clipboard_seconds": 30,
}


@dataclass
class OperationRecord:
    operation: str
    status: str
    input_path: str = ""
    output_path: str = ""
    payload_kind: str = ""
    payload_size: int = 0
    encrypted: bool = False
    compressed: bool = False
    bits_per_channel: int = 0
    scattered: bool = False
    input_sha256: str = ""
    output_sha256: str = ""
    duration_ms: int = 0
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    id: int | None = None

    @property
    def operation_label(self) -> str:
        return OPERATION_LABELS.get(self.operation, self.operation)

    @property
    def status_label(self) -> str:
        return "Sucesso" if self.status == STATUS_SUCCESS else "Falha"


_COLUMNS = [
    "timestamp", "operation", "status", "input_path", "output_path", "payload_kind",
    "payload_size", "encrypted", "compressed", "bits_per_channel", "scattered",
    "input_sha256", "output_sha256", "duration_ms", "message",
]


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA secure_delete=ON")
        self._migrate()

    # -- infraestrutura --------------------------------------------------
    def _migrate(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS operations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_path TEXT DEFAULT '',
                    output_path TEXT DEFAULT '',
                    payload_kind TEXT DEFAULT '',
                    payload_size INTEGER DEFAULT 0,
                    encrypted INTEGER DEFAULT 0,
                    compressed INTEGER DEFAULT 0,
                    bits_per_channel INTEGER DEFAULT 0,
                    scattered INTEGER DEFAULT 0,
                    input_sha256 TEXT DEFAULT '',
                    output_sha256 TEXT DEFAULT '',
                    duration_ms INTEGER DEFAULT 0,
                    message TEXT DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS idx_operations_ts ON operations(timestamp);
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                """
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- histórico -------------------------------------------------------
    def add_operation(self, rec: OperationRecord) -> int:
        values = [getattr(rec, c) for c in _COLUMNS]
        values = [int(v) if isinstance(v, bool) else v for v in values]
        with self._lock, self._conn:
            cur = self._conn.execute(
                f"INSERT INTO operations({', '.join(_COLUMNS)}) "
                f"VALUES({', '.join('?' * len(_COLUMNS))})",
                values,
            )
            rec.id = int(cur.lastrowid)
            return rec.id

    def _row_to_record(self, row: sqlite3.Row) -> OperationRecord:
        data = {c: row[c] for c in _COLUMNS}
        for b in ("encrypted", "compressed", "scattered"):
            data[b] = bool(data[b])
        return OperationRecord(id=row["id"], **data)

    def list_operations(
        self,
        limit: int | None = None,
        operation: str | None = None,
        status: str | None = None,
        search: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[OperationRecord]:
        sql = "SELECT * FROM operations WHERE 1=1"
        params: list[Any] = []
        if operation:
            sql += " AND operation = ?"
            params.append(operation)
        if status:
            sql += " AND status = ?"
            params.append(status)
        if search:
            sql += " AND (input_path LIKE ? OR output_path LIKE ? OR message LIKE ?)"
            like = f"%{search}%"
            params += [like, like, like]
        if date_from:
            sql += " AND timestamp >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND timestamp <= ?"
            params.append(date_to + "T23:59:59" if len(date_to) == 10 else date_to)
        sql += " ORDER BY id DESC"
        if limit:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_record(r) for r in rows]

    def delete_operation(self, op_id: int) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM operations WHERE id = ?", (op_id,))

    def clear_history(self) -> int:
        with self._lock, self._conn:
            n = self._conn.execute("DELETE FROM operations").rowcount
        with self._lock:
            self._conn.execute("VACUUM")
        return n

    def statistics(self) -> dict[str, Any]:
        with self._lock:
            c = self._conn
            total = c.execute("SELECT COUNT(*) FROM operations").fetchone()[0]
            ok = c.execute(
                "SELECT COUNT(*) FROM operations WHERE status = ?", (STATUS_SUCCESS,)
            ).fetchone()[0]
            by_op = {
                r[0]: r[1]
                for r in c.execute(
                    "SELECT operation, COUNT(*) FROM operations WHERE status = ? GROUP BY operation",
                    (STATUS_SUCCESS,),
                )
            }
            hidden_bytes = c.execute(
                "SELECT COALESCE(SUM(payload_size), 0) FROM operations WHERE status = ? "
                "AND operation IN ('ocultar_mensagem', 'ocultar_arquivo')",
                (STATUS_SUCCESS,),
            ).fetchone()[0]
            since = (datetime.now() - timedelta(days=6)).date().isoformat()
            daily = {
                r[0]: r[1]
                for r in c.execute(
                    "SELECT substr(timestamp, 1, 10) d, COUNT(*) FROM operations "
                    "WHERE timestamp >= ? GROUP BY d",
                    (since,),
                )
            }
        days = [(datetime.now() - timedelta(days=i)).date().isoformat() for i in range(6, -1, -1)]
        return {
            "total": total,
            "success": ok,
            "failure": total - ok,
            "success_rate": (ok / total * 100.0) if total else 0.0,
            "by_operation": by_op,
            "hidden_bytes": int(hidden_bytes),
            "last7": [(d, daily.get(d, 0)) for d in days],
        }

    # -- configurações ---------------------------------------------------
    def get_setting(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        if row is None:
            return DEFAULT_SETTINGS.get(key, default) if default is None else default
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return DEFAULT_SETTINGS.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)",
                (key, json.dumps(value)),
            )

    def all_settings(self) -> dict[str, Any]:
        result = dict(DEFAULT_SETTINGS)
        with self._lock:
            for row in self._conn.execute("SELECT key, value FROM settings"):
                try:
                    result[row[0]] = json.loads(row[1])
                except json.JSONDecodeError:
                    pass
        return result

    def reset_settings(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM settings")


def record_to_dict(rec: OperationRecord) -> dict[str, Any]:
    d = asdict(rec)
    d["operation_label"] = rec.operation_label
    d["status_label"] = rec.status_label
    return d
