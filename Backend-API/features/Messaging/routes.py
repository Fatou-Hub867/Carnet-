from fastapi import APIRouter, Depends, Form, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.deps import get_current_participant, get_current_patient
from core.storage import upload_file
from features.Auth.models import Patient
from features.Messaging import logic
from features.Messaging.models import SenderType
from features.Messaging.schemas import ConversationCreateRequest, ConversationOut, MessageOut

router = APIRouter(prefix="/messaging", tags=["messaging"])


@router.post("/conversations", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    data: ConversationCreateRequest,
    current_patient: Patient = Depends(get_current_patient),
    db: AsyncSession = Depends(get_db),
):
    # Only the patient initiates a conversation (they pick the doctor to contact).
    return await logic.get_or_create_conversation(db, current_patient.id, data.doctor_id)


@router.get("/conversations", response_model=list[ConversationOut])
async def list_my_conversations(
    participant: tuple[str, int] = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    user_type, user_id = participant
    return await logic.list_my_conversations(db, user_type, user_id)


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
async def list_conversation_messages(
    conversation_id: int,
    participant: tuple[str, int] = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    """Polled periodically by the frontend, no server push."""
    user_type, user_id = participant
    await logic.authorize_conversation(db, conversation_id, user_type, user_id)
    # Fetching the thread is what marks the other party's messages as read.
    await logic.mark_messages_as_read(db, conversation_id, SenderType(user_type))
    return await logic.list_conversation_messages(db, conversation_id)


@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: int,
    content: str | None = Form(default=None),
    file: UploadFile | None = None,
    participant: tuple[str, int] = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    user_type, user_id = participant
    conversation = await logic.authorize_conversation(db, conversation_id, user_type, user_id)

    file_key = None
    filename = None
    if file is not None:
        file_key = upload_file(await file.read(), file.filename, file.content_type)
        filename = file.filename

    return await logic.send_message(
        db, conversation, SenderType(user_type), content, file_key, filename
    )


@router.get("/conversations/{conversation_id}/messages/{message_id}/attachment")
async def download_attachment(
    conversation_id: int,
    message_id: int,
    participant: tuple[str, int] = Depends(get_current_participant),
    db: AsyncSession = Depends(get_db),
):
    user_type, user_id = participant
    await logic.authorize_conversation(db, conversation_id, user_type, user_id)
    url = await logic.get_message_attachment_url(db, conversation_id, message_id)
    return {"download_url": url}
