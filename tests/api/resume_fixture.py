"""测试时生成一份可被 pdfplumber / python-docx 读出的简历，不写入仓库。"""

import sys


def write_pdf(path: str, text: str) -> None:
    raw = text.encode("utf-16-be")
    hexstr = raw.hex().upper()
    content = f"BT /F1 12 Tf 72 720 Td <{hexstr}> Tj ET\n".encode("latin1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"endstream",
        b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UTF16-H /DescendantFonts [6 0 R] >>",
        b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light /CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> /FontDescriptor 7 0 R >>",
        b"<< /Type /FontDescriptor /FontName /STSong-Light /Flags 4 /FontBBox [0 0 1000 1000] /ItalicAngle 0 /Ascent 800 /Descent -200 /CapHeight 700 >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode("latin1") + obj + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("latin1")
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("latin1")
    out += (
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("latin1")
    )
    with open(path, "wb") as handle:
        handle.write(out)


def write_docx(path: str, text: str) -> None:
    from docx import Document

    document = Document()
    document.add_paragraph(text)
    document.save(path)


def main() -> None:
    kind, path, text = sys.argv[1], sys.argv[2], sys.argv[3]
    if kind == "pdf":
        write_pdf(path, text)
    elif kind == "docx":
        write_docx(path, text)
    else:
        raise SystemExit("kind 只能是 pdf 或 docx")


if __name__ == "__main__":
    main()
