import asyncio
import sys
import types
from types import SimpleNamespace

from helpers import runtime_patch


class FakePage:
    def __init__(self, url):
        self.url = url
        self.closed = False

    def is_closed(self):
        return self.closed

    async def close(self):
        self.closed = True

    async def goto(self, url):
        self.url = url


class FakeContext:
    def __init__(self, pages=None):
        self.pages = list(pages or [])

    async def new_page(self):
        page = FakePage("about:blank")
        self.pages.append(page)
        return page


class FakeRuntimeCore:
    @staticmethod
    def _shadow_dom_script():
        return "original"

    def __init__(self, pages=None):
        self.context = FakeContext(pages)
        self.pages = {}
        self.next_browser_id = 1
        self.last_interacted_browser_id = None
        self.original_close_all_called = False
        for page in self.context.pages:
            self._register_page_sync(page)

    async def _start(self):
        return None

    async def ensure_started(self):
        return None

    async def _stop_all_screencasts(self):
        return None

    async def _register_page(self, page):
        return self._register_page_sync(page)

    def _register_page_sync(self, page):
        for record in self.pages.values():
            if record.page is page:
                return record
        record = SimpleNamespace(id=self.next_browser_id, page=page)
        self.pages[record.id] = record
        self.next_browser_id += 1
        self.last_interacted_browser_id = record.id
        return record

    async def list(self):
        return {
            "browsers": [
                {"id": browser_id, "currentUrl": record.page.url}
                for browser_id, record in sorted(self.pages.items())
            ],
            "last_interacted_browser_id": self.last_interacted_browser_id,
        }

    async def close_all(self):
        self.original_close_all_called = True
        for record in list(self.pages.values()):
            await record.page.close()
        self.pages.clear()
        self.last_interacted_browser_id = None
        return {"browsers": [], "last_interacted_browser_id": None}

    async def close_all_browsers(self):
        return await self.close_all()


def install_fake_runtime(monkeypatch):
    runtime_mod = types.ModuleType("plugins._browser.helpers.runtime")
    runtime_mod._BrowserRuntimeCore = FakeRuntimeCore
    monkeypatch.setitem(sys.modules, "plugins", types.ModuleType("plugins"))
    monkeypatch.setitem(sys.modules, "plugins._browser", types.ModuleType("plugins._browser"))
    monkeypatch.setitem(sys.modules, "plugins._browser.helpers", types.ModuleType("plugins._browser.helpers"))
    monkeypatch.setitem(sys.modules, "plugins._browser.helpers.runtime", runtime_mod)


def test_shadow_dom_script_is_noop_and_restored(monkeypatch):
    install_fake_runtime(monkeypatch)
    monkeypatch.setattr(
        runtime_patch,
        "_agent_zero_import_context",
        lambda: _NullContext(),
    )
    monkeypatch.setattr(
        "helpers.config.get_config",
        lambda: {
            "advanced": {
                "disable_shadow_dom_init_patch": True,
                "preserve_headed_placeholder_page": True,
            },
            "runtime": {"headed": True},
        },
    )

    runtime_patch.unpatch_runtime()
    status = runtime_patch.apply_runtime_patch()

    assert status["patched"] is True
    assert status["shadow_dom_disabled"] is True
    assert FakeRuntimeCore._shadow_dom_script() == "(() => {})();"

    restored = runtime_patch.unpatch_runtime()
    assert restored["patched"] is False
    assert FakeRuntimeCore._shadow_dom_script() == "original"


def test_headed_close_all_leaves_one_about_blank(monkeypatch):
    install_fake_runtime(monkeypatch)
    monkeypatch.setattr(runtime_patch, "_agent_zero_import_context", lambda: _NullContext())
    monkeypatch.setattr(
        "helpers.config.get_config",
        lambda: {
            "advanced": {
                "disable_shadow_dom_init_patch": True,
                "preserve_headed_placeholder_page": True,
            },
            "runtime": {"headed": True},
        },
    )

    runtime_patch.unpatch_runtime()
    runtime_patch.apply_runtime_patch()
    about_blank = FakePage("about:blank")
    user_page = FakePage("https://example.test/")
    core = FakeRuntimeCore([about_blank, user_page])

    result = asyncio.run(core.close_all())

    assert result["browsers"] == [{"id": 1, "currentUrl": "about:blank"}]
    assert result["last_interacted_browser_id"] == 1
    assert about_blank.closed is False
    assert user_page.closed is True
    runtime_patch.unpatch_runtime()


