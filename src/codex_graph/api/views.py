"""JSON:API view classes for files and ast-nodes resources."""

from __future__ import annotations

from typing import Any, ClassVar

from fastapi import Depends
from fastapi_jsonapi.views import Operation, OperationConfig, ViewBase
from pydantic import BaseModel, ConfigDict

from codex_graph.api.data_layer import AstNodeDataLayer, FileDataLayer
from codex_graph.api.dependencies import get_database


class DbDependency(BaseModel):
    """Pydantic model whose fields become FastAPI Depends() parameters."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    db: Any = Depends(get_database)


async def prepare_dl_kwargs(view: ViewBase, deps: DbDependency) -> dict[str, Any]:
    """Extract resolved dependencies and return kwargs for the data layer constructor."""
    return {"db": deps.db}


class FileView(ViewBase):
    data_layer_cls = FileDataLayer  # type: ignore[assignment]
    operation_dependencies: ClassVar[dict[Operation, OperationConfig]] = {
        Operation.ALL: OperationConfig(
            dependencies=DbDependency,
            prepare_data_layer_kwargs=prepare_dl_kwargs,
        ),
    }


class AstNodeView(ViewBase):
    data_layer_cls = AstNodeDataLayer  # type: ignore[assignment]
    operation_dependencies: ClassVar[dict[Operation, OperationConfig]] = {
        Operation.ALL: OperationConfig(
            dependencies=DbDependency,
            prepare_data_layer_kwargs=prepare_dl_kwargs,
        ),
    }
