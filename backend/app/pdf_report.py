"""Generation of the simulation report as a PDF.

The report is built server-side with ReportLab (no dependency on a headless
browser): it is therefore available even offline and consumes no client-side
resource.

The document contains:

1. a header with the played grid and the enabled options;
2. the financial balance (staked / won / net / return on stake);
3. the jackpot information (rank 1) and the "best approach";
4. the breakdown of winnings per rank;
5. the cumulative evolution curve;
6. the main wins of the series.
"""

from __future__ import annotations

import datetime as dt
import io
from typing import Any

from reportlab.graphics.shapes import Drawing, Line, PolyLine
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# --- Palette (consistent with the web interface) ----------------------------
INK = colors.HexColor("#16203c")
GOLD = colors.HexColor("#f5c451")
BLUE = colors.HexColor("#4f7cff")
GREEN = colors.HexColor("#22c55e")
RED = colors.HexColor("#ef4444")
GREY = colors.HexColor("#6b7280")
LIGHT = colors.HexColor("#f1f3f9")
LIGHT_GOLD = colors.HexColor("#fdf6e3")

# --- Domain labels ----------------------------------------------------------
RANK_LABELS = {
    1: "5 numéros + n° chance (cagnotte)",
    2: "5 numéros",
    3: "4 numéros + n° chance",
    4: "4 numéros",
    5: "3 numéros + n° chance",
    6: "3 numéros",
    7: "2 numéros + n° chance",
    8: "2 numéros",
    9: "1 numéro + n° chance (remboursé)",
}


def _money(value: float) -> str:
    """Formats an amount the French way: "1 234,56 €"."""
    formatted = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return f"{formatted} €"


def _number(value: int) -> str:
    return f"{value:02d}"


def _date(iso: str | None) -> str:
    if not iso:
        return "—"
    parsed = dt.date.fromisoformat(iso)
    return parsed.strftime("%d/%m/%Y")


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontSize=9.5,
            textColor=GREY,
            alignment=TA_LEFT,
            spaceAfter=10,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=INK,
            spaceBefore=12,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontSize=9.5,
            textColor=INK,
            leading=13,
        ),
        "cell": ParagraphStyle("Cell", parent=base["Normal"], fontSize=9.5, textColor=INK),
        "header": ParagraphStyle(
            "Header",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            textColor=colors.white,
        ),
        "headerRight": ParagraphStyle(
            "HeaderRight",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            textColor=colors.white,
            alignment=2,
        ),
        "cellRight": ParagraphStyle(
            "CellRight", parent=base["Normal"], fontSize=9.5, textColor=INK, alignment=2
        ),
        "hint": ParagraphStyle(
            "Hint", parent=base["Normal"], fontSize=8.5, textColor=GREY, leading=12
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            fontSize=7.5,
            textColor=GREY,
            alignment=TA_CENTER,
            leading=10,
        ),
    }


def _balls_row(numbers: list[int], chance: int, size: float = 22) -> Table:
    """Renders the grid as a row of separated "balls"."""
    cells: list[Paragraph] = []
    styles: list[tuple] = []
    widths: list[float] = []

    def add_ball(value: int, background, text_color) -> None:
        if cells:  # spacing column between two balls
            cells.append(Paragraph("", _ball_text_style()))
            styles.append(("BACKGROUND", (len(cells) - 1, 0), (len(cells) - 1, 0), colors.white))
            widths.append(2.5 * mm)
        cells.append(Paragraph(_number(value), _ball_text_style(text_color)))
        index = len(cells) - 1
        styles.append(("BACKGROUND", (index, 0), (index, 0), background))
        widths.append(size * mm / 3.2)

    for value in numbers:
        add_ball(value, INK, colors.white)

    # "+" separator (not a ball).
    cells.append(Paragraph("+", _ball_text_style(INK, size=13)))
    widths.append(7 * mm)

    add_ball(chance, GOLD, INK)

    table = Table([cells], colWidths=widths)
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                *styles,
            ]
        )
    )
    return table


