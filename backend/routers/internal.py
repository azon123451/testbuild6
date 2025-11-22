from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from shared.schemas import MessageCreate, MessageRead

from .. import crud
from ..database import get_db
from ..dependencies import verify_bot_token

router = APIRouter(prefix="/internal", tags=["internal"], dependencies=[Depends(verify_bot_token)])


@router.post("/messages", response_model=MessageRead)
def log_message(payload: MessageCreate, db: Session = Depends(get_db)):
    """
    Called by the Telegram bot to persist chat history.
    """
    return crud.create_message(db, payload)


@router.post("/sessions/{client_id}/close")
def close_session(client_id: int, db: Session = Depends(get_db)):
    crud.close_session(db, client_id=client_id)
    return {"status": "closed"}

