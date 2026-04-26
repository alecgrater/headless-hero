"""Post-It CRUD endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlmodel import Session, func, select

from database import get_session
from models.postit import VALID_SOURCES, VALID_STATUSES, PostIt

router = APIRouter(prefix="/api", tags=["postits"])


class CreatePostItRequest(BaseModel):
    text: str
    rank: int = 50
    source: str = "manual"

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in VALID_SOURCES:
            raise ValueError(f"source must be one of {VALID_SOURCES}")
        return v


class UpdatePostItRequest(BaseModel):
    text: str | None = None
    rank: int | None = None
    status: str | None = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


@router.get("/postits")
def list_postits(session: Session = Depends(get_session)) -> list[PostIt]:
    stmt = select(PostIt).order_by(PostIt.rank.desc(), PostIt.created_at.desc())  # type: ignore[union-attr]
    return list(session.exec(stmt).all())


@router.post("/postits", status_code=201)
def create_postit(body: CreatePostItRequest, session: Session = Depends(get_session)) -> PostIt:
    postit = PostIt(text=body.text, rank=body.rank, source=body.source)
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
    if body.status is not None:
        postit.status = body.status
    session.add(postit)
    session.commit()
    session.refresh(postit)
    return postit


@router.get("/postits/counts")
def postit_counts(session: Session = Depends(get_session)) -> dict[str, int]:
    rows = session.exec(
        select(PostIt.status, func.count()).group_by(PostIt.status)
    ).all()
    counts = {s: 0 for s in VALID_STATUSES}
    for status, count in rows:
        counts[status] = count
    return counts


@router.delete("/postits/{postit_id}", status_code=204)
def delete_postit(postit_id: str, session: Session = Depends(get_session)) -> None:
    postit = session.get(PostIt, postit_id)
    if not postit:
        raise HTTPException(status_code=404, detail="Post-It not found")
    session.delete(postit)
    session.commit()
