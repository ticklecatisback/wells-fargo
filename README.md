# Credit Card Tracking API

This API provides endpoints to track credit card information using the Wells Fargo API.

## Features

- Get all credit cards associated with an account
- Retrieve transactions for specific cards
- Check card balances
- Rate limiting to prevent abuse
- Secure API key authentication
- CORS support

## Setup

1. Clone this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```
4. Edit `.env` with your Wells Fargo API credentials

## Environment Variables

- `WELLS_FARGO_API_BASE_URL`: Wells Fargo API base URL
- `WELLS_FARGO_CLIENT_ID`: Your Wells Fargo API client ID
- `WELLS_FARGO_CLIENT_SECRET`: Your Wells Fargo API client secret
- `JWT_SECRET_KEY`: Secret key for JWT token generation
- `PORT`: Port to run the application (default: 5000)

## API Endpoints

### Get All Cards
```
GET /api/v1/cards
Header: X-API-Key: your_api_key
```

### Get Card Transactions
```
GET /api/v1/cards/{card_id}/transactions
Header: X-API-Key: your_api_key
Query Parameters:
  - start_date (optional): YYYY-MM-DD
  - end_date (optional): YYYY-MM-DD
```

### Get Card Balance
```
GET /api/v1/cards/{card_id}/balance
Header: X-API-Key: your_api_key
```

## Rate Limits

- 100 requests per day
- 10 requests per minute

## Security

- API key authentication required for all endpoints
- Rate limiting to prevent abuse
- CORS enabled
- Environment variables for sensitive data

## Running the Application

```bash
python app.py
```

The API will be available at `http://localhost:5000`

## Note

You'll need to register for Wells Fargo's API access and obtain the necessary credentials to use this application.
