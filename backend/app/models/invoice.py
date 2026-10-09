from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Identity,
    Index, Integer, MetaData, Numeric, SmallInteger, String, Text,
    UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.schema import FetchedValue


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "pk": "pk_%(table_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
    })


class Dealer(Base):
    __tablename__ = "dealers"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dealer_code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    gstin: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    documents: Mapped[list[InboundDocument]] = relationship(back_populates="dealer")


class DmsSystem(Base):
    __tablename__ = "dms_systems"
    __table_args__ = (CheckConstraint("integration_tier IN (1, 2, 3)", name="integration_tier"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    integration_tier: Mapped[int] = mapped_column(SmallInteger)
    integration_method: Mapped[str] = mapped_column(String(20))
    input_format: Mapped[str] = mapped_column(String(20))

    documents: Mapped[list[InboundDocument]] = relationship(back_populates="dms")
    mapping_configs: Mapped[list[MappingConfig]] = relationship(back_populates="dms")


class InboundDocument(Base):
    __tablename__ = "inbound_documents"
    __table_args__ = (
        CheckConstraint("status IN ('RECEIVED', 'PROCESSING', 'COMPLETED', 'REVIEW_REQUIRED', 'FAILED')", name="status"),
        CheckConstraint("file_size_bytes >= 0", name="file_size"),
        Index("ix_inbound_documents_dealer_received", "dealer_id", "received_at"),
        Index("ix_inbound_documents_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dealer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dealers.id"))
    dms_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dms_systems.id"))
    document_type: Mapped[str] = mapped_column(String(30), server_default="INVOICE")
    original_file_name: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    storage_key: Mapped[str | None] = mapped_column(Text)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64))
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(30), server_default="RECEIVED")
    error_message: Mapped[str | None] = mapped_column(Text)

    dealer: Mapped[Dealer] = relationship(back_populates="documents")
    dms: Mapped[DmsSystem] = relationship(back_populates="documents")
    invoice: Mapped[StandardizedInvoice | None] = relationship(back_populates="document")


class MappingConfig(Base):
    __tablename__ = "mapping_configs"
    __table_args__ = (
        CheckConstraint(
            "(mapping_direction = 'SOURCE_TO_CANONICAL' AND dms_id IS NOT NULL AND target_system IS NULL) "
            "OR (mapping_direction = 'CANONICAL_TO_OEM' AND dms_id IS NULL AND target_system IS NOT NULL)",
            name="direction_owner",
        ),
        CheckConstraint("version > 0", name="version"),
        Index("uq_mapping_configs_inbound_version", "dms_id", "document_type", "version", unique=True,
              postgresql_where=text("mapping_direction = 'SOURCE_TO_CANONICAL'")),
        Index("uq_mapping_configs_outbound_version", "target_system", "document_type", "version", unique=True,
              postgresql_where=text("mapping_direction = 'CANONICAL_TO_OEM'")),
        Index("uq_mapping_configs_active_inbound", "dms_id", "document_type", unique=True,
              postgresql_where=text("is_active AND mapping_direction = 'SOURCE_TO_CANONICAL'")),
        Index("uq_mapping_configs_active_outbound", "target_system", "document_type", unique=True,
              postgresql_where=text("is_active AND mapping_direction = 'CANONICAL_TO_OEM'")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    mapping_name: Mapped[str] = mapped_column(String(150))
    mapping_direction: Mapped[str] = mapped_column(String(30))
    dms_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dms_systems.id"))
    target_system: Mapped[str | None] = mapped_column(String(100))
    document_type: Mapped[str] = mapped_column(String(30), server_default="INVOICE")
    mapping_config: Mapped[dict] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    dms: Mapped[DmsSystem | None] = relationship(back_populates="mapping_configs")


class ValidationRule(Base):
    __tablename__ = "validation_rules"
    __table_args__ = (CheckConstraint("severity IN ('ERROR', 'WARNING')", name="severity"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    rule_code: Mapped[str] = mapped_column(String(80), unique=True)
    rule_name: Mapped[str] = mapped_column(String(200))
    document_type: Mapped[str] = mapped_column(String(30), server_default="INVOICE")
    rule_config: Mapped[dict] = mapped_column(JSONB)
    severity: Mapped[str] = mapped_column(String(20))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StandardizedInvoice(Base):
    __tablename__ = "standardized_invoices"
    __table_args__ = (
        CheckConstraint("validation_status IN ('PENDING', 'VALID', 'INVALID', 'REVIEW_REQUIRED')", name="validation_status"),
        CheckConstraint("review_status IN ('NOT_REQUIRED', 'PENDING', 'APPROVED', 'REJECTED')", name="review_status"),
        CheckConstraint("oem_delivery_status IN ('NOT_SENT', 'SENT', 'FAILED')", name="oem_delivery_status"),
        Index("ix_standardized_invoices_number_validation", "invoice_number", "validation_status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("inbound_documents.id"), unique=True)
    invoice_number: Mapped[str] = mapped_column(String(100))
    invoice_date: Mapped[date] = mapped_column(Date)
    buyer_oem_id: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    canonical_payload: Mapped[dict] = mapped_column(JSONB)
    validation_status: Mapped[str] = mapped_column(String(30), server_default="PENDING")
    review_status: Mapped[str] = mapped_column(String(30), server_default="NOT_REQUIRED")
    oem_delivery_status: Mapped[str] = mapped_column(String(30), server_default="NOT_SENT")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), server_onupdate=FetchedValue(),
    )

    document: Mapped[InboundDocument] = relationship(back_populates="invoice")
    line_items: Mapped[list[InvoiceLineItem]] = relationship(back_populates="invoice")


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"
    __table_args__ = (
        UniqueConstraint("invoice_id", "line_number", name="uq_invoice_line_items_invoice_line"),
        CheckConstraint("line_number > 0", name="line_number"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    invoice_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("standardized_invoices.id"))
    line_number: Mapped[int] = mapped_column()
    item_code: Mapped[str | None] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), server_default="0")
    taxable_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    chassis_number: Mapped[str | None] = mapped_column(String(50))

    invoice: Mapped[StandardizedInvoice] = relationship(back_populates="line_items")