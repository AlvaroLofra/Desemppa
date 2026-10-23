"""Cifrado local de datos sensibles (texto original de la consulta, mapa de seudónimos, adjuntos).

En Windows usa DPAPI (CryptProtectData, ámbito del usuario): solo el mismo usuario de Windows en el mismo
equipo puede descifrar. En otros sistemas no hay cifrado (prefijo distinto) y se avisa en el log.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

log = logging.getLogger(__name__)
_DPAPI = b"DPAPI1:"
_PLAIN = b"PLAIN1:"


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _to_blob(data: bytes) -> _Blob:
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _from_blob(blob: _Blob) -> bytes:
    out = ctypes.string_at(blob.pbData, blob.cbData)
    ctypes.windll.kernel32.LocalFree(blob.pbData)
    return out


def encrypt(text: str) -> bytes:
    data = text.encode("utf-8")
    if sys.platform != "win32":
        log.warning("Cifrado DPAPI no disponible fuera de Windows: se guarda sin cifrar")
        return _PLAIN + data
    blob_in, blob_out = _to_blob(data), _Blob()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(blob_in), "iuris-ia", None, None, None, 0x01, ctypes.byref(blob_out)
    )
    if not ok:
        raise OSError("CryptProtectData falló")
    return _DPAPI + _from_blob(blob_out)


def decrypt(data: bytes) -> str:
    if data.startswith(_PLAIN):
        return data[len(_PLAIN) :].decode("utf-8")
    if not data.startswith(_DPAPI):
        raise ValueError("formato cifrado desconocido")
    blob_in, blob_out = _to_blob(data[len(_DPAPI) :]), _Blob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(blob_in), None, None, None, None, 0x01, ctypes.byref(blob_out)
    )
    if not ok:
        raise OSError("CryptUnprotectData falló (¿otro usuario o equipo?)")
    return _from_blob(blob_out).decode("utf-8")
