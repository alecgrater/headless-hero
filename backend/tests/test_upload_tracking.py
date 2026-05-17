from datetime import datetime, timedelta, timezone

from api.scripts import _build_upload_tracking
from models.publish import PublishRecord
from sqlmodel import Session, SQLModel, create_engine


def test_manual_not_uploaded_overrides_older_real_upload(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    base_time = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add(
            PublishRecord(
                script_id="script-1",
                brand_id="brand-1",
                platform="youtube",
                asset_kind="long_form",
                status="published",
                updated_at=base_time,
            )
        )
        session.add(
            PublishRecord(
                script_id="script-1",
                brand_id="brand-1",
                platform="youtube",
                asset_kind="long_form",
                upload_batch_id="manual",
                status="not_uploaded",
                updated_at=base_time + timedelta(minutes=1),
            )
        )
        session.commit()

        tracking = _build_upload_tracking(session, "script-1")

    assert tracking.longform_youtube is False


def test_newer_real_upload_overrides_manual_not_uploaded(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    base_time = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add(
            PublishRecord(
                script_id="script-1",
                brand_id="brand-1",
                platform="youtube",
                asset_kind="short_form",
                upload_batch_id="manual",
                status="not_uploaded",
                updated_at=base_time,
            )
        )
        session.add(
            PublishRecord(
                script_id="script-1",
                brand_id="brand-1",
                platform="youtube",
                asset_kind="short_form",
                short_index=0,
                status="published",
                updated_at=base_time + timedelta(minutes=1),
            )
        )
        session.commit()

        tracking = _build_upload_tracking(session, "script-1")

    assert tracking.shortform_youtube is True
