"""Receipts API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import require_api_key
from app.core.db import get_db
from app.repositories.receipt_repo import ReceiptRepository
from app.schemas.receipts import ReceiptCreate, ReceiptRead
from app.services.receipt_service import ReceiptService

router = APIRouter()


@router.post("", response_model=ReceiptRead)
async def create_receipt(
    body: ReceiptCreate,
    session: AsyncSession = Depends(get_db),
    _: None = Depends(require_api_key),
) -> ReceiptRead:
    svc = ReceiptService(session)
    receipt = await svc.record_receipt(
        mission_id=body.mission_id,
        receipt_type=body.receipt_type,
        source=body.source,
        payload=body.payload,
        summary=body.summary,
    )
    return ReceiptRead.model_validate(receipt)


@router.get("/{receipt_id}", response_model=ReceiptRead)
async def get_receipt(
    receipt_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> ReceiptRead:
    receipt = await ReceiptRepository.get(session, receipt_id)
    if receipt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Receipt not found",
        )
    return ReceiptRead.model_validate(receipt)
