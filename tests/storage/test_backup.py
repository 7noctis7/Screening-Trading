import sqlite3, tempfile, os
from packages.storage.backup import backup_sqlite, restore_sqlite


def test_backup_then_restore_preserves_data():
    d = tempfile.mkdtemp()
    src = os.path.join(d, "src.db")
    con = sqlite3.connect(src)
    con.execute("CREATE TABLE t(x)"); con.execute("INSERT INTO t VALUES (42)")
    con.commit(); con.close()
    bak = backup_sqlite(src, os.path.join(d, "bak.db"))
    tgt = restore_sqlite(bak, os.path.join(d, "restored.db"))
    con = sqlite3.connect(str(tgt))
    assert con.execute("SELECT x FROM t").fetchone()[0] == 42
    con.close()
