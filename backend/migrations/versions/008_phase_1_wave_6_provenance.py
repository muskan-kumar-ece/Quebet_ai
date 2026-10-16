"""Phase 1 Wave 6: Engineering Knowledge, Evidence & Traceability

Revision ID: 008_phase_1_wave_6_provenance
Revises: 007_phase_1_wave_5_verification
Create Date: 2026-10-02 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "008_phase_1_wave_6_provenance"
down_revision: Union[str, None] = "007_phase_1_wave_5_verification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. engineering_sources
    op.create_table(
        "engineering_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("source_type", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("publisher", sa.String(255), nullable=False),
        sa.Column("document_identifier", sa.String(128), nullable=False),
        sa.Column("revision", sa.String(64), server_default="Rev A", nullable=False),
        sa.Column("version", sa.String(32), server_default="1.0", nullable=False),
        sa.Column("publication_date", sa.String(64), nullable=True),
        sa.Column("effective_date", sa.String(64), nullable=True),
        sa.Column("uri", sa.String(512), nullable=True),
        sa.Column("document_hash", sa.String(64), nullable=True),
        sa.Column("trust_level", sa.String(64), server_default="UNVERIFIED", nullable=False),
        sa.Column("status", sa.String(32), server_default="CURRENT", nullable=False),
        sa.Column("supersedes_source_id", sa.String(36), sa.ForeignKey("engineering_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_sources_tenant_id", "engineering_sources", ["tenant_id"])
    op.create_index("ix_engineering_sources_document_identifier", "engineering_sources", ["document_identifier"])

    # 2. engineering_knowledge_records
    op.create_table(
        "engineering_knowledge_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("source_id", sa.String(36), sa.ForeignKey("engineering_sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("domain", sa.String(64), server_default="SEMICONDUCTOR", nullable=False),
        sa.Column("subject_type", sa.String(64), server_default="COMPONENT", nullable=False),
        sa.Column("subject_identifier", sa.String(128), nullable=False),
        sa.Column("parameter", sa.String(128), nullable=False),
        sa.Column("value", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("valid_range", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(32), server_default="VERIFIED", nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("supersedes_knowledge_id", sa.String(36), sa.ForeignKey("engineering_knowledge_records.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_knowledge_records_tenant_id", "engineering_knowledge_records", ["tenant_id"])
    op.create_index("ix_engineering_knowledge_records_source_id", "engineering_knowledge_records", ["source_id"])
    op.create_index("ix_engineering_knowledge_records_subject_identifier", "engineering_knowledge_records", ["subject_identifier"])
    op.create_index("ix_engineering_knowledge_records_parameter", "engineering_knowledge_records", ["parameter"])

    # 3. engineering_knowledge_snapshots
    op.create_table(
        "engineering_knowledge_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("snapshot_hash", sa.String(64), nullable=False),
        sa.Column("knowledge_record_ids", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_knowledge_snapshots_tenant_id", "engineering_knowledge_snapshots", ["tenant_id"])
    op.create_index("ix_engineering_knowledge_snapshots_snapshot_hash", "engineering_knowledge_snapshots", ["snapshot_hash"])

    # 4. engineering_analysis_provenances
    op.create_table(
        "engineering_analysis_provenances",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("analysis_id", sa.String(36), sa.ForeignKey("circuit_analyses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("circuit_id", sa.String(36), sa.ForeignKey("circuits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("circuit_revision", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("engine_versions", sa.JSON(), nullable=False),
        sa.Column("rule_set_version", sa.String(64), nullable=False),
        sa.Column("knowledge_snapshot_id", sa.String(36), sa.ForeignKey("engineering_knowledge_snapshots.id", ondelete="SET NULL"), nullable=True),
        sa.Column("input_values", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("calculation_methods", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_engineering_analysis_provenances_analysis_id", "engineering_analysis_provenances", ["analysis_id"], unique=True)
    op.create_index("ix_engineering_analysis_provenances_circuit_id", "engineering_analysis_provenances", ["circuit_id"])
    op.create_index("ix_engineering_analysis_provenances_tenant_id", "engineering_analysis_provenances", ["tenant_id"])

    # 5. Extend engineering_evidence
    op.add_column("engineering_evidence", sa.Column("source_id", sa.String(36), nullable=True))
    op.add_column("engineering_evidence", sa.Column("instrument", sa.String(128), nullable=True))
    op.add_column("engineering_evidence", sa.Column("instrument_model", sa.String(128), nullable=True))
    op.add_column("engineering_evidence", sa.Column("instrument_serial", sa.String(128), nullable=True))
    op.add_column("engineering_evidence", sa.Column("calibration_reference", sa.String(128), nullable=True))
    op.add_column("engineering_evidence", sa.Column("calibration_status", sa.String(32), server_default="UNKNOWN", nullable=False))
    op.add_column("engineering_evidence", sa.Column("measurement_timestamp", sa.DateTime(timezone=True), nullable=True))
    op.add_column("engineering_evidence", sa.Column("circuit_id", sa.String(36), nullable=True))
    op.add_column("engineering_evidence", sa.Column("circuit_revision", sa.Integer(), nullable=True))
    op.add_column("engineering_evidence", sa.Column("analysis_id", sa.String(36), nullable=True))
    op.add_column("engineering_evidence", sa.Column("is_stale", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.create_index("ix_engineering_evidence_source_id", "engineering_evidence", ["source_id"])
    op.create_index("ix_engineering_evidence_circuit_id", "engineering_evidence", ["circuit_id"])


def downgrade() -> None:
    op.drop_index("ix_engineering_evidence_circuit_id", table_name="engineering_evidence")
    op.drop_index("ix_engineering_evidence_source_id", table_name="engineering_evidence")
    op.drop_column("engineering_evidence", "is_stale")
    op.drop_column("engineering_evidence", "analysis_id")
    op.drop_column("engineering_evidence", "circuit_revision")
    op.drop_column("engineering_evidence", "circuit_id")
    op.drop_column("engineering_evidence", "measurement_timestamp")
    op.drop_column("engineering_evidence", "calibration_status")
    op.drop_column("engineering_evidence", "calibration_reference")
    op.drop_column("engineering_evidence", "instrument_serial")
    op.drop_column("engineering_evidence", "instrument_model")
    op.drop_column("engineering_evidence", "instrument")
    op.drop_column("engineering_evidence", "source_id")

    op.drop_table("engineering_analysis_provenances")
    op.drop_table("engineering_knowledge_snapshots")
    op.drop_table("engineering_knowledge_records")
    op.drop_table("engineering_sources")
