import asyncio
import importlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

_TMP_DIR = tempfile.TemporaryDirectory()
_KEYS_FILE = Path(_TMP_DIR.name) / "api_keys.json"
_KEYS_FILE.write_text(
    json.dumps(
        [
            {"user": "carlos", "key": "key-carlos-123"},
            {"user": "alice", "key": "key-alice-456"},
        ]
    ),
    encoding="utf-8",
)

os.environ["VECTOR_MEMORY_DATA_DIR"] = _TMP_DIR.name
os.environ["API_KEYS_FILE"] = str(_KEYS_FILE)
os.environ["EMBEDDING_DIM"] = "4"


def _ensure_stub_deps():
    """Provide lightweight stubs when running unit tests outside the Docker image."""
    if "mcp.server.fastmcp" not in sys.modules:
        mcp_mod = types.ModuleType("mcp")
        mcp_srv = types.ModuleType("mcp.server")
        mcp_fast = types.ModuleType("mcp.server.fastmcp")

        class _DummyFastMCP:
            def __init__(self, *args, **kwargs):
                pass

            def tool(self):
                return lambda fn: fn

            def sse_app(self):
                return lambda scope, receive, send: None

        mcp_fast.FastMCP = _DummyFastMCP
        sys.modules.setdefault("mcp", mcp_mod)
        sys.modules.setdefault("mcp.server", mcp_srv)
        sys.modules["mcp.server.fastmcp"] = mcp_fast

    for mod_name in ("uvicorn", "httpx"):
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)


_ensure_stub_deps()

try:
    import sqlite_vec  # noqa: F401
    HAS_SQLITE_VEC = True
except ImportError:
    HAS_SQLITE_VEC = False
    sys.modules["sqlite_vec"] = types.SimpleNamespace(load=lambda conn: None)

server = importlib.import_module("server")


def _fake_embed(texts: list[str]) -> list[list[float]]:
    """Deterministic 4-D embedding based on keyword buckets for isolated unit testing."""
    out = []
    for t in texts:
        low = t.lower()
        if "neovim" in low or "editor" in low:
            out.append([1.0, 0.0, 0.0, 0.0])
        elif "docker" in low or "container" in low:
            out.append([0.0, 1.0, 0.0, 0.0])
        elif "weather" in low or "rain" in low:
            out.append([0.0, 0.0, 1.0, 0.0])
        else:
            out.append([0.0, 0.0, 0.0, 1.0])
    return out


class TestAuthAndHelpers(unittest.TestCase):
    def test_authenticate_param_and_header(self):
        self.assertEqual(server.authenticate_user("key-carlos-123"), "carlos")
        self.assertEqual(server.authenticate_user("key-alice-456"), "alice")
        with self.assertRaises(PermissionError):
            server.authenticate_user("wrong-key")
        with self.assertRaises(PermissionError):
            server.authenticate_user("")

        tok = server._HEADER_API_KEY.set("key-alice-456")
        try:
            self.assertEqual(server.authenticate_user(""), "alice")
        finally:
            server._HEADER_API_KEY.reset(tok)

    def test_user_db_path_isolation(self):
        p_carlos = server.get_user_db_path("carlos")
        p_alice = server.get_user_db_path("alice")
        self.assertNotEqual(p_carlos, p_alice)
        self.assertIn("users/carlos/memory.db", str(p_carlos))
        with self.assertRaises(ValueError):
            server.get_user_db_path("../escape")

    def test_chunk_text(self):
        chunks = server._chunk_text("a" * 250, chunk_size=100, chunk_overlap=20)
        self.assertEqual(len(chunks), 3)
        self.assertEqual(server._chunk_text("   ", 100, 20), [])

    def test_invalid_embedding_backend(self):
        with patch.object(server, "EMBEDDING_BACKEND", "invalid"):
            with self.assertRaises(ValueError):
                asyncio.run(server.get_embeddings(["hello"]))


@unittest.skipUnless(HAS_SQLITE_VEC, "sqlite-vec not installed in host Python")
class TestVectorMemoryEndToEnd(unittest.TestCase):
    def test_isolation_crud_hybrid_and_trash(self):
        async def run_scenario():
            with patch("server.get_embeddings", side_effect=AsyncMock(side_effect=_fake_embed)):
                res1 = await server.store_memory(
                    "Carlos prefers Neovim for Python.",
                    namespace="dev",
                    tags="editor,python",
                    importance=5,
                    api_key="key-carlos-123",
                )
                self.assertIn("Stored memory", res1)

                # Deduplication / upsert
                res_dup = await server.store_memory(
                    "Carlos strongly prefers Neovim for Python.",
                    namespace="dev",
                    tags="editor",
                    api_key="key-carlos-123",
                )
                self.assertIn("Updated existing near-duplicate", res_dup)

                # Alice stores her own memory
                res_alice = await server.store_memory(
                    "Alice uses Docker compose daily.",
                    namespace="dev",
                    api_key="key-alice-456",
                )
                self.assertIn("Stored memory", res_alice)

                # Carlos cannot see Alice's Docker memory
                search_carlos = await server.search_memories(
                    "Docker", mode="hybrid", api_key="key-carlos-123"
                )
                self.assertNotIn("Alice uses Docker", search_carlos)

                # Carlos finds his Neovim memory
                search_neovim = await server.search_memories(
                    "editor", namespace="dev", mode="hybrid", api_key="key-carlos-123"
                )
                self.assertIn("Neovim", search_neovim)

                # Document chunking
                doc_res = await server.store_document(
                    "x" * 250,
                    title="Notes",
                    chunk_size=100,
                    chunk_overlap=20,
                    api_key="key-carlos-123",
                )
                self.assertIn("3 chunk(s)", doc_res)

                # Stats & export
                stats = await server.get_memory_stats(api_key="key-carlos-123")
                self.assertIn("Active memories: 4", stats)
                exported = await server.export_memories(format="json", api_key="key-carlos-123")
                parsed = json.loads(exported)
                self.assertEqual(parsed["user"], "carlos")
                self.assertEqual(parsed["count"], 4)

                # Soft delete, restore, purge
                mem_id = parsed["memories"][0]["id"]
                self.assertIn("Soft-deleted", await server.delete_memory(mem_id, api_key="key-carlos-123"))
                self.assertIn("Restored", await server.restore_memory(mem_id, api_key="key-carlos-123"))
                self.assertIn("Soft-deleted", await server.delete_memory(mem_id, api_key="key-carlos-123"))
                self.assertIn("Purged 1", await server.purge_trash(api_key="key-carlos-123"))

        asyncio.run(run_scenario())


if __name__ == "__main__":
    unittest.main()
