"""Generate the editable draw.io sources for the README diagrams.

    python docs/architecture/build_diagrams.py        # writes docs/architecture/*.drawio

Export to PNG with the draw.io desktop CLI (see docs/architecture/README.md). The .drawio files are
the source of truth: open them in draw.io to edit, then re-export.
"""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import quoteattr

OUT = Path(__file__).resolve().parent

PALETTE = {
    "blue": ("#dae8fc", "#6c8ebf"),
    "green": ("#d5e8d4", "#82b366"),
    "yellow": ("#fff2cc", "#d6b656"),
    "orange": ("#ffe6cc", "#d79b00"),
    "red": ("#f8cecc", "#b85450"),
    "grey": ("#f5f5f5", "#666666"),
    "purple": ("#e1d5e7", "#9673a6"),
    "teal": ("#d3efe9", "#01A88D"),
    "white": ("#ffffff", "#666666"),
}
INK = "#1f2933"
MUTED = "#5f6b76"


def label(title: str, sub: str = "") -> str:
    out = f"<b>{title}</b>"
    if sub:
        out += f'<br><font style="font-size:10px" color="{MUTED}">{sub}</font>'
    return out


class Diagram:
    def __init__(self, name: str, width: int, height: int) -> None:
        self.name, self.width, self.height = name, width, height
        self.cells: list[str] = []
        self.count = 1

    def _id(self) -> str:
        self.count += 1
        return f"n{self.count}"

    def vertex(self, value: str, x: int, y: int, w: int, h: int, style: str, parent: str = "1") -> str:
        cid = self._id()
        self.cells.append(
            f'<mxCell id="{cid}" value={quoteattr(value)} style="{style}" vertex="1" parent="{parent}">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>'
        )
        return cid

    def box(self, value: str, x: int, y: int, w: int, h: int, kind: str = "blue", parent: str = "1",
            extra: str = "", rounded: int = 1) -> str:
        fill, stroke = PALETTE[kind]
        style = (f"rounded={rounded};arcSize=8;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                 f"fontColor={INK};fontSize=12;strokeWidth=1.5;" + extra)
        return self.vertex(value, x, y, w, h, style, parent)

    def text(self, value: str, x: int, y: int, w: int, h: int, size: int = 12, bold: bool = False,
             color: str = INK, align: str = "left", parent: str = "1") -> str:
        style = (f"text;html=1;whiteSpace=wrap;align={align};verticalAlign=middle;fontSize={size};"
                 f"fontColor={color};fontStyle={1 if bold else 0};strokeColor=none;fillColor=none;")
        return self.vertex(value, x, y, w, h, style, parent)

    def container(self, value: str, x: int, y: int, w: int, h: int, kind: str = "grey", start: int = 34,
                  parent: str = "1") -> str:
        fill, stroke = PALETTE[kind]
        style = (f"swimlane;startSize={start};whiteSpace=wrap;html=1;rounded=1;arcSize=3;fillColor={fill};"
                 f"strokeColor={stroke};fontColor={INK};fontSize=13;fontStyle=1;strokeWidth=1.5;"
                 "swimlaneFillColor=#ffffff;collapsible=0;")
        return self.vertex(value, x, y, w, h, style, parent)

    def aws_icon(self, icon: str, color: str, x: int, y: int, size: int = 64, parent: str = "1",
                 value: str = "", below: bool = True) -> str:
        pos = "verticalLabelPosition=bottom;verticalAlign=top;" if below else ""
        style = (f"sketch=0;outlineConnect=0;fontColor={INK};fillColor={color};strokeColor=#ffffff;dashed=0;"
                 f"{pos}align=center;html=1;fontSize=11;aspect=fixed;shape=mxgraph.aws4.resourceIcon;"
                 f"resIcon=mxgraph.aws4.{icon};")
        return self.vertex(value, x, y, size, size, style, parent)

    def edge(self, src: str, dst: str, value: str = "", exit: tuple[float, float] | None = None,
             entry: tuple[float, float] | None = None, points: list[tuple[int, int]] | None = None,
             dashed: bool = False, color: str = "#4a5568", both: bool = False, width: float = 2,
             label_pos: float = 0) -> str:
        cid = self._id()
        style = ("edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;html=1;"
                 f"strokeColor={color};strokeWidth={width};endArrow=blockThin;endFill=1;fontSize=11;"
                 f"fontColor={INK};labelBackgroundColor=#ffffff;")
        if both:
            style += "startArrow=blockThin;startFill=1;"
        if dashed:
            style += "dashed=1;dashPattern=6 4;"
        if exit:
            style += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
        if entry:
            style += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
        pts = ""
        if points:
            pts = '<Array as="points">' + "".join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in points) + "</Array>"
        self.cells.append(
            f'<mxCell id="{cid}" value={quoteattr(value)} style="{style}" edge="1" parent="1" source="{src}" target="{dst}">'
            f'<mxGeometry x="{label_pos}" relative="1" as="geometry">{pts}</mxGeometry></mxCell>'
        )
        return cid

    def save(self) -> Path:
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n<mxfile host="drawio" version="26.0.0">'
            f'<diagram name={quoteattr(self.name)}><mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" '
            f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{self.width}" '
            f'pageHeight="{self.height}" background="#ffffff" math="0" shadow="0"><root><mxCell id="0"/>'
            '<mxCell id="1" parent="0"/>' + "".join(self.cells) + "</root></mxGraphModel></diagram></mxfile>\n"
        )
        path = OUT / f"{self.name}.drawio"
        path.write_bytes(xml.encode("utf-8"))
        return path


