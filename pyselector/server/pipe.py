from __future__ import annotations

from pyselector.server.transport import ConnectionClosed


PIPE_NAME_PREFIX = "\\\\.\\pipe\\pyselector-"
BUFFER_SIZE = 1 << 20
LOCAL_SYSTEM_SID = "S-1-5-18"
_ERROR_MORE_DATA = 234
_ERROR_PIPE_CONNECTED = 535
_ERROR_IO_PENDING = 997


class PipeUnavailableError(Exception):
    """名前付きパイプを使えない（pywin32 が無い、サーバーが居ない、など）。"""


def _win32():
    """pywin32 をまとめて読み込む。

    pywinauto が既に依存しているため追加の依存関係にはならないが、import 自体は
    薄いクライアントの起動コストになるので、必要になった時点で読み込む。
    """
    try:
        import pywintypes
        import win32con
        import win32event
        import win32file
        import win32pipe
        import win32process
        import win32security
    except ImportError as exc:  # pragma: no cover - pywin32 が無い環境
        raise PipeUnavailableError("pywin32 が利用できないため常駐モードは使えません") from exc
    return _Win32(pywintypes, win32con, win32event, win32file, win32pipe, win32process, win32security)


class _Win32:
    """pywin32 のモジュール束。呼び出し側の import 文を 1 行に収めるためだけの入れ物。"""

    def __init__(self, types, con, event, file, pipe, process, security) -> None:
        self.types = types
        self.con = con
        self.event = event
        self.file = file
        self.pipe = pipe
        self.process = process
        self.security = security


def _current_user_sid_object(api: _Win32):
    handle = api.security.OpenProcessToken(api.process.GetCurrentProcess(), api.con.TOKEN_QUERY)
    try:
        return api.security.GetTokenInformation(handle, api.security.TokenUser)[0]
    finally:
        handle.Close()


def current_user_sid() -> str:
    """実行ユーザーの SID を文字列で返す。"""
    api = _win32()
    return api.security.ConvertSidToStringSid(_current_user_sid_object(api))


def pipe_name_for_current_user() -> str:
    """SID からパイプ名を決める。

    同一マシンの複数ユーザーが衝突せず、状態ファイルを読まなくても
    クライアントが接続先を知れる（設計 4.2）。
    """
    return PIPE_NAME_PREFIX + current_user_sid()


def _security_attributes(api: _Win32):
    """実行ユーザーと SYSTEM だけに全権を与える ACL を組み立てる。

    認証はカーネルが SID で強制するので、こちらで秘密情報を持つ必要がない。
    """
    user_sid = _current_user_sid_object(api)
    system_sid = api.security.ConvertStringSidToSid(LOCAL_SYSTEM_SID)

    dacl = api.security.ACL()
    dacl.AddAccessAllowedAce(api.security.ACL_REVISION, api.con.GENERIC_ALL, user_sid)
    dacl.AddAccessAllowedAce(api.security.ACL_REVISION, api.con.GENERIC_ALL, system_sid)

    descriptor = api.security.SECURITY_DESCRIPTOR()
    descriptor.SetSecurityDescriptorDacl(1, dacl, 0)

    attributes = api.security.SECURITY_ATTRIBUTES()
    attributes.SECURITY_DESCRIPTOR = descriptor
    attributes.bInheritHandle = False
    return attributes


class PipeConnection:
    """接続済みのパイプインスタンス 1 本。応答を返したら切断する。"""

    def __init__(self, handle, owns_instance: bool) -> None:
        self._handle = handle
        self._owns_instance = owns_instance
        self._closed = False

    def receive(self) -> bytes:
        api = _win32()
        chunks: list[bytes] = []
        while True:
            try:
                code, data = api.file.ReadFile(self._handle, BUFFER_SIZE)
            except api.types.error as exc:
                raise ConnectionClosed(str(exc)) from exc
            chunks.append(data)
            # メッセージモードでは、1 メッセージを読み切れないと ERROR_MORE_DATA になる。
            if code != _ERROR_MORE_DATA:
                break
        return b"".join(chunks)

    def send(self, payload: bytes) -> None:
        api = _win32()
        try:
            api.file.WriteFile(self._handle, payload)
            api.file.FlushFileBuffers(self._handle)
        except api.types.error as exc:
            raise ConnectionClosed(str(exc)) from exc

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        api = _win32()
        if self._owns_instance:
            try:
                api.pipe.DisconnectNamedPipe(self._handle)
            except Exception:
                pass
        try:
            api.file.CloseHandle(self._handle)
        except Exception:
            pass


