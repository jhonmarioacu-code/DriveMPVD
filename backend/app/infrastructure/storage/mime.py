"""Conservative bounded-prefix MIME detection without external processes."""

import mimetypes


class SignatureMimeDetector:
    def detect(self, prefix: bytes, *, filename: str) -> str:
        if not prefix:
            return "application/x-empty"
        signatures = (
            (b"%PDF-", "application/pdf"),
            (b"\x89PNG\r\n\x1a\n", "image/png"),
            (b"\xff\xd8\xff", "image/jpeg"),
            (b"GIF87a", "image/gif"),
            (b"GIF89a", "image/gif"),
            (b"PK\x03\x04", "application/zip"),
            (b"7z\xbc\xaf\x27\x1c", "application/x-7z-compressed"),
            (b"Rar!\x1a\x07", "application/vnd.rar"),
            (b"ID3", "audio/mpeg"),
        )
        for signature, mime_type in signatures:
            if prefix.startswith(signature):
                return mime_type
        if prefix.startswith(b"RIFF") and prefix[8:12] == b"WAVE":
            return "audio/wav"
        if prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP":
            return "image/webp"
        if len(prefix) >= 12 and prefix[4:8] == b"ftyp":
            return "video/mp4"
        if self._looks_like_text(prefix):
            guessed, _ = mimetypes.guess_type(filename)
            return (
                guessed
                if guessed is not None and guessed.startswith("text/")
                else "text/plain"
            )
        return "application/octet-stream"

    @staticmethod
    def _looks_like_text(prefix: bytes) -> bool:
        if b"\x00" in prefix:
            return False
        try:
            decoded = prefix.decode("utf-8")
        except UnicodeDecodeError:
            return False
        controls = sum(
            ord(character) < 32 and character not in "\n\r\t" for character in decoded
        )
        return controls / max(1, len(decoded)) < 0.01