# ------------------------------------------------------------------------------------------------
def system_architecture() -> Path:
    d = Diagram("system-architecture", 1760, 880)
    d.text("TariffTrail: system architecture", 30, 14, 700, 30, size=22, bold=True)
    d.text("A calibrated 2B model makes many small choices; one short LLM call chooses among real codes; "
           "a Strands intervention guards the action.", 30, 44, 1100, 22, size=12, color=MUTED)

    actor = d.vertex("Importer / broker", 40, 250, 44, 84,
                     f"shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;"
                     f"fontSize=11;fontColor={INK};strokeColor=#666666;fillColor=#f5f5f5;")

    agent = d.container("Strands Agent", 140, 120, 270, 360, "blue")
    c1 = d.box(label("classify_product", "product facts → HTS code + alternatives"), 20, 50, 230, 56, "green", agent)
    d.box(label("lookup_duty", "duty rates for a code"), 20, 122, 230, 50, "grey", agent)
    d.box(label("list_lines", "lines under a code"), 20, 188, 230, 50, "grey", agent)
    c4 = d.box(label("file_entry", "files a customs entry: has a side effect"), 20, 276, 230, 60, "red", agent)

    gate = d.box(label("ClassificationGate", "Strands InterventionHandler<br>Deny · Guide · Confirm"),
                 140, 540, 270, 84, "purple", extra="strokeWidth=2.5;")
    broker = d.box(label("Licensed customs broker", "approves every filing"), 140, 690, 270, 60, "orange")
    entry = d.vertex(label("Customs entry", "simulated: entries.jsonl"), 170, 790, 210, 70,
                     f"shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=10;"
                     f"fillColor={PALETTE['green'][0]};strokeColor={PALETTE['green'][1]};fontColor={INK};fontSize=12;strokeWidth=1.5;")

    pipe = d.container("TariffTrail.classify()", 480, 120, 600, 600, "grey")
    s1 = d.box(label("1 · Retrieval seed", "embed the product, find the 20 most similar pre-2026 rulings, propose 8 headings"),
               30, 54, 540, 76, "blue", pipe)
    s2 = d.box(label("2 · Calibrated Tree Descent", "one Decider choice per fork, none_of_these at every level, "
                     "best-first search on path probability"), 30, 168, 540, 76, "green", pipe, extra="strokeWidth=2.5;")
    s3 = d.box(label("3 · Shortlist", "Decider's top 3 complete codes + the nearest past ruling's code"),
               30, 282, 540, 76, "yellow", pipe)
    s4 = d.box(label("4 · Adjudicator", "one Bedrock call picks among real codes, with similar rulings as context"),
               30, 396, 540, 76, "teal", pipe)
    s5 = d.box(label("5 · Classification", "a real HTS leaf · alternatives · fast-track flag when all sources agree"),
               30, 510, 540, 76, "white", pipe)

    def service(title: str, sub: str, y: int, kind: str, icon: str, color: str) -> str:
        box = d.box(label(title, sub), 1200, y, 300, 96, kind, extra="align=left;spacingLeft=12;spacingRight=56;")
        d.aws_icon(icon, color, 300 - 52, 16, 40, parent=box, below=False)
        return box

    titan = service("Amazon Titan Text Embeddings V2", "512-d vectors · Bedrock", 164, "white", "bedrock", "#01A88D")
    index = d.vertex(label("Ruling index", "7,024 pre-2026 CBP rulings<br>top-20 by cosine"), 1580, 164, 160, 96,
                     f"shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=12;"
                     f"fillColor={PALETTE['grey'][0]};strokeColor={PALETTE['grey'][1]};fontColor={INK};fontSize=12;strokeWidth=1.5;")
    decider = service("Strands Decider 2B", "/v1systemone · choice · noul · score<br>GPU 72 ms per call · CPU 2.5 s",
                      278, "green", "ec2", "#ED7100")
    tree = d.vertex(label("HTS 2026 Rev 21 tree", "30,462 nodes · 11,516 decisions<br>18,946 final codes"), 1200, 392, 300, 96,
                    f"shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=12;"
                    f"fillColor={PALETTE['grey'][0]};strokeColor={PALETTE['grey'][1]};fontColor={INK};fontSize=12;strokeWidth=1.5;")
    nova = service("Amazon Nova Pro", "Bedrock Converse · 1 call, ~1,260 tokens<br>cannot invent a code",
                   506, "teal", "bedrock", "#01A88D")

    d.edge(actor, agent, "", exit=(1, 0.5), entry=(0, 0.3))
    d.edge(c1, s1, "", exit=(1, 0.5), entry=(0, 0.32))
    for a, b in ((s1, s2), (s2, s3), (s3, s4), (s4, s5)):
        d.edge(a, b, "", exit=(0.5, 1), entry=(0.5, 0), color="#2d6a4f", width=2.5)
    d.edge(s1, titan, "embed", exit=(1, 0.5), entry=(0, 0.5))
    d.edge(titan, index, "vectors", exit=(1, 0.5), entry=(0, 0.5))
    d.edge(s2, decider, "choice / noul", exit=(1, 0.25), entry=(0, 0.3))
    d.edge(s2, tree, "children", exit=(1, 0.85), entry=(0, 0.5), points=[(1140, 353), (1140, 440)])
    d.edge(s4, nova, "1 call", exit=(1, 0.5), entry=(0, 0.5))
    d.edge(c4, gate, "intercepted before it runs", exit=(0.5, 1), entry=(0.5, 0))
    d.edge(gate, broker, "Confirm", exit=(0.5, 1), entry=(0.5, 0), color="#9673a6")
    d.edge(broker, entry, "approved", exit=(0.5, 1), entry=(0.5, 0), color="#d79b00")

    d.box(label("Result on 332 held-out 2026 CBP rulings",
                "36.7% exact 10-digit · 57.5% at 4 digits · 0% invented codes<br>"
                "7.8× fewer Bedrock tokens than the tool-using agent (p = 1.3e-7)"),
          480, 760, 600, 76, "yellow", extra="strokeWidth=2;")

    lx, ly = 1200, 660
    d.text("Legend", lx, ly - 30, 120, 22, size=12, bold=True)
    for i, (kind, text) in enumerate((("green", "Strands Decider decision"), ("blue", "Retrieval / agent"),
                                      ("teal", "Amazon Bedrock LLM"), ("purple", "Guardrail (Strands intervention)"),
                                      ("orange", "Human in the loop"), ("grey", "Data"))):
        col, row = i % 2, i // 2
        d.box("", lx + col * 250, ly + row * 36, 22, 22, kind)
        d.text(text, lx + col * 250 + 30, ly + row * 36 - 2, 210, 26, size=11)
    return d.save()


