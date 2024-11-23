from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, date

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    wells_fargo_username: str
    wells_fargo_password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class WellsFargoLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class CardBase(BaseModel):
    card_number_last_four: str
    card_type: str
    expiration_date: str

class CardCreate(CardBase):
    wells_fargo_card_id: str
    credit_limit: float
    current_balance: float
    available_credit: float
    card_metadata: Dict[str, Any] = {}

class CardInDB(CardBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class TransactionBase(BaseModel):
    description: str
    amount: float
    transaction_date: datetime
    category: Optional[str] = None
    merchant: Optional[str] = None
    location: Optional[str] = None

class TransactionCreate(TransactionBase):
    wells_fargo_transaction_id: str
    card_id: int
    post_date: Optional[datetime] = None
    transaction_type: str
    transaction_metadata: Dict[str, Any] = {}

class TransactionInDB(TransactionBase):
    id: int
    user_id: int
    card_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class SpendingAnalytics(BaseModel):
    total_spent: float
    spending_by_category: Dict[str, float]
    spending_by_merchant: Dict[str, float]
    daily_spending: Dict[date, float]
    average_transaction: float
    largest_transaction: float
    most_frequent_merchant: str

class CardAnalytics(BaseModel):
    utilization_rate: float
    available_credit: float
    total_balance: float
    payment_due_date: Optional[date]
    minimum_payment: Optional[float]
    recent_transactions: List[TransactionBase]
    spending_trends: Dict[str, Any]

class UserProfile(BaseModel):
    email: str
    total_credit_limit: float
    total_balance: float
    number_of_cards: int
    spending_summary: SpendingAnalytics
    cards: List[CardInDB]

    class Config:
        from_attributes = True
