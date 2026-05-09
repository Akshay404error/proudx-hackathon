"""PDF report generation: progress / resource bundle / completion certificate.

Visual style: Professional / formal — designed to be shareable with recruiters,
colleges, and on LinkedIn. Cream/off-white background, refined typography,
real progress bars (no emoji fallbacks), donut chart for overall progress.
"""
from __future__ import annotations
import io
import math
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch, cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, Flowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from sqlalchemy.orm import Session

from app.models import User, Roadmap, Milestone, Lesson, Project


# ---------- Brand palette (formal) ----------
NAVY = colors.HexColor("#0F172A")         # primary text
INDIGO = colors.HexColor("#3949AB")       # accent (deeper, more formal than neon)
INDIGO_LIGHT = colors.HexColor("#E8EAF6")
GOLD = colors.HexColor("#B8860B")         # accent for "verified / certified" feel
GOLD_LIGHT = colors.HexColor("#FFF8E1")
GREEN = colors.HexColor("#2E7D32")        # completed states
GREEN_LIGHT = colors.HexColor("#E8F5E9")
GRAY_900 = colors.HexColor("#1E293B")
GRAY_700 = colors.HexColor("#475569")
GRAY_500 = colors.HexColor("#94A3B8")
GRAY_300 = colors.HexColor("#CBD5E1")
GRAY_100 = colors.HexColor("#F1F5F9")
CREAM = colors.HexColor("#FAFAF7")        # off-white background feel
WHITE = colors.white


def _styles():
    s = getSampleStyleSheet()

    s.add(ParagraphStyle("PFKicker", fontName="Helvetica-Bold", fontSize=10,
                         textColor=GOLD, leading=12, spaceAfter=4,
                         letterSpace=0.6))
    s.add(ParagraphStyle("PFTitle", fontName="Helvetica-Bold", fontSize=26,
                         textColor=NAVY, leading=30, spaceAfter=4))
    s.add(ParagraphStyle("PFSubtitle", fontName="Helvetica", fontSize=12,
                         textColor=GRAY_700, leading=16, spaceAfter=20))
    s.add(ParagraphStyle("PFH2", fontName="Helvetica-Bold", fontSize=14,
                         textColor=NAVY, leading=18, spaceBefore=18, spaceAfter=8))
    s.add(ParagraphStyle("PFH3", fontName="Helvetica-Bold", fontSize=11,
                         textColor=NAVY, leading=15, spaceBefore=10, spaceAfter=4))
    s.add(ParagraphStyle("PFBody", fontName="Helvetica", fontSize=10,
                         textColor=GRAY_900, leading=14))
    s.add(ParagraphStyle("PFBodyMuted", fontName="Helvetica", fontSize=10,
                         textColor=GRAY_700, leading=14))
    s.add(ParagraphStyle("PFSmall", fontName="Helvetica", fontSize=8.5,
                         textColor=GRAY_500, leading=11))
    s.add(ParagraphStyle("PFLessonDone", fontName="Helvetica", fontSize=10,
                         textColor=GREEN, leading=14))
    s.add(ParagraphStyle("PFLessonTodo", fontName="Helvetica", fontSize=10,
                         textColor=GRAY_700, leading=14))
    return s


# ---------- Page chrome ----------
def _draw_header_footer(canvas, doc):
    canvas.saveState()
    w, h = A4
    # Top: thin gold accent line + brand name
    canvas.setStrokeColor(GOLD)
    canvas.setLineWidth(2)
    canvas.line(0.6 * inch, h - 0.55 * inch, w - 0.6 * inch, h - 0.55 * inch)

    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(0.6 * inch, h - 0.4 * inch, "PathForge")
    canvas.setFillColor(GRAY_500)
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(1.4 * inch, h - 0.4 * inch, "·  Verified Learning Outcomes")

    canvas.setFillColor(GRAY_700)
    canvas.setFont("Helvetica", 8.5)
    canvas.drawRightString(w - 0.6 * inch, h - 0.4 * inch,
                           f"Issued {datetime.now().strftime('%d %B %Y')}")

    # Bottom: thin gray line + page no.
    canvas.setStrokeColor(GRAY_300)
    canvas.setLineWidth(0.5)
    canvas.line(0.6 * inch, 0.6 * inch, w - 0.6 * inch, 0.6 * inch)
    canvas.setFillColor(GRAY_500)
    canvas.setFont("Helvetica", 8)
    canvas.drawString(0.6 * inch, 0.42 * inch, "pathforge.dev")
    canvas.drawRightString(w - 0.6 * inch, 0.42 * inch, f"Page {doc.page}")
    canvas.restoreState()