# ------------------------------------------------------------------------------------------------
def calibrated_tree_descent() -> Path:
    d = Diagram("calibrated-tree-descent", 1560, 900)
    d.text("Calibrated Tree Descent: the reusable pattern", 30, 14, 900, 30, size=22, bold=True)
    d.text("Real trace of CBP ruling N357194 (an adult Anubis costume, gold code 9505.90.60.00). "
           "Each number is Decider's calibrated probability at that fork.", 30, 44, 1300, 22, size=12, color=MUTED)

    oy = 100
    for label_text, x in (("Fork 1: seed (headings from similar rulings)", 270), ("Fork 2: inside heading 9505", 560),
                          ("Fork 3: inside 9505.90", 890)):
        d.text(label_text, x, oy - 24, 270, 20, size=11, bold=True, color=MUTED)

    n0 = d.box(label("Seed fork", "8 headings proposed from the 20 nearest past rulings<br>+ none_of_these"),
               30, oy + 150, 200, 92, "blue")
    n1 = d.box(label("9505 Festive, carnival…", "p = 0.48 · path 0.48"), 270, oy + 80, 240, 62, "green")
    n1n = d.box(label("none_of_these", "p = 0.52 → full walk from the root"), 270, oy + 280, 240, 62, "red", extra="dashed=1;")
    n2 = d.box(label("9505.90 Other (not covered by…)", "p = 0.38 · path 0.18"), 560, oy + 20, 260, 62, "green")
    n2b = d.box(label("9505.10 Christmas articles", "p = 0.18 · path 0.09"), 560, oy + 110, 260, 62, "grey")
    n2n = d.box(label("none_of_these", "p = 0.44 · subtree paths are scaled down"), 560, oy + 200, 260, 62, "red", extra="dashed=1;")
    n3 = d.box(label("9505.90.60.00 Other  ✔ leaf", "p = 0.69 · path 0.13 = the gold code"), 890, oy + 4, 260, 66,
               "yellow", extra="strokeWidth=3;strokeColor=#d79b00;")
    n3b = d.box(label("9505.90.20.00 Magic tricks", "p = 0.11 · path 0.02"), 890, oy + 90, 260, 56, "grey")
    n3n = d.box(label("none_of_these", "p = 0.20"), 890, oy + 164, 260, 50, "red", extra="dashed=1;")

    d.edge(n0, n1, "", exit=(1, 0.35), entry=(0, 0.5))
    d.edge(n0, n1n, "", exit=(1, 0.8), entry=(0, 0.5), color="#b85450", dashed=True)
    d.edge(n1, n2, "", exit=(1, 0.5), entry=(0, 0.5))
    d.edge(n1, n2b, "", exit=(1, 0.5), entry=(0, 0.5))
    d.edge(n1, n2n, "", exit=(1, 0.5), entry=(0, 0.5), color="#b85450", dashed=True)
    d.edge(n2, n3, "", exit=(1, 0.5), entry=(0, 0.5))
    d.edge(n2, n3b, "", exit=(1, 0.5), entry=(0, 0.5))
    d.edge(n2, n3n, "", exit=(1, 0.5), entry=(0, 0.5), color="#b85450", dashed=True)

    qx = 1190
    q = d.container("Frontier: a priority queue ordered by path probability", qx, oy - 30, 340, 260, "grey", start=40)
    d.box(label("0.13 · 9505.90.60.00", "leaf → becomes candidate #1"), 20, 52, 300, 46, "yellow", q,
          extra="strokeWidth=2.5;strokeColor=#d79b00;")
    d.box(label("0.09 · 9505.10 Christmas", "expand next if budget allows"), 20, 106, 300, 46, "grey", q)
    d.box(label("0.02 · 9505.90.20.00", "leaf → candidate #3"), 20, 160, 300, 46, "grey", q)
    d.text("…and the other seeded headings", 20, 212, 300, 20, size=11, color=MUTED, parent=q)

    d.box(label("A wrong turn fixes itself", "On a wrong branch Decider puts most of its mass on none_of_these, so every path "
                "below it collapses and the search resumes at the next-best path anywhere in the tree. "
                "No hand-written backtracking."), qx, oy + 245, 340, 130, "red", extra="align=left;spacingLeft=10;")

    d.text("Then the pattern hands a few real candidates to the rest of the system", 30, 540, 900, 24, size=14, bold=True)
    steps = (
        ("1 · Top 3 complete paths", "plus the nearest past ruling's code", "yellow"),
        ("2 · One LLM call", "Amazon Nova Pro chooses among real codes only", "teal"),
        ("3 · Agreement decides the queue", "Decider ∧ Bedrock ∧ past rulings agree → fast-track", "green"),
        ("4 · A human confirms", "tariffs never auto-file (auto bar = 1.01)", "orange"),
    )
    ids = []
    for i, (title, sub, kind) in enumerate(steps):
        ids.append(d.box(label(title, sub), 30 + i * 380, 580, 330, 84, kind))
    for a, b in zip(ids, ids[1:]):
        d.edge(a, b, "", exit=(1, 0.5), entry=(0, 0.5), color="#2d6a4f", width=2.5)

    d.box(label("Why path probability?", "Every fork sums to 1, so the product along a path is comparable across the entire tree. "
                "That gives free backtracking and one number to measure as 'safe to act'."),
          30, 710, 740, 90, "white", extra="align=left;spacingLeft=10;")
    d.box(label("Measured, not assumed", "Safe on a 48-tool catalog (17/17 confident calls right). On the 8-level tariff tree "
                "path probability was only modestly predictive (AUROC 0.63), so TariffTrail never auto-files."),
          800, 710, 730, 90, "white", extra="align=left;spacingLeft=10;")
    return d.save()


