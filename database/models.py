from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Integer, Numeric, String, Text, func
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """Пользователь бота."""
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)          # Telegram user_id
    username = Column(String(64), nullable=True)
    full_name = Column(String(128), nullable=True)
    referral_code = Column(String(16), unique=True, nullable=False)  # его код
    referred_by = Column(BigInteger, ForeignKey("users.id"), nullable=True)  # кто пригласил

    is_banned = Column(Boolean, default=False)
    is_admin = Column(Boolean, default=False)

    trial_used = Column(Boolean, default=False)        # использовал ли триал
    balance = Column(Numeric(10, 2), default=0)        # бонусный баланс (руб)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    subscriptions = relationship("Subscription", back_populates="user", foreign_keys="Subscription.user_id")
    payments = relationship("Payment", back_populates="user")
    referrals = relationship("User", foreign_keys=[referred_by])  # кого пригласил


class Subscription(Base):
    """Подписка пользователя (VPN доступ)."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)

    # Данные из 3X-UI
    xray_uuid = Column(String(64), unique=True, nullable=False)  # UUID клиента в Xray
    vless_link = Column(Text, nullable=True)                      # готовая ссылка для подключения

    plan_key = Column(String(8), nullable=True)        # "1m", "3m", "6m" или "trial"
    is_active = Column(Boolean, default=True)

    started_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    user = relationship("User", back_populates="subscriptions", foreign_keys=[user_id])


class Payment(Base):
    """История платежей."""
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)

    yukassa_id = Column(String(64), unique=True, nullable=True)  # ID платежа в ЮKassa
    plan_key = Column(String(8), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)

    status = Column(String(16), default="pending")     # pending / succeeded / cancelled
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    paid_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="payments")


class ReferralBonus(Base):
    """Начисленные реферальные бонусы."""
    __tablename__ = "referral_bonuses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    referrer_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)  # кто пригласил
    referred_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)  # кого пригласили
    bonus_days = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
