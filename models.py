from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    wells_fargo_username = Column(String)
    wells_fargo_encrypted_password = Column(String)
    wells_fargo_access_token = Column(String, nullable=True)
    wells_fargo_refresh_token = Column(String, nullable=True)
    token_expiry = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    cards = relationship("CreditCard", back_populates="user")
    transactions = relationship("Transaction", back_populates="user")

class CreditCard(Base):
    __tablename__ = "credit_cards"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    card_number_last_four = Column(String)
    card_type = Column(String)
    expiration_date = Column(String)
    credit_limit = Column(Float)
    current_balance = Column(Float)
    available_credit = Column(Float)
    wells_fargo_card_id = Column(String, unique=True)
    card_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="cards")
    transactions = relationship("Transaction", back_populates="card")

class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    card_id = Column(Integer, ForeignKey("credit_cards.id"))
    transaction_date = Column(DateTime)
    post_date = Column(DateTime)
    description = Column(String)
    amount = Column(Float)
    category = Column(String)
    merchant = Column(String)
    location = Column(String)
    transaction_type = Column(String)
    wells_fargo_transaction_id = Column(String, unique=True)
    transaction_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="transactions")
    card = relationship("CreditCard", back_populates="transactions")

class SpendingCategory(Base):
    __tablename__ = "spending_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True)
    description = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