def _ball_text_style(color=INK, size: int = 11) -> ParagraphStyle:
    """Text style of a ball (the colour must be carried by the Paragraph)."""
    return ParagraphStyle(
        "Ball",
        fontName="Helvetica-Bold",
        fontSize=size,
        alignment=TA_CENTER,
        textColor=color,
    )


def _summary_table(result: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    summary = result["summary"]
    net = summary["net"]
    net_color = GREEN if net >= 0 else RED
    net_label_style = ParagraphStyle(
        "NetLabel", parent=styles["cell"], fontName="Helvetica-Bold"
    )
    net_value_style = ParagraphStyle(
        "NetValue",
        parent=styles["cellRight"],
        fontName="Helvetica-Bold",
        textColor=net_color,
    )

    rows = [
        ("Tirages joués", f"{summary['total_draws']}"),
        ("Période couverte", f"{_date(summary['first_draw'])} → {_date(summary['last_draw'])}"),
        ("Mise par tirage", _money(summary["stake_per_draw"])),
        ("Total misé", _money(summary["total_spent"])),
        ("Total gagné", _money(summary["total_won"])),
        ("Bilan cumulé (gains − mises)", _money(net)),
        ("Retour sur mise", f"{summary['roi']:+.2f} %".replace(".", ",")),
        (
            "Tirages gagnants",
            f"{summary['winning_draws']} ({summary['win_rate']:.2f} %)".replace(".", ","),
        ),
        ("Meilleur gain", _money(summary["biggest_win"])),
        (
            "Meilleur rang atteint",
            summary["best_rank_label"] or "Aucun",
        ),
    ]

    table_rows = []
    for index, (label, value) in enumerate(rows):
        if index == 5:  # balance line, highlighted
            table_rows.append(
                [Paragraph(label, net_label_style), Paragraph(value, net_value_style)]
            )
        else:
            table_rows.append(
                [Paragraph(label, styles["cell"]), Paragraph(value, styles["cellRight"])]
            )

    table = Table(table_rows, colWidths=[95 * mm, 40 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BACKGROUND", (0, 5), (-1, 5), LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.6, LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _jackpot_table(result: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    summary = result["summary"]
    jackpot = result["jackpot"]

    amounts = jackpot.get("amounts") or []
    biggest = max(amounts) if amounts else 0.0

    rows = [
        ("Cagnotte (rang 1) remportée", f"{jackpot['hits']} fois"),
        ("Dernière cagnotte", _date(jackpot.get("last_date"))),
        (
            "Montant le plus élevé décroché",
            _money(biggest) if biggest else "—",
        ),
        ("Plus longue série sans rang 1", f"{jackpot['longest_drought_draws']} tirages"),
        ("Série actuelle sans rang 1", f"{jackpot['current_drought_draws']} tirages"),
    ]

    table = Table(
        [
            [Paragraph(label, styles["cell"]), Paragraph(value, styles["cellRight"])]
            for label, value in rows
        ],
        colWidths=[95 * mm, 40 * mm],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_GOLD),
                ("BOX", (0, 0), (-1, -1), 0.6, GOLD),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#f0e2bb")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _ranks_table(result: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    rows = [[Paragraph("Rang", styles["header"]), Paragraph("Combinaison", styles["header"]),
             Paragraph("Fois", styles["headerRight"]), Paragraph("Total gagné", styles["headerRight"])]]

    highlighted: list[int] = []
    for index, entry in enumerate(result["by_rank"], start=1):
        if entry["count"] == 0:
            continue
        label = entry["label"] or RANK_LABELS.get(entry["rank"], "")
        rows.append(
            [
                Paragraph(f"Rang {entry['rank']}", styles["cell"]),
                Paragraph(label, styles["cell"]),
                Paragraph(str(entry["count"]), styles["cellRight"]),
                Paragraph(_money(entry["total_won"]), styles["cellRight"]),
            ]
        )
        if entry["rank"] == 1:
            highlighted.append(index)

    if len(rows) == 1:
        rows.append(
            [
                Paragraph("—", styles["cell"]),
                Paragraph("Aucun rang atteint sur la période", styles["cell"]),
                Paragraph("0", styles["cellRight"]),
                Paragraph(_money(0), styles["cellRight"]),
            ]
        )

    table = Table(rows, colWidths=[20 * mm, 75 * mm, 18 * mm, 30 * mm], hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("BOX", (0, 0), (-1, -1), 0.6, LIGHT),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
    ]
    for row_index in highlighted:
        style.append(("BACKGROUND", (0, row_index), (-1, row_index), LIGHT_GOLD))
    table.setStyle(TableStyle(style))
    return table


def _top_gains_table(result: dict[str, Any], styles: dict[str, ParagraphStyle]) -> Table:
    timeline = result["timeline"]
    wins = sorted(
        (entry for entry in timeline if entry["gain"] > 0),
        key=lambda entry: entry["gain"],
        reverse=True,
    )[:10]

    rows = [[Paragraph("Date", styles["header"]), Paragraph("Correspondances", styles["header"]),
             Paragraph("Gain", styles["headerRight"])]]

    if not wins:
        rows.append(
            [
                Paragraph("—", styles["cell"]),
                Paragraph("Aucun gain sur la période", styles["cell"]),
                Paragraph(_money(0), styles["cellRight"]),
            ]
        )
    for entry in wins:
        rank_label = f"rang {entry['rank']}" if entry["rank"] else "sans gain"
        rows.append(
            [
                Paragraph(_date(entry["date"]), styles["cell"]),
                Paragraph(f"{entry['matches']} n° — {rank_label}", styles["cell"]),
                Paragraph(_money(entry["gain"]), styles["cellRight"]),
            ]
        )

    table = Table(rows, colWidths=[30 * mm, 75 * mm, 38 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("BOX", (0, 0), (-1, -1), 0.6, LIGHT),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LIGHT),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ]
        )
    )
    return table


