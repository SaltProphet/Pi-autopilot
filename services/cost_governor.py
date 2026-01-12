import sqlite3
import json
import time
from contextlib import contextmanager
from config import settings


class CostGovernor:
    def __init__(self):
        self.db_path = settings.database_path
        self.run_id = int(time.time())
        self._init_db()
        self.run_tokens_sent = 0
        self.run_tokens_received = 0
        self.run_cost = 0.0
        self.aborted = False
        self.abort_reason = None

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cost_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    tokens_sent INTEGER NOT NULL,
                    tokens_received INTEGER NOT NULL,
                    usd_cost REAL NOT NULL,
                    timestamp INTEGER NOT NULL,
                    model TEXT,
                    abort_reason TEXT
                )
            """)
            conn.commit()

    def estimate_tokens(self, text: str) -> int:
        return int(len(text) / 3.5)

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        input_cost = input_tokens * settings.openai_input_token_price
        output_cost = output_tokens * settings.openai_output_token_price
        return input_cost + output_cost

    def get_lifetime_cost(self) -> float:
        with self._get_conn() as conn:
            row = conn.execute("SELECT SUM(usd_cost) as total FROM cost_tracking").fetchone()
            return row["total"] if row["total"] else 0.0

    def check_limits_before_call(self, estimated_input_tokens: int, estimated_output_tokens: int):
        if self.aborted:
            raise CostLimitExceeded(self.abort_reason)

        estimated_cost = self.estimate_cost(estimated_input_tokens, estimated_output_tokens)

        if self.run_tokens_sent + estimated_input_tokens > settings.max_tokens_per_run:
            self.abort_reason = f"MAX_TOKENS_PER_RUN exceeded: {self.run_tokens_sent + estimated_input_tokens} > {settings.max_tokens_per_run}"
            self.aborted = True
            self._write_abort_record()
            raise CostLimitExceeded(self.abort_reason)

        if self.run_cost + estimated_cost > settings.max_usd_per_run:
            self.abort_reason = f"MAX_USD_PER_RUN exceeded: {self.run_cost + estimated_cost:.4f} > {settings.max_usd_per_run}"
            self.aborted = True
            self._write_abort_record()
            raise CostLimitExceeded(self.abort_reason)

        lifetime_cost = self.get_lifetime_cost()
        if lifetime_cost + estimated_cost > settings.max_usd_lifetime:
            self.abort_reason = f"MAX_USD_LIFETIME exceeded: {lifetime_cost + estimated_cost:.4f} > {settings.max_usd_lifetime}"
            self.aborted = True
            self._write_abort_record()
            raise CostLimitExceeded(self.abort_reason)

    def record_usage(self, input_tokens: int, output_tokens: int):
        cost = self.estimate_cost(input_tokens, output_tokens)

        self.run_tokens_sent += input_tokens
        self.run_tokens_received += output_tokens
        self.run_cost += cost

        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO cost_tracking (run_id, tokens_sent, tokens_received, usd_cost, timestamp, model)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (self.run_id, input_tokens, output_tokens, cost, int(time.time()), settings.openai_model))
            conn.commit()

    def _write_abort_record(self):
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO cost_tracking (run_id, tokens_sent, tokens_received, usd_cost, timestamp, model, abort_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (self.run_id, 0, 0, 0.0, int(time.time()), settings.openai_model, self.abort_reason))
            conn.commit()

        abort_file = f"{settings.artifacts_path}/abort_{self.run_id}.json"
        with open(abort_file, 'w') as f:
            json.dump({
                "run_id": self.run_id,
                "abort_reason": self.abort_reason,
                "run_tokens_sent": self.run_tokens_sent,
                "run_tokens_received": self.run_tokens_received,
                "run_cost": self.run_cost,
                "timestamp": int(time.time())
            }, f, indent=2)

    def get_run_stats(self) -> dict:
        return {
            "run_id": self.run_id,
            "tokens_sent": self.run_tokens_sent,
            "tokens_received": self.run_tokens_received,
            "cost_usd": self.run_cost,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason
        }


class CostLimitExceeded(Exception):
    pass