# ------------------------------------------------------------------------------------------------
def guardrail_flow() -> Path:
    d = Diagram("guardrail-flow", 1120, 1110)
    d.text("ClassificationGate: guarding the one action with consequences", 30, 14, 1000, 30, size=22, bold=True)
    d.text("A Strands InterventionHandler on file_entry. Checks 1 and 2 are plain code; check 3 is a second Decider decision.",
           30, 44, 1050, 22, size=12, color=MUTED)

    def diamond(text: str, y: int) -> str:
        return d.vertex(text, 320, y, 400, 140,
                        f"rhombus;whiteSpace=wrap;html=1;fillColor={PALETTE['yellow'][0]};strokeColor={PALETTE['yellow'][1]};"
                        f"fontColor={INK};fontSize=11;strokeWidth=1.5;")

    start = d.box(label("Agent calls file_entry(hts_code, description)", "the tool call is intercepted before it runs"),
                  340, 90, 360, 64, "blue")
    d1 = diamond("<b>1</b> Is the code a real line of the current HTS?", 190)
    d2 = diamond("<b>2</b> Did this code come from classify_product in this session?", 370)
    d3 = diamond("<b>3</b> Decider <i>noul</i>: does the entry describe the classified goods? (p ≥ 0.5)", 550)
    d4 = diamond("<b>4</b> Do Decider, Bedrock and the nearest past rulings agree on the code?", 730)

    deny = d.box(label("Deny", "“not a line in the current HTS”"), 800, 229, 260, 62, "red", extra="strokeWidth=2;")
    g2 = d.box(label("Guide", "“only file codes from classify_product; classify first”"), 800, 409, 260, 62, "yellow", extra="strokeWidth=2;")
    g3 = d.box(label("Guide", "“describe the same goods, or classify the new description”"), 800, 589, 260, 62, "yellow", extra="strokeWidth=2;")

    fast = d.box(label("Confirm · FAST-TRACK", "front of the broker's queue<br>16% of test products, 76% correct"),
                 20, 764, 240, 72, "green", extra="strokeWidth=2.5;")
    disp = d.box(label("Confirm · DISPUTED", "shows the alternatives considered<br>the other 84%: 29% correct"),
                 800, 764, 260, 72, "orange", extra="strokeWidth=2.5;")
    done = d.box(label("Licensed broker answers yes / no", "yes → the entry is filed · no → nothing is filed"),
                 340, 950, 360, 70, "purple", extra="strokeWidth=2.5;")

    d.edge(start, d1, "", exit=(0.5, 1), entry=(0.5, 0))
    d.edge(d1, deny, "No", exit=(1, 0.5), entry=(0, 0.5), color="#b85450")
    d.edge(d1, d2, "Yes", exit=(0.5, 1), entry=(0.5, 0))
    d.edge(d2, g2, "No", exit=(1, 0.5), entry=(0, 0.5), color="#d6b656")
    d.edge(d2, d3, "Yes", exit=(0.5, 1), entry=(0.5, 0))
    d.edge(d3, g3, "No", exit=(1, 0.5), entry=(0, 0.5), color="#d6b656")
    d.edge(d3, d4, "Yes", exit=(0.5, 1), entry=(0.5, 0))
    d.edge(d4, fast, "Yes", exit=(0, 0.5), entry=(1, 0.5), color="#82b366")
    d.edge(d4, disp, "No", exit=(1, 0.5), entry=(0, 0.5), color="#d79b00")
    d.edge(fast, done, "", exit=(0.5, 1), entry=(0, 0.5), points=[(140, 985)], color="#9673a6")
    d.edge(disp, done, "", exit=(0.5, 1), entry=(1, 0.5), points=[(930, 985)], color="#9673a6")

    d.box(label("Tariffs never skip the human", "TARIFF_POLICY sets auto = 1.01, so “Proceed without a broker” is unreachable "
                "for tariff codes. Path probability had AUROC 0.63 on 332 test rulings: informative, not file-safe."),
          30, 190, 280, 150, "white", extra="align=left;spacingLeft=10;")
    d.box(label("Reusable", "Swap the four checks for your own: the gate only needs a ledger of what the classifier "
                "produced and a Decider question per risk."), 30, 380, 280, 110, "white", extra="align=left;spacingLeft=10;")
    return d.save()


# ------------------------------------------------------------------------------------------------
def aws_deployment() -> Path:
    d = Diagram("aws-deployment", 1720, 900)
    d.text("AWS deployment used for the evaluation and the demo", 30, 14, 1000, 30, size=22, bold=True)
    d.text("The Decider host has no inbound ports: it is driven over SSM and reaches Bedrock and S3 through an instance role.",
           30, 44, 1200, 22, size=12, color=MUTED)

    laptop = d.box(label("Developer laptop", "infra/remote.ps1 · deploy_site.ps1<br>aws CLI, profile “hackathon”"),
                   30, 340, 200, 100, "grey")

    cloud = d.vertex("AWS Cloud · us-east-1", 270, 90, 1260, 700,
                     "points=[[0,0],[0.25,0],[0.5,0],[0.75,0],[1,0],[1,0.25],[1,0.5],[1,0.75],[1,1],[0.75,1],[0.5,1],[0.25,1],"
                     "[0,1],[0,0.75],[0,0.5],[0,0.25]];outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=13;"
                     "fontStyle=1;container=1;pointerEvents=0;collapsible=0;recursiveResize=0;shape=mxgraph.aws4.group;"
                     "grIcon=mxgraph.aws4.group_aws_cloud;strokeColor=#232F3E;fillColor=none;verticalAlign=top;align=left;"
                     "spacingLeft=30;fontColor=#232F3E;dashed=0;")

    ssm = d.aws_icon("systems_manager", "#E7157B", 40, 120, 64, cloud)
    d.text(label("Systems Manager", "send-command over HTTPS<br>no SSH, no open ports"), 10, 190, 130, 56, size=11, align="center", parent=cloud)
    s3 = d.aws_icon("s3", "#7AA116", 40, 400, 64, cloud)
    d.text(label("S3 bucket (private)", "code zip pushed from laptop<br>results synced back"), 5, 470, 140, 56, size=11, align="center", parent=cloud)

    vpc = d.vertex("Default VPC · security group with no inbound rules", 230, 90, 590, 560,
                   "fillColor=none;strokeColor=#248814;dashed=1;verticalAlign=top;align=left;spacingLeft=12;fontColor=#248814;"
                   "html=1;whiteSpace=wrap;container=1;pointerEvents=0;collapsible=0;fontSize=12;fontStyle=1;rounded=1;arcSize=2;",
                   cloud)
    ec2 = d.container("EC2 g6.xlarge · NVIDIA L4 · Deep Learning AMI (Ubuntu 22.04)", 30, 50, 530, 470, "orange", start=36, parent=vpc)
    dec = d.box(label("strands-decider serve", "systemd · 127.0.0.1:8099 · /v1systemone<br>binds localhost only, never exposed"),
                30, 60, 470, 80, "green", ec2, extra="strokeWidth=2.5;")
    run = d.box(label("TariffTrail", "run_eval.py (332 test cases) · FastAPI demo · Strands agent"), 30, 190, 470, 70, "blue", ec2)
    d.box(label("SSM agent", "receives commands"), 30, 310, 220, 56, "grey", ec2)
    d.box(label("IAM instance profile", "Bedrock invoke · S3 read/write"), 280, 310, 220, 56, "red", ec2)
    d.box(label("Measured", "GPU: 72 ms per Decider call, 2.6 s per product<br>CPU (c7i.4xlarge): 2.5 s per call, 61 s per product"),
          30, 396, 470, 56, "yellow", ec2)

    bedrock = d.aws_icon("bedrock", "#01A88D", 960, 150, 64, cloud)
    d.text(label("Amazon Bedrock", "Titan Text Embeddings V2<br>Nova Pro (Converse)"), 920, 220, 150, 60, size=11, align="center", parent=cloud)
    budgets = d.aws_icon("budgets_2", "#7AA116", 960, 380, 64, cloud)
    d.text(label("AWS Budgets", "$50 per month alert → email"), 920, 450, 150, 40, size=11, align="center", parent=cloud)
    amplify = d.aws_icon("amplify", "#DD344C", 960, 550, 64, cloud)
    d.text(label("AWS Amplify Hosting", "replay-only demo · 392 recorded runs"), 910, 620, 170, 40, size=11, align="center", parent=cloud)

    visitors = d.vertex("Judges / visitors", 1610, 560, 44, 84,
                        f"shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;fontSize=11;"
                        f"fontColor={INK};strokeColor=#666666;fillColor=#f5f5f5;")

    d.edge(laptop, ssm, "", exit=(1, 0.3), entry=(0, 0.5))
    d.edge(laptop, s3, "", exit=(1, 0.7), entry=(0, 0.5))
    d.edge(ssm, ec2, "run shell command", exit=(1, 0.5), entry=(0, 0.1), color="#E7157B")
    d.edge(s3, ec2, "pull bundle · sync results", exit=(1, 0.5), entry=(0, 0.62), both=True, color="#7AA116")
    d.edge(dec, run, "", exit=(0.5, 1), entry=(0.5, 0), both=True, color="#2d6a4f")
    d.edge(run, bedrock, "Converse · embeddings (via IAM role)", exit=(1, 0.5), entry=(0, 0.5), color="#01A88D",
           points=[(1160, 455), (1160, 272)])
    d.edge(laptop, amplify, "deploy_site.ps1 (zip)", exit=(0.5, 1), entry=(0, 0.5), color="#DD344C",
           points=[(130, 840), (1150, 840), (1150, 672)])
    d.edge(amplify, visitors, "HTTPS", exit=(1, 0.5), entry=(0, 0.3), color="#DD344C")
    return d.save()


if __name__ == "__main__":
    for build in (system_architecture, calibrated_tree_descent, guardrail_flow, aws_deployment):
        print("wrote", build().name)
