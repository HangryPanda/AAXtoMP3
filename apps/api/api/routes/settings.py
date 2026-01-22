"""Settings management endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SettingsModel, SettingsUpdate
from db.session import get_session

router = APIRouter()


class SettingsResponse(BaseModel):
    """Settings response model."""

    output_format: str
    single_file: bool
    compression_mp3: int
    compression_flac: int
    compression_opus: int
    cover_size: str
    dir_naming_scheme: str
    file_naming_scheme: str
    chapter_naming_scheme: str
    no_clobber: bool
    move_after_complete: bool
    auto_retry: bool
    max_retries: int
    author_override: str
    keep_author_index: int


class NamingVariablesResponse(BaseModel):
    """Available naming scheme variables."""

    directory: list[str]
    file: list[str]
    chapter: list[str]


# Available naming scheme variables
NAMING_VARIABLES = [
    "$title",
    "$artist",
    "$album_artist",
    "$genre",
    "$narrator",
    "$series",
    "$series_sequence",
    "$year",
]
CHAPTER_NAMING_VARIABLES = NAMING_VARIABLES + [
    "$chapter",
    "$chapternum",
    "$chaptercount",
]


@router.get("", response_model=SettingsResponse)
async def get_settings(
    session: AsyncSession = Depends(get_session),
) -> SettingsResponse:
    """Get current application settings."""
    result = await session.execute(select(SettingsModel).where(SettingsModel.id == 1))
    settings = result.scalar_one_or_none()

    if not settings:
        # Create default settings if not exists
        settings = SettingsModel(id=1)
        session.add(settings)
        await session.commit()
        await session.refresh(settings)

    return SettingsResponse(
        output_format=settings.output_format,
        single_file=settings.single_file,
        compression_mp3=settings.compression_mp3,
        compression_flac=settings.compression_flac,
        compression_opus=settings.compression_opus,
        cover_size=settings.cover_size,
        dir_naming_scheme=settings.dir_naming_scheme,
        file_naming_scheme=settings.file_naming_scheme,
        chapter_naming_scheme=settings.chapter_naming_scheme,
        no_clobber=settings.no_clobber,
        move_after_complete=settings.move_after_complete,
        auto_retry=settings.auto_retry,
        max_retries=settings.max_retries,
        author_override=settings.author_override,
        keep_author_index=settings.keep_author_index,
    )


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    settings_update: SettingsUpdate,
    session: AsyncSession = Depends(get_session),
) -> SettingsResponse:
    """Update application settings."""
    result = await session.execute(select(SettingsModel).where(SettingsModel.id == 1))
    settings = result.scalar_one_or_none()

    if not settings:
        settings = SettingsModel(id=1)
        session.add(settings)

    # Update fields
    update_data = settings_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)

    settings.updated_at = datetime.utcnow()
    session.add(settings)
    await session.commit()
    await session.refresh(settings)

    return SettingsResponse(
        output_format=settings.output_format,
        single_file=settings.single_file,
        compression_mp3=settings.compression_mp3,
        compression_flac=settings.compression_flac,
        compression_opus=settings.compression_opus,
        cover_size=settings.cover_size,
        dir_naming_scheme=settings.dir_naming_scheme,
        file_naming_scheme=settings.file_naming_scheme,
        chapter_naming_scheme=settings.chapter_naming_scheme,
        no_clobber=settings.no_clobber,
        move_after_complete=settings.move_after_complete,
        auto_retry=settings.auto_retry,
        max_retries=settings.max_retries,
        author_override=settings.author_override,
        keep_author_index=settings.keep_author_index,
    )


@router.get("/naming-variables", response_model=NamingVariablesResponse)
async def get_naming_variables() -> NamingVariablesResponse:
    """Get available naming scheme variables."""
    return NamingVariablesResponse(
        directory=NAMING_VARIABLES,
        file=NAMING_VARIABLES,
        chapter=CHAPTER_NAMING_VARIABLES,
    )
