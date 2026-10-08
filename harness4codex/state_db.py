from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class StateTransitionError(RuntimeError):
    pass


ACTIVE_STATUSES = ("suggested", "active", "awaiting_gate", "verified")
HUMAN_GATES = {"approve-spec", "approve-plan", "answer-clarifications", "escalation", "branch-open"}
ARTIFACT_OBLIGATIONS = {
    "graph-context": "graph-context",
    "write-spec-light": "spec-light",
    "write-spec": "spec",
    "design-doc": "design",
}


#: Que evidencia verifica cada `kind` de task. O que nao esta aqui e verificado
#: por teste; `kind` nulo ou desconhecido cai em `test`.
#:
#: Ate 2026-09-30 so `test` ligava `verified` e `complete` so aceitava teste:
#: uma task de docs, cujas pipelines nao tem fase que produza teste, so fechava
#: fabricando pytest. Porta da decisao D3 do harness4claude
#: (`docs/specs/portao-stop-sem-codigo-plano.md`). Ver
#: `docs/superpowers/specs/portao-stop-pre-implementacao-diagnostico.md`.
EVIDENCIA_DO_KIND = {"docs": "docs"}

#: Tipos de evidencia cujos numeros sao declarados por quem verificou, e que por
#: isso so valem ancorados no hash de um relatorio em disco (D3).
EVIDENCIA_COM_RELATORIO = frozenset({"docs"})

#: Tipos de evidencia que so podem existir na ULTIMA fase da pipeline (D1).
EVIDENCIA_NA_FASE_FINAL = frozenset({"docs"})

#: As fases que produzem teste. Para o tipo `test`, o Stop cobra a partir da
#: primeira delas na pipeline da task, e em todas as seguintes. Pipeline de tipo
#: `test` sem nenhuma (hoje so `review`) cobra em toda fase (D-G2);
#: `tests/test_portao_pre_implementacao.py::test_AC10_*` amarra o conjunto ao
#: contrato.
FASES_DE_IMPLEMENTACAO = frozenset({"tdd", "systematic-debugging"})

#: O evento que `transition` e `resolve_gate` gravam quando o avanco sai de uma
#: fase de implementacao ou entra nela (D-G3, D-G4). Reclassificar volta a
#: pipeline ao indice 0; sem a marca, uma task com codigo escrito no `tdd`
#: sairia do portao so por ter sido reclassificada. `start_task`,
#: `confirm_classification` e `reclassify` NAO gravam: `systematic-debugging` e
#: a fase 1 de toda pipeline de bug, e corrigir um L1-bug para L2-feature antes
#: de qualquer trabalho nao e avanco.
EVENTO_IMPLEMENTACAO = "passou-pela-implementacao"


def tipo_de_evidencia(kind: str | None) -> str:
    """O `evidence_type` que liga `verified` numa task deste `kind`."""
    return EVIDENCIA_DO_KIND.get(str(kind or ""), "test")


