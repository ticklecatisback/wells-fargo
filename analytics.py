from typing import List, Dict, Any
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy.orm import Session
from models import Transaction, CreditCard
from schemas import SpendingAnalytics, CardAnalytics

def calculate_spending_analytics(transactions: List[Transaction]) -> SpendingAnalytics:
    if not transactions:
        return SpendingAnalytics(
            total_spent=0,
            spending_by_category={},
            spending_by_merchant={},
            daily_spending={},
            average_transaction=0,
            largest_transaction=0,
            most_frequent_merchant=""
        )
    
    df = pd.DataFrame([{
        'amount': t.amount,
        'category': t.category,
        'merchant': t.merchant,
        'date': t.transaction_date.date(),
    } for t in transactions])
    
    total_spent = df['amount'].sum()
    
    # Spending by category
    spending_by_category = df.groupby('category')['amount'].sum().to_dict()
    
    # Spending by merchant
    spending_by_merchant = df.groupby('merchant')['amount'].sum().to_dict()
    
    # Daily spending
    daily_spending = df.groupby('date')['amount'].sum().to_dict()
    
    # Average transaction
    average_transaction = df['amount'].mean()
    
    # Largest transaction
    largest_transaction = df['amount'].max()
    
    # Most frequent merchant
    most_frequent_merchant = df['merchant'].mode().iloc[0] if not df['merchant'].empty else ""
    
    return SpendingAnalytics(
        total_spent=float(total_spent),
        spending_by_category=spending_by_category,
        spending_by_merchant=spending_by_merchant,
        daily_spending=daily_spending,
        average_transaction=float(average_transaction),
        largest_transaction=float(largest_transaction),
        most_frequent_merchant=most_frequent_merchant
    )

def calculate_card_analytics(card: CreditCard, transactions: List[Transaction]) -> CardAnalytics:
    # Calculate basic metrics
    utilization_rate = (card.current_balance / card.credit_limit) * 100 if card.credit_limit > 0 else 0
    
    # Get recent transactions
    recent_transactions = sorted(
        transactions,
        key=lambda x: x.transaction_date,
        reverse=True
    )[:10]  # Last 10 transactions
    
    # Calculate spending trends
    df = pd.DataFrame([{
        'amount': t.amount,
        'category': t.category,
        'date': t.transaction_date,
    } for t in transactions])
    
    spending_trends = {}
    if not df.empty:
        # Monthly spending trend
        monthly_spending = df.set_index('date').resample('M')['amount'].sum()
        spending_trends['monthly'] = monthly_spending.to_dict()
        
        # Category trends
        category_trends = df.groupby(['category', pd.Grouper(key='date', freq='M')])['amount'].sum()
        spending_trends['by_category'] = {
            cat: amounts.to_dict() 
            for cat, amounts in category_trends.groupby(level=0)
        }
    
    return CardAnalytics(
        utilization_rate=float(utilization_rate),
        available_credit=float(card.available_credit),
        total_balance=float(card.current_balance),
        payment_due_date=None,  # Would come from Wells Fargo API
        minimum_payment=None,   # Would come from Wells Fargo API
        recent_transactions=recent_transactions,
        spending_trends=spending_trends
    )

def detect_unusual_transactions(transactions: List[Transaction]) -> List[Transaction]:
    if not transactions:
        return []
    
    df = pd.DataFrame([{
        'amount': t.amount,
        'category': t.category,
        'merchant': t.merchant,
        'date': t.transaction_date,
    } for t in transactions])
    
    # Calculate statistical measures
    mean = df['amount'].mean()
    std = df['amount'].std()
    
    # Flag transactions that are more than 2 standard deviations from the mean
    unusual_amounts = df[abs(df['amount'] - mean) > 2 * std]
    
    # Get the original Transaction objects for unusual transactions
    unusual_transactions = [
        t for t in transactions
        if any((t.amount == amount and t.transaction_date == date)
               for amount, date in zip(unusual_amounts['amount'], unusual_amounts['date']))
    ]
    
    return unusual_transactions

def generate_spending_insights(transactions: List[Transaction]) -> Dict[str, Any]:
    if not transactions:
        return {
            "top_categories": [],
            "spending_patterns": {},
            "recommendations": []
        }
    
    df = pd.DataFrame([{
        'amount': t.amount,
        'category': t.category,
        'merchant': t.merchant,
        'date': t.transaction_date,
    } for t in transactions])
    
    # Top spending categories
    top_categories = df.groupby('category')['amount'].sum().sort_values(ascending=False).head(5)
    
    # Weekly spending patterns
    weekly_patterns = df.set_index('date').resample('W')['amount'].sum()
    
    # Generate recommendations based on spending patterns
    recommendations = []
    
    # Check if any category exceeds 30% of total spending
    category_percentages = df.groupby('category')['amount'].sum() / df['amount'].sum() * 100
    high_spending_categories = category_percentages[category_percentages > 30]
    
    for category, percentage in high_spending_categories.items():
        recommendations.append(
            f"Consider reducing spending in {category} category "
            f"(currently {percentage:.1f}% of total spending)"
        )
    
    # Check for potential savings in frequent merchants
    merchant_spending = df.groupby('merchant')['amount'].agg(['sum', 'count'])
    frequent_merchants = merchant_spending[merchant_spending['count'] > 5]
    
    for merchant, stats in frequent_merchants.iterrows():
        recommendations.append(
            f"You frequently shop at {merchant} "
            f"(${stats['sum']:.2f} total). Consider looking for deals or alternatives."
        )
    
    return {
        "top_categories": [
            {"category": cat, "amount": float(amt)}
            for cat, amt in top_categories.items()
        ],
        "spending_patterns": weekly_patterns.to_dict(),
        "recommendations": recommendations
    }
