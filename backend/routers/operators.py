from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from shared.schemas import MessageRead, SessionRead

from .. import crud
from ..database import get_db
from ..dependencies import verify_operator_token

router = APIRouter(
    prefix="/operators",
    tags=["operators"],
    dependencies=[Depends(verify_operator_token)],
)


@router.get("/sessions", response_model=List[SessionRead])
def list_active_sessions(db: Session = Depends(get_db)):
    return crud.list_active_sessions(db)


@router.get("/history/{client_id}", response_model=List[MessageRead])
def get_history(client_id: int, db: Session = Depends(get_db)):
    history = crud.list_messages(db, client_id)
    if not history:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History not found")
    return history

