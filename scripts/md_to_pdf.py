from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem, Preformatted
from reportlab.lib import colors


def convert_markdown_to_pdf(md_path: Path, pdf_path: Path) -> None:
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Mobile OS Memory Management System - Project Report",
        author="OS Course Project",
    )

    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "NormalCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        spaceAfter=6,
    )
    h1 = ParagraphStyle(
        "H1Custom",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0d1b2a"),
        spaceBefore=10,
        spaceAfter=10,
    )
    h2 = ParagraphStyle(
        "H2Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1b263b"),
        spaceBefore=8,
        spaceAfter=8,
    )
    h3 = ParagraphStyle(
        "H3Custom",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        textColor=colors.HexColor("#415a77"),
        spaceBefore=6,
        spaceAfter=6,
    )
    code_style = ParagraphStyle(
        "CodeCustom",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=8.6,
        leading=11,
        leftIndent=10,
        rightIndent=10,
        backColor=colors.HexColor("#f4f7fb"),
        borderColor=colors.HexColor("#d9e2ec"),
        borderWidth=0.5,
        borderPadding=5,
        spaceBefore=6,
        spaceAfter=6,
    )

    flow = []
    in_code = False
    code_buffer = []
    list_buffer = []

    def flush_list():
        nonlocal list_buffer
        if not list_buffer:
            return
        items = [ListItem(Paragraph(item, normal), leftIndent=8) for item in list_buffer]
        flow.append(ListFlowable(items, bulletType="bullet", leftIndent=14))
        flow.append(Spacer(1, 4))
        list_buffer = []

    def flush_code():
        nonlocal code_buffer
        if not code_buffer:
            return
        code_text = "\n".join(code_buffer)
        flow.append(Preformatted(code_text, code_style))
        flow.append(Spacer(1, 4))
        code_buffer = []

    for raw in lines:
        line = raw.rstrip()

        if line.strip().startswith("```"):
            flush_list()
            if in_code:
                flush_code()
                in_code = False
            else:
                in_code = True
            continue

        if in_code:
            code_buffer.append(line)
            continue

        if not line.strip():
            flush_list()
            flow.append(Spacer(1, 4))
            continue

        if line.startswith("# "):
            flush_list()
            flow.append(Paragraph(line[2:].strip(), h1))
            continue
        if line.startswith("## "):
            flush_list()
            flow.append(Paragraph(line[3:].strip(), h2))
            continue
        if line.startswith("### "):
            flush_list()
            flow.append(Paragraph(line[4:].strip(), h3))
            continue

        if line.lstrip().startswith("- "):
            list_buffer.append(line.lstrip()[2:].strip())
            continue

        if line.strip() == "---":
            flush_list()
            flow.append(Spacer(1, 10))
            continue

        flush_list()
        para = (
            line.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        para = para.replace("**", "")
        flow.append(Paragraph(para, normal))

    flush_list()
    flush_code()

    doc.build(flow)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    md = root / "PROJECT_REPORT.md"
    pdf = root / "PROJECT_REPORT.pdf"

    if not md.exists():
        raise FileNotFoundError(f"Missing markdown file: {md}")

    convert_markdown_to_pdf(md, pdf)
    print(f"PDF created: {pdf}")
