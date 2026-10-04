from __future__ import annotations

import json
import mimetypes
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import (
    QWebEnginePage,
    QWebEngineProfile,
    QWebEngineSettings,
    QWebEngineUrlRequestJob,
    QWebEngineUrlScheme,
    QWebEngineUrlSchemeHandler,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget


def register_react_scheme() -> None:
    scheme = QWebEngineUrlScheme.schemeByName(b"crosshair")
    if scheme.name():
        return
    scheme = QWebEngineUrlScheme()
    scheme.setName(b"crosshair")
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.HostAndPort)
    scheme.setFlags(QWebEngineUrlScheme.Flag.SecureScheme | QWebEngineUrlScheme.Flag.LocalScheme)
    QWebEngineUrlScheme.registerScheme(scheme)


class _BundleHandler(QWebEngineUrlSchemeHandler):
    def __init__(self, root: Path, parent: QWidget) -> None:
        super().__init__(parent)
        self._root = root.resolve()

    def requestStarted(self, job: QWebEngineUrlRequestJob) -> None:  # noqa: N802
        try:
            relative = job.requestUrl().path().lstrip("/") or "index.html"
            path = (self._root / relative).resolve()
            path.relative_to(self._root)
            if not path.is_file():
                raise FileNotFoundError(relative)
            device = QBuffer(job)
            device.setData(QByteArray(path.read_bytes()))
            device.open(QIODevice.OpenModeFlag.ReadOnly)
            mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            job.reply(QByteArray(mime.encode("ascii")), device)
        except (OSError, ValueError):
            job.fail(QWebEngineUrlRequestJob.Error.UrlNotFound)


class _TrustedPage(QWebEnginePage):
    def acceptNavigationRequest(self, url: QUrl, navigation_type, is_main_frame: bool) -> bool:  # noqa: N802
        del is_main_frame
        if url.scheme() == "crosshair" and url.host() == "ui":
            return True
        if url.scheme() in {"https", "http", "mailto"}:
            if navigation_type == QWebEnginePage.NavigationType.NavigationTypeLinkClicked:
                QDesktopServices.openUrl(url)
        return False


class _ChannelObject(QWidget):
    response = Signal(str)
    stateEvent = Signal(str)
    commandRequested = Signal(str, object, str)

    @Slot(str)
    def request(self, raw: str) -> None:
        request_id = ""
        try:
            if len(raw) > 65536:
                raise ValueError("Request exceeds the size limit")
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("version") != 1:
                raise ValueError("Unsupported bridge protocol")
            request_id = data.get("id", "")
            command = data.get("command")
            payload = data.get("payload")
            if not isinstance(request_id, str) or not request_id or len(request_id) > 128:
                raise ValueError("Invalid request id")
            if not isinstance(command, str) or not isinstance(payload, dict):
                raise ValueError("Invalid command envelope")
            self.commandRequested.emit(command, payload, request_id)
        except Exception as exc:
            self.response.emit(json.dumps({"id": request_id, "ok": False,
                                           "error": {"code": "invalid_request", "message": str(exc)[:240]}},
                                          separators=(",", ":")))


class ReactSurface(QWidget):
    command_requested = Signal(str, object, str)
    load_finished = Signal(bool)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._bundle = Path(__file__).resolve().parents[1] / "webui" / "dist"
        self.view = QWebEngineView(self)
        self._profile = QWebEngineProfile(self)
        self._handler = _BundleHandler(self._bundle, self._profile)
        self._profile.installUrlSchemeHandler(b"crosshair", self._handler)
        self._page = _TrustedPage(self._profile, self.view)
        self.view.setPage(self._page)
        self.view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, False)
        self.view.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, False)
        self._channel = QWebChannel(self._page)
        self._object = _ChannelObject(self)
        self._channel.registerObject("control", self._object)
        self._page.setWebChannel(self._channel)
        self._object.commandRequested.connect(self.command_requested)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.view.loadFinished.connect(self.load_finished)
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._started = True
        if (self._bundle / "index.html").is_file():
            self.view.load(QUrl("crosshair://ui/index.html"))
        else:
            self.load_finished.emit(False)

    def complete(self, request_id: str, result: object = None, error: str = "") -> None:
        if error:
            payload = {"id": request_id, "ok": False, "error": {"code": "command_failed", "message": error[:240]}}
        else:
            payload = {"id": request_id, "ok": True, "result": result}
        self._object.response.emit(json.dumps(payload, separators=(",", ":"), default=str))

    def publish(self, snapshot: dict) -> None:
        self._object.stateEvent.emit(json.dumps({"type": "state", "snapshot": snapshot}, separators=(",", ":"), default=str))

    def set_active(self, active: bool) -> None:
        target = QWebEnginePage.LifecycleState.Active if active else QWebEnginePage.LifecycleState.Frozen
        if self._page.lifecycleState() != target:
            self._page.setLifecycleState(target)
