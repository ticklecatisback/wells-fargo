from fastapi import FastAPI, HTTPException, Depends, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv
import requests
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

from database import get_db, engine, Base
from models import User, CreditCard, Transaction
from schemas import (
    UserCreate, UserLogin, WellsFargoLogin, Token,
    CardBase, CardCreate, CardInDB,
    TransactionBase, TransactionCreate, TransactionInDB,
    SpendingAnalytics, CardAnalytics, UserProfile
)
from security import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, authenticate_user,
    encrypt_wells_fargo_password, decrypt_wells_fargo_password
)
from analytics import (
    calculate_spending_analytics, calculate_card_analytics,
    detect_unusual_transactions, generate_spending_insights
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="Credit Card Tracking API",
    description="API for tracking credit cards using Wells Fargo API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

# Wells Fargo API configuration
class WellsFargoAPI:
    BASE_URL = os.getenv("WELLS_FARGO_API_BASE_URL")
    
    @staticmethod
    async def login(username: str, password: str) -> dict:
        """Login to Wells Fargo and get access token"""
        try:
            url = f"{WellsFargoAPI.BASE_URL}/login"
            response = requests.post(url, json={
                "username": username,
                "password": password
            })
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Wells Fargo login error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to authenticate with Wells Fargo"
            )

    @staticmethod
    async def get_credit_cards(access_token: str) -> List[dict]:
        """Get all credit cards from Wells Fargo"""
        try:
            url = f"{WellsFargoAPI.BASE_URL}/credit-cards"
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting credit cards: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve credit cards"
            )

    @staticmethod
    async def get_card_transactions(
        access_token: str,
        card_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[dict]:
        """Get transactions for a specific card"""
        try:
            url = f"{WellsFargoAPI.BASE_URL}/credit-cards/{card_id}/transactions"
            headers = {"Authorization": f"Bearer {access_token}"}
            params = {}
            if start_date:
                params["startDate"] = start_date.isoformat()
            if end_date:
                params["endDate"] = end_date.isoformat()
            
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting transactions: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve transactions"
            )

# Authentication endpoints
@app.post("/api/v1/auth/register", response_model=Token)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if user exists
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    db_user = User(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        wells_fargo_username=user.wells_fargo_username,
        wells_fargo_encrypted_password=encrypt_wells_fargo_password(user.wells_fargo_password)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Create access token
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=30)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/v1/auth/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """Login user"""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": user.email},
        expires_delta=timedelta(minutes=30)
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/api/v1/auth/wells-fargo-login")
async def wells_fargo_login(
    login_data: WellsFargoLogin,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Login to Wells Fargo and update user's access token"""
    try:
        # Login to Wells Fargo
        wf_auth = await WellsFargoAPI.login(
            login_data.username,
            login_data.password
        )
        
        # Update user's Wells Fargo credentials
        current_user.wells_fargo_access_token = wf_auth["access_token"]
        current_user.wells_fargo_refresh_token = wf_auth.get("refresh_token")
        current_user.token_expiry = datetime.utcnow() + timedelta(
            seconds=wf_auth.get("expires_in", 3600)
        )
        
        db.commit()
        return {"message": "Successfully logged in to Wells Fargo"}
    except Exception as e:
        logger.error(f"Wells Fargo login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to login to Wells Fargo"
        )

# Card endpoints
@app.get("/api/v1/cards", response_model=List[CardInDB])
async def get_cards(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all credit cards for the current user"""
    return db.query(CreditCard).filter(CreditCard.user_id == current_user.id).all()

@app.get("/api/v1/cards/{card_id}", response_model=CardInDB)
async def get_card(
    card_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific credit card"""
    card = db.query(CreditCard).filter(
        CreditCard.id == card_id,
        CreditCard.user_id == current_user.id
    ).first()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    return card

@app.get("/api/v1/cards/{card_id}/transactions", response_model=List[TransactionInDB])
async def get_card_transactions(
    card_id: int,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get transactions for a specific card"""
    # Verify card belongs to user
    card = db.query(CreditCard).filter(
        CreditCard.id == card_id,
        CreditCard.user_id == current_user.id
    ).first()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    # Get transactions from Wells Fargo
    transactions = await WellsFargoAPI.get_card_transactions(
        current_user.wells_fargo_access_token,
        card.wells_fargo_card_id,
        start_date,
        end_date
    )
    
    # Save transactions to database
    db_transactions = []
    for t in transactions:
        db_transaction = Transaction(
            user_id=current_user.id,
            card_id=card_id,
            wells_fargo_transaction_id=t["id"],
            amount=t["amount"],
            description=t["description"],
            transaction_date=datetime.fromisoformat(t["transactionDate"]),
            post_date=datetime.fromisoformat(t["postDate"]) if "postDate" in t else None,
            category=t.get("category"),
            merchant=t.get("merchant"),
            location=t.get("location"),
            transaction_type=t.get("type"),
            transaction_metadata=t
        )
        db.add(db_transaction)
        db_transactions.append(db_transaction)
    
    db.commit()
    return db_transactions

# Analytics endpoints
@app.get("/api/v1/analytics/spending", response_model=SpendingAnalytics)
async def get_spending_analytics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get spending analytics for the current user"""
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)
    if start_date:
        query = query.filter(Transaction.transaction_date >= start_date)
    if end_date:
        query = query.filter(Transaction.transaction_date <= end_date)
    
    transactions = query.all()
    return calculate_spending_analytics(transactions)

@app.get("/api/v1/analytics/cards/{card_id}", response_model=CardAnalytics)
async def get_card_analytics(
    card_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get analytics for a specific card"""
    card = db.query(CreditCard).filter(
        CreditCard.id == card_id,
        CreditCard.user_id == current_user.id
    ).first()
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Card not found"
        )
    
    transactions = db.query(Transaction).filter(
        Transaction.card_id == card_id
    ).all()
    
    return calculate_card_analytics(card, transactions)

@app.get("/api/v1/analytics/unusual-transactions")
async def get_unusual_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get unusual transactions for the current user"""
    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id
    ).all()
    
    unusual = detect_unusual_transactions(transactions)
    return {"unusual_transactions": unusual}

@app.get("/api/v1/analytics/insights")
async def get_spending_insights(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get spending insights and recommendations"""
    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id
    ).all()
    
    return generate_spending_insights(transactions)

@app.get("/api/v1/profile", response_model=UserProfile)
async def get_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user profile with cards and spending summary"""
    cards = db.query(CreditCard).filter(
        CreditCard.user_id == current_user.id
    ).all()
    
    transactions = db.query(Transaction).filter(
        Transaction.user_id == current_user.id
    ).all()
    
    total_credit_limit = sum(card.credit_limit for card in cards)
    total_balance = sum(card.current_balance for card in cards)
    
    spending_summary = calculate_spending_analytics(transactions)
    
    return UserProfile(
        email=current_user.email,
        total_credit_limit=total_credit_limit,
        total_balance=total_balance,
        number_of_cards=len(cards),
        spending_summary=spending_summary,
        cards=cards
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
