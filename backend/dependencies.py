from fastapi import Depends, Header, HTTPException, status

from .config import get_settings


def verify_bot_token(x_bot_token: str = Header(..., alias="X-Bot-Token")):
    settings = get_settings()
    if x_bot_token != settings.bot_api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bot token")


def verify_operator_token(x_operator_token: str = Header(..., alias="X-Operator-Token")):
    settings = get_settings()
    if x_operator_token != settings.operator_history_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid operator token")

