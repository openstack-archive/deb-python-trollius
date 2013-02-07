/*
 * Support for overlapped IO
 *
 * Some code borrowed from Modules/_winapi.c of CPython
 */

/* XXX check overflow and DWORD <-> Py_ssize_t conversions
   Check itemsize */

#include "Python.h"
#include "structmember.h"

#define WINDOWS_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#include <mswsock.h>

#if defined(MS_WIN32) && !defined(MS_WIN64)
#  define F_POINTER "k"
#  define T_POINTER T_ULONG
#else
#  define F_POINTER "K"
#  define T_POINTER T_ULONGLONG
#endif

#define F_HANDLE F_POINTER
#define F_ULONG_PTR F_POINTER
#define F_DWORD "k"
#define F_BOOL "i"
#define F_UINT "I"

#define T_HANDLE T_POINTER

enum {TYPE_NONE, TYPE_NOT_STARTED, TYPE_READ, TYPE_WRITE, TYPE_ACCEPT,
      TYPE_CONNECT, TYPE_DISCONNECT};

/*
 * Map Windows error codes to subclasses of OSError
 */

static PyObject *
SetFromWindowsErr(DWORD err)
{
    PyObject *exception_type;

    if (err == 0)
        err = GetLastError();
    switch (err) {
        case ERROR_CONNECTION_REFUSED:
            exception_type = PyExc_ConnectionRefusedError;
            break;
        case ERROR_CONNECTION_ABORTED:
            exception_type = PyExc_ConnectionAbortedError;
            break;
        default:
            exception_type = PyExc_OSError;
    }
    return PyErr_SetExcFromWindowsErr(exception_type, err);
}

/*
 * Some functions should be loaded at runtime
 */

static LPFN_ACCEPTEX Py_AcceptEx = NULL;
static LPFN_CONNECTEX Py_ConnectEx = NULL;
static LPFN_DISCONNECTEX Py_DisconnectEx = NULL;
static BOOL (CALLBACK *Py_CancelIoEx)(HANDLE, LPOVERLAPPED) = NULL;