def _cumulative_chart(timeline: list[dict], width: float, height: float) -> Drawing | None:
    """Cumulative curve (winnings − stakes) as a ReportLab Drawing."""
    if len(timeline) < 2:
        return None

    values = [entry["cumulative"] for entry in timeline]
    low = min(min(values), 0.0)
    high = max(max(values), 0.0)
    span = (high - low) or 1.0

    padding = 8
    inner_w = width - padding * 2
    inner_h = height - padding * 2

    def x_at(index: int) -> float:
        return padding + (index / (len(values) - 1)) * inner_w

    def y_at(value: float) -> float:
        return padding + ((value - low) / span) * inner_h

    last = values[-1]
    line_color = GREEN if last >= 0 else RED

    drawing = Drawing(width, height)

    # Zero line.
    zero_y = y_at(0.0)
    drawing.add(
        Line(padding, zero_y, width - padding, zero_y,
             strokeColor=colors.HexColor("#c9cede"), strokeWidth=0.6,
             strokeDashArray=[3, 3])
    )

    points: list[float] = []
    for index, value in enumerate(values):
        points.extend([x_at(index), y_at(value)])

    drawing.add(PolyLine(points, strokeColor=line_color, strokeWidth=1.4))

    # Final point.
    drawing.add(
        Line(x_at(len(values) - 1), y_at(last), x_at(len(values) - 1), y_at(last),
             strokeColor=line_color, strokeWidth=3)
    )
    return drawing


