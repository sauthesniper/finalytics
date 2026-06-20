"""
Report generation for US11 — export a company report as JSON or PDF.

PDF generation uses fpdf2 (pure Python, no system dependencies). The
report bundles the Collaboration Health Score, the explainability
pillars and both AI agent assessments.
"""
from datetime import datetime, timezone
from typing import Dict, Any

from fpdf import FPDF
from fpdf.enums import XPos, YPos


def build_report_data(cui: str, company_name: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble the canonical JSON report structure."""
    score = (analysis or {}).get("score") or {}
    return {
        "report": "Finalytics Company Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "company": {
            "cui": cui or score.get("cui"),
            "name": company_name or score.get("company_name"),
        },
        "collaboration_score": {
            "score": score.get("score"),
            "band": score.get("band"),
            "pillars": score.get("pillars", []),
            "positives": score.get("positives", []),
            "negatives": score.get("negatives", []),
            "missing_data": score.get("missing_data", []),
        },
        "risk_analyst": (analysis or {}).get("risk_analyst", {}),
        "sales_strategist": (analysis or {}).get("sales_strategist", {}),
    }


def _ascii(text: Any) -> str:
    """fpdf core fonts are latin-1; strip unsupported chars safely."""
    s = str(text if text is not None else "")
    return s.encode("latin-1", "replace").decode("latin-1")


class _ReportPDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(249, 115, 22)
        self.cell(0, 10, "Finalytics - Company Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(249, 115, 22)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Generat {datetime.now().strftime('%Y-%m-%d %H:%M')} - pagina {self.page_no()}", align="C")

    def line_text(self, text: str, size: int = 10, bold: bool = False):
        """Write a full-width line, resetting x to the left margin first."""
        self.set_font("Helvetica", "B" if bold else "", size)
        self.set_x(self.l_margin)
        self.multi_cell(self.epw, 5, _ascii(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def build_report_pdf(report: Dict[str, Any]) -> bytes:
    pdf = _ReportPDF()
    pdf.add_page()
    pdf.set_text_color(30, 30, 30)

    company = report.get("company", {})
    pdf.line_text(company.get("name") or "Companie necunoscuta", size=13, bold=True)
    pdf.line_text(f"CUI: {company.get('cui') or '-'}", size=10)
    pdf.ln(2)

    cs = report.get("collaboration_score", {})
    pdf.line_text(f"Scor colaborare: {cs.get('score')}/100  ({cs.get('band')})", size=12, bold=True)
    pdf.ln(1)

    # Pillars
    pdf.line_text("Piloni de scoring", size=11, bold=True)
    for p in cs.get("pillars", []):
        pdf.line_text(
            f"{p.get('label')}: {p.get('score')}/100 (pondere {int(p.get('weight', 0) * 100)}%)",
            size=9, bold=True,
        )
        for reason in p.get("reasons", []):
            pdf.line_text(f"   - {reason}", size=9)
        pdf.ln(1)

    # Agents
    for key, title in (("risk_analyst", "Analist de risc (AI)"),
                       ("sales_strategist", "Strateg de vanzari (AI)")):
        agent = report.get(key, {})
        if not agent:
            continue
        pdf.ln(2)
        pdf.line_text(title, size=11, bold=True)
        pdf.line_text(agent.get("summary", ""), size=9)
        for b in agent.get("bullets", []):
            pdf.line_text(f"   - {b}", size=9)

    out = pdf.output()
    return bytes(out)