# ---------- Custom Flowables ----------
class DonutChart(Flowable):
    """Hand-drawn donut for overall progress percentage."""
    def __init__(self, percent: float, size: float = 1.4 * inch,
                 label: str = "Overall Progress"):
        super().__init__()
        self.percent = max(0.0, min(100.0, percent))
        self.size = size
        self.label = label
        self.width = size + 2.2 * inch
        self.height = size

    def draw(self):
        c = self.canv
        s = self.size
        cx, cy = s / 2, s / 2
        radius = s / 2 - 4
        thickness = 14

        # Background ring
        c.setStrokeColor(GRAY_100)
        c.setLineWidth(thickness)
        c.setLineCap(1)  # round
        c.circle(cx, cy, radius, stroke=1, fill=0)

        # Foreground arc
        if self.percent > 0:
            c.setStrokeColor(INDIGO)
            c.setLineWidth(thickness)
            # arc from 90deg (top) clockwise
            extent = -360 * (self.percent / 100.0)
            c.arc(cx - radius, cy - radius, cx + radius, cy + radius,
                  startAng=90, extent=extent)

        # Centered percentage
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 22)
        pct_text = f"{int(round(self.percent))}%"
        text_width = c.stringWidth(pct_text, "Helvetica-Bold", 22)
        c.drawString(cx - text_width / 2, cy - 6, pct_text)

        c.setFillColor(GRAY_500)
        c.setFont("Helvetica", 7)
        sub = "complete"
        sub_width = c.stringWidth(sub, "Helvetica", 7)
        c.drawString(cx - sub_width / 2, cy - 18, sub)

        # Label to the right of the donut
        label_x = s + 0.25 * inch
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(label_x, s - 0.4 * inch, self.label)
        c.setFillColor(GRAY_700)
        c.setFont("Helvetica", 9)
        c.drawString(label_x, s - 0.6 * inch,
                     "Progress across all milestones")


class ProgressBar(Flowable):
    """Slim horizontal progress bar for a milestone."""
    def __init__(self, percent: float, width: float = 3.0 * inch,
                 height: float = 7, color=INDIGO, bg=GRAY_100):
        super().__init__()
        self.percent = max(0.0, min(100.0, percent))
        self.width = width
        self.height = height
        self.color = color
        self.bg = bg

    def draw(self):
        c = self.canv
        # Background
        c.setFillColor(self.bg)
        c.setStrokeColor(self.bg)
        c.roundRect(0, 0, self.width, self.height, 3, stroke=0, fill=1)
        # Fill
        if self.percent > 0:
            c.setFillColor(self.color)
            c.setStrokeColor(self.color)
            fill_w = self.width * (self.percent / 100.0)
            c.roundRect(0, 0, fill_w, self.height, 3, stroke=0, fill=1)


class StatusGlyph(Flowable):
    """Small colored circle/check used inline. Avoids emoji rendering issues."""
    def __init__(self, kind: str = "todo", size: float = 8):
        super().__init__()
        self.kind = kind  # "done" | "todo" | "partial"
        self.width = size + 2
        self.height = size
        self.size = size

    def draw(self):
        c = self.canv
        s = self.size
        if self.kind == "done":
            c.setFillColor(GREEN)
            c.setStrokeColor(GREEN)
            c.circle(s / 2, s / 2, s / 2, stroke=0, fill=1)
            # white check
            c.setStrokeColor(WHITE)
            c.setLineWidth(1.2)
            c.line(s * 0.25, s * 0.5, s * 0.45, s * 0.3)
            c.line(s * 0.45, s * 0.3, s * 0.78, s * 0.65)
        elif self.kind == "partial":
            c.setStrokeColor(INDIGO)
            c.setFillColor(INDIGO_LIGHT)
            c.setLineWidth(1.2)
            c.circle(s / 2, s / 2, s / 2 - 0.5, stroke=1, fill=1)
        else:
            c.setStrokeColor(GRAY_300)
            c.setFillColor(WHITE)
            c.setLineWidth(1)
            c.circle(s / 2, s / 2, s / 2 - 0.5, stroke=1, fill=1)


