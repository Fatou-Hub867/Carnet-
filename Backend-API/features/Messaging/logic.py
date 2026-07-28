"""Patient-doctor messaging: REST + polling, no WebSocket for the V1."""

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.storage import get_file_url
from features.Auth.models import Doctor, DoctorStatus
from features.HealthRecords.models import (
    DocumentAddedBy,
    DocumentSourceType,
    HealthRecordDocument,
)
from features.Messaging.models import Conversation, Message, SenderType


async def authorize_conversation(
    db: AsyncSession, conversation_id: int, user_type: str, user_id: int
) -> Conversation:
    """A participant may only touch a conversation they belong to."""
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    belongs = (user_type == "patient" and conversation.patient_id == user_id) or (
        user_type == "doctor" and conversation.doctor_id == user_id
    )
    if not belongs:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not a participant of this conversation")
    return conversation


async def get_or_create_conversation(db: AsyncSession, patient_id: int, doctor_id: int) -> Conversation:
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None or doctor.status != DoctorStatus.VALIDATED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Doctor not found")

    existing = (
        await db.scalars(
            select(Conversation).where(
                Conversation.patient_id == patient_id, Conversation.doctor_id == doctor_id
            )
        )
    ).first()
    if existing is not None:
        return existing

    conversation = Conversation(patient_id=patient_id, doctor_id=doctor_id)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def list_my_conversations(db: AsyncSession, user_type: str, user_id: int) -> list[Conversation]:
    column = Conversation.patient_id if user_type == "patient" else Conversation.doctor_id
    return list(
        (
            await db.scalars(
                select(Conversation).where(column == user_id).order_by(Conversation.created_at.desc())
            )
        ).all()
    )


async def send_message(
    db: AsyncSession,
    conversation: Conversation,
    sender_type: SenderType,
    content: str | None,
    file_key: str | None,
    filename: str | None,
) -> Message:
    """When a doctor attaches a file, it is also filed in the patient's health
    record (source MESSAGE), per the automatic-save-to-carnet decision. Written
    inline here because this is the only place the original filename is in scope."""
    if not content and file_key is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A message must have text or an attachment")

    message = Message(
        conversation_id=conversation.id,
        sender_type=sender_type,
        content=content,
        file_key=file_key,
    )
    db.add(message)
    await db.flush()  # need message.id to link the health-record document

    if sender_type == SenderType.DOCTOR and file_key is not None:
        db.add(
            HealthRecordDocument(
                patient_id=conversation.patient_id,
                source_type=DocumentSourceType.MESSAGE,
                added_by=DocumentAddedBy.DOCTOR,
                file_key=file_key,
                original_filename=filename or "document",
                message_id=message.id,
                doctor_id=conversation.doctor_id,
            )
        )

    await db.commit()
    await db.refresh(message)
    return message


async def list_conversation_messages(db: AsyncSession, conversation_id: int) -> list[Message]:
    """Polled periodically by the frontend, no server push."""
    return list(
        (
            await db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.sent_at)
            )
        ).all()
    )


async def mark_messages_as_read(db: AsyncSession, conversation_id: int, reader_type: SenderType) -> None:
    """Marks the other party's still-unread messages as read. Triggered when the
    reader fetches the thread (the natural read event in a polling design)."""
    await db.execute(
        update(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.sender_type != reader_type,
            Message.read_at.is_(None),
        )
        .values(read_at=datetime.now(timezone.utc))
    )
    await db.commit()


async def get_message_attachment_url(db: AsyncSession, conversation_id: int, message_id: int) -> str:
    message = await db.get(Message, message_id)
    if message is None or message.conversation_id != conversation_id or message.file_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attachment not found")
    return get_file_url(message.file_key)
