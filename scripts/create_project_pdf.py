from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem


def build_pdf(output_path: Path) -> None:
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Mobile OS Memory Management System - Project Report",
        author="OS Course Project",
    )

    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=14,
        textColor=colors.HexColor("#1b263b"),
        spaceAfter=6,
    )
    h1 = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0d1b2a"),
        spaceBefore=6,
        spaceAfter=10,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13.5,
        leading=18,
        textColor=colors.HexColor("#1b263b"),
        spaceBefore=6,
        spaceAfter=8,
    )

    story = []

    def add_heading(text: str):
        story.append(Paragraph(text, h2))

    def add_para(text: str):
        story.append(Paragraph(text, body))

    def add_bullets(items):
        bullet_items = [ListItem(Paragraph(i, body), leftIndent=8) for i in items]
        story.append(ListFlowable(bullet_items, bulletType="bullet", leftIndent=14))
        story.append(Spacer(1, 6))

    story.append(Paragraph("Mobile OS Memory Management System", h1))
    add_para("Project Report (Direct PDF Generation)")
    add_para("This PDF is generated directly from Python code and project understanding, not from Markdown conversion.")
    story.append(Spacer(1, 6))

    add_heading("1. Project Goal")
    add_para("The project builds a real-time Android memory monitoring and optimisation dashboard using ADB, Python, and Streamlit. It provides visibility into memory consumption and allows safe user-driven cleanup of low-priority apps.")

    add_heading("2. Core Workflow")
    add_bullets([
        "Detect whether an Android device is connected through ADB.",
        "Collect system memory from dumpsys meminfo (with /proc/meminfo fallback).",
        "Collect per-process PSS and OOM priority from dumpsys outputs.",
        "Score processes by kill safety and estimate freeable memory.",
        "Render results in a Streamlit dashboard with charts and action buttons.",
    ])

    add_heading("3. Main Modules")
    add_bullets([
        "config.py: thresholds, OOM priority mapping, kill blocklist, refresh settings.",
        "modules/adb_utils.py: ADB discovery, shell execution, connectivity checks, force-stop command.",
        "modules/memory_reader.py: parses total/used/free/lost RAM.",
        "modules/process_reader.py: extracts process PSS and OOM codes, supports Android 15 format.",
        "modules/smart_manager.py: recommendation logic and kill-candidate filtering.",
        "modules/demo_data.py: realistic simulated data when no device is available.",
        "app.py: full dashboard UI with 5 tabs and glassmorphism theme.",
    ])

    add_heading("4. Decision Logic")
    add_bullets([
        "Usage >= 80%: Critical memory pressure.",
        "Usage >= 60%: Warning state.",
        "Usage < 60%: Healthy state.",
        "Candidate process must have kill_score >= 3 and must not be in blocklist.",
        "Candidates are sorted by highest PSS first for maximum memory recovery.",
    ])

    add_heading("5. Dashboard Features")
    add_bullets([
        "Memory Overview: metric cards, gauge, progress bar, status alerts.",
        "Running Processes: table, top consumers chart, per-app stop buttons.",
        "History: time-series graphs for used/free memory and usage percent.",
        "Smart Recommendations: kill candidates, estimated freeable MB, pie chart, optimize-all.",
        "Android vs Our Model: comparison table for academic presentation.",
    ])

    add_heading("6. Reliability and Safety")
    add_bullets([
        "Automatic demo fallback when device/ADB is unavailable.",
        "System-critical package blocklist prevents unsafe force-stop actions.",
        "Cache TTL and optional 30s auto-refresh reduce command load and lag.",
        "ADB path auto-discovery supports common Windows installation paths.",
    ])

    add_heading("7. Technology Stack")
    add_bullets([
        "Python 3.14",
        "Streamlit 1.53",
        "Plotly 6.5",
        "Pandas 2.3",
        "Android Debug Bridge (ADB)",
    ])

    add_heading("8. Conclusion")
    add_para("This project successfully demonstrates an adaptive memory management interface over Android's low-level process state. It improves user visibility, control, and practical understanding of OS memory behavior while remaining safe through priority-based filtering and blocklist protection.")

    doc.build(story)


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    output = root / "PROJECT_REPORT_DIRECT.pdf"
    build_pdf(output)
    print(f"Created: {output}")
