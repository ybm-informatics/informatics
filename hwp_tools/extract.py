from __future__ import annotations

import argparse
import json
import re
import zlib
from pathlib import Path
from typing import Any

import olefile


HWP_TEXT_RECORD = 67
COMPRESSED_FLAG = 1


def is_compressed(ole: olefile.OleFileIO) -> bool:
    header = ole.openstream("FileHeader").read()
    flags = int.from_bytes(header[36:40], "little")
    return bool(flags & COMPRESSED_FLAG)


def read_body_streams(ole: olefile.OleFileIO) -> list[bytes]:
    compressed = is_compressed(ole)
    streams: list[bytes] = []
    for entry in ole.listdir():
        if len(entry) == 2 and entry[0] == "BodyText" and entry[1].startswith("Section"):
            data = ole.openstream(entry).read()
            if compressed:
                data = zlib.decompress(data, -15)
            streams.append(data)
    return streams


def extract_text_from_stream(data: bytes) -> str:
    position = 0
    chunks: list[str] = []
    while position + 4 <= len(data):
        header = int.from_bytes(data[position : position + 4], "little")
        tag_id = header & 0x3FF
        size = (header >> 20) & 0xFFF
        position += 4
        if size == 0xFFF:
            if position + 4 > len(data):
                break
            size = int.from_bytes(data[position : position + 4], "little")
            position += 4
        payload = data[position : position + size]
        position += size
        if tag_id == HWP_TEXT_RECORD:
            text = payload.decode("utf-16le", errors="ignore")
            chunks.append(text)
    return "\n".join(chunks)


def normalize_text(text: str) -> str:
    text = text.replace("\x00", "")
    text = re.sub(r"[\x01-\x08\x0b-\x1f]+", "\n", text)
    text = re.sub(r"^[捤獥汤捯氠瑢漠杳\s]+", "", text)
    text = re.sub(r"^\s*漠杳\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_hwp(path: Path) -> dict[str, Any]:
    with olefile.OleFileIO(str(path)) as ole:
        streams = read_body_streams(ole)
        text = normalize_text("\n".join(extract_text_from_stream(stream) for stream in streams))
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return {
        "source_file": str(path),
        "line_count": len(lines),
        "text": text,
        "lines": lines,
    }


def convert_samples(input_dir: Path, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for path in sorted(input_dir.glob("*.hwp*")):
        extracted = extract_hwp(path)
        stem = path.name.replace(".hwp", "")
        txt_path = output_dir / f"{stem}.txt"
        json_path = output_dir / f"{stem}.json"
        txt_path.write_text(extracted["text"] + "\n", encoding="utf-8")
        json_path.write_text(json.dumps(extracted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.extend([txt_path, json_path])
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract text from HWP5 sample files.")
    parser.add_argument("--input-dir", type=Path, default=Path("inputs/middle_school_informatics/unit_3/samples"))
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("inputs/middle_school_informatics/unit_3/samples/converted"),
    )
    args = parser.parse_args()
    written = convert_samples(args.input_dir, args.output_dir)
    print("HWP 견본 변환을 완료했습니다.")
    for path in written:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