# ---------- Helpers ----------
def _progress_pct(milestones) -> float:
    total = sum(len(m.lessons) for m in milestones)
    done = sum(1 for m in milestones for l in m.lessons if l.is_completed)
    return 0.0 if total == 0 else (done * 100.0 / total)


def _milestone_pct(m) -> float:
    if not m.lessons:
        return 0.0
    done = sum(1 for l in m.lessons if l.is_completed)
    return done * 100.0 / len(m.lessons)


def _stat_card_table(stats: list[tuple[str, str, str]]) -> Table:
    """stats = [(label, value, sub), ...]"""
    # Two rows per card: label on top, value+sub below
    n = len(stats)
    col_widths = [(7.2 * inch / n)] * n

    label_row = [Paragraph(
        f'<font size="8" color="#94A3B8"><b>{label.upper()}</b></font>',
        ParagraphStyle("lbl", leading=11, spaceAfter=0)
    ) for label, _, _ in stats]
    value_row = [Paragraph(
        f'<font size="20" color="#0F172A"><b>{value}</b></font>',
        ParagraphStyle("val", leading=24, spaceAfter=0)
    ) for _, value, _ in stats]
    sub_row = [Paragraph(
        f'<font size="8" color="#475569">{sub}</font>',
        ParagraphStyle("sub", leading=10)
    ) for _, _, sub in stats]

    t = Table([label_row, value_row, sub_row], colWidths=col_widths,
              rowHeights=[14, 26, 12])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CREAM),
        ("BOX", (0, 0), (-1, -1), 0.5, GRAY_300),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEAFTER", (0, 0), (-2, -1), 0.5, GRAY_300),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


