"""Type generation, regeneration safety, and CLI regression tests."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Header
from pydantic import BaseModel
import pytest

from qpyserve._cli import create_project, main
from qpyserve._client import (
    _ts_type, client_output, generate_client, save_client,
)


class Item(BaseModel):
    name: str
    count: int
    tags: list[str] = []
    note: str | None = None


def sample_app() -> FastAPI:
    app = FastAPI()

    @app.get("/api/items/{item_id}", response_model=Item, operation_id="getItem")
    def get_item(
        item_id: int, verbose: bool = False, x_token: str = Header(alias="X-Token"),
    ):
        return Item(name=f"Item-{item_id}", count=1)

    @app.post("/api/items", response_model=Item, operation_id="createItem")
    def create(item: Item):
        return item

    @app.delete("/api/items/{item_id}", status_code=204, operation_id="deleteItem")
    def delete(item_id: int):
        return None

    return app


def test_generated_contract_tracks_real_pydantic_models() -> None:
    source = generate_client(sample_app().openapi())
    assert source.operations == ("createItem", "getItem", "deleteItem")
    assert not source.skipped
    assert '"Item":' in source.source
    assert '"name": string;' in source.source
    assert '"count": number;' in source.source
    assert '"tags"?: Array<string>;' in source.source
    assert '"note"?: (string) | (null);' in source.source
    assert '"getItem": (options:' in source.source
    assert '"item_id": number;' in source.source
    assert '"X-Token": string;' in source.source
    assert '"verbose"?: boolean;' in source.source
    assert '"createItem": (options:' in source.source
    assert 'body: Schemas["Item"]' in source.source
    assert 'Promise<void>' in source.source
    assert "x-qpyserve-trace-id" in source.source
    assert "encodeURIComponent(String(value))" in source.source
    assert "new URLSearchParams()" in source.source
    assert "extra request bodies" in source.source


def test_common_json_schema_types() -> None:
    assert _ts_type({"enum": ["A", "B"]}) == '"A" | "B"'
    assert _ts_type({"const": 3}) == "3"
    assert _ts_type({"type": "array", "items": {"type": "integer"}}) == "Array<number>"
    assert _ts_type({"$ref": "#/components/schemas/MyModel"}) == 'Schemas["MyModel"]'
    assert _ts_type({"type": "string", "nullable": True}) == "(string | null)"
    assert _ts_type({"type": ["number", "null"]}) == "number | null"
    assert _ts_type({"type": "object", "additionalProperties": {"type": "boolean"}}) == (
        "Record<string, boolean>"
    )
    with pytest.raises(ValueError, match="Unsupported OpenAPI schema"):
        _ts_type({"$ref": "https://attacker/schema"})


def test_media_and_cookie_limitations_are_explicit() -> None:
    document = sample_app().openapi()
    document["paths"]["/upload"] = {
        "post": {
            "operationId": "upload",
            "requestBody": {"content": {"multipart/form-data": {"schema": {}}}},
            "responses": {"200": {"description": "OK"}},
        },
    }
    document["paths"]["/cookie"] = {
        "get": {
            "operationId": "cookie",
            "parameters": [{"in": "cookie", "name": "session", "schema": {"type": "string"}}],
            "responses": {"200": {"description": "OK"}},
        },
    }
    document["paths"]["/pdf"] = {
        "get": {
            "operationId": "downloadPdf",
            "responses": {
                "200": {"description": "ok", "content": {"application/pdf": {"schema": {}}}},
            },
        },
    }
    generated = generate_client(document)
    assert len(generated.skipped) == 3
    assert "upload" not in generated.operations
    assert "cookie" not in generated.operations
    assert "downloadPdf" not in generated.operations
    assert any("non-JSON request body" in warning for warning in generated.skipped)
    assert any("unsupported parameter location cookie" in warning for warning in generated.skipped)
    assert any("non-JSON success response" in warning for warning in generated.skipped)


def test_generator_is_deterministic_and_does_not_silently_duplicate_names() -> None:
    document = sample_app().openapi()
    assert generate_client(document).source == generate_client(document).source
    document["paths"]["/api/duplicate"] = {
        "get": {
            "operationId": "getItem",
            "responses": {"200": {"description": "OK"}},
        },
    }
    generated = generate_client(document)
    assert len(generated.operations) == 3
    assert any("duplicate operation ID" in warning for warning in generated.skipped)


def test_write_check_and_nondestructive_behavior(tmp_path: Path) -> None:
    project = create_project(tmp_path / "client", template="react")
    destination = client_output(project)
    result = generate_client(sample_app().openapi())
    report = save_client(result, destination)
    assert report["written"]
    assert destination.is_file()
    assert not save_client(result, destination)["written"]
    assert save_client(result, destination, check=True)["drift"] is False
    destination.write_text(result.source + "\n// edited locally\n")
    report = save_client(result, destination, check=True)
    assert report["drift"] is True
    assert not report["written"]
    assert "edited locally" in destination.read_text()
    assert save_client(result, destination)["written"]
    destination.write_text("user-owned types")
    with pytest.raises(FileExistsError, match="non-generated"):
        save_client(result, destination)
    assert destination.read_text() == "user-owned types"


def test_generated_client_cannot_escape_or_overwrite_symlinks(tmp_path: Path) -> None:
    project = create_project(tmp_path / "client", template="react")
    with pytest.raises(ValueError, match="frontend"):
        client_output(project, "../outside.ts")
    with pytest.raises(ValueError, match="frontend"):
        client_output(project, "main.ts")
    with pytest.raises(ValueError, match="build directories"):
        client_output(project, "frontend/dist/generated.ts")
    with pytest.raises(ValueError, match="build directories"):
        client_output(project, "frontend/.env/generated.ts")
    link = project / "frontend" / "src" / "link.ts"
    try:
        link.symlink_to(tmp_path / "secret")
    except (OSError, NotImplementedError):
        pytest.skip("Platform disallows symlinks")
    with pytest.raises(ValueError, match="non-symlink"):
        client_output(project, "frontend/src/link.ts")


def test_cli_api_json_and_check_drift(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = create_project(tmp_path / "react-client", template="react")
    assert main(["api", str(project), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["written"] is True
    assert len(report["operations"]) == 1
    dest = project / "frontend/src/qpyserve-api.ts"
    assert dest.exists()
    assert main(["api", str(project), "--check", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["drift"] is False
    dest.write_text(dest.read_text() + "\n// CHANGED\n")
    assert main(["api", str(project), "--check", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert report["drift"] is True
    assert "CHANGED" in dest.read_text()