#define GET_WSA_POINTER(s, x)                                           \
    (SOCKET_ERROR != WSAIoctl(s, SIO_GET_EXTENSION_FUNCTION_POINTER,    \
                              &Guid##x, sizeof(Guid##x), &Py_##x,       \
                              sizeof(Py_##x), &dwBytes, NULL, NULL))

static int
initialize_function_pointers(void)
{
    GUID GuidAcceptEx = WSAID_ACCEPTEX;
    GUID GuidConnectEx = WSAID_CONNECTEX;
    GUID GuidDisconnectEx = WSAID_DISCONNECTEX;
    HINSTANCE hKernel32;
    SOCKET s;
    DWORD dwBytes;

    s = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (s == INVALID_SOCKET) {
        SetFromWindowsErr(WSAGetLastError());
        return -1;
    }

    if (!GET_WSA_POINTER(s, AcceptEx) ||
        !GET_WSA_POINTER(s, ConnectEx) ||
        !GET_WSA_POINTER(s, DisconnectEx))
    {
        closesocket(s);
        SetFromWindowsErr(WSAGetLastError());
        return -1;
    }

    closesocket(s);

    /* On WinXP we will have Py_CancelIoEx == NULL */
    hKernel32 = GetModuleHandle("KERNEL32");
    *(FARPROC *)&Py_CancelIoEx = GetProcAddress(hKernel32, "CancelIoEx");
    return 0;
}

/*
 * Completion port stuff
 */

PyDoc_STRVAR(
    CreateIoCompletionPort_doc,
    "CreateIoCompletionPort(handle, port, key, concurrency) -> port\n\n"
    "Create a completion port or register a handle with a port.");

static PyObject *
overlapped_CreateIoCompletionPort(PyObject *self, PyObject *args)
{
    HANDLE FileHandle;
    HANDLE ExistingCompletionPort;
    ULONG_PTR CompletionKey;
    DWORD NumberOfConcurrentThreads;
    HANDLE ret;

    if (!PyArg_ParseTuple(args, F_HANDLE F_HANDLE F_ULONG_PTR F_DWORD,
                          &FileHandle, &ExistingCompletionPort, &CompletionKey,
                          &NumberOfConcurrentThreads))
        return NULL;

    Py_BEGIN_ALLOW_THREADS
    ret = CreateIoCompletionPort(FileHandle, ExistingCompletionPort,
                                 CompletionKey, NumberOfConcurrentThreads);
    Py_END_ALLOW_THREADS

    if (ret == NULL)
        return SetFromWindowsErr(0);
    return Py_BuildValue(F_HANDLE, ret);
}

PyDoc_STRVAR(
    GetQueuedCompletionStatus_doc,
    "GetQueuedCompletionStatus(port, msecs) -> (err, bytes, key, address)\n\n"
    "Get a message from completion port.  Wait for up to msecs milliseconds.");

static PyObject *
overlapped_GetQueuedCompletionStatus(PyObject *self, PyObject *args)
{
    HANDLE CompletionPort = NULL;
    DWORD NumberOfBytes = 0;
    ULONG_PTR CompletionKey = 0;
    OVERLAPPED *Overlapped = NULL;
    DWORD Milliseconds;
    DWORD err;
    BOOL ret;

    if (!PyArg_ParseTuple(args, F_HANDLE F_DWORD,
                          &CompletionPort, &Milliseconds))
        return NULL;

    Py_BEGIN_ALLOW_THREADS
    ret = GetQueuedCompletionStatus(CompletionPort, &NumberOfBytes,
                                    &CompletionKey, &Overlapped, Milliseconds);
    Py_END_ALLOW_THREADS

    err = ret ? ERROR_SUCCESS : GetLastError();
    if (Overlapped == NULL) {
        if (err == WAIT_TIMEOUT)
            Py_RETURN_NONE;
        else
            return SetFromWindowsErr(err);
    }
    return Py_BuildValue(F_DWORD F_DWORD F_ULONG_PTR F_POINTER,
                         err, NumberOfBytes, CompletionKey, Overlapped);
}

PyDoc_STRVAR(
    PostQueuedCompletionStatus_doc,
    "PostQueuedCompletionStatus(port, bytes, key, address) -> None\n\n"
    "Post a message to completion port.");

static PyObject *
overlapped_PostQueuedCompletionStatus(PyObject *self, PyObject *args)
{
    HANDLE CompletionPort;
    DWORD NumberOfBytes;
    ULONG_PTR CompletionKey;
    OVERLAPPED *Overlapped;
    BOOL ret;

    if (!PyArg_ParseTuple(args, F_HANDLE F_DWORD F_ULONG_PTR F_POINTER,
                          &CompletionPort, &NumberOfBytes, &CompletionKey,
                          &Overlapped))
        return NULL;

    Py_BEGIN_ALLOW_THREADS
    ret = PostQueuedCompletionStatus(CompletionPort, NumberOfBytes,
                                     CompletionKey, Overlapped);
    Py_END_ALLOW_THREADS

    if (!ret)
        return SetFromWindowsErr(0);
    Py_RETURN_NONE;
}

/*
 * Bind socket handle to local port without doing slow getaddrinfo()
 */

PyDoc_STRVAR(
    BindLocal_doc,
    "BindLocal(handle, length_of_address_tuple) -> None\n\n"
    "Bind a socket handle to an arbitrary local port.\n"
    "If length_of_address_tuple is 2 then an AF_INET address is used.\n"
    "If length_of_address_tuple is 4 then an AF_INET6 address is used.");

static PyObject *
overlapped_BindLocal(PyObject *self, PyObject *args)
{
    SOCKET Socket;
    int TupleLength;
    BOOL ret;

    if (!PyArg_ParseTuple(args, F_HANDLE "i", &Socket, &TupleLength))
        return NULL;

    if (TupleLength == 2) {
        struct sockaddr_in addr;
        memset(&addr, 0, sizeof(addr));
        addr.sin_family = AF_INET;
        addr.sin_port = 0;
        addr.sin_addr.S_un.S_addr = INADDR_ANY;
        ret = bind(Socket, (SOCKADDR*)&addr, sizeof(addr)) != SOCKET_ERROR;
    } else if (TupleLength == 4) {
        struct sockaddr_in6 addr;
        memset(&addr, 0, sizeof(addr));
        addr.sin6_family = AF_INET6;
        addr.sin6_port = 0;
        addr.sin6_addr = in6addr_any;
        ret = bind(Socket, (SOCKADDR*)&addr, sizeof(addr)) != SOCKET_ERROR;
    } else {
        PyErr_SetString(PyExc_ValueError, "expected tuple of length 2 or 4");
        return NULL;
    }

    if (!ret)
        return SetFromWindowsErr(WSAGetLastError());
    Py_RETURN_NONE;
}

/*
 * Set notification mode for the handle
 */

PyDoc_STRVAR(
    SetFileCompletionNotificationModes_doc,
    "SetFileCompletionNotificationModes(FileHandle, Flags) -> None\n\n"
    "Set whether notification happens if operation succeeds without blocking");

static PyObject *
overlapped_SetFileCompletionNotificationModes(PyObject *self, PyObject *args)
{
    HANDLE FileHandle;
    UCHAR Flags;

    if (!PyArg_ParseTuple(args, F_HANDLE F_BOOL, &FileHandle, &Flags))
        return NULL;

    if (!SetFileCompletionNotificationModes(FileHandle, Flags))
        return SetFromWindowsErr(0);

    Py_RETURN_NONE;
}

/*
 * A Python object wrapping an OVERLAPPED structure and other useful data
 * for overlapped I/O
 */

PyDoc_STRVAR(
    Overlapped_doc,
    "Overlapped object");

typedef struct {
    PyObject_HEAD
    OVERLAPPED overlapped;
    /* For convenience, we store the file handle too */
    HANDLE handle;
    /* Error returned by last method call */
    DWORD error;
    /* Type of operation */
    DWORD type;
    /* Buffer used for reading (optional) */
    PyObject *read_buffer;
    /* Buffer used for writing (optional) */
    Py_buffer write_buffer;
} OverlappedObject;


static PyObject *
Overlapped_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    OverlappedObject *self;
    HANDLE event = INVALID_HANDLE_VALUE;
    static char *kwlist[] = {"event", NULL};

    if (!PyArg_ParseTupleAndKeywords(args, kwds, "|" F_HANDLE, kwlist, &event))
        return NULL;

    if (event == INVALID_HANDLE_VALUE) {
        event = CreateEvent(NULL, TRUE, FALSE, NULL);
        if (event == NULL)
            return SetFromWindowsErr(0);
    }

    self = PyObject_New(OverlappedObject, type);
    if (self == NULL) {
        if (event != NULL)
            CloseHandle(event);
        return NULL;
    }

    self->handle = NULL;
    self->error = 0;
    self->type = TYPE_NONE;
    self->read_buffer = NULL;
    memset(&self->overlapped, 0, sizeof(OVERLAPPED));
    memset(&self->write_buffer, 0, sizeof(Py_buffer));
    if (event)
        self->overlapped.hEvent = event;
    return (PyObject *)self;
}

static void
Overlapped_dealloc(OverlappedObject *self)
{
    DWORD bytes;
    DWORD olderr = GetLastError();
    BOOL wait = FALSE;
    BOOL ret;

    if (!HasOverlappedIoCompleted(&self->overlapped) &&
        self->type != TYPE_NOT_STARTED)
    {
        if (Py_CancelIoEx && Py_CancelIoEx(self->handle, &self->overlapped))
            wait = TRUE;

        Py_BEGIN_ALLOW_THREADS
        ret = GetOverlappedResult(self->handle, &self->overlapped,
                                  &bytes, wait);
        Py_END_ALLOW_THREADS

        switch (ret ? ERROR_SUCCESS : GetLastError()) {
            case ERROR_SUCCESS:
            case ERROR_NOT_FOUND:
            case ERROR_OPERATION_ABORTED:
                break;
            default:
                PyErr_Format(
                    PyExc_RuntimeError,
                    "%R still has pending operation at "
                    "deallocation, the process may crash", self);
                PyErr_WriteUnraisable(NULL);
        }
    }

    if (self->overlapped.hEvent != NULL)
        CloseHandle(self->overlapped.hEvent);

    if (self->write_buffer.obj)
        PyBuffer_Release(&self->write_buffer);

    Py_CLEAR(self->read_buffer);
    PyObject_Del(self);
    SetLastError(olderr);
}

PyDoc_STRVAR(
    Overlapped_cancel_doc,
    "cancel() -> None\n\n"
    "Cancel overlapped operation");

static PyObject *
Overlapped_cancel(OverlappedObject *self)
{
    BOOL ret = TRUE;

    if (self->type == TYPE_NOT_STARTED)
        Py_RETURN_NONE;

    if (!HasOverlappedIoCompleted(&self->overlapped)) {
        Py_BEGIN_ALLOW_THREADS
        if (Py_CancelIoEx)
            ret = Py_CancelIoEx(self->handle, &self->overlapped);
        else
            ret = CancelIo(self->handle);
        Py_END_ALLOW_THREADS
    }

    /* CancelIoEx returns ERROR_NOT_FOUND if the I/O completed in-between */
    if (!ret && GetLastError() != ERROR_NOT_FOUND)
        return SetFromWindowsErr(0);
    Py_RETURN_NONE;
}

PyDoc_STRVAR(
    Overlapped_getresult_doc,
    "getresult(wait=False) -> result\n\n"
    "Retrieve result of operation.  If wait is true then it blocks\n"
    "until the operation is finished.  If wait is false and the\n"
    "operation is still pending then an error is raised.");

static PyObject *
Overlapped_getresult(OverlappedObject *self, PyObject *args)
{
    BOOL wait = FALSE;
    DWORD transferred = 0;
    BOOL ret;
    DWORD err;

    if (!PyArg_ParseTuple(args, "|" F_BOOL, &wait))
        return NULL;

    if (self->type == TYPE_NONE) {
        PyErr_SetString(PyExc_ValueError, "operation not yet attempted");
        return NULL;
    }

    if (self->type == TYPE_NOT_STARTED) {
        PyErr_SetString(PyExc_ValueError, "operation failed to start");
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS
    ret = GetOverlappedResult(self->handle, &self->overlapped, &transferred,
                              wait);
    Py_END_ALLOW_THREADS

    self->error = err = ret ? ERROR_SUCCESS : GetLastError();
    switch (err) {
        case ERROR_SUCCESS:
        case ERROR_MORE_DATA:
            break;
        case ERROR_BROKEN_PIPE:
            if (self->read_buffer != NULL)
                break;
            /* fall through */
        default:
            return SetFromWindowsErr(err);
    }

    switch (self->type) {
        case TYPE_READ:
            assert(PyBytes_CheckExact(self->read_buffer));
            if (transferred != PyBytes_GET_SIZE(self->read_buffer) &&
                _PyBytes_Resize(&self->read_buffer, transferred))
                return NULL;
            Py_INCREF(self->read_buffer);
            return self->read_buffer;
        case TYPE_ACCEPT:
        case TYPE_CONNECT:
        case TYPE_DISCONNECT:
            Py_RETURN_NONE;
        default:
            return PyLong_FromUnsignedLong((unsigned long) transferred);
    }
}

PyDoc_STRVAR(
    Overlapped_ReadFile_doc,
    "ReadFile(handle, size) -> Overlapped[message]\n\n"
    "Start overlapped read");

static PyObject *
Overlapped_ReadFile(OverlappedObject *self, PyObject *args)
{
    HANDLE handle;
    DWORD size;
    DWORD nread;
    PyObject *buf;
    BOOL ret;
    DWORD err;

    if (!PyArg_ParseTuple(args, F_HANDLE F_DWORD, &handle, &size))
        return NULL;

    if (self->type != TYPE_NONE) {
        PyErr_SetString(PyExc_ValueError, "operation already attempted");
        return NULL;
    }

#if SIZEOF_SIZE_T <= SIZEOF_LONG
    size = Py_MIN(size, (DWORD)PY_SSIZE_T_MAX);
#endif
    buf = PyBytes_FromStringAndSize(NULL, Py_MAX(size, 1));
    if (buf == NULL)
        return NULL;

    self->type = TYPE_READ;
    self->handle = handle;
    self->read_buffer = buf;

    Py_BEGIN_ALLOW_THREADS
    ret = ReadFile(handle, PyBytes_AS_STRING(buf), size, &nread,
                   &self->overlapped);
    Py_END_ALLOW_THREADS

    self->error = err = ret ? ERROR_SUCCESS : GetLastError();
    switch (err) {
        case ERROR_BROKEN_PIPE:
            self->type = TYPE_NOT_STARTED;
            Py_RETURN_NONE;
        case ERROR_SUCCESS:
        case ERROR_MORE_DATA:
        case ERROR_IO_PENDING:
            Py_RETURN_NONE;
        default:
            self->type = TYPE_NOT_STARTED;
            return SetFromWindowsErr(err);
    }
}

PyDoc_STRVAR(
    Overlapped_WSARecv_doc,
    "RecvFile(handle, size, flags) -> Overlapped[message]\n\n"
    "Start overlapped receive");

static PyObject *
Overlapped_WSARecv(OverlappedObject *self, PyObject *args)
{
    HANDLE handle;
    DWORD size;
    DWORD flags = 0;
    DWORD nread;
    PyObject *buf;
    WSABUF wsabuf;
    int ret;
    DWORD err;

    if (!PyArg_ParseTuple(args, F_HANDLE F_DWORD "|" F_DWORD,
                          &handle, &size, &flags))
        return NULL;

    if (self->type != TYPE_NONE) {
        PyErr_SetString(PyExc_ValueError, "operation already attempted");
        return NULL;
    }

#if SIZEOF_SIZE_T <= SIZEOF_LONG
    size = Py_MIN(size, (DWORD)PY_SSIZE_T_MAX);
#endif
    buf = PyBytes_FromStringAndSize(NULL, Py_MAX(size, 1));
    if (buf == NULL)
        return NULL;

    self->type = TYPE_READ;
    self->handle = handle;
    self->read_buffer = buf;
    wsabuf.len = size;
    wsabuf.buf = PyBytes_AS_STRING(buf);

    Py_BEGIN_ALLOW_THREADS
    ret = WSARecv((SOCKET)handle, &wsabuf, 1, &nread, &flags,
                  &self->overlapped, NULL);
    Py_END_ALLOW_THREADS

    self->error = err = (ret < 0 ? WSAGetLastError() : ERROR_SUCCESS);
    switch (err) {
        case ERROR_BROKEN_PIPE:
            self->type = TYPE_NOT_STARTED;
            Py_RETURN_NONE;
        case ERROR_SUCCESS:
        case ERROR_MORE_DATA:
        case ERROR_IO_PENDING:
            Py_RETURN_NONE;
        default:
            self->type = TYPE_NOT_STARTED;
            return SetFromWindowsErr(err);
    }
}

PyDoc_STRVAR(
    Overlapped_WriteFile_doc,
    "WriteFile(handle, buf) -> Overlapped[bytes_transferred]\n\n"
    "Start overlapped write");

static PyObject *
Overlapped_WriteFile(OverlappedObject *self, PyObject *args)
{
    HANDLE handle;
    PyObject *bufobj;
    DWORD written;
    BOOL ret;
    DWORD err;

    if (!PyArg_ParseTuple(args, F_HANDLE "O", &handle, &bufobj))
        return NULL;

    if (self->type != TYPE_NONE) {
        PyErr_SetString(PyExc_ValueError, "operation already attempted");
        return NULL;
    }

    if (!PyArg_Parse(bufobj, "y*", &self->write_buffer))
        return NULL;

#if SIZEOF_SIZE_T > SIZEOF_LONG
    if (self->write_buffer.len > (Py_ssize_t)ULONG_MAX) {
        PyBuffer_Release(&self->write_buffer);
        PyErr_SetString(PyExc_ValueError, "buffer to large");
        return NULL;
    }
#endif

    self->type = TYPE_WRITE;
    self->handle = handle;

    Py_BEGIN_ALLOW_THREADS
    ret = WriteFile(handle, self->write_buffer.buf, self->write_buffer.len,
                    &written, &self->overlapped);
    Py_END_ALLOW_THREADS

    self->error = err = ret ? ERROR_SUCCESS : GetLastError();
    switch (err) {
        case ERROR_SUCCESS:
        case ERROR_IO_PENDING:
            Py_RETURN_NONE;
        default:
            self->type = TYPE_NOT_STARTED;
            return SetFromWindowsErr(err);
    }
}

PyDoc_STRVAR(
    Overlapped_WSASend_doc,
    "WSASend(handle, buf, flags) -> Overlapped[bytes_transferred]\n\n"
    "Start overlapped send");

static PyObject *
Overlapped_WSASend(OverlappedObject *self, PyObject *args)
{
    HANDLE handle;
    PyObject *bufobj;
    DWORD flags;
    DWORD written;
    WSABUF wsabuf;
    int ret;
    DWORD err;

    if (!PyArg_ParseTuple(args, F_HANDLE "O" F_DWORD,
                          &handle, &bufobj, &flags))
        return NULL;

    if (self->type != TYPE_NONE) {
        PyErr_SetString(PyExc_ValueError, "operation already attempted");
        return NULL;
    }

    if (!PyArg_Parse(bufobj, "y*", &self->write_buffer))
        return NULL;

#if SIZEOF_SIZE_T > SIZEOF_LONG
    if (self->write_buffer.len > (Py_ssize_t)PY_ULONG_MAX) {
        PyBuffer_Release(&self->write_buffer);
        PyErr_SetString(PyExc_ValueError, "buffer to large");
        return NULL;
    }
#endif

    self->type = TYPE_WRITE;
    self->handle = handle;
    wsabuf.len = (DWORD)self->write_buffer.len;
    wsabuf.buf = self->write_buffer.buf;

    Py_BEGIN_ALLOW_THREADS
    ret = WSASend((SOCKET)handle, &wsabuf, 1, &written, flags,
                  &self->overlapped, NULL);
    Py_END_ALLOW_THREADS

    self->error = err = (ret < 0 ? WSAGetLastError() : ERROR_SUCCESS);
    switch (err) {
        case ERROR_SUCCESS:
        case ERROR_IO_PENDING:
            Py_RETURN_NONE;
        default:
            self->type = TYPE_NOT_STARTED;
            return SetFromWindowsErr(err);
    }
}

PyDoc_STRVAR(
    Overlapped_AcceptEx_doc,
    "AcceptEx(listen_handle, accept_handle) -> Overlapped[address_as_bytes]\n\n"
    "Start overlapped wait for client to connect");

static PyObject *
Overlapped_AcceptEx(OverlappedObject *self, PyObject *args)
{
    SOCKET ListenSocket;
    SOCKET AcceptSocket;
    DWORD BytesReceived;
    DWORD size;
    PyObject *buf;
    BOOL ret;
    DWORD err;

    if (!PyArg_ParseTuple(args, F_HANDLE F_HANDLE,
                          &ListenSocket, &AcceptSocket))
        return NULL;

    if (self->type != TYPE_NONE) {
        PyErr_SetString(PyExc_ValueError, "operation already attempted");
        return NULL;
    }

    size = sizeof(struct sockaddr_in6) + 16;
    buf = PyBytes_FromStringAndSize(NULL, size*2);
    if (!buf)
        return NULL;

    self->type = TYPE_ACCEPT;
    self->handle = (HANDLE)ListenSocket;
    self->read_buffer = buf;

    Py_BEGIN_ALLOW_THREADS
    ret = Py_AcceptEx(ListenSocket, AcceptSocket, PyBytes_AS_STRING(buf),
                      0, size, size, &BytesReceived, &self->overlapped);
    Py_END_ALLOW_THREADS

    self->error = err = ret ? ERROR_SUCCESS : WSAGetLastError();
    switch (err) {
        case ERROR_SUCCESS:
        case ERROR_IO_PENDING:
            Py_RETURN_NONE;
        default:
            self->type = TYPE_NOT_STARTED;
            return SetFromWindowsErr(err);
    }
}


static int
parse_address(PyObject *obj, SOCKADDR *Address, int Length)
{
    char *Host;
    unsigned short Port;
    unsigned long FlowInfo;
    unsigned long ScopeId;

    memset(Address, 0, Length);

    if (PyArg_ParseTuple(obj, "sH", &Host, &Port))
    {
        Address->sa_family = AF_INET;
        if (WSAStringToAddressA(Host, AF_INET, NULL, Address, &Length) < 0) {
            SetFromWindowsErr(WSAGetLastError());
            return -1;
        }
        ((SOCKADDR_IN*)Address)->sin_port = htons(Port);
        return Length;
    }
    else if (PyArg_ParseTuple(obj, "sHkk", &Host, &Port, &FlowInfo, &ScopeId))
    {
        PyErr_Clear();
        Address->sa_family = AF_INET6;
        if (WSAStringToAddressA(Host, AF_INET6, NULL, Address, &Length) < 0) {
            SetFromWindowsErr(WSAGetLastError());
            return -1;
        }
        ((SOCKADDR_IN6*)Address)->sin6_port = htons(Port);
        ((SOCKADDR_IN6*)Address)->sin6_flowinfo = FlowInfo;
        ((SOCKADDR_IN6*)Address)->sin6_scope_id = ScopeId;
        return Length;
    }

    return -1;
}


PyDoc_STRVAR(
    Overlapped_ConnectEx_doc,
    "ConnectEx(client_handle, address_as_bytes) -> Overlapped[None]\n\n"
    "Start overlapped connect.  client_handle should be unbound.");

static PyObject *
Overlapped_ConnectEx(OverlappedObject *self, PyObject *args)
{
    SOCKET ConnectSocket;
    PyObject *AddressObj;
    char AddressBuf[sizeof(struct sockaddr_in6)];
    SOCKADDR *Address = (SOCKADDR*)AddressBuf;
    int Length;
    BOOL ret;
    DWORD err;

    if (!PyArg_ParseTuple(args, F_HANDLE "O", &ConnectSocket, &AddressObj))
        return NULL;

    if (self->type != TYPE_NONE) {
        PyErr_SetString(PyExc_ValueError, "operation already attempted");
        return NULL;
    }

    Length = sizeof(AddressBuf);
    Length = parse_address(AddressObj, Address, Length);
    if (Length < 0)
        return NULL;

    self->type = TYPE_CONNECT;
    self->handle = (HANDLE)ConnectSocket;

    Py_BEGIN_ALLOW_THREADS
    ret = Py_ConnectEx(ConnectSocket, Address, Length,
                       NULL, 0, NULL, &self->overlapped);
    Py_END_ALLOW_THREADS

    self->error = err = ret ? ERROR_SUCCESS : WSAGetLastError();
    switch (err) {
        case ERROR_SUCCESS:
        case ERROR_IO_PENDING:
            Py_RETURN_NONE;
        default:
            self->type = TYPE_NOT_STARTED;
            return SetFromWindowsErr(err);
    }
}

PyDoc_STRVAR(
    Overlapped_DisconnectEx_doc,
    "DisconnectEx(handle, flags) -> Overlapped[None]\n\n"
    "Start overlapped connect.  client_handle should be unbound.");

static PyObject *
Overlapped_DisconnectEx(OverlappedObject *self, PyObject *args)
{
    SOCKET Socket;
    DWORD flags;
    BOOL ret;
    DWORD err;

    if (!PyArg_ParseTuple(args, F_HANDLE F_DWORD, &Socket, &flags))
        return NULL;

    if (self->type != TYPE_NONE) {
        PyErr_SetString(PyExc_ValueError, "operation already attempted");
        return NULL;
    }

    self->type = TYPE_DISCONNECT;
    self->handle = (HANDLE)Socket;

    Py_BEGIN_ALLOW_THREADS
    ret = Py_DisconnectEx(Socket, &self->overlapped, flags, 0);
    Py_END_ALLOW_THREADS

    self->error = err = ret ? ERROR_SUCCESS : WSAGetLastError();
    switch (err) {
        case ERROR_SUCCESS:
        case ERROR_IO_PENDING:
            Py_RETURN_NONE;
        default:
            self->type = TYPE_NOT_STARTED;
            return SetFromWindowsErr(err);
    }
}

static PyObject*
Overlapped_getaddress(OverlappedObject *self)
{
    return PyLong_FromVoidPtr(&self->overlapped);
}

static PyObject*
Overlapped_getpending(OverlappedObject *self)
{
    return PyBool_FromLong(!HasOverlappedIoCompleted(&self->overlapped) &&
                           self->type != TYPE_NOT_STARTED);
}

static PyMethodDef Overlapped_methods[] = {
    {"getresult", (PyCFunction) Overlapped_getresult,
     METH_VARARGS, Overlapped_getresult_doc},
    {"cancel", (PyCFunction) Overlapped_cancel,
     METH_NOARGS, Overlapped_cancel_doc},
    {"ReadFile", (PyCFunction) Overlapped_ReadFile,
     METH_VARARGS, Overlapped_ReadFile_doc},
    {"WSARecv", (PyCFunction) Overlapped_WSARecv,
     METH_VARARGS, Overlapped_WSARecv_doc},
    {"WriteFile", (PyCFunction) Overlapped_WriteFile,
     METH_VARARGS, Overlapped_WriteFile_doc},
    {"WSASend", (PyCFunction) Overlapped_WSASend,
     METH_VARARGS, Overlapped_WSASend_doc},
    {"AcceptEx", (PyCFunction) Overlapped_AcceptEx,
     METH_VARARGS, Overlapped_AcceptEx_doc},
    {"ConnectEx", (PyCFunction) Overlapped_ConnectEx,
     METH_VARARGS, Overlapped_ConnectEx_doc},
    {"DisconnectEx", (PyCFunction) Overlapped_DisconnectEx,
     METH_VARARGS, Overlapped_DisconnectEx_doc},
    {NULL}
};

static PyMemberDef Overlapped_members[] = {
    {"error", T_ULONG,
     offsetof(OverlappedObject, error),
     READONLY, "Error from last operation"},
    {"event", T_HANDLE,
     offsetof(OverlappedObject, overlapped) + offsetof(OVERLAPPED, hEvent),
     READONLY, "Overlapped event handle"},
    {NULL}
};

static PyGetSetDef Overlapped_getsets[] = {
    {"address", (getter)Overlapped_getaddress, NULL,
     "Address of overlapped structure"},
    {"pending", (getter)Overlapped_getpending, NULL,
     "Whether the operation is pending"},
    {NULL},
};

PyTypeObject OverlappedType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    /* tp_name           */ "_overlapped.Overlapped",
    /* tp_basicsize      */ sizeof(OverlappedObject),
    /* tp_itemsize       */ 0,
    /* tp_dealloc        */ (destructor) Overlapped_dealloc,
    /* tp_print          */ 0,
    /* tp_getattr        */ 0,
    /* tp_setattr        */ 0,
    /* tp_reserved       */ 0,
    /* tp_repr           */ 0,
    /* tp_as_number      */ 0,
    /* tp_as_sequence    */ 0,
    /* tp_as_mapping     */ 0,
    /* tp_hash           */ 0,
    /* tp_call           */ 0,
    /* tp_str            */ 0,
    /* tp_getattro       */ 0,
    /* tp_setattro       */ 0,
    /* tp_as_buffer      */ 0,
    /* tp_flags          */ Py_TPFLAGS_DEFAULT,
    /* tp_doc            */ "OVERLAPPED structure wrapper",
    /* tp_traverse       */ 0,
    /* tp_clear          */ 0,
    /* tp_richcompare    */ 0,
    /* tp_weaklistoffset */ 0,
    /* tp_iter           */ 0,
    /* tp_iternext       */ 0,
    /* tp_methods        */ Overlapped_methods,
    /* tp_members        */ Overlapped_members,
    /* tp_getset         */ Overlapped_getsets,
    /* tp_base           */ 0,
    /* tp_dict           */ 0,
    /* tp_descr_get      */ 0,
    /* tp_descr_set      */ 0,
    /* tp_dictoffset     */ 0,
    /* tp_init           */ 0,
    /* tp_alloc          */ 0,
    /* tp_new            */ Overlapped_new,
};

static PyMethodDef overlapped_functions[] = {
    {"CreateIoCompletionPort", overlapped_CreateIoCompletionPort,
     METH_VARARGS, CreateIoCompletionPort_doc},
    {"GetQueuedCompletionStatus", overlapped_GetQueuedCompletionStatus,
     METH_VARARGS, GetQueuedCompletionStatus_doc},
    {"PostQueuedCompletionStatus", overlapped_PostQueuedCompletionStatus,
     METH_VARARGS, PostQueuedCompletionStatus_doc},
    {"BindLocal", overlapped_BindLocal,
     METH_VARARGS, BindLocal_doc},
    {"SetFileCompletionNotificationModes",
     overlapped_SetFileCompletionNotificationModes,
     METH_VARARGS, SetFileCompletionNotificationModes_doc},
    {NULL}
};

static struct PyModuleDef overlapped_module = {
    PyModuleDef_HEAD_INIT,
    "_overlapped",
    NULL,
    -1,
    overlapped_functions,
    NULL,
    NULL,
    NULL,
    NULL
};

#define WINAPI_CONSTANT(fmt, con) \
    PyDict_SetItemString(d, #con, Py_BuildValue(fmt, con))

PyMODINIT_FUNC
PyInit__overlapped(void)
{
    PyObject *m, *d;

    /* Ensure WSAStartup() called before initializing function pointers */
    m = PyImport_ImportModule("_socket");
    if (!m)
        return NULL;
    Py_DECREF(m);

    if (initialize_function_pointers() < 0)
        return NULL;

    if (PyType_Ready(&OverlappedType) < 0)
        return NULL;

    m = PyModule_Create(&overlapped_module);
    if (PyModule_AddObject(m, "Overlapped", (PyObject *)&OverlappedType) < 0)
        return NULL;

    d = PyModule_GetDict(m);

    WINAPI_CONSTANT(F_DWORD,  ERROR_IO_PENDING);
    WINAPI_CONSTANT(F_DWORD,  FILE_SKIP_COMPLETION_PORT_ON_SUCCESS);
    WINAPI_CONSTANT(F_DWORD,  INFINITE);
    WINAPI_CONSTANT(F_HANDLE, INVALID_HANDLE_VALUE);
    WINAPI_CONSTANT(F_HANDLE, NULL);
    WINAPI_CONSTANT(F_DWORD,  SO_UPDATE_ACCEPT_CONTEXT);
    WINAPI_CONSTANT(F_DWORD,  SO_UPDATE_CONNECT_CONTEXT);
    WINAPI_CONSTANT(F_DWORD,  TF_REUSE_SOCKET);

    return m;
}
