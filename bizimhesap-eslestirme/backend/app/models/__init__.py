from datetime import date, datetime
from sqlalchemy import (String, Integer, Date, DateTime, ForeignKey, Boolean, Text,
                        CheckConstraint, UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base

class BankAccount(Base):
    __tablename__ = "bank_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    iban: Mapped[str] = mapped_column(String(34), unique=True)
    currency: Mapped[str] = mapped_column(String(3))
    transactions = relationship("BankTransaction", back_populates="account")
    __table_args__ = (CheckConstraint("currency IN ('TRY','USD','EUR')"),)

class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    tax_no: Mapped[str | None] = mapped_column(String(20))

class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    tax_no: Mapped[str | None] = mapped_column(String(20))

class BankTransaction(Base):
    __tablename__ = "bank_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("bank_accounts.id"))
    tx_date: Mapped[date] = mapped_column(Date)
    direction: Mapped[str] = mapped_column(String(3))      # IN / OUT (açık işlem yönü)
    category: Mapped[str] = mapped_column(String(10), default="PAYMENT")  # PAYMENT/TRANSFER/FEE/LOAN/OTHER
    description: Mapped[str] = mapped_column(Text, default="")
    amount_kurus: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    dedup_key: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="UNMATCHED")
    account = relationship("BankAccount", back_populates="transactions")
    __table_args__ = (CheckConstraint("direction IN ('IN','OUT')"),
                      CheckConstraint("amount_kurus > 0"))

class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    invoice_no: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(5))  # SALE / PURCH
    doc_type: Mapped[str] = mapped_column(String(20), default="Faturalaşmış")
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"))
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    total_kurus: Mapped[int] = mapped_column(Integer)
    paid_kurus: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(3))
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)
    customer = relationship("Customer")
    supplier = relationship("Supplier")
    __table_args__ = (UniqueConstraint("invoice_no", "kind"),
                      CheckConstraint("kind IN ('SALE','PURCH')"),
                      CheckConstraint("paid_kurus >= 0 AND paid_kurus <= total_kurus"))

    @property
    def remaining_kurus(self) -> int:
        return self.total_kurus - self.paid_kurus

    @property
    def payment_status(self) -> str:
        if self.cancelled: return "İptal Edildi"
        if self.paid_kurus == 0: return "Ödenmedi"
        if self.paid_kurus < self.total_kurus: return "Kısmen Ödendi"
        return "Ödendi"

    @property
    def party_name(self) -> str:
        p = self.customer if self.kind == "SALE" else self.supplier
        return p.name if p else ""

class ReconciliationMatch(Base):
    __tablename__ = "reconciliation_matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("bank_transactions.id"))
    score: Mapped[int] = mapped_column(Integer, default=0)
    reasons: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(12), default="SUGGESTED")  # SUGGESTED/APPROVED/REJECTED/UNDONE
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime)
    allocations = relationship("ReconciliationAllocation", back_populates="match")

class ReconciliationAllocation(Base):
    __tablename__ = "reconciliation_allocations"
    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("reconciliation_matches.id"))
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"))
    amount_kurus: Mapped[int] = mapped_column(Integer)
    match = relationship("ReconciliationMatch", back_populates="allocations")
    __table_args__ = (UniqueConstraint("match_id", "invoice_id"),
                      CheckConstraint("amount_kurus > 0"))

class AutomationSettings(Base):
    __tablename__ = "automation_settings"
    id: Mapped[int] = mapped_column(primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    min_score: Mapped[int] = mapped_column(Integer, default=60)
    auto_approve: Mapped[bool] = mapped_column(Boolean, default=False)
    date_tolerance_days: Mapped[int] = mapped_column(Integer, default=30)
    w_amount: Mapped[int] = mapped_column(Integer, default=40)
    w_name: Mapped[int] = mapped_column(Integer, default=25)
    w_invoice_no: Mapped[int] = mapped_column(Integer, default=25)
    w_date: Mapped[int] = mapped_column(Integer, default=10)

class AutomationLog(Base):
    __tablename__ = "automation_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    trigger: Mapped[str] = mapped_column(String(12))
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    action: Mapped[str] = mapped_column(String(30))
    entity: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[str] = mapped_column(Text, default="")
