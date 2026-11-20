from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse

from askboard.ask.llm import LLMNotConfiguredError
from askboard.models import (
    AskRecord,
    AskRequest,
    ConfirmRequest,
    Conversation,
    ConversationDetail,
    ConversationUpdate,
    Dataset,
    DatasetPreview,
    Relationship,
    RelationshipUpdate,
    Workspace,
    WorkspaceCreate,
)
from askboard.services.ask import AskService
from askboard.services.conversations import ConversationService
from askboard.services.datasets import DatasetService
from askboard.services.errors import ConflictError, InvalidInputError, NotFoundError, ServiceError
from askboard.services.relationships import RelationshipService
from askboard.services.workspaces import WorkspaceService

_READ_CHUNK = 1024 * 1024

router = APIRouter()


def get_workspaces(request: Request) -> WorkspaceService:
    return request.app.state.workspaces


def get_datasets(request: Request) -> DatasetService:
    return request.app.state.datasets


def get_ask(request: Request) -> AskService:
    return request.app.state.ask


def get_relationships(request: Request) -> RelationshipService:
    return request.app.state.relationships


def get_conversations(request: Request) -> ConversationService:
    return request.app.state.conversations


async def read_limited(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    size = 0
    while chunk := await file.read(_READ_CHUNK):
        size += len(chunk)
        if size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File exceeds the {max_bytes // (1024 * 1024)} MB limit",
            )
        chunks.append(chunk)
    return b"".join(chunks)


# --- workspaces ----------------------------------------------------------------------

@router.post("/workspaces", status_code=status.HTTP_201_CREATED, response_model=Workspace)
async def create_workspace(body: WorkspaceCreate, workspaces: WorkspaceService = Depends(get_workspaces)):
    return await workspaces.create(body.name)


@router.get("/workspaces", response_model=list[Workspace])
async def list_workspaces(workspaces: WorkspaceService = Depends(get_workspaces)):
    return await workspaces.list()


@router.get("/workspaces/{workspace_id}", response_model=Workspace)
async def get_workspace(workspace_id: UUID, workspaces: WorkspaceService = Depends(get_workspaces)):
    return await workspaces.get(workspace_id)


# --- datasets ---------------------------------------------------------------------------

@router.post(
    "/workspaces/{workspace_id}/datasets",
    status_code=status.HTTP_201_CREATED,
    response_model=DatasetPreview,
)
async def upload_dataset(
    workspace_id: UUID,
    file: UploadFile,
    request: Request,
    datasets: DatasetService = Depends(get_datasets),
):
    max_bytes = request.app.state.settings.max_upload_mb * 1024 * 1024
    raw = await read_limited(file, max_bytes)
    return await datasets.create_preview(workspace_id, file.filename or "dataset.csv", raw)


@router.post("/workspaces/{workspace_id}/datasets/{dataset_id}/confirm", response_model=Dataset)
async def confirm_dataset(
    workspace_id: UUID,
    dataset_id: UUID,
    body: ConfirmRequest,
    datasets: DatasetService = Depends(get_datasets),
):
    return await datasets.confirm(workspace_id, dataset_id, body)


@router.get("/workspaces/{workspace_id}/datasets", response_model=list[Dataset])
async def list_datasets(workspace_id: UUID, datasets: DatasetService = Depends(get_datasets)):
    return await datasets.list(workspace_id)


@router.get("/workspaces/{workspace_id}/datasets/{dataset_id}", response_model=Dataset)
async def get_dataset(workspace_id: UUID, dataset_id: UUID, datasets: DatasetService = Depends(get_datasets)):
    return await datasets.get(workspace_id, dataset_id)


# --- relationships -----------------------------------------------------------------------------

@router.get("/workspaces/{workspace_id}/relationships", response_model=list[Relationship])
async def list_relationships(
    workspace_id: UUID,
    workspaces: WorkspaceService = Depends(get_workspaces),
    relationships: RelationshipService = Depends(get_relationships),
):
    await workspaces.get(workspace_id)
    return await relationships.list(workspace_id)


@router.patch("/workspaces/{workspace_id}/relationships/{relationship_id}", response_model=Relationship)
async def update_relationship(
    workspace_id: UUID,
    relationship_id: UUID,
    body: RelationshipUpdate,
    relationships: RelationshipService = Depends(get_relationships),
):
    return await relationships.set_status(workspace_id, relationship_id, body.status)


# --- ask ------------------------------------------------------------------------------------

@router.post("/workspaces/{workspace_id}/ask", response_model=AskRecord)
async def ask(workspace_id: UUID, body: AskRequest, service: AskService = Depends(get_ask)):
    return await service.ask(workspace_id, body.question, body.conversation_id)


@router.get("/workspaces/{workspace_id}/questions", response_model=list[AskRecord])
async def question_history(workspace_id: UUID, service: AskService = Depends(get_ask)):
    return await service.history(workspace_id)


# --- conversations ------------------------------------------------------------------------

@router.get("/workspaces/{workspace_id}/conversations", response_model=list[Conversation])
async def list_conversations(
    workspace_id: UUID,
    workspaces: WorkspaceService = Depends(get_workspaces),
    conversations: ConversationService = Depends(get_conversations),
):
    await workspaces.get(workspace_id)
    return await conversations.list(workspace_id)


@router.get("/workspaces/{workspace_id}/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    workspace_id: UUID, conversation_id: UUID, conversations: ConversationService = Depends(get_conversations)
):
    return await conversations.detail(workspace_id, conversation_id)


@router.patch("/workspaces/{workspace_id}/conversations/{conversation_id}", response_model=Conversation)
async def rename_conversation(
    workspace_id: UUID,
    conversation_id: UUID,
    body: ConversationUpdate,
    conversations: ConversationService = Depends(get_conversations),
):
    return await conversations.rename(workspace_id, conversation_id, body.title)


@router.delete(
    "/workspaces/{workspace_id}/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_conversation(
    workspace_id: UUID, conversation_id: UUID, conversations: ConversationService = Depends(get_conversations)
):
    await conversations.delete(workspace_id, conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- error mapping ---------------------------------------------------------------------------

_STATUS_BY_ERROR: dict[type[ServiceError], int] = {
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    InvalidInputError: status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def handle_service_error(_: Request, exc: ServiceError):
        code = next(
            (c for cls, c in _STATUS_BY_ERROR.items() if isinstance(exc, cls)),
            status.HTTP_400_BAD_REQUEST,
        )
        return JSONResponse(status_code=code, content={"detail": str(exc)})

    @app.exception_handler(LLMNotConfiguredError)
    async def handle_llm_not_configured(_: Request, exc: LLMNotConfiguredError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": f"The question service is not configured: {exc}"},
        )
