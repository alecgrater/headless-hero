"""Post-It CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from database import get_session
from models.postit import PostIt

router = APIRouter(prefix="/api", tags=["postits"])


class CreatePostItRequest(BaseModel):
    text: str
    rank: int = 50


class UpdatePostItRequest(BaseModel):
    text: str | None = None
    rank: int | None = None


@router.get("/postits")
def list_postits(session: Session = Depends(get_session)) -> list[PostIt]:
    stmt = select(PostIt).order_by(PostIt.rank.desc(), PostIt.created_at.desc())  # type: ignore[union-attr]
    return list(session.exec(stmt).all())


@router.post("/postits", status_code=201)
def create_postit(body: CreatePostItRequest, session: Session = Depends(get_session)) -> PostIt:
    postit = PostIt(text=body.text, rank=body.rank)
    session.add(postit)
    session.commit()
    session.refresh(postit)
    return postit


@router.put("/postits/{postit_id}")
def update_postit(postit_id: str, body: UpdatePostItRequest, session: Session = Depends(get_session)) -> PostIt:
    postit = session.get(PostIt, postit_id)
    if not postit:
        raise HTTPException(status_code=404, detail="Post-It not found")
    if body.text is not None:
        postit.text = body.text
    if body.rank is not None:
        postit.rank = body.rank
    session.add(postit)
    session.commit()
    session.refresh(postit)
    return postit


@router.delete("/postits/{postit_id}", status_code=204)
def delete_postit(postit_id: str, session: Session = Depends(get_session)) -> None:
    postit = session.get(PostIt, postit_id)
    if not postit:
        raise HTTPException(status_code=404, detail="Post-It not found")
    session.delete(postit)
    session.commit()
