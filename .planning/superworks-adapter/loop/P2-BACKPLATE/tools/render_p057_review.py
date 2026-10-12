"""P2-BACKPLATE: magnified review of the ten undetermined p057 sheet-09 cases (read-only, PNG only).

Panels: A template device field (free text at the table top), B title block (where a device caption would be),
C the SW identity point of the first undetermined case. Reuses the panel drawing of render_judge.py.
Usage: python render_p057_review.py <cases.json> <out_png>
"""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from render_judge import panel

cases_path, out_png = sys.argv[1], sys.argv[2]
cases = [c for c in json.load(open(cases_path, encoding="utf-8")) if c["project"] == "p057" and c["cls"] == "device_prefix_differs"]
c0 = cases[0]
dxf = c0["dxf"]
fig, axes = plt.subplots(1, 3, figsize=(16.5, 6.2), dpi=120)
fig.subplots_adjust(left=0.01, right=0.99, top=0.9, bottom=0.02, wspace=0.08)
panel(axes[0], dxf, (215.0, 268.0), 70.0, [("row", (210.29, 281.47), "#1f4fd1", "template '1-1n'")], "A template device field (top of table)")
panel(axes[1], dxf, (300.0, 40.0), 70.0, [("row", (317.2, 9.8), "#1f4fd1", "REAR WIRING caption")], "B title block: caption / device name")
panel(axes[2], dxf, (c0["sw_id_xy"][0], c0["sw_id_xy"][1]), 35.0,
      [("sw", c0["sw_id_xy"], "#1a9b3a", "SW %s" % c0["sw_identity"]), ("R", c0["R_xy"], "#c81e1e", "R %s" % c0["R"])],
      "C SW identity point (case %d)" % c0["case_no"])
fig.text(0.01, 0.955, "p057 sheet 09 (装置背板), undetermined cases %s: V1 device 1-1n (template) vs SW device 7n" %
         ", ".join(str(c["case_no"]) for c in cases), fontsize=10, ha="left")
fig.savefig(out_png, dpi=120)
plt.close(fig)
print("wrote", out_png)