# ============================================================
# REPORT 1: PROGRESS REPORT
# ============================================================
def generate_progress_report(db: Session, user: User,
                             roadmap: Roadmap | None = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.85 * inch, bottomMargin=0.7 * inch,
    )
    s = _styles()
    story = []

    # ----- Title block -----
    story.append(Paragraph("LEARNING PROGRESS REPORT", s["PFKicker"]))
    story.append(Paragraph(user.full_name or user.username, s["PFTitle"]))
    handle_line = f"@{user.username}"
    if user.email:
        handle_line += f"  ·  {user.email}"
    story.append(Paragraph(handle_line, s["PFSubtitle"]))

    # ----- Stats row -----
    total_roadmaps = db.query(Roadmap).filter(Roadmap.user_id == user.id).count()
    stats = [
        ("Current Streak", f"{user.current_streak}",
         f"days  ·  best {user.longest_streak}"),
        ("Total XP Earned", f"{user.total_xp:,}", "across all activities"),
        ("Active Roadmaps", f"{total_roadmaps}", "in progress or completed"),
        ("Member Since", user.created_at.strftime("%b %Y"), "PathForge learner"),
    ]
    story.append(_stat_card_table(stats))
    story.append(Spacer(1, 18))

    # ----- Resolve roadmap to feature -----
    rm = roadmap or db.query(Roadmap).filter(
        Roadmap.user_id == user.id,
        Roadmap.is_active == True  # noqa: E712
    ).order_by(Roadmap.created_at.desc()).first()

    if not rm:
        story.append(Paragraph(
            "No active roadmap. Create one in PathForge to track your progress.",
            s["PFBodyMuted"]))
        doc.build(story, onFirstPage=_draw_header_footer,
                  onLaterPages=_draw_header_footer)
        return buf.getvalue()

    pct = _progress_pct(rm.milestones)
    total_lessons = sum(len(m.lessons) for m in rm.milestones)
    done_lessons = sum(1 for m in rm.milestones for l in m.lessons if l.is_completed)

    # ----- Featured roadmap header -----
    story.append(Paragraph("ACTIVE ROADMAP", s["PFKicker"]))
    story.append(Paragraph(rm.title, s["PFH2"]))
    story.append(Paragraph(rm.goal, s["PFBodyMuted"]))
    if rm.description:
        story.append(Spacer(1, 4))
        story.append(Paragraph(rm.description, s["PFSmall"]))
    story.append(Spacer(1, 8))

    # ----- Donut chart + summary side by side -----
    donut = DonutChart(pct, size=1.4 * inch)
    summary_lines = [
        Paragraph(f"<b>{done_lessons}</b> of <b>{total_lessons}</b> lessons completed",
                  s["PFBody"]),
        Paragraph(f"<b>{len(rm.milestones)}</b> milestones  ·  "
                  f"<b>{rm.duration_weeks}</b> weeks  ·  "
                  f"<b>{rm.skill_level}</b> level",
                  s["PFBody"]),
        Spacer(1, 4),
        Paragraph(f"Started {rm.created_at.strftime('%d %b %Y')}",
                  s["PFSmall"]),
    ]
    chart_table = Table(
        [[donut, summary_lines]],
        colWidths=[1.6 * inch, 5.6 * inch],
    )
    chart_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(chart_table)
    story.append(Spacer(1, 10))

    # divider
    story.append(Table([[""]], colWidths=[7.2 * inch], rowHeights=[1],
                       style=[("LINEBELOW", (0, 0), (-1, -1), 0.5, GRAY_300)]))
    story.append(Spacer(1, 10))

    # ----- Milestone progress bars -----
    story.append(Paragraph("MILESTONE BREAKDOWN", s["PFKicker"]))
    story.append(Spacer(1, 6))

    rows = []
    for i, m in enumerate(rm.milestones, 1):
        m_pct = _milestone_pct(m)
        m_done = sum(1 for l in m.lessons if l.is_completed)
        m_total = len(m.lessons)

        if m_total > 0 and m_done == m_total:
            glyph = StatusGlyph("done")
        elif m_done > 0:
            glyph = StatusGlyph("partial")
        else:
            glyph = StatusGlyph("todo")

        title_para = Paragraph(
            f'<font size="10"><b>{i}. {m.title}</b></font>',
            ParagraphStyle("mt", leading=12)
        )
        bar = ProgressBar(m_pct, width=2.2 * inch, height=6)
        count_para = Paragraph(
            f'<font size="9" color="#475569">{m_done} / {m_total}</font>',
            ParagraphStyle("mc", leading=12, alignment=TA_RIGHT)
        )
        pct_para = Paragraph(
            f'<font size="9" color="#0F172A"><b>{int(round(m_pct))}%</b></font>',
            ParagraphStyle("mp", leading=12, alignment=TA_RIGHT)
        )
        rows.append([glyph, title_para, bar, count_para, pct_para])

    if rows:
        ms_table = Table(rows, colWidths=[
            0.25 * inch, 2.8 * inch, 2.4 * inch, 0.8 * inch, 0.7 * inch
        ])
        ms_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, GRAY_100),
        ]))
        story.append(ms_table)

    story.append(Spacer(1, 14))

    # ----- Lesson detail (compact) -----
    story.append(Paragraph("LESSON DETAIL", s["PFKicker"]))
    story.append(Spacer(1, 4))

    for i, m in enumerate(rm.milestones, 1):
        story.append(Paragraph(f"{i}. {m.title}", s["PFH3"]))
        if not m.lessons:
            story.append(Paragraph("No lessons in this milestone.", s["PFSmall"]))
            continue

        lesson_rows = []
        for l in m.lessons:
            glyph = StatusGlyph("done" if l.is_completed else "todo")
            style_choice = s["PFLessonDone"] if l.is_completed else s["PFLessonTodo"]
            title_text = l.title
            if l.is_completed:
                title_text = f'<strike>{title_text}</strike>'
            title_para = Paragraph(title_text, style_choice)
            meta_para = Paragraph(
                f'<font size="8" color="#94A3B8">{l.estimated_minutes}m  ·  +{l.xp_reward} XP</font>',
                ParagraphStyle("lm", leading=10, alignment=TA_RIGHT)
            )
            lesson_rows.append([glyph, title_para, meta_para])

        lt = Table(lesson_rows, colWidths=[0.25 * inch, 5.6 * inch, 1.35 * inch])
        lt.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(lt)
        story.append(Spacer(1, 6))

    # Footer signature line
    story.append(Spacer(1, 16))
    story.append(Table([[""]], colWidths=[7.2 * inch], rowHeights=[1],
                       style=[("LINEABOVE", (0, 0), (-1, -1), 0.5, GRAY_300)]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"This report was automatically generated by PathForge on "
        f"{datetime.now().strftime('%d %B %Y at %H:%M')}. "
        f"Verify at pathforge.dev/u/{user.username}",
        s["PFSmall"],
    ))

    doc.build(story, onFirstPage=_draw_header_footer,
              onLaterPages=_draw_header_footer)
    return buf.getvalue()


