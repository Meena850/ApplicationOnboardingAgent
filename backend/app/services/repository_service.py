import logging
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo
from git.exc import BadName

from app.core.config import get_settings
from app.models.repository import (
    AnalysisRecord,
    AnalyzeRequest,
    CommitInfo,
    RepositoryInput,
    RepositoryMetadata,
)

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"^(https?://|ssh://|git@|git://|file://)")


class RepositoryError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class RepositoryService:
    def __init__(self) -> None:
        data = Path(get_settings().data_dir)
        self.clones_dir = data / "clones"
        self.meta_dir = data / "repositories"
        self.analyses_dir = data / "analyses"
        for d in (self.clones_dir, self.meta_dir, self.analyses_dir):
            d.mkdir(parents=True, exist_ok=True)

    # ---- ingestion ----
    def ingest(self, inp: RepositoryInput) -> RepositoryMetadata:
        source = inp.source.strip()
        branch = (inp.branch or "").strip() or None
        if not source:
            raise RepositoryError("Repository path or URL is required.")
        if _URL_RE.match(source):
            repo, source_type = self._clone(source, branch), "remote"
        else:
            repo, source_type = self._load_local(source), "local"
            if branch:
                try:
                    active = repo.active_branch.name
                except TypeError:
                    active = None
                if branch != active and branch in self._branches(repo):
                    # Don't touch the user's working tree: check the branch out in a private clone.
                    repo = self._clone(str(Path(source).resolve()), branch)
        path = Path(repo.working_dir)
        try:
            meta = self._build_metadata(repo, source, source_type, path, branch)
        except RepositoryError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed reading repository")
            raise RepositoryError(f"Could not read repository: {exc}", 500) from exc
        self._save(self.meta_dir / f"{meta.id}.json", meta.model_dump_json(indent=2))
        logger.info("Ingested %s (%s) branch=%s", source, source_type, meta.branch)
        return meta

    def _clone(self, url: str, branch: Optional[str]) -> Repo:
        dest = self.clones_dir / uuid.uuid4().hex
        try:
            kwargs = {"branch": branch} if branch else {}
            return Repo.clone_from(url, dest, **kwargs)
        except GitCommandError as exc:
            shutil.rmtree(dest, ignore_errors=True)
            detail = (exc.stderr or str(exc)).strip().splitlines()
            msg = detail[-1] if detail else "git clone failed"
            logger.warning("Clone failed for %s: %s", url, msg)
            raise RepositoryError(f"Failed to clone '{url}': {msg}") from exc

    def _load_local(self, path: str) -> Repo:
        try:
            return Repo(path, search_parent_directories=False)
        except NoSuchPathError as exc:
            raise RepositoryError(f"Path does not exist: {path}") from exc
        except InvalidGitRepositoryError as exc:
            raise RepositoryError(f"Not a git repository: {path}") from exc

    def _build_metadata(self, repo: Repo, source: str, source_type: str,
                        path: Path, branch: Optional[str]) -> RepositoryMetadata:
        if repo.bare or not repo.head.is_valid():
            raise RepositoryError("Repository has no commits.")
        branches = self._branches(repo)
        try:
            current = repo.active_branch.name
        except TypeError:
            current = "HEAD (detached)"
        target = branch or current
        if branch and branch not in branches:
            raise RepositoryError(
                f"Branch '{branch}' not found. Available: {', '.join(branches) or 'none'}"
            )
        try:
            commit = self._resolve(repo, target)
        except BadName as exc:
            raise RepositoryError(f"Cannot resolve branch '{target}'.") from exc
        return RepositoryMetadata(
            id=uuid.uuid4().hex,
            source=source,
            source_type=source_type,  # type: ignore[arg-type]
            local_path=str(path),
            branch=target,
            branches=branches,
            head=CommitInfo(
                sha=commit.hexsha,
                message=str(commit.message).strip().splitlines()[0] if commit.message else "",
                author=str(commit.author),
                date=datetime.fromtimestamp(commit.committed_date, tz=timezone.utc),
            ),
            commit_count=sum(1 for _ in repo.iter_commits(commit)),
        )

    @staticmethod
    def _resolve(repo: Repo, name: str):
        try:
            return repo.commit(name)
        except BadName:
            return repo.commit(f"origin/{name}")

    @staticmethod
    def _branches(repo: Repo) -> List[str]:
        names = {h.name for h in repo.heads}
        for ref in repo.remotes.origin.refs if "origin" in [r.name for r in repo.remotes] else []:
            short = ref.name.split("/", 1)[-1]
            if short != "HEAD":
                names.add(short)
        return sorted(names)

    # ---- analysis pair ----
    def analyze(self, req: AnalyzeRequest) -> AnalysisRecord:
        base = self.ingest(req.base)
        try:
            enh = self.ingest(req.enhancement)
        except RepositoryError as exc:
            raise RepositoryError(f"Enhancement repo: {exc.message}", exc.status_code) from exc
        record = AnalysisRecord(id=uuid.uuid4().hex, base=base, enhancement=enh)
        self._save(self.analyses_dir / f"{record.id}.json", record.model_dump_json(indent=2))
        return record

    # ---- queries ----
    def list(self) -> List[RepositoryMetadata]:
        return [RepositoryMetadata.model_validate_json(p.read_text(encoding="utf-8"))
                for p in sorted(self.meta_dir.glob("*.json"))]

    def get(self, repo_id: str) -> RepositoryMetadata:
        path = self.meta_dir / f"{Path(repo_id).name}.json"
        if not path.exists():
            raise RepositoryError("Repository not found.", 404)
        return RepositoryMetadata.model_validate_json(path.read_text(encoding="utf-8"))

    @staticmethod
    def _save(path: Path, content: str) -> None:
        path.write_text(content, encoding="utf-8")
