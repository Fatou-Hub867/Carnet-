from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from features.Messaging.models import SenderType


class ConversationCreateRequest(BaseModel):
    doctor_id: int


class ConversationOut(BaseModel):
    id: int
    patient_id: int
    patient_name: str
    patient_photo_url: str | None
    doctor_id: int
    doctor_name: str
    doctor_photo_url: str | None
    created_at: datetime
    unread_count: int

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender_type: SenderType
    content: str | None
    file_key: str | None
    sent_at: datetime
    read_at: datetime | None

    model_config = {"from_attributes": True}
