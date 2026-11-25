# SPDX-License-Identifier: GPL-3.0-or-later
"""Cherche, pour chaque point de test posé sur une piste, l'endroit le plus dégagé de la face supérieure.
Écrit gen/tp.json, lu par pcb_rev3.py. À lancer avec le Python de KiCad sur la carte déjà révisée."""
import json
import math
import os

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
b = pcbnew.LoadBoard(os.path.join(HERE, "..", "kicad", "portail.kicad_pcb"))
mm = pcbnew.ToMM
F = pcbnew.F_Cu
R = 0.75                       # rayon de la pastille
WANT = {"TP3": "ISENSE1", "TP4": "ISENSE2"}


def P(v):
    return (mm(v.x) - 50, mm(v.y) - 50)


def dseg(p, a, c):
    ax, ay, cx, cy = a[0], a[1], c[0], c[1]
    dx, dy = cx - ax, cy - ay
    L2 = dx * dx + dy * dy
    t = 0 if L2 == 0 else max(0, min(1, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def dbox(p, box):
    x0, y0, x1, y1 = box
    return math.hypot(max(x0 - p[0], 0, p[0] - x1), max(y0 - p[1], 0, p[1] - y1))


segs, vias, pads, yards, holes = [], [], [], [], []
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        vias.append((t.GetNetname(), P(t.GetPosition()), mm(t.GetWidth(F)) / 2))
    else:
        segs.append((t.GetNetname(), t.GetLayer(), P(t.GetStart()), P(t.GetEnd()), mm(t.GetWidth()) / 2))
for fp in b.GetFootprints():
    for p in fp.Pads():
        bb = p.GetBoundingBox()
        box = (mm(bb.GetLeft()) - 50, mm(bb.GetTop()) - 50, mm(bb.GetRight()) - 50, mm(bb.GetBottom()) - 50)
        if p.IsOnLayer(F):
            pads.append((p.GetNetname(), box))
    c = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
    if c.GetWidth() > 0:
        yards.append((fp.GetReference(), (mm(c.GetLeft()) - 50, mm(c.GetTop()) - 50, mm(c.GetRight()) - 50, mm(c.GetBottom()) - 50)))
power = [z for z in b.Zones() if not z.GetIsRuleArea() and z.IsOnLayer(F) and z.GetAssignedPriority() >= 3]


def margin(p, netname):
    """Plus petite distance entre le bord de la pastille et un obstacle (négatif = collision)."""
    m = min(p[0], p[1], 150 - p[0], 100 - p[1]) - R - 1.0
    for n, lay, a, c, w in segs:
        if lay == F and n != netname:
            m = min(m, dseg(p, a, c) - w - R)
    for n, q, r in vias:
        m = min(m, math.hypot(p[0] - q[0], p[1] - q[1]) - r - R - (0.0 if n == netname else 0.0))
    for n, box in pads:
        m = min(m, dbox(p, box) - R - (0.3 if n == netname else 0.0))
    for ref, box in yards:
        m = min(m, dbox(p, box) - 1.3)
    for z in power:
        if z.GetNetname() != netname:
            for k in range(8):
                q = pcbnew.VECTOR2I(pcbnew.FromMM(50 + p[0] + (R + 0.3) * math.cos(k * math.pi / 4)),
                                    pcbnew.FromMM(50 + p[1] + (R + 0.3) * math.sin(k * math.pi / 4)))
                if z.HitTestFilledArea(F, q, 0):
                    return -1
    return m


out = {}
for ref, netname in WANT.items():
    best = (-9, None)
    for n, lay, a, c, w in segs:
        if n != netname or lay != F:
            continue
        L = math.hypot(c[0] - a[0], c[1] - a[1])
        for i in range(int(L / 0.25) + 1):
            t = 0 if L == 0 else min(1, i * 0.25 / L)
            p = (round(a[0] + t * (c[0] - a[0]), 2), round(a[1] + t * (c[1] - a[1]), 2))
            m = margin(p, netname)
            if m > best[0]:
                best = (m, p)
    print(ref, netname, "emplacement", best[1], "marge %.2f mm" % best[0])
    assert best[0] >= 0.25, "pas d'emplacement dégagé pour " + ref
    out[ref] = best[1]
json.dump(out, open(os.path.join(HERE, "tp.json"), "w"), indent=1)
