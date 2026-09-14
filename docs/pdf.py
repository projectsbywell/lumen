"""Gera examples/book/LIVRO.pdf a partir de LIVRO.md + tutorials. Uso: python3 docs/pdf.py"""
import glob
import os
import re
import sys

VERSAO = "0.5.3"

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate,
                                    Paragraph, Preformatted, Spacer, Table,
                                    TableStyle, PageBreak)
    from reportlab.lib import colors
except ImportError:
    sys.exit("erro: reportlab não instalado (pip install reportlab)")

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
W, H = A4


def md_inline(s):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"`(.+?)`", r'<font face="Courier">\1</font>', s)
    return s


def md_table(lines, styles):
    rows = []
    for ln in lines:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        rows.append([Paragraph(md_inline(c), styles["body"]) for c in cells])
    t = Table(rows, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#222222")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def md_to_flow(text, styles):
    flow = []
    lines = text.splitlines()
    i = 0
    in_code, buf = False, []
    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            if in_code:
                flow.append(Preformatted("\n".join(buf), styles["code"]))
                buf = []
            in_code = not in_code
            i += 1
            continue
        if in_code:
            buf.append(ln)
            i += 1
            continue
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1]):
            tbl = [ln, lines[i + 1]]
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                tbl.append(lines[i])
                i += 1
            flow.append(md_table([tbl[0]] + tbl[2:], styles))
            flow.append(Spacer(1, 0.3 * cm))
            continue
        if ln.startswith("# "):
            flow.append(Paragraph(md_inline(ln[2:]), styles["h1"]))
        elif ln.startswith("## "):
            flow.append(Paragraph(md_inline(ln[3:]), styles["h2"]))
        elif ln.startswith("### "):
            flow.append(Paragraph(md_inline(ln[4:]), styles["h3"]))
        elif ln.strip().startswith(("- ", "* ")):
            flow.append(Paragraph("• " + md_inline(ln.strip()[2:]), styles["body"]))
        elif ln.strip() == "":
            flow.append(Spacer(1, 0.2 * cm))
        else:
            flow.append(Paragraph(md_inline(ln), styles["body"]))
        i += 1
    return flow


def foot(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.drawString(2 * cm, 1.2 * cm, f"Lumen v{VERSAO} — livro didático (público iniciante)")
    canvas.drawRightString(W - 2 * cm, 1.2 * cm, str(doc.page))
    canvas.restoreState()


def main():
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20,
                        spaceBefore=14, spaceAfter=8)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=15,
                        spaceBefore=10, spaceAfter=6)
    h3 = ParagraphStyle("h3", parent=styles["Heading3"], fontSize=12,
                        spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10,
                          leading=14)
    code = ParagraphStyle("code", parent=styles["Code"], fontName="Courier",
                          fontSize=8.5, leading=11, backColor=colors.HexColor("#f4f4f4"),
                          borderPadding=6)
    st = {"h1": h1, "h2": h2, "h3": h3, "body": body, "code": code}

    livro = os.path.join(ROOT, "examples", "book", "LIVRO.md")
    if not os.path.isfile(livro):
        sys.exit(f"erro: fonte obrigatória ausente: {livro}")
    tuts = sorted(glob.glob(os.path.join(ROOT, "examples", "tutorials", "*.md")))
    if not tuts:
        sys.exit("erro: nenhum tutorial encontrado em examples/tutorials/*.md")
    parts = [livro] + tuts
    missing = [p for p in parts if not os.path.isfile(p)]
    if missing:
        sys.exit("erro: fontes ausentes: " + ", ".join(missing))
    flow = []
    for p in parts:
        if flow:
            flow.append(PageBreak())
        flow.extend(md_to_flow(open(p, encoding="utf8").read(), st))
    if not flow:
        sys.exit("erro: zero fontes renderizadas, PDF não gerado")

    out = os.path.join(ROOT, "examples", "book", "LIVRO.pdf")
    doc = BaseDocTemplate(out, pagesize=A4,
                          leftMargin=2 * cm, rightMargin=2 * cm,
                          topMargin=2 * cm, bottomMargin=2 * cm,
                          title=f"Lumen v{VERSAO} — do zero ao avançado", author="Lumen")
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="f")
    doc.addPageTemplates([PageTemplate(id="p", frames=[frame], onPage=foot)])
    doc.build(flow)
    print(f"PDF: {out} ({os.path.getsize(out)} bytes, {len(parts)} fontes)")


if __name__ == "__main__":
    main()