def test_headed_close_all_creates_placeholder_when_missing(monkeypatch):
    install_fake_runtime(monkeypatch)
    monkeypatch.setattr(runtime_patch, "_agent_zero_import_context", lambda: _NullContext())
    monkeypatch.setattr(
        "helpers.config.get_config",
        lambda: {
            "advanced": {
                "disable_shadow_dom_init_patch": True,
                "preserve_headed_placeholder_page": True,
            },
            "runtime": {"headed": True},
        },
    )

    runtime_patch.unpatch_runtime()
    runtime_patch.apply_runtime_patch()
    user_page = FakePage("https://example.test/")
    core = FakeRuntimeCore([user_page])

    result = asyncio.run(core.close_all())

    assert len(result["browsers"]) == 1
    assert result["browsers"][0]["currentUrl"] == "about:blank"
    assert user_page.closed is True
    assert len([page for page in core.context.pages if not page.closed]) == 1
    runtime_patch.unpatch_runtime()


def test_headed_close_all_browsers_leaves_one_about_blank(monkeypatch):
    install_fake_runtime(monkeypatch)
    monkeypatch.setattr(runtime_patch, "_agent_zero_import_context", lambda: _NullContext())
    monkeypatch.setattr(
        "helpers.config.get_config",
        lambda: {
            "advanced": {
                "disable_shadow_dom_init_patch": True,
                "preserve_headed_placeholder_page": True,
            },
            "runtime": {"headed": True},
        },
    )

    runtime_patch.unpatch_runtime()
    runtime_patch.apply_runtime_patch()
    about_blank = FakePage("about:blank")
    user_page = FakePage("https://example.test/")
    core = FakeRuntimeCore([about_blank, user_page])

    result = asyncio.run(core.close_all_browsers())

    assert result["browsers"] == [{"id": 1, "currentUrl": "about:blank"}]
    assert about_blank.closed is False
    assert user_page.closed is True
    runtime_patch.unpatch_runtime()


def test_headless_close_all_delegates_upstream(monkeypatch):
    install_fake_runtime(monkeypatch)
    monkeypatch.setattr(runtime_patch, "_agent_zero_import_context", lambda: _NullContext())
    monkeypatch.setattr(
        "helpers.config.get_config",
        lambda: {
            "advanced": {
                "disable_shadow_dom_init_patch": True,
                "preserve_headed_placeholder_page": True,
            },
            "runtime": {"headed": False},
        },
    )

    runtime_patch.unpatch_runtime()
    runtime_patch.apply_runtime_patch()
    core = FakeRuntimeCore([FakePage("https://example.test/")])

    result = asyncio.run(core.close_all())

    assert core.original_close_all_called is True
    assert result == {"browsers": [], "last_interacted_browser_id": None}
    runtime_patch.unpatch_runtime()


def test_unpatch_restores_original_close_all(monkeypatch):
    install_fake_runtime(monkeypatch)
    monkeypatch.setattr(runtime_patch, "_agent_zero_import_context", lambda: _NullContext())
    monkeypatch.setattr(
        "helpers.config.get_config",
        lambda: {
            "advanced": {
                "disable_shadow_dom_init_patch": True,
                "preserve_headed_placeholder_page": True,
            },
            "runtime": {"headed": True},
        },
    )

    runtime_patch.unpatch_runtime()
    original_close_all = FakeRuntimeCore.close_all
    runtime_patch.apply_runtime_patch()
    assert FakeRuntimeCore.close_all is not original_close_all

    runtime_patch.unpatch_runtime()

    assert FakeRuntimeCore.close_all is original_close_all


class _NullContext:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return False
