from jev_mcp.cache.sqlite import SqliteCache


def test_sqlite_files_are_owner_only(tmp_path):
    path = tmp_path / "cache.sqlite"
    cache = SqliteCache(path, ttl_seconds=60, max_entries=10)
    mode = path.stat().st_mode & 0o777
    assert mode == 0o600
    dir_mode = path.parent.stat().st_mode & 0o777
    assert dir_mode == 0o700
    cache._conn.close()