# ============================================================
# REPORT 2: RESOURCE BUNDLE
# ============================================================
def generate_resource_bundle(db: Session, user: User, roadmap: Roadmap) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.85 * inch, bottomMargin=0.7 * inch,
    )
    s = _styles()
    story = []

    total_resources = sum(
        len(l.resources or []) for m in roadmap.milestones for l in m.lessons
    )

    story.append(Paragraph("CURATED RESOURCE BUNDLE", s["PFKicker"]))
    story.append(Paragraph(roadmap.title, s["PFTitle"]))
    story.append(Paragraph(
        f"Prepared for {user.full_name or user.username}  ·  "
        f"{total_resources} resources across {len(roadmap.milestones)} milestones",
        s["PFSubtitle"],
    ))

    # Goal callout
    goal_table = Table(
        [[Paragraph(f'<font size="9" color="#94A3B8"><b>LEARNING GOAL</b></font>',
                    ParagraphStyle("g1", leading=11))],
         [Paragraph(f'<font size="11" color="#0F172A">{roadmap.goal}</font>',
                    ParagraphStyle("g2", leading=15))]],
        colWidths=[7.2 * inch],
    )
    goal_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GOLD_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, GOLD),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(goal_table)
    story.append(Spacer(1, 18))

    # Resources by milestone
    for i, m in enumerate(roadmap.milestones, 1):
        story.append(Paragraph(f"MILESTONE {i}", s["PFKicker"]))
        story.append(Paragraph(m.title, s["PFH2"]))

        any_res = False
        for l in m.lessons:
            resources = l.resources or []
            if not resources:
                continue
            any_res = True
            story.append(Paragraph(l.title, s["PFH3"]))

            for r in resources:
                if not isinstance(r, dict):
                    continue
                title = r.get("title", "Resource")
                url = r.get("url", "")
                rtype = (r.get("type", "article") or "article").upper()

                # Type pill
                pill_color = {
                    "VIDEO": "#B91C1C", "DOCS": "#1F4ED8",
                    "ARTICLE": "#3949AB", "INTERACTIVE": "#9333EA",
                }.get(rtype, "#3949AB")

                resource_html = (
                    f'<font size="8" color="{pill_color}"><b>[{rtype}]</b></font>  '
                    f'<font size="10" color="#0F172A"><b>{title}</b></font><br/>'
                    f'<font size="8.5" color="#3949AB">{url}</font>'
                )
                story.append(Paragraph(resource_html,
                                       ParagraphStyle("r", leading=14,
                                                      leftIndent=8, spaceAfter=6)))
        if not any_res:
            story.append(Paragraph("No resources curated for this milestone yet.",
                                   s["PFSmall"]))
        story.append(Spacer(1, 8))

    # Sign-off
    story.append(Spacer(1, 12))
    story.append(Table([[""]], colWidths=[7.2 * inch], rowHeights=[1],
                       style=[("LINEABOVE", (0, 0), (-1, -1), 0.5, GRAY_300)]))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"Resources curated by PathForge AI  ·  Bundle #{roadmap.id}  ·  "
        f"Generated {datetime.now().strftime('%d %B %Y')}",
        s["PFSmall"],
    ))

    doc.build(story, onFirstPage=_draw_header_footer,
              onLaterPages=_draw_header_footer)
    return buf.getvalue()


