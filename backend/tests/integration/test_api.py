import uuid

import httpx
import pytest

from askboard.config import load_settings
from askboard.server import create_app

pytestmark = pytest.mark.integration


@pytest.fixture
async def client(clean_database):
    settings = load_settings({
        "DATABASE_URL": clean_database,
        "AUTO_MIGRATE": "true",
        "MAX_UPLOAD_MB": "1",
        "DB_POOL_MAX_SIZE": "2",
    })
    app = create_app(settings=settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def create_workspace(client, name="Sales"):
    response = await client.post("/workspaces", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


async def upload(client, workspace_id, content: bytes, filename="pedidos.csv"):
    return await client.post(
        f"/workspaces/{workspace_id}/datasets",
        files={"file": (filename, content, "text/csv")},
    )


# --- workspaces --------------------------------------------------------------------

async def test_create_list_and_get_workspace(client):
    ws = await create_workspace(client)

    listed = (await client.get("/workspaces")).json()
    fetched = await client.get(f"/workspaces/{ws['id']}")

    assert [w["id"] for w in listed] == [ws["id"]]
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "Sales"


async def test_blank_workspace_name_is_422(client):
    assert (await client.post("/workspaces", json={"name": "   "})).status_code == 422
    assert (await client.post("/workspaces", json={"name": ""})).status_code == 422


async def test_unknown_workspace_is_404(client):
    assert (await client.get(f"/workspaces/{uuid.uuid4()}")).status_code == 404


# --- upload / preview ----------------------------------------------------------------

async def test_upload_returns_preview(client, pedidos_csv):
    ws = await create_workspace(client)

    response = await upload(client, ws["id"], pedidos_csv)

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "pending"
    assert body["table_name"] == "pedidos"
    assert body["preview_rows"][0][1] == "Ana"
    assert {c["name"]: c["pg_type"] for c in body["columns"]}["valor_total"] == "numeric"


async def test_upload_invalid_csv_is_422_with_reason(client):
    ws = await create_workspace(client)

    response = await upload(client, ws["id"], b"\x00\x01\x02binary")

    assert response.status_code == 422
    assert "binary" in response.json()["detail"]


async def test_upload_too_large_is_413(client):
    ws = await create_workspace(client)
    too_big = b"a,b\n" + b"1,2\n" * (1024 * 1024 // 4 + 10)

    response = await upload(client, ws["id"], too_big)

    assert response.status_code == 413


async def test_upload_to_unknown_workspace_is_404(client, pedidos_csv):
    response = await upload(client, uuid.uuid4(), pedidos_csv)
    assert response.status_code == 404


async def test_upload_without_file_is_422(client):
    ws = await create_workspace(client)
    response = await client.post(f"/workspaces/{ws['id']}/datasets")
    assert response.status_code == 422


# --- confirm ---------------------------------------------------------------------------

async def test_confirm_loads_dataset(client, pedidos_csv):
    ws = await create_workspace(client)
    ds = (await upload(client, ws["id"], pedidos_csv)).json()

    response = await client.post(
        f"/workspaces/{ws['id']}/datasets/{ds['id']}/confirm",
        json={"table_name": "orders", "columns": [{"position": 4, "pg_type": "text"}]},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "loaded"
    assert body["table_name"] == "orders"
    assert body["row_count"] == 5
    assert {c["name"]: c["pg_type"] for c in body["columns"]}["data_do_pedido"] == "text"


async def test_confirm_with_empty_body_uses_inferred_schema(client, pedidos_csv):
    ws = await create_workspace(client)
    ds = (await upload(client, ws["id"], pedidos_csv)).json()

    response = await client.post(f"/workspaces/{ws['id']}/datasets/{ds['id']}/confirm", json={})

    assert response.status_code == 200
    assert response.json()["status"] == "loaded"


async def test_confirm_twice_is_409(client, pedidos_csv):
    ws = await create_workspace(client)
    ds = (await upload(client, ws["id"], pedidos_csv)).json()
    url = f"/workspaces/{ws['id']}/datasets/{ds['id']}/confirm"

    assert (await client.post(url, json={})).status_code == 200
    assert (await client.post(url, json={})).status_code == 409


async def test_confirm_invalid_type_is_422(client, pedidos_csv):
    ws = await create_workspace(client)
    ds = (await upload(client, ws["id"], pedidos_csv)).json()

    response = await client.post(
        f"/workspaces/{ws['id']}/datasets/{ds['id']}/confirm",
        json={"columns": [{"position": 1, "pg_type": "varchar(10); DROP TABLE x"}]},
    )

    assert response.status_code == 422


async def test_confirm_unknown_dataset_is_404(client):
    ws = await create_workspace(client)
    response = await client.post(f"/workspaces/{ws['id']}/datasets/{uuid.uuid4()}/confirm", json={})
    assert response.status_code == 404


# --- reads -----------------------------------------------------------------------------

async def test_list_and_get_datasets(client, pedidos_csv):
    ws = await create_workspace(client)
    ds = (await upload(client, ws["id"], pedidos_csv)).json()

    listed = await client.get(f"/workspaces/{ws['id']}/datasets")
    fetched = await client.get(f"/workspaces/{ws['id']}/datasets/{ds['id']}")

    assert [d["id"] for d in listed.json()] == [ds["id"]]
    assert fetched.json()["table_name"] == "pedidos"
    assert "preview_rows" not in fetched.json()


# --- ask ---------------------------------------------------------------------------------

from askboard.ask.llm import LLMNotConfiguredError  # noqa: E402
from askboard.ask.prompts import NarrativeOutput, PlanOutput, SQLOutput  # noqa: E402
from tests.fakes import ScriptedLLM  # noqa: E402


@pytest.fixture
async def make_client(clean_database):
    """Builds a client whose app uses the given LLM (or raises the given error)."""
    contexts = []

    async def _make(llm):
        settings = load_settings({"DATABASE_URL": clean_database, "AUTO_MIGRATE": "true", "DB_POOL_MAX_SIZE": "2"})

        def llm_factory():
            if isinstance(llm, Exception):
                raise llm
            return llm

        app = create_app(settings=settings, llm_factory=llm_factory)
        lifespan = app.router.lifespan_context(app)
        await lifespan.__aenter__()
        contexts.append(lifespan)
        return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    yield _make
    for ctx in contexts:
        await ctx.__aexit__(None, None, None)


async def loaded_workspace(c, pedidos_csv):
    ws = await create_workspace(c)
    ds = (await upload(c, ws["id"], pedidos_csv)).json()
    await c.post(f"/workspaces/{ws['id']}/datasets/{ds['id']}/confirm", json={})
    return ws


async def test_ask_returns_dashboard_and_history(make_client, pedidos_csv):
    llm = ScriptedLLM({
        PlanOutput: [PlanOutput(sub_questions=[])],
        SQLOutput: [SQLOutput(sql="SELECT count(*) AS pedidos FROM pedidos")],
        NarrativeOutput: [NarrativeOutput(title="Total de pedidos", summary=["5 pedidos"], follow_ups=[])],
    })
    async with await make_client(llm) as c:
        ws = await loaded_workspace(c, pedidos_csv)

        response = await c.post(f"/workspaces/{ws['id']}/ask", json={"question": "Quantos pedidos?"})
        history = await c.get(f"/workspaces/{ws['id']}/questions")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["title"] == "Total de pedidos"
    assert body["panels"][0]["rows"] == [[5]]
    assert body["panels"][0]["columns"] == [{"name": "pedidos", "type": "number"}]
    assert [q["id"] for q in history.json()] == [body["id"]]


async def test_ask_blank_question_is_422(make_client, pedidos_csv):
    async with await make_client(ScriptedLLM({})) as c:
        ws = await create_workspace(c)
        response = await c.post(f"/workspaces/{ws['id']}/ask", json={"question": "   "})

    assert response.status_code == 422


async def test_ask_without_llm_configuration_is_503(make_client, pedidos_csv):
    async with await make_client(LLMNotConfiguredError("OPENROUTER_API_KEY is not set")) as c:
        ws = await loaded_workspace(c, pedidos_csv)
        response = await c.post(f"/workspaces/{ws['id']}/ask", json={"question": "Quantos pedidos?"})

    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]


async def test_ask_unknown_workspace_is_404(make_client):
    async with await make_client(ScriptedLLM({})) as c:
        response = await c.post(f"/workspaces/{uuid.uuid4()}/ask", json={"question": "Oi?"})

    assert response.status_code == 404


# --- relationships -------------------------------------------------------------------------

from tests.integration.conftest import FIXTURES  # noqa: E402


async def upload_and_confirm(c, ws_id, filename, fixture_name):
    ds = (await upload(c, ws_id, (FIXTURES / fixture_name).read_bytes(), filename=filename)).json()
    response = await c.post(f"/workspaces/{ws_id}/datasets/{ds['id']}/confirm", json={})
    assert response.status_code == 200, response.text


async def test_relationships_are_listed_and_can_be_confirmed(client):
    ws = await create_workspace(client)
    await upload_and_confirm(client, ws["id"], "clientes.csv", "loja_clientes.csv")
    await upload_and_confirm(client, ws["id"], "pedidos.csv", "loja_pedidos.csv")

    listed = (await client.get(f"/workspaces/{ws['id']}/relationships")).json()
    [rel] = listed
    response = await client.patch(f"/workspaces/{ws['id']}/relationships/{rel['id']}", json={"status": "confirmed"})

    assert (rel["from_table"], rel["from_column"], rel["to_table"], rel["to_column"]) == (
        "pedidos", "cliente_id", "clientes", "id",
    )
    assert rel["status"] == "suggested"
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"


async def test_invalid_relationship_status_is_422(client):
    ws = await create_workspace(client)
    response = await client.patch(f"/workspaces/{ws['id']}/relationships/{uuid.uuid4()}", json={"status": "maybe"})
    assert response.status_code == 422


async def test_unknown_relationship_is_404(client):
    ws = await create_workspace(client)
    response = await client.patch(f"/workspaces/{ws['id']}/relationships/{uuid.uuid4()}", json={"status": "rejected"})
    assert response.status_code == 404


async def test_relationships_of_unknown_workspace_is_404(client):
    assert (await client.get(f"/workspaces/{uuid.uuid4()}/relationships")).status_code == 404
