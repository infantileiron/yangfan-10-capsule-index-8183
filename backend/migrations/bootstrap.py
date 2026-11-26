"""Initial schema for a fresh Compose volume."""
from src.models.account import Account
from src.models.audit import Event
from src.models.calibration import Calibration
from src.models.dataset import Dataset
from src.models.review import Review
from src.models.run import Run

SCHEMA = (Account, Dataset, Calibration, Run, Review, Event)


def migrate(engine):
    tables = [model.__table__ for model in SCHEMA]
    Account.metadata.create_all(engine, tables=tables)
    _ensure_columns(engine)


def _ensure_columns(engine):
    """Add columns introduced after the initial volume snapshot.

    ``create_all`` creates missing tables but does not alter existing ones.
    The application's deployment model uses persistent MySQL volumes, so keep
    this small, idempotent SQLite/MySQL-compatible migration for new columns.
    """
    inspector = __import__("sqlalchemy").inspect(engine)
    existing_tables = set(inspector.get_table_names())
    statements = []
    if "datasets" in existing_tables:
        columns = {column["name"] for column in inspector.get_columns("datasets")}
        if "parent_id" not in columns:
            statements.append("ALTER TABLE datasets ADD COLUMN parent_id VARCHAR(36) NULL")
        if "correction" not in columns:
            json_type = "JSON" if engine.dialect.name == "mysql" else "JSON"
            statements.append(f"ALTER TABLE datasets ADD COLUMN correction {json_type} NULL")
    if "runs" in existing_tables:
        columns = {column["name"] for column in inspector.get_columns("runs")}
        if "hold_reason" not in columns:
            statements.append("ALTER TABLE runs ADD COLUMN hold_reason TEXT NULL")
        if "held_queue" not in columns:
            statements.append("ALTER TABLE runs ADD COLUMN held_queue JSON NULL")
        if "line_versions" not in columns:
            statements.append("ALTER TABLE runs ADD COLUMN line_versions JSON NULL")
    if not statements:
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
