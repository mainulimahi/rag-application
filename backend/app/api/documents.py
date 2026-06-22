"""Document management endpoints.

Routes:
  POST /api/documents/upload         — multipart file upload; processing runs in background
  GET  /api/documents                — list current user's documents (no file bytes)
  GET  /api/documents/{id}/status    — poll processing status
  DELETE /api/documents/{id}         — delete document + cascade chunks; verifies ownership

Accepted formats: PDF, DOCX, DOC, TXT, MD, JSON, XLSX, XLS, CSV (max 20 MB).
DOC and XLS are accepted at upload but will fail processing with a conversion message.
"""

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.document import DocumentListItem, DocumentStatusResponse, DocumentUploadResponse
from app.services import document_service

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document for processing",
)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentUploadResponse:
    """
    Accept a file upload (PDF, DOCX, DOC, TXT, MD, JSON, XLSX, XLS, CSV; max 20 MB)
    and schedule background processing (text extraction → chunking → embedding → storage).

    Returns 202 immediately with status='processing'. Poll
    GET /api/documents/{id}/status until status becomes 'ready' or 'failed'.
    """
    file_data = await file.read()

    try:
        document_service.validate_file(
            filename=file.filename or "",
            content_type=file.content_type or "",
            file_size=len(file_data),
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    doc = await document_service.save_document(
        db,
        user_id=current_user.id,
        filename=file.filename or "upload",
        content_type=file.content_type or "application/octet-stream",
        file_data=file_data,
    )

    background_tasks.add_task(
        document_service.process_document,
        document_id=doc.id,
        user_id=current_user.id,
        file_data=file_data,
        filename=doc.filename,
        content_type=doc.content_type,
    )

    return DocumentUploadResponse.model_validate(doc)


@router.get(
    "",
    response_model=list[DocumentListItem],
    summary="List uploaded documents",
)
async def list_documents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DocumentListItem]:
    """Return all documents uploaded by the authenticated user, newest first."""
    rows = await document_service.list_documents(db, current_user.id)
    return [DocumentListItem(**row) for row in rows]


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Get document processing status",
)
async def get_document_status(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentStatusResponse:
    """
    Return the current processing status and chunk count for a document.

    Poll this endpoint after upload until status is 'ready' or 'failed'.
    Returns 404 if the document doesn't exist or isn't owned by the user.
    """
    status_data = await document_service.get_document_status(db, document_id, current_user.id)
    if status_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentStatusResponse(**status_data)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document and its chunks",
)
async def delete_document(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """
    Delete a document and cascade-delete all its chunks.

    Returns 404 if the document doesn't exist or isn't owned by the user.
    The DB ON DELETE CASCADE handles chunk cleanup automatically.
    """
    deleted = await document_service.delete_document(db, document_id, current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
