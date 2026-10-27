from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class RepositoryInput(BaseModel):
    source: str = Field(..., min_length=1, description="Git URL or local repository path")
    branch: Optional[str] = Field(None, description="Branch to use; defaults to the current/default branch")


class CommitInfo(BaseModel):
    sha: str
    message: str
    author: str
    date: datetime


class RepositoryMetadata(BaseModel):
    id: str
    source: str
    source_type: Literal["remote", "local"]
    local_path: str
    branch: str
    branches: List[str] = []
    head: CommitInfo
    commit_count: int
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AnalyzeRequest(BaseModel):
    base: RepositoryInput
    enhancement: RepositoryInput


class AnalysisRecord(BaseModel):
    id: str
    base: RepositoryMetadata
    enhancement: RepositoryMetadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
