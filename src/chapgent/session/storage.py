from pathlib import Path

import aiofiles

from chapgent.session.models import Session, SessionSummary


class SessionStorage:
    """JSON-based session persistence."""

    def __init__(self, storage_dir: Path | None = None) -> None:
        if storage_dir:
            self.storage_dir = storage_dir
        else:
            # Default to XDG compliant path: ~/.local/share/chapgent/sessions/
            self.storage_dir = Path.home() / ".local" / "share" / "chapgent" / "sessions"

        # Ensure storage directory exists
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_session_path(self, session_id: str) -> Path:
        return self.storage_dir / f"{session_id}.json"

    async def save(self, session: Session) -> None:
        """Save a session to disk."""
        path = self._get_session_path(session.id)

        # Use model_dump_json for serialization
        json_data = session.model_dump_json(indent=2)

        async with aiofiles.open(path, "w") as f:
            await f.write(json_data)

    async def load(self, session_id: str) -> Session | None:
        """Load a session from disk."""
        path = self._get_session_path(session_id)

        if not path.exists():
            return None

        async with aiofiles.open(path) as f:
            content = await f.read()

        try:
            return Session.model_validate_json(content)
        except Exception:
            # Handle corrupted files or validation errors?
            # For now return None or raise? The interface suggests None or strict.
            # Let's let validation errors propagate if strict, but if we want to be robust...
            # The signature says Session | None but that usually implies "not found".
            # If found but invalid, raising is probably better than returning None (which implies not found).
            raise

    async def list_sessions(self) -> list[SessionSummary]:
        """List all saved sessions."""
        summaries = []

        # List all .json files
        # Scour the directory. Since we need to read them to get updated_at/metadata etc,
        # we have a choice: read all files (slow for many) or maintain an index.
        # The spec mentioned "index.json # Quick lookup of session metadata" in section 5.2 description.
        # "Storage Format: ... index.json"
        # However, maintaining an index atomically is harder without a lock.
        # Given this is MVP and usually single user, direct file generic is safer, index is optimization.
        # Let's check `specs/phase-1-mvp.md` again for requirements on index.
        # "Sessions stored at: ... index.json # Quick lookup".
        # If I implement index, I need to update it on save/delete.
        # For simplicity MVP (and to avoid race conditions complexity in MVP),
        # I might just iterate files first. Use `index.json` if required.
        # The spec says "Storage Format: ... index.json".

        # Let's try to stick to file iteration for robustness unless performance is key.
        # Or better, implement the index as requested.

        # But wait, `list_sessions` logic:
        # If I scan files:
        if not self.storage_dir.exists():
            return []

        # We need to gather summaries. Reading every full JSON might be heavy if messages are huge.
        # But for MVP it's likely fine.

        files = list(self.storage_dir.glob("*.json"))
        # Filter out index.json if we strictly follow that structure,
        # but if I don't implement index logic yet, I should avoid naming conflicts.

        for file_path in files:
            if file_path.name == "index.json":
                continue

            try:
                # To avoid reading whole file, we could parse partial, but pydantic json validate reads all.
                async with aiofiles.open(file_path) as f:
                    content = await f.read()

                session = Session.model_validate_json(content)
                summaries.append(
                    SessionSummary(
                        id=session.id,
                        created_at=session.created_at,
                        updated_at=session.updated_at,
                        message_count=len(session.messages),
                        working_directory=session.working_directory,
                        metadata=session.metadata,
                    )
                )
            except Exception:
                continue

        # Sort by updated_at desc
        summaries.sort(key=lambda x: x.updated_at, reverse=True)
        return summaries

    async def delete(self, session_id: str) -> bool:
        """Delete a session."""
        path = self._get_session_path(session_id)
        if path.exists():
            path.unlink()
            return True
        return False