class NamedPipeTransport:
    """本番で使うトランスポート。

    アイドル判定のために ``ConnectNamedPipe`` をオーバーラップド I/O で行い、
    待機にタイムアウトを設ける（設計 5.4）。
    """

    def __init__(self, name: str | None = None, max_instances: int | None = None) -> None:
        self._name = name
        self._max_instances = max_instances
        self._pending = None
        self._event = None
        self._overlapped = None
        self._connected_immediately = False

    @property
    def name(self) -> str:
        if self._name is None:
            self._name = pipe_name_for_current_user()
        return self._name

    def listen(self) -> None:
        """最初のパイプインスタンスをここで作る。

        listen が返った時点でパイプが名前空間に現れるので、直後に接続してくる
        クライアントが「パイプが無い」で弾かれることがない。
        """
        if self._pending is not None:
            return
        self._begin_connect(_win32())

    def accept(self, timeout: float):
        api = _win32()
        if self._pending is None:
            self._begin_connect(api)
            if self._pending is None:
                return None
        if self._connected_immediately:
            return self._take_pending()

        waited = api.event.WaitForSingleObject(self._event, int(max(timeout, 0) * 1000))
        if waited != api.event.WAIT_OBJECT_0:
            return None
        return self._take_pending()

    def close(self) -> None:
        self._discard_pending()

    def _begin_connect(self, api: _Win32) -> None:
        self._connected_immediately = False
        self._pending = self._create_instance(api)
        self._event = api.event.CreateEvent(None, True, False, None)
        self._overlapped = api.types.OVERLAPPED()
        self._overlapped.hEvent = self._event
        try:
            api.pipe.ConnectNamedPipe(self._pending, self._overlapped)
        except api.types.error as exc:
            if exc.winerror == _ERROR_PIPE_CONNECTED:
                # accept を呼ぶ前にクライアントが繋いでいた場合。待たずに引き渡す。
                self._connected_immediately = True
                return
            if exc.winerror != _ERROR_IO_PENDING:
                self._discard_pending()
                raise ConnectionClosed(str(exc)) from exc

    def _create_instance(self, api: _Win32):
        max_instances = self._max_instances or api.pipe.PIPE_UNLIMITED_INSTANCES
        try:
            return api.pipe.CreateNamedPipe(
                self.name,
                api.pipe.PIPE_ACCESS_DUPLEX | api.file.FILE_FLAG_OVERLAPPED,
                api.pipe.PIPE_TYPE_MESSAGE | api.pipe.PIPE_READMODE_MESSAGE | api.pipe.PIPE_WAIT,
                max_instances,
                BUFFER_SIZE,
                BUFFER_SIZE,
                0,
                _security_attributes(api),
            )
        except api.types.error as exc:
            raise PipeUnavailableError(f"パイプを作成できませんでした: {exc}") from exc

    def _take_pending(self):
        handle = self._pending
        self._pending = None
        self._close_event()
        connection = PipeConnection(handle, owns_instance=True)
        # 次のインスタンスをすぐ用意する。インスタンスが 0 本になるとパイプ名自体が
        # 名前空間から消え、その隙に繋ぎにきたクライアントが「パイプが無い」で
        # 即座に弾かれてしまう（WaitNamedPipe は存在しない名前を待たない）。
        try:
            self._begin_connect(_win32())
        except Exception:
            self._pending = None
        return connection

    def _discard_pending(self) -> None:
        if self._pending is not None:
            api = _win32()
            try:
                api.pipe.DisconnectNamedPipe(self._pending)
            except Exception:
                pass
            try:
                api.file.CloseHandle(self._pending)
            except Exception:
                pass
            self._pending = None
        self._close_event()

    def _close_event(self) -> None:
        if self._event is not None:
            try:
                self._event.Close()
            except Exception:
                pass
            self._event = None
            self._overlapped = None


def connect_pipe(name: str, timeout: float) -> PipeConnection:
    """クライアント側からパイプに繋ぐ。

    サーバーが処理中でも ``WaitNamedPipe`` で順番待ちができる。時間切れなら
    ``PipeUnavailableError`` を送出し、呼び出し側がローカル実行に落ちる。
    """
    api = _win32()
    try:
        api.pipe.WaitNamedPipe(name, max(int(max(timeout, 0) * 1000), 1))
    except api.types.error as exc:
        raise PipeUnavailableError(f"常駐サーバーに接続できませんでした: {exc}") from exc
    try:
        handle = api.file.CreateFile(
            name,
            api.con.GENERIC_READ | api.con.GENERIC_WRITE,
            0,
            None,
            api.con.OPEN_EXISTING,
            0,
            None,
        )
        api.pipe.SetNamedPipeHandleState(handle, api.pipe.PIPE_READMODE_MESSAGE, None, None)
    except api.types.error as exc:
        raise PipeUnavailableError(f"常駐サーバーに接続できませんでした: {exc}") from exc
    return PipeConnection(handle, owns_instance=False)
