"""Saved workflows, visible to everyone. A workflow is saved as it is drawn; its check says what keeps it from
running."""

from datetime import UTC, datetime

from acex.models.workflow import WorkflowRow
from acex_devkit.models.workflows import WorkflowCreate, WorkflowResponse, WorkflowUpdate
from acex_devkit.workflows.check import WorkflowChecker
from sqlmodel import select


class WorkflowNotFound(LookupError):
    pass


class WorkflowLibrary:
    def __init__(self, db_manager):
        self.db = db_manager

    def workflows(self) -> list[WorkflowResponse]:
        session = next(self.db.get_session())
        try:
            rows = session.exec(select(WorkflowRow).order_by(WorkflowRow.name)).all()
            return [self.response(row) for row in rows]
        finally:
            session.close()

    def workflow(self, workflow_id: int) -> WorkflowResponse:
        session = next(self.db.get_session())
        try:
            return self.response(self.row(session, workflow_id))
        finally:
            session.close()

    def create_workflow(self, payload: WorkflowCreate, *, created_by: str) -> WorkflowResponse:
        row = WorkflowRow(**payload.model_dump(mode="json"), created_by=created_by, updated_by=created_by)
        session = next(self.db.get_session())
        try:
            session.add(row)
            session.commit()
            session.refresh(row)
            return self.response(row)
        finally:
            session.close()

    def update_workflow(self, workflow_id: int, payload: WorkflowUpdate, *, updated_by: str) -> WorkflowResponse:
        """Change the fields sent; only a description can be cleared."""
        session = next(self.db.get_session())
        try:
            row = self.row(session, workflow_id)
            for field, value in payload.model_dump(mode="json", include=payload.model_fields_set).items():
                if value is not None or field == "description":
                    setattr(row, field, value)
            row.updated_by = updated_by
            row.updated_at = datetime.now(UTC)
            session.add(row)
            session.commit()
            session.refresh(row)
            return self.response(row)
        finally:
            session.close()

    def delete_workflow(self, workflow_id: int) -> None:
        """Delete the workflow; its runs are kept, each with its own copy of what it ran."""
        session = next(self.db.get_session())
        try:
            session.delete(self.row(session, workflow_id))
            session.commit()
        finally:
            session.close()

    def row(self, session, workflow_id: int) -> WorkflowRow:
        row = session.get(WorkflowRow, workflow_id)
        if row is None:
            raise WorkflowNotFound(f"No workflow {workflow_id}")
        return row

    def response(self, row: WorkflowRow) -> WorkflowResponse:
        workflow = WorkflowResponse.model_validate(row)
        workflow.check = WorkflowChecker(workflow.graph).check()
        return workflow