def build_simulation_pdf(result: dict[str, Any]) -> bytes:
    """Builds the PDF report of a simulation and returns its binary content."""
    styles = _styles()
    buffer = io.BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title="Loto Winner — Rapport de simulation",
        author="Loto Winner",
        subject="Simulation de grille LOTO",
        creator="Loto Winner",
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )

    summary = result["summary"]
    story: list[Any] = []

    # --- Header -------------------------------------------------------------
    story.append(Paragraph("Loto Winner — Rapport de simulation", styles["title"]))
    story.append(
        Paragraph(
            f"Grille {', '.join(_number(n) for n in summary['numbers'])} "
            f"+ numéro chance {_number(summary['chance'])} · "
            f"rejouée sur {summary['total_draws']} tirages",
            styles["subtitle"],
        )
    )
    story.append(_balls_row(summary["numbers"], summary["chance"]))
    story.append(Spacer(1, 6))

    options = ["grille simple"]
    story.append(Paragraph(f"Options activées : {', '.join(options)}.", styles["hint"]))

    source_label = (
        "Données officielles FDJ"
        if summary.get("data_source") == "fdj"
        else "Données simulées (repli hors ligne) — résultats non officiels"
    )
    story.append(Paragraph(f"Source des tirages : {source_label}.", styles["hint"]))
    if summary.get("simulation_start"):
        story.append(
            Paragraph(
                "Périmètre : formule actuelle à 9 rangs de gains uniquement — les "
                f"tirages antérieurs au {_date(summary['simulation_start'])} sont exclus.",
                styles["hint"],
            )
        )

    # --- Financial balance --------------------------------------------------
    story.append(Paragraph("Bilan financier", styles["section"]))
    story.append(_summary_table(result, styles))

    # --- Jackpot ------------------------------------------------------------
    story.append(Paragraph("Cagnotte (rang 1) et historique", styles["section"]))
    story.append(_jackpot_table(result, styles))

    # --- Ranks --------------------------------------------------------------
    story.append(Paragraph("Répartition des gains par rang", styles["section"]))
    story.append(_ranks_table(result, styles))

    # --- Curve --------------------------------------------------------------
    chart = _cumulative_chart(result["timeline"], width=170 * mm, height=45 * mm)
    if chart is not None:
        story.append(Paragraph("Évolution du bilan cumulé", styles["section"]))
        story.append(chart)
        story.append(Spacer(1, 4))
        story.append(
            Paragraph(
                f"De {_date(summary['first_draw'])} à {_date(summary['last_draw'])} — "
                f"bilan final {_money(summary['net'])}.",
                styles["hint"],
            )
        )

    # --- Main wins ----------------------------------------------------------
    story.append(Paragraph("Principaux gains de la série", styles["section"]))
    story.append(_top_gains_table(result, styles))

    # --- Disclaimer ---------------------------------------------------------
    story.append(Spacer(1, 10))
    story.append(
        KeepTogether(
            Paragraph(
                "Projet pédagogique indépendant, non affilié à La Française des Jeux. "
                "Les résultats proviennent des archives officielles publiées par la FDJ. "
                "Les jeux d'argent et de hasard peuvent être dangereux : pertes d'argent, "
                "endettement, isolement, dépendance. Jouer comporte des risques.",
                styles["footer"],
            )
        )
    )

    generated = dt.datetime.now().strftime("%d/%m/%Y à %H:%M")
    document.build(story, onFirstPage=_footer_factory(generated), onLaterPages=_footer_factory(generated))

    return buffer.getvalue()


def _footer_factory(generated: str):
    """Returns a page decorator drawing the footer."""

    def decorate(canvas, doc):  # noqa: ANN001 - signature imposed by ReportLab
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GREY)
        canvas.drawString(18 * mm, 10 * mm, f"Loto Winner · rapport généré le {generated}")
        canvas.drawRightString(
            A4[0] - 18 * mm, 10 * mm, f"Page {canvas.getPageNumber()}"
        )
        canvas.setStrokeColor(LIGHT)
        canvas.line(18 * mm, 13 * mm, A4[0] - 18 * mm, 13 * mm)
        canvas.restoreState()

    return decorate