def cobra_evidencia_nesta_fase(
    kind: str | None,
    pipeline: list[str],
    phase: str | None,
    *,
    passou_pela_implementacao: bool = False,
) -> bool:
    """O Stop deve cobrar evidencia desta task na fase em que ela esta?

    Docs: so na ultima fase, a que produz a verificacao (D1). Teste: da primeira
    fase de `FASES_DE_IMPLEMENTACAO` da pipeline em diante, ou em qualquer fase
    se a task ja avancou por uma delas. Falha fechada: pipeline de teste sem fase
    de implementacao cobra em toda fase, e fase fora da pipeline cobra.
    """
    if tipo_de_evidencia(kind) in EVIDENCIA_NA_FASE_FINAL:
        return bool(pipeline) and phase == pipeline[-1]
    if passou_pela_implementacao or phase not in pipeline:
        return True
    inicio = next((indice for indice, fase in enumerate(pipeline) if fase in FASES_DE_IMPLEMENTACAO), 0)
    return pipeline.index(phase) >= inicio


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HarnessDatabase:
    def __init__(self, home: str | Path):
        self.home = Path(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self.path = self.home / "harness.db"
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = NORMAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS scopes (
                    scope_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    scope_id TEXT NOT NULL REFERENCES scopes(scope_id),
                    legacy_level TEXT NOT NULL,
                    tier TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    pipeline_json TEXT NOT NULL,
                    phase_index INTEGER NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,
                    code_revision INTEGER NOT NULL DEFAULT 0,
                    owner_epoch INTEGER NOT NULL DEFAULT 1,
                    verified INTEGER NOT NULL DEFAULT 0,
                    prompt_hash TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_task_per_scope
                ON tasks(scope_id) WHERE status IN ('suggested', 'active', 'awaiting_gate', 'verified');
                CREATE TABLE IF NOT EXISTS classifications (
                    task_id TEXT PRIMARY KEY REFERENCES tasks(task_id),
                    suggested TEXT NOT NULL,
                    final TEXT,
                    source TEXT NOT NULL,
                    confidence REAL,
                    agreed INTEGER
                );
                CREATE TABLE IF NOT EXISTS files (
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    normalized_path TEXT NOT NULL,
                    first_seen_code_revision INTEGER NOT NULL,
                    PRIMARY KEY(task_id, normalized_path)
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    artifact_type TEXT NOT NULL,
                    path TEXT NOT NULL,
                    content_hash TEXT,
                    phase TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY(task_id, artifact_type, path)
                );
                CREATE TABLE IF NOT EXISTS evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    code_revision INTEGER NOT NULL,
                    evidence_type TEXT NOT NULL,
                    command TEXT,
                    exit_code INTEGER,
                    tests_collected INTEGER,
                    tests_passed INTEGER,
                    output_hash TEXT,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS gates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    gate_type TEXT NOT NULL,
                    subject_id TEXT,
                    status TEXT NOT NULL,
                    decision TEXT,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                );
                CREATE TABLE IF NOT EXISTS transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    from_phase TEXT,
                    to_phase TEXT,
                    revision INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT,
                    scope_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS leases (
                    scope_id TEXT PRIMARY KEY REFERENCES scopes(scope_id),
                    owner_token TEXT NOT NULL,
                    owner_epoch INTEGER NOT NULL,
                    expires_at REAL NOT NULL,
                    heartbeat_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS branches (
                    branch_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES tasks(task_id),
                    scope_id TEXT NOT NULL REFERENCES scopes(scope_id),
                    slug TEXT NOT NULL,
                    name TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    topic_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    offered_turn INTEGER NOT NULL,
                    seed_path TEXT,
                    conclusion TEXT,
                    approved_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(task_id, slug),
                    UNIQUE(task_id, topic_hash)
                );
                """
            )
            gate_columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(gates)").fetchall()}
            if "subject_id" not in gate_columns:
                connection.execute("ALTER TABLE gates ADD COLUMN subject_id TEXT")
            connection.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS one_pending_gate_per_subject "
                "ON gates(task_id, gate_type, subject_id) "
                "WHERE status = 'pending' AND subject_id IS NOT NULL"
            )

    def start_task(
        self,
        *,
        scope_id: str,
        legacy_level: str,
        tier: str,
        kind: str,
        pipeline: list[str],
        prompt: str,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        now = utc_now()
        task_id = task_id or f"t-{int(time.time() * 1000)}-{uuid.uuid4().hex[:8]}"
        status = "active" if pipeline else "done"
        with self._write() as connection:
            connection.execute("INSERT OR IGNORE INTO scopes(scope_id, created_at) VALUES (?, ?)", (scope_id, now))
            connection.execute(
                "UPDATE gates SET status = 'cancelled', decision = 'task-switch', resolved_at = ? "
                "WHERE status = 'pending' AND task_id IN ("
                "SELECT task_id FROM tasks WHERE scope_id = ? "
                "AND status IN ('suggested', 'active', 'awaiting_gate', 'verified'))",
                (now, scope_id),
            )
            connection.execute(
                "UPDATE tasks SET status = 'abandoned', revision = revision + 1, updated_at = ? "
                "WHERE scope_id = ? AND status IN ('suggested', 'active', 'awaiting_gate', 'verified')",
                (now, scope_id),
            )
            connection.execute(
                """
                INSERT INTO tasks(
                    task_id, scope_id, legacy_level, tier, kind, status, pipeline_json,
                    phase_index, revision, code_revision, owner_epoch, verified,
                    prompt_hash, started_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, 1, 0, ?, ?, ?)
                """,
                (
                    task_id,
                    scope_id,
                    legacy_level,
                    tier,
                    kind,
                    status,
                    json.dumps(pipeline),
                    0 if pipeline else -1,
                    hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO classifications(task_id, suggested, final, source, confidence, agreed) "
                "VALUES (?, ?, NULL, 'regex', NULL, NULL)",
                (task_id, f"{tier}-{kind}"),
            )
        return self.task(task_id)

    def classification(self, task_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT suggested, final, source, confidence, agreed FROM classifications WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            raise StateTransitionError(f"classification not found for task: {task_id}")
        return {
            "suggested": row["suggested"],
            "final": row["final"],
            "source": row["source"],
            "confidence": row["confidence"],
            "agreed": None if row["agreed"] is None else bool(row["agreed"]),
        }

    def confirm_classification(
        self,
        task_id: str,
        *,
        tier: str,
        kind: str,
        pipeline: list[str],
        source: str,
        confidence: float,
    ) -> dict[str, Any]:
        if source not in {"semantic", "human_override"}:
            raise StateTransitionError(f"invalid classification source: {source}")
        if not 0 <= confidence <= 1:
            raise StateTransitionError("classification confidence must be between 0 and 1")
        final = f"{tier}-{kind}"
        with self._write() as connection:
            row = self._locked_task(connection, task_id)
            decision = connection.execute(
                "SELECT suggested FROM classifications WHERE task_id = ?", (task_id,)
            ).fetchone()
            if decision is None:
                raise StateTransitionError(f"classification not found for task: {task_id}")
            agreed = decision["suggested"] == final
            connection.execute(
                "UPDATE classifications SET final = ?, source = ?, confidence = ?, agreed = ? WHERE task_id = ?",
                (final, source, confidence, 1 if agreed else 0, task_id),
            )
            connection.execute(
                """
                UPDATE tasks
                SET tier = ?, kind = ?, pipeline_json = ?, phase_index = ?,
                    status = ?, verified = 0, revision = revision + 1, updated_at = ?
                WHERE task_id = ?
                """,
                (
                    tier,
                    kind,
                    json.dumps(pipeline),
                    0 if pipeline else -1,
                    "active" if pipeline else "done",
                    utc_now(),
                    task_id,
                ),
            )
            connection.execute(
                "INSERT INTO transitions(task_id, from_phase, to_phase, revision, created_at) VALUES (?, ?, ?, ?, ?)",
                (
                    task_id,
                    self._phase(row),
                    pipeline[0] if pipeline else None,
                    int(row["revision"]) + 1,
                    utc_now(),
                ),
            )
        return self.task(task_id)

    def task(self, task_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise StateTransitionError(f"task not found: {task_id}")
            gate = connection.execute(
                "SELECT gate_type, subject_id FROM gates WHERE task_id = ? AND status = 'pending' "
                "ORDER BY id DESC LIMIT 1",
                (task_id,),
            ).fetchone()
            passou = self._passou_pela_implementacao(connection, task_id)
        pending_gate = None
        if gate:
            pending_gate = str(gate["gate_type"])
            if gate["subject_id"]:
                pending_gate += f":{gate['subject_id']}"
        renderizada = self._render_task(row, pending_gate)
        # Lido aqui para o hook de Stop decidir com o fato que so o banco guarda.
        renderizada["passou_pela_implementacao"] = passou
        return renderizada

    def current_task(self, scope_id: str) -> dict[str, Any] | None:
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        with self._connect() as connection:
            row = connection.execute(
                f"SELECT task_id FROM tasks WHERE scope_id = ? AND status IN ({placeholders}) "
                "ORDER BY started_at DESC LIMIT 1",
                (scope_id, *ACTIVE_STATUSES),
            ).fetchone()
        return self.task(str(row["task_id"])) if row else None

    def expire_stale_tasks(
        self,
        scope_id: str | None,
        *,
        ttl_seconds: float,
        now: float | None = None,
    ) -> list[dict[str, Any]]:
        """Abandona toda task nao terminal vencida pelo TTL, gravando um evento por task.

        `scope_id=None` varre todos os escopos: o indice `one_active_task_per_scope`
        garante uma task ativa por escopo, entao as tasks presas de sessoes mortas
        so saem por varredura, nunca pelo hook da sessao viva."""
        current_time = time.time() if now is None else float(now)
        ttl = max(float(ttl_seconds), 0.001)
        placeholders = ",".join("?" for _ in ACTIVE_STATUSES)
        expired_ids: list[str] = []
        with self._write() as connection:
            query = f"SELECT * FROM tasks WHERE status IN ({placeholders})"
            params: tuple[Any, ...] = tuple(ACTIVE_STATUSES)
            if scope_id is not None:
                query += " AND scope_id = ?"
                params += (scope_id,)
            for row in connection.execute(query + " ORDER BY started_at", params).fetchall():
                try:
                    started = datetime.fromisoformat(str(row["started_at"]))
                    if started.tzinfo is None:
                        started = started.replace(tzinfo=timezone.utc)
                    expired = current_time - started.timestamp() > ttl
                except (TypeError, ValueError, OverflowError):
                    expired = True
                if not expired:
                    continue
                task_id = str(row["task_id"])
                occurred_at = datetime.fromtimestamp(current_time, timezone.utc).isoformat()
                connection.execute(
                    "UPDATE tasks SET status = 'abandoned', verified = 0, revision = revision + 1, "
                    "updated_at = ? WHERE task_id = ?",
                    (occurred_at, task_id),
                )
                connection.execute(
                    "UPDATE gates SET status = 'cancelled', decision = 'ttl-expired', resolved_at = ? "
                    "WHERE task_id = ? AND status = 'pending'",
                    (occurred_at, task_id),
                )
                connection.execute(
                    "INSERT INTO events(task_id, scope_id, event_type, payload_json, created_at) "
                    "VALUES (?, ?, 'pipeline-expired', ?, ?)",
                    (task_id, row["scope_id"], json.dumps({"ttl_seconds": ttl}, sort_keys=True), occurred_at),
                )
                expired_ids.append(task_id)
        return [self.task(task_id) for task_id in expired_ids]

    # RESERVA DECLARADA (decisao 6 de master-harness/docs/decisoes-capacidades-orfas.md,
    # secoes 6 e 10; segue a decisao 2): `acquire_lease` nao tem chamador de producao.
    # Ligar a cerca de epoca exige o lease, e os dois entram juntos ou nenhum.
    def acquire_lease(
        self,
        scope_id: str,
        owner_token: str,
        *,
        ttl_seconds: float = 30.0,
        now: float | None = None,
    ) -> dict[str, Any]:
        current_time = time.time() if now is None else float(now)
        expires_at = current_time + max(float(ttl_seconds), 0.001)
        with self._write() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO scopes(scope_id, created_at) VALUES (?, ?)",
                (scope_id, utc_now()),
            )
            current = connection.execute(
                "SELECT owner_token, owner_epoch, expires_at FROM leases WHERE scope_id = ?",
                (scope_id,),
            ).fetchone()
            if current is None:
                epoch = 1
                connection.execute(
                    "INSERT INTO leases(scope_id, owner_token, owner_epoch, expires_at, heartbeat_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (scope_id, owner_token, epoch, expires_at, current_time),
                )
            elif current["owner_token"] == owner_token:
                epoch = int(current["owner_epoch"])
                connection.execute(
                    "UPDATE leases SET expires_at = ?, heartbeat_at = ? WHERE scope_id = ?",
                    (expires_at, current_time, scope_id),
                )
            elif float(current["expires_at"]) > current_time:
                raise StateTransitionError(f"scope {scope_id} has an active lease owned by another writer")
            else:
                epoch = int(current["owner_epoch"]) + 1
                connection.execute(
                    "UPDATE leases SET owner_token = ?, owner_epoch = ?, expires_at = ?, heartbeat_at = ? "
                    "WHERE scope_id = ?",
                    (owner_token, epoch, expires_at, current_time, scope_id),
                )
            connection.execute(
                "UPDATE tasks SET owner_epoch = ?, revision = revision + 1, updated_at = ? "
                "WHERE scope_id = ? AND status IN ('suggested', 'active', 'awaiting_gate', 'verified') "
                "AND owner_epoch <> ?",
                (epoch, utc_now(), scope_id, epoch),
            )
        return {
            "scope_id": scope_id,
            "owner_token": owner_token,
            "owner_epoch": epoch,
            "expires_at": expires_at,
        }

    def record_artifact(
        self,
        task_id: str,
        artifact_type: str,
        path: str,
        content_hash: str | None,
    ) -> dict[str, Any]:
        with self._write() as connection:
            row = self._locked_task(connection, task_id)
            phase = self._phase(row)
            connection.execute(
                """
                INSERT INTO artifacts(task_id, artifact_type, path, content_hash, phase, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id, artifact_type, path) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    phase = excluded.phase,
                    created_at = excluded.created_at
                """,
                (task_id, artifact_type, path, content_hash, phase, utc_now()),
            )
            self._bump(connection, task_id)
        return self.task(task_id)

    def create_branch(
        self,
        task_id: str,
        *,
        branch_id: str,
        slug: str,
        name: str,
        topic: str,
        topic_hash: str,
        offered_turn: int,
        max_offers: int,
        cooldown_turns: int,
    ) -> dict[str, Any]:
        now = utc_now()
        with self._write() as connection:
            task = self._locked_task(connection, task_id)
            offer_stats = connection.execute(
                "SELECT COUNT(*) AS count, MAX(offered_turn) AS last_turn FROM branches WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            if int(offer_stats["count"]) >= max_offers:
                raise StateTransitionError("branch offer limit reached")
            if offer_stats["last_turn"] is not None and offered_turn - int(offer_stats["last_turn"]) < cooldown_turns:
                raise StateTransitionError("branch offer cooldown is active")
            connection.execute(
                """
                INSERT INTO branches(
                    branch_id, task_id, scope_id, slug, name, topic, topic_hash,
                    status, offered_turn, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    branch_id,
                    task_id,
                    task["scope_id"],
                    slug,
                    name,
                    topic,
                    topic_hash,
                    offered_turn,
                    now,
                    now,
                ),
            )
            connection.execute(
                "INSERT INTO gates(task_id, gate_type, subject_id, status, created_at) "
                "VALUES (?, 'branch-open', ?, 'pending', ?)",
                (task_id, branch_id, now),
            )
            connection.execute(
                "UPDATE tasks SET status = 'awaiting_gate', revision = revision + 1, updated_at = ? WHERE task_id = ?",
                (now, task_id),
            )
        return self.branch(branch_id)

    def branch(self, branch_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM branches WHERE branch_id = ?", (branch_id,)).fetchone()
        if row is None:
            raise StateTransitionError(f"branch not found: {branch_id}")
        return dict(row)

    def list_branches(self, task_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM branches WHERE task_id = ? ORDER BY created_at, branch_id", (task_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def approve_branch(self, branch_id: str) -> dict[str, Any]:
        now = utc_now()
        with self._write() as connection:
            branch = connection.execute("SELECT * FROM branches WHERE branch_id = ?", (branch_id,)).fetchone()
            if branch is None:
                raise StateTransitionError(f"branch not found: {branch_id}")
            gate = connection.execute(
                "SELECT id FROM gates WHERE task_id = ? AND gate_type = 'branch-open' AND status = 'pending' "
                "AND subject_id = ? ORDER BY id DESC LIMIT 1",
                (branch["task_id"], branch_id),
            ).fetchone()
            if gate is None:
                raise StateTransitionError("pending branch-open gate not found")
            connection.execute(
                "UPDATE gates SET status = 'resolved', decision = 'approve', resolved_at = ? WHERE id = ?",
                (now, gate["id"]),
            )
            connection.execute(
                "UPDATE branches SET approved_at = ?, updated_at = ? WHERE branch_id = ?",
                (now, now, branch_id),
            )
            still_pending = connection.execute(
                "SELECT 1 FROM gates WHERE task_id = ? AND status = 'pending' LIMIT 1",
                (branch["task_id"],),
            ).fetchone()
            connection.execute(
                "UPDATE tasks SET status = ?, revision = revision + 1, updated_at = ? WHERE task_id = ?",
                ("awaiting_gate" if still_pending else "active", now, branch["task_id"]),
            )
        return self.branch(branch_id)

    def open_branch(self, branch_id: str, *, seed_path: str, max_open: int) -> dict[str, Any]:
        with self._write() as connection:
            branch = connection.execute("SELECT * FROM branches WHERE branch_id = ?", (branch_id,)).fetchone()
            if branch is None:
                raise StateTransitionError(f"branch not found: {branch_id}")
            if not branch["approved_at"]:
                raise StateTransitionError("branch-open approval is required")
            open_count = connection.execute(
                "SELECT COUNT(*) AS count FROM branches WHERE task_id = ? AND status = 'open'",
                (branch["task_id"],),
            ).fetchone()
            if int(open_count["count"]) >= max_open:
                raise StateTransitionError("open branch limit reached")
            connection.execute(
                "UPDATE branches SET status = 'open', seed_path = ?, updated_at = ? WHERE branch_id = ?",
                (seed_path, utc_now(), branch_id),
            )
        return self.branch(branch_id)

    def update_branch(
        self,
        branch_id: str,
        *,
        status: str,
        seed_path: str | None = None,
        conclusion: str | None = None,
    ) -> dict[str, Any]:
        if status not in {"pending", "open", "parked", "recalled", "closed"}:
            raise StateTransitionError(f"invalid branch status: {status}")
        with self._write() as connection:
            branch = connection.execute("SELECT 1 FROM branches WHERE branch_id = ?", (branch_id,)).fetchone()
            if branch is None:
                raise StateTransitionError(f"branch not found: {branch_id}")
            connection.execute(
                "UPDATE branches SET status = ?, seed_path = COALESCE(?, seed_path), "
                "conclusion = COALESCE(?, conclusion), updated_at = ? WHERE branch_id = ?",
                (status, seed_path, conclusion, utc_now(), branch_id),
            )
        return self.branch(branch_id)

    def reclassify(
        self,
        task_id: str,
        *,
        legacy_level: str,
        tier: str,
        kind: str,
        pipeline: list[str],
    ) -> dict[str, Any]:
        with self._write() as connection:
            self._locked_task(connection, task_id)
            connection.execute(
                """
                UPDATE tasks
                SET legacy_level = ?, tier = ?, kind = ?, pipeline_json = ?,
                    phase_index = ?, status = ?, verified = 0,
                    revision = revision + 1, updated_at = ?
                WHERE task_id = ?
                """,
                (
                    legacy_level,
                    tier,
                    kind,
                    json.dumps(pipeline),
                    0 if pipeline else -1,
                    "active" if pipeline else "done",
                    utc_now(),
                    task_id,
                ),
            )
        return self.task(task_id)

    def open_gate(self, task_id: str, gate_type: str) -> dict[str, Any]:
        with self._write() as connection:
            self._locked_task(connection, task_id)
            pending = connection.execute(
                "SELECT 1 FROM gates WHERE task_id = ? AND gate_type = ? AND status = 'pending'",
                (task_id, gate_type),
            ).fetchone()
            if pending is None:
                connection.execute(
                    "INSERT INTO gates(task_id, gate_type, status, created_at) VALUES (?, ?, 'pending', ?)",
                    (task_id, gate_type, utc_now()),
                )
            connection.execute(
                "UPDATE tasks SET status = 'awaiting_gate', revision = revision + 1, updated_at = ? WHERE task_id = ?",
                (utc_now(), task_id),
            )
        return self.task(task_id)

    def transition(
        self,
        task_id: str,
        to_phase: str,
        *,
        expected_revision: int,
        owner_epoch: int | None = None,
    ) -> dict[str, Any]:
        with self._write() as connection:
            row = self._locked_task(connection, task_id)
            self._expect_revision(row, expected_revision)
            if owner_epoch is not None and int(row["owner_epoch"]) != owner_epoch:
                raise StateTransitionError(f"owner epoch mismatch: expected {owner_epoch}, actual {row['owner_epoch']}")
            pipeline = json.loads(row["pipeline_json"])
            current_index = int(row["phase_index"])
            next_index = current_index + 1
            if next_index >= len(pipeline) or pipeline[next_index] != to_phase:
                expected = pipeline[next_index] if next_index < len(pipeline) else "<terminal>"
                raise StateTransitionError(f"next phase must be {expected}, got {to_phase}")
            current_phase = pipeline[current_index]
            obligation = ARTIFACT_OBLIGATIONS.get(current_phase)
            if obligation and not self._has_artifact(connection, task_id, obligation):
                raise StateTransitionError(f"phase {current_phase} requires artifact {obligation}")
            new_revision = int(row["revision"]) + 1
            status = "awaiting_gate" if to_phase in HUMAN_GATES else "active"
            connection.execute(
                "UPDATE tasks SET phase_index = ?, status = ?, revision = ?, updated_at = ? WHERE task_id = ?",
                (next_index, status, new_revision, utc_now(), task_id),
            )
            connection.execute(
                "INSERT INTO transitions(task_id, from_phase, to_phase, revision, created_at) VALUES (?, ?, ?, ?, ?)",
                (task_id, current_phase, to_phase, new_revision, utc_now()),
            )
            if to_phase in HUMAN_GATES:
                connection.execute(
                    "INSERT INTO gates(task_id, gate_type, status, created_at) VALUES (?, ?, 'pending', ?)",
                    (task_id, to_phase, utc_now()),
                )
            self._marcar_implementacao(connection, row, current_phase, to_phase)
        return self.task(task_id)

    def resolve_gate(
        self,
        task_id: str,
        gate_type: str,
        decision: str,
        *,
        expected_revision: int,
    ) -> dict[str, Any]:
        if decision not in {"approve", "reject"}:
            raise StateTransitionError(f"unsupported gate decision: {decision}")
        with self._write() as connection:
            row = self._locked_task(connection, task_id)
            self._expect_revision(row, expected_revision)
            pending = connection.execute(
                "SELECT id FROM gates WHERE task_id = ? AND gate_type = ? "
                "AND status = 'pending' ORDER BY id DESC LIMIT 1",
                (task_id, gate_type),
            ).fetchone()
            if pending is None:
                raise StateTransitionError(f"pending gate not found: {gate_type}")
            if decision == "reject":
                # Recusar encerra a task: o gate fecha como `reject` e o escopo e liberado.
                # Nao passa por `_marcar_implementacao`: recusa nao e avanco.
                occurred_at = utc_now()
                connection.execute(
                    "UPDATE gates SET status = 'resolved', decision = ?, resolved_at = ? WHERE id = ?",
                    (decision, occurred_at, pending["id"]),
                )
                connection.execute(
                    "UPDATE tasks SET status = 'abandoned', verified = 0, revision = ?, updated_at = ? "
                    "WHERE task_id = ?",
                    (int(row["revision"]) + 1, occurred_at, task_id),
                )
            elif gate_type == "escalation":
                # A escalada nasce no Stop, fora do pipeline: aprovar devolve a task a mesma fase.
                occurred_at = utc_now()
                connection.execute(
                    "UPDATE gates SET status = 'resolved', decision = ?, resolved_at = ? WHERE id = ?",
                    (decision, occurred_at, pending["id"]),
                )
                connection.execute(
                    "UPDATE tasks SET status = 'active', revision = ?, updated_at = ? WHERE task_id = ?",
                    (int(row["revision"]) + 1, occurred_at, task_id),
                )
            else:
                pipeline = json.loads(row["pipeline_json"])
                current_index = int(row["phase_index"])
                if pipeline[current_index] != gate_type or current_index + 1 >= len(pipeline):
                    raise StateTransitionError(f"gate is not at an advanceable phase: {gate_type}")
                next_phase = pipeline[current_index + 1]
                new_revision = int(row["revision"]) + 1
                connection.execute(
                    "UPDATE gates SET status = 'resolved', decision = ?, resolved_at = ? WHERE id = ?",
                    (decision, utc_now(), pending["id"]),
                )
                connection.execute(
                    "UPDATE tasks SET phase_index = ?, status = 'active', revision = ?, "
                    "updated_at = ? WHERE task_id = ?",
                    (current_index + 1, new_revision, utc_now(), task_id),
                )
                connection.execute(
                    "INSERT INTO transitions(task_id, from_phase, to_phase, revision, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (task_id, gate_type, next_phase, new_revision, utc_now()),
                )
                self._marcar_implementacao(connection, row, gate_type, next_phase)
        return self.task(task_id)

    def touch_file(self, task_id: str, path: str) -> dict[str, Any]:
        normalized = str(Path(path))
        with self._write() as connection:
            row = self._locked_task(connection, task_id)
            next_code_revision = int(row["code_revision"]) + 1
            connection.execute(
                "INSERT OR IGNORE INTO files(task_id, normalized_path, first_seen_code_revision) VALUES (?, ?, ?)",
                (task_id, normalized, next_code_revision),
            )
            connection.execute(
                "UPDATE tasks SET code_revision = ?, revision = revision + 1, verified = 0, "
                "status = CASE WHEN status = 'verified' THEN 'active' ELSE status END, "
                "updated_at = ? WHERE task_id = ?",
                (next_code_revision, utc_now(), task_id),
            )
        return self.task(task_id)

    def record_evidence(
        self,
        task_id: str,
        *,
        evidence_type: str,
        command: str | None,
        exit_code: int | None,
        tests_collected: int | None,
        tests_passed: int | None,
        output_hash: str | None,
    ) -> dict[str, Any]:
        with self._write() as connection:
            row = self._locked_task(connection, task_id)
            # A regua e a do tipo que ESTA task exige. Evidencia de outro tipo e
            # historico e nao mexe em `verified` para nenhum lado: um pytest nao
            # verifica uma doc, e um pytest vermelho tambem nao a desverifica.
            exigido = tipo_de_evidencia(row["kind"])
            valid_test = (
                evidence_type == exigido
                and exit_code == 0
                and isinstance(tests_collected, int)
                and tests_collected > 0
                and tests_passed == tests_collected
                and (exigido not in EVIDENCIA_COM_RELATORIO or output_hash is not None)
            )
            connection.execute(
                """
                INSERT INTO evidence(
                    task_id, code_revision, evidence_type, command, exit_code,
                    tests_collected, tests_passed, output_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    row["code_revision"],
                    evidence_type,
                    command,
                    exit_code,
                    tests_collected,
                    tests_passed,
                    output_hash,
                    utc_now(),
                ),
            )
            connection.execute(
                "UPDATE tasks SET verified = ?, status = ?, revision = revision + 1, updated_at = ? WHERE task_id = ?",
                (
                    1 if valid_test else 0 if evidence_type == exigido else int(row["verified"]),
                    (
                        "verified"
                        if valid_test
                        else "active"
                        if evidence_type == exigido and row["status"] == "verified"
                        else row["status"]
                    ),
                    utc_now(),
                    task_id,
                ),
            )
        return self.task(task_id)

    def complete(self, task_id: str, *, expected_revision: int) -> dict[str, Any]:
        with self._write() as connection:
            row = self._locked_task(connection, task_id)
            self._expect_revision(row, expected_revision)
            if not bool(row["verified"]) or not self._has_fresh_evidence(connection, row):
                raise StateTransitionError("task requires fresh verification evidence")
            pipeline = json.loads(row["pipeline_json"])
            if pipeline and int(row["phase_index"]) != len(pipeline) - 1:
                raise StateTransitionError(f"task is not at final phase: {self._phase(row)}")
            connection.execute(
                "UPDATE tasks SET status = 'done', revision = revision + 1, updated_at = ? WHERE task_id = ?",
                (utc_now(), task_id),
            )
        return self.task(task_id)

    def log_event(self, scope_id: str, event_type: str, payload: dict[str, Any], task_id: str | None = None) -> None:
        with self._write() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO scopes(scope_id, created_at) VALUES (?, ?)", (scope_id, utc_now())
            )
            connection.execute(
                "INSERT INTO events(task_id, scope_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
                (task_id, scope_id, event_type, json.dumps(payload, sort_keys=True), utc_now()),
            )

    def _locked_task(self, connection: sqlite3.Connection, task_id: str) -> sqlite3.Row:
        row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise StateTransitionError(f"task not found: {task_id}")
        return row

    @staticmethod
    def _expect_revision(row: sqlite3.Row, expected: int) -> None:
        actual = int(row["revision"])
        if actual != expected:
            raise StateTransitionError(f"revision mismatch: expected {expected}, actual {actual}")

    @staticmethod
    def _phase(row: sqlite3.Row) -> str | None:
        pipeline = json.loads(row["pipeline_json"])
        index = int(row["phase_index"])
        return pipeline[index] if pipeline and 0 <= index < len(pipeline) else None

    @staticmethod
    def _has_artifact(connection: sqlite3.Connection, task_id: str, artifact_type: str) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM artifacts WHERE task_id = ? AND artifact_type = ? LIMIT 1",
                (task_id, artifact_type),
            ).fetchone()
            is not None
        )

    @staticmethod
    def _has_fresh_evidence(connection: sqlite3.Connection, row: sqlite3.Row) -> bool:
        """A ultima evidencia do tipo que esta task exige, na revisao atual, passa."""
        exigido = tipo_de_evidencia(row["kind"])
        com_relatorio = 1 if exigido in EVIDENCIA_COM_RELATORIO else 0
        return (
            connection.execute(
                """
            SELECT 1 FROM evidence
            WHERE task_id = ? AND code_revision = ? AND evidence_type = ?
              AND exit_code = 0 AND tests_collected > 0 AND tests_passed = tests_collected
              AND (? = 0 OR output_hash IS NOT NULL)
              AND id = (
                  SELECT MAX(id) FROM evidence
                  WHERE task_id = ? AND code_revision = ? AND evidence_type = ?
              )
            LIMIT 1
            """,
                (
                    row["task_id"],
                    row["code_revision"],
                    exigido,
                    com_relatorio,
                    row["task_id"],
                    row["code_revision"],
                    exigido,
                ),
            ).fetchone()
            is not None
        )

    @staticmethod
    def _marcar_implementacao(
        connection: sqlite3.Connection, row: sqlite3.Row, de: str | None, para: str | None
    ) -> None:
        """Grava `EVENTO_IMPLEMENTACAO` quando o AVANCO sai de uma fase de
        implementacao ou entra nela. So `transition` e `resolve_gate` chamam, e
        so depois de o avanco ter passado por todas as recusas."""
        if de not in FASES_DE_IMPLEMENTACAO and para not in FASES_DE_IMPLEMENTACAO:
            return
        connection.execute(
            "INSERT INTO events(task_id, scope_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (
                row["task_id"],
                row["scope_id"],
                EVENTO_IMPLEMENTACAO,
                json.dumps({"de": de, "para": para}, sort_keys=True),
                utc_now(),
            ),
        )

    @staticmethod
    def _passou_pela_implementacao(connection: sqlite3.Connection, task_id: str) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM events WHERE task_id = ? AND event_type = ? LIMIT 1",
                (task_id, EVENTO_IMPLEMENTACAO),
            ).fetchone()
            is not None
        )

    @staticmethod
    def _bump(connection: sqlite3.Connection, task_id: str) -> None:
        connection.execute(
            "UPDATE tasks SET revision = revision + 1, updated_at = ? WHERE task_id = ?",
            (utc_now(), task_id),
        )

    @classmethod
    def _render_task(cls, row: sqlite3.Row, pending_gate: str | None) -> dict[str, Any]:
        pipeline = json.loads(row["pipeline_json"])
        index = int(row["phase_index"])
        return {
            "task_id": row["task_id"],
            "scope_id": row["scope_id"],
            "legacy_level": row["legacy_level"],
            "tier": row["tier"],
            "kind": row["kind"],
            "status": row["status"],
            "pipeline": pipeline,
            "phase": pipeline[index] if pipeline and 0 <= index < len(pipeline) else None,
            "revision": int(row["revision"]),
            "code_revision": int(row["code_revision"]),
            "owner_epoch": int(row["owner_epoch"]),
            "verified": bool(row["verified"]),
            "pending_gate": pending_gate,
            "started_at": row["started_at"],
            "updated_at": row["updated_at"],
        }
