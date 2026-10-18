# Architecture diagrams

Editable [draw.io](https://www.drawio.com) diagrams used in the main README.

| Diagram | Source | Image |
|---|---|---|
| System overview | `system-architecture.drawio` | `system-architecture.drawio.png` |
| Calibrated Tree Descent on a real trace | `calibrated-tree-descent.drawio` | `calibrated-tree-descent.drawio.png` |
| ClassificationGate decision flow | `guardrail-flow.drawio` | `guardrail-flow.drawio.png` |
| AWS deployment | `aws-deployment.drawio` | `aws-deployment.drawio.png` |

The `.drawio.png` files embed their own diagram XML: open one in draw.io (File > Open) and it is fully editable.

## Edit

Either open a `.drawio` file in draw.io and export, or change [`build_diagrams.py`](build_diagrams.py) (every box and
arrow is a coordinate in one Python file) and regenerate:

```bash
python docs/architecture/build_diagrams.py        # rewrites the four .drawio files
```

CI regenerates the `.drawio` files and fails if they differ from the committed ones.

## Export to PNG

With the [draw.io desktop](https://github.com/jgraph/drawio-desktop/releases) CLI (`-e` embeds the source):

```bash
cd docs/architecture
draw.io -x -f png -e -s 1.5 -b 10 -o system-architecture.drawio.png system-architecture.drawio
```

On Windows the binary is `"C:\Program Files\draw.io\draw.io.exe"`. Some draw.io versions write a truncated PNG
trailer when embedding XML; repair it with the helper from the [drawio-skill](https://github.com/Agents365-ai/drawio-skill)
(`scripts/repair_png.py`) if a PNG will not open in strict viewers. PNG is used rather than SVG because GitHub does not
render draw.io's SVG text reliably.

## Data behind the numbers

The probabilities in the Calibrated Tree Descent diagram are the recorded Decider outputs for ruling N357194
(`eval/results/test/tariff_trail.jsonl`). The accuracy, token and latency figures come from `eval/RESULTS.md`.
