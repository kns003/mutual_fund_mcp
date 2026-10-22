import json, sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from mutual_fund_mcp.models import Transaction

class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True); self.path = path; self._init()
    def connect(self):
        c=sqlite3.connect(self.path); c.row_factory=sqlite3.Row; return c
    def _init(self):
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL, expires TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS transactions (transaction_id INTEGER PRIMARY KEY AUTOINCREMENT, scheme_code INTEGER NOT NULL, date TEXT NOT NULL, transaction_type TEXT NOT NULL, units TEXT NOT NULL, nav TEXT NOT NULL, amount TEXT NOT NULL, notes TEXT);''')
    def get_cache(self,key):
        with self.connect() as c:
            r=c.execute("SELECT value,expires FROM cache WHERE key=?",(key,)).fetchone()
        return json.loads(r["value"]) if r and datetime.fromisoformat(r["expires"]) > datetime.now(UTC) else None
    def set_cache(self,key,value,ttl_hours):
        expiry=(datetime.now(UTC)+timedelta(hours=ttl_hours)).isoformat()
        with self.connect() as c: c.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)",(key,json.dumps(value),expiry))
    def clear_cache(self):
        with self.connect() as c: c.execute("DELETE FROM cache")
    def add_transaction(self,t:Transaction):
        with self.connect() as c:
            cur=c.execute("INSERT INTO transactions(scheme_code,date,transaction_type,units,nav,amount,notes) VALUES (?,?,?,?,?,?,?)",(t.scheme_code,t.date.isoformat(),t.transaction_type,str(t.units),str(t.nav),str(t.amount),t.notes)); return cur.lastrowid
    def list_transactions(self):
        with self.connect() as c: rows=c.execute("SELECT * FROM transactions ORDER BY date,transaction_id").fetchall()
        return [Transaction(**dict(r)) for r in rows]
    def delete_transaction(self, ident:int):
        with self.connect() as c: return c.execute("DELETE FROM transactions WHERE transaction_id=?",(ident,)).rowcount > 0
