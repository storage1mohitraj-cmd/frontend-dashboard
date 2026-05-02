from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
import httpx
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Auth"])

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
# This should match your Vercel redirect URI exactly
REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "https://whiteout-survival.vercel.app/oauth-callback.html")

class CodeExchangeRequest(BaseModel):
    code: str

@router.post("/exchange")
async def exchange_code(request: CodeExchangeRequest):
    """Exchanges Discord OAuth code for an access token."""
    if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="Discord OAuth credentials not configured on bot.")

    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': request.code,
        'redirect_uri': REDIRECT_URI
    }
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    
    async with httpx.AsyncClient() as client:
        r = await client.post('https://discord.com/api/oauth2/token', data=data, headers=headers)
        
        if r.status_code != 200:
            logger.error(f"OAuth exchange failed: {r.text}")
            raise HTTPException(status_code=400, detail="Failed to exchange code")
            
        token_data = r.json()
        
        # Now fetch user profile to verify
        user_headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        user_req = await client.get('https://discord.com/api/users/@me', headers=user_headers)
        
        if user_req.status_code == 200:
            user_data = user_req.json()
            return {
                "token": token_data['access_token'],
                "user": user_data
            }
        
        raise HTTPException(status_code=400, detail="Failed to fetch user data")

@router.get("/me")
async def get_current_user(request: Request):
    """Validates the token and returns the user."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
        
    async with httpx.AsyncClient() as client:
        r = await client.get('https://discord.com/api/users/@me', headers={"Authorization": auth_header})
        if r.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid token")
        return r.json()