# ============================================================
# REPORT 3: COMPLETION CERTIFICATE
# ============================================================
def generate_certificate(user: User, roadmap: Roadmap) -> bytes:
    buf = io.BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(
        buf, pagesize=page,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
    )

    cert_kicker = ParagraphStyle(
        "ck", fontName="Helvetica-Bold", fontSize=11, textColor=GOLD,
        alignment=TA_CENTER, leading=14, spaceAfter=8,
    )
    cert_title = ParagraphStyle(
        "ct", fontName="Helvetica-Bold", fontSize=44, textColor=NAVY,
        alignment=TA_CENTER, leading=50, spaceAfter=10,
    )
    cert_sub = ParagraphStyle(
        "cs", fontName="Helvetica", fontSize=12, textColor=GRAY_700,
        alignment=TA_CENTER, leading=16, spaceAfter=24,
    )
    cert_presented = ParagraphStyle(
        "cp", fontName="Helvetica-Oblique", fontSize=13, textColor=GRAY_700,
        alignment=TA_CENTER, leading=18, spaceAfter=8,
    )
    cert_name = ParagraphStyle(
        "cn", fontName="Helvetica-Bold", fontSize=38, textColor=NAVY,
        alignment=TA_CENTER, leading=44, spaceAfter=14,
    )
    cert_body = ParagraphStyle(
        "cb", fontName="Helvetica", fontSize=13, textColor=GRAY_900,
        alignment=TA_CENTER, leading=20, spaceAfter=10,
    )
    cert_roadmap = ParagraphStyle(
        "cr", fontName="Helvetica-Bold", fontSize=22, textColor=GOLD,
        alignment=TA_CENTER, leading=28, spaceAfter=24,
    )

    story = []
    story.append(Spacer(1, 30))
    story.append(Paragraph("PATHFORGE  ·  CERTIFICATE OF COMPLETION", cert_kicker))
    story.append(Paragraph("Certificate of Completion", cert_title))
    story.append(Paragraph(
        "This document certifies the successful completion of a "
        "personalized AI-curated learning roadmap.", cert_sub,
    ))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Presented to", cert_presented))
    story.append(Paragraph(user.full_name or user.username, cert_name))
    story.append(Paragraph("for the successful completion of", cert_body))
    story.append(Paragraph(roadmap.title, cert_roadmap))

    completed = sum(
        1 for m in roadmap.milestones for l in m.lessons if l.is_completed
    )
    total_milestones = len(roadmap.milestones)
    story.append(Paragraph(
        f"comprising <b>{completed}</b> lessons across <b>{total_milestones}</b> "
        f"milestones, demonstrating sustained commitment and verified progress.",
        cert_body,
    ))

    doc.build(story, onFirstPage=_certificate_decor(roadmap, user),
              onLaterPages=_certificate_decor(roadmap, user))
    return buf.getvalue()


def _certificate_decor(roadmap, user):
    """Return a draw fn that renders the certificate's borders + signature line."""
    page = landscape(A4)

    def _draw(canvas, doc):
        canvas.saveState()
        w, h = page

        # Outer navy border
        canvas.setStrokeColor(NAVY)
        canvas.setLineWidth(3)
        canvas.rect(0.4 * inch, 0.4 * inch, w - 0.8 * inch, h - 0.8 * inch)

        # Inner gold border
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(0.8)
        canvas.rect(0.55 * inch, 0.55 * inch, w - 1.1 * inch, h - 1.1 * inch)

        # Top corner ornaments (small gold squares)
        for cx, cy in [
            (0.55 * inch, h - 0.55 * inch),
            (w - 0.55 * inch, h - 0.55 * inch),
            (0.55 * inch, 0.55 * inch),
            (w - 0.55 * inch, 0.55 * inch),
        ]:
            canvas.setFillColor(GOLD)
            canvas.circle(cx, cy, 4, stroke=0, fill=1)

        # Bottom: date + signature line on either side
        sig_y = 1.0 * inch
        # Left: Date
        canvas.setStrokeColor(GRAY_700)
        canvas.setLineWidth(0.5)
        canvas.line(1.5 * inch, sig_y, 3.5 * inch, sig_y)
        canvas.setFillColor(GRAY_700)
        canvas.setFont("Helvetica", 9)
        canvas.drawCentredString(2.5 * inch, sig_y - 0.18 * inch,
                                 datetime.now().strftime("%d %B %Y"))
        canvas.setFillColor(GRAY_500)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawCentredString(2.5 * inch, sig_y - 0.32 * inch, "DATE OF ISSUE")

        # Right: PathForge sig
        canvas.setStrokeColor(GRAY_700)
        canvas.line(w - 3.5 * inch, sig_y, w - 1.5 * inch, sig_y)
        canvas.setFillColor(NAVY)
        canvas.setFont("Helvetica-BoldOblique", 12)
        canvas.drawCentredString(w - 2.5 * inch, sig_y + 0.06 * inch,
                                 "PathForge")
        canvas.setFillColor(GRAY_500)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawCentredString(w - 2.5 * inch, sig_y - 0.18 * inch,
                                 "VERIFIED BY PATHFORGE")
        canvas.drawCentredString(w - 2.5 * inch, sig_y - 0.32 * inch,
                                 f"pathforge.dev/u/{user.username}")

        # Verification ID centered at very bottom
        canvas.setFillColor(GRAY_500)
        canvas.setFont("Helvetica", 7.5)
        canvas.drawCentredString(w / 2, 0.7 * inch,
                                 f"Verification ID: PF-{roadmap.id:06d}-{user.id:04d}")
        canvas.restoreState()
    return _draw