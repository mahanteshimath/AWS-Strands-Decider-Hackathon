"""Build the US Harmonized Tariff Schedule as a decision tree.

Levels: root -> 22 sections -> chapters -> 4-digit headings -> indented lines (subheadings,
8-digit lines, 10-digit statistical suffixes and the unnumbered grouping rows between them,
such as "Of wool or fine animal hair:"). Every internal node is one decision; its children are
the options, worded with the official HTS text.

Input files come from `python data/fetch_hts.py`:
  data/raw/hts_full.json   exportList rows (htsno, indent, description, general duty)
  data/hts_sections.json   section and chapter titles from the HTS web app
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
SPECIAL_CHAPTERS = {"98", "99"}  # special provisions and temporary legislation: not product classification
_OTHER = re.compile(r"^others?\b[\s:;,.-]*$", re.IGNORECASE)
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def digits(code: str | None) -> str:
    return re.sub(r"\D", "", code or "")


def clean(text: str) -> str:
    return _WS.sub(" ", _TAGS.sub("", text or "")).strip()


@dataclass
class Node:
    id: str
    kind: str  # root | section | chapter | heading | line
    text: str  # official wording, cleaned
    code: str = ""  # digits only ("611011", "6110110015"); "" for grouping rows
    htsno: str = ""  # as printed ("6110.11.00.15")
    duty: str = ""  # general (column 1) rate of duty, when the line carries one
    parent: str | None = None
    children: list[str] = field(default_factory=list)

    @property
    def is_other(self) -> bool:
        return bool(_OTHER.match(self.text))


class HTSTree:
    """Implements the `tree_descent.Tree` protocol over the tariff schedule."""

    root_id = "root"

    def __init__(self, nodes: dict[str, Node], release: dict):
        self.nodes = nodes
        self.release = release
        self.by_code: dict[str, str] = {}
        for node in nodes.values():
            if node.code and node.kind in ("heading", "line"):
                self.by_code.setdefault(node.code, node.id)

    # ---- structure -------------------------------------------------------

    def __getitem__(self, node_id: str) -> Node:
        return self.nodes[node_id]

    @property
    def root(self) -> Node:
        return self.nodes["root"]

    def child_ids(self, node_id: str) -> list[str]:
        return list(self.nodes[node_id].children)

    def children(self, node_id: str) -> list[Node]:
        return [self.nodes[c] for c in self.nodes[node_id].children]

    def path(self, node_id: str) -> list[Node]:
        """Root-exclusive path from the top to `node_id`."""
        out = []
        node = self.nodes[node_id]
        while node.parent is not None:
            out.append(node)
            node = self.nodes[node.parent]
        return out[::-1]

    def code_of(self, node_id: str) -> str:
        """The most specific code on the way to `node_id` (grouping rows inherit their ancestor's)."""
        for node in reversed(self.path(node_id)):
            if node.code:
                return node.code
        return ""

    def is_terminal(self, node_id: str) -> bool:
        node = self.nodes[node_id]
        return not node.children and bool(node.code)

    def exists(self, code: str) -> bool:
        return digits(code) in self.by_code

    # ---- option wording --------------------------------------------------

    def option_text(self, node_id: str) -> str:
        """Self-contained wording for one option, so the decision model can compare siblings.

        A bare "Other" means nothing on its own, so it is rewritten against its siblings.
        """
        node = self.nodes[node_id]
        text = node.text.rstrip(":").strip()
        if node.kind == "section":
            # Section titles alone are vague ("Miscellaneous Manufactured Articles"); list what they hold.
            chapters = "; ".join(self.nodes[c].text.split(";")[0].strip() for c in node.children)
            return f"{text} (chapters: {chapters})"
        if node.kind == "chapter":
            return text
        if node.is_other and node.parent is not None:
            siblings = [
                self.nodes[s].text.rstrip(":").strip()
                for s in self.nodes[node.parent].children
                if s != node_id and not self.nodes[s].is_other
            ]
            if siblings:
                listed = "; ".join(siblings)
                if len(listed) > 280:
                    listed = listed[:277].rsplit(" ", 1)[0] + "..."
                return f"Other (anything not covered by: {listed})"
        return text

    def path_text(self, node_id: str) -> str:
        """The official wording from section to `node_id`, one line per level."""
        lines = []
        for node in self.path(node_id):
            label = {"section": "Section", "chapter": "Chapter"}.get(node.kind)
            if label:
                ident = node.id.split(":", 1)[1]
                lines.append(f"{label} {ident}: {node.text}")
            else:
                lines.append(f"{node.htsno or '(group)'}: {node.text.rstrip(':')}")
        return "\n".join(lines)

    def stats(self) -> dict:
        internal = [n for n in self.nodes.values() if n.children]
        fan = [len(n.children) for n in internal]
        return {
            "nodes": len(self.nodes),
            "decisions": len(internal),
            "terminal_codes": sum(1 for n in self.nodes.values() if not n.children and n.code),
            "max_options": max(fan),
            "two_or_three_options": sum(1 for f in fan if f <= 3),
            "other_options": sum(1 for n in self.nodes.values() if n.is_other),
        }


def build(rows: list[dict], sections: list[dict], release: dict | None = None) -> HTSTree:
    nodes: dict[str, Node] = {"root": Node(id="root", kind="root", text="Harmonized Tariff Schedule of the United States")}

    chapter_ids: dict[str, str] = {}
    for section in sections:
        sid = f"S:{section['section']}"
        nodes[sid] = Node(id=sid, kind="section", text=clean(section["title"]), parent="root")
        nodes["root"].children.append(sid)
        for chapter in section["chapters"]:
            num = f"{chapter['chapter']:02d}"
            if num in SPECIAL_CHAPTERS:
                continue
            cid = f"C:{num}"
            nodes[cid] = Node(id=cid, kind="chapter", text=clean(chapter["title"]), code=num, parent=sid)
            nodes[sid].children.append(cid)
            chapter_ids[num] = cid

    # Lines nest by `indent`; a line's parent is the nearest earlier line with a smaller indent.
    # That also absorbs the handful of rows whose indent skips a level in the source data.
    stack: list[tuple[int, str]] = []
    heading_id: str | None = None
    for index, row in enumerate(rows):
        htsno = (row.get("htsno") or "").strip()
        code = digits(htsno)
        indent = int(row.get("indent") or 0)
        text = clean(row.get("description") or "")

        if indent == 0:
            chapter = code[:2]
            if len(code) != 4 or chapter not in chapter_ids:
                heading_id = None  # chapters 98/99, or a malformed heading row
                stack = []
                continue
            heading_id = f"H:{code}"
            nodes[heading_id] = Node(
                id=heading_id, kind="heading", text=text, code=code, htsno=htsno,
                duty=(row.get("general") or "").strip(), parent=chapter_ids[chapter],
            )
            nodes[chapter_ids[chapter]].children.append(heading_id)
            stack = [(0, heading_id)]
            continue

        if heading_id is None:
            continue
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if not stack:
            stack = [(0, heading_id)]
        parent = stack[-1][1]
        node_id = f"R:{index}"
        nodes[node_id] = Node(
            id=node_id, kind="line", text=text, code=code, htsno=htsno,
            duty=(row.get("general") or "").strip(), parent=parent,
        )
        nodes[parent].children.append(node_id)
        stack.append((indent, node_id))

    # Grouping rows with nothing beneath them are dead ends: drop them so every leaf is a code.
    for node_id in [n.id for n in nodes.values() if n.kind == "line" and not n.children and not n.code]:
        nodes[nodes[node_id].parent].children.remove(node_id)
        del nodes[node_id]

    # Sections and chapters with no headings left (chapter 77 is reserved; 98/99 are excluded).
    for kind in ("chapter", "section"):
        for node_id in [n.id for n in nodes.values() if n.kind == kind and not n.children]:
            nodes[nodes[node_id].parent].children.remove(node_id)
            del nodes[node_id]

    return HTSTree(nodes, release or {})


@lru_cache(maxsize=1)
def load(data_dir: str | None = None) -> HTSTree:
    base = Path(data_dir) if data_dir else DATA
    rows = json.loads((base / "raw" / "hts_full.json").read_text(encoding="utf-8"))
    sections = json.loads((base / "hts_sections.json").read_text(encoding="utf-8"))
    release_path = base / "hts_release.json"
    release = json.loads(release_path.read_text(encoding="utf-8")) if release_path.exists() else {}
    return build(rows, sections, release)


if __name__ == "__main__":
    tree = load()
    print(tree.release.get("description"), tree.stats())
    leaf = tree.by_code["6110909028"]
    print(tree.path_text(leaf))
    print("options at each fork on the way down:")
    for node in tree.path(leaf)[-3:]:
        siblings = tree.children(node.parent)
        print(f"  choosing among {len(siblings)} under {tree[node.parent].htsno or tree[node.parent].id}:")
        for child in siblings:
            mark = "*" if child.id == node.id else " "
            print(f"    {mark} {child.htsno or '(group)':14} {tree.option_text(child.id)[:110]}")
