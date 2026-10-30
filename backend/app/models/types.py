from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy.dialects.mysql import BIGINT, DATETIME

# BIGINT UNSIGNED on MariaDB; INTEGER on SQLite so AUTOINCREMENT works in tests.
BigIntPK = BigInteger().with_variant(BIGINT(unsigned=True), "mysql").with_variant(Integer, "sqlite")

# Millisecond precision on MariaDB (plain DATETIME truncates to seconds).
Timestamp = DateTime().with_variant(DATETIME(fsp=3), "mysql")
