# SPDX-License-Identifier: GPL-3.0-or-later
"""Importe le résultat de Freerouting (.ses) dans la carte, remplit les zones, lance le contrôle des règles."""
import collections, os, re, sys
import pcbnew
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sexpr import parse, find, first
K = os.path.join(HERE, "..", "kicad")
PCB = os.path.join(K, "portail.kicad_pcb")
b = pcbnew.LoadBoard(PCB)
nc = b.GetDesignSettings().m_NetSettings.m_DefaultNetClass
nc.SetTrackWidth(pcbnew.FromMM(0.2)); nc.SetClearance(pcbnew.FromMM(0.15))
nc.SetViaDiameter(pcbnew.FromMM(0.6)); nc.SetViaDrill(pcbnew.FromMM(0.3))
ses = parse(open(os.path.join(K, "portail.ses")).read())
routes = first(ses, "routes")
res = first(routes, "resolution")
unit = 1000.0 * float(res[2]) if res[1] == "um" else None   # unités par mm
def P(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(float(x) / unit), pcbnew.FromMM(-float(y) / unit))
layers = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}
nt = nv = 0
for net in find(first(routes, "network_out"), "net"):
    ni = b.FindNet(str(net[1]))
    assert ni, net[1]
    for w in find(net, "wire"):
        path = first(w, "path")
        layer, width, pts = layers[str(path[1])], float(path[2]) / unit, path[3:]
        for i in range(0, len(pts) - 2, 2):
            t = pcbnew.PCB_TRACK(b)
            t.SetStart(P(pts[i], pts[i + 1])); t.SetEnd(P(pts[i + 2], pts[i + 3]))
            t.SetWidth(pcbnew.FromMM(width)); t.SetLayer(layer); t.SetNet(ni)
            b.Add(t); nt += 1
    for v in find(net, "via"):
        if first(v, "type") and first(v, "type")[1] == "protect":
            continue
        via = pcbnew.PCB_VIA(b)
        via.SetPosition(P(v[2], v[3])); via.SetDrill(pcbnew.FromMM(0.3)); via.SetWidth(pcbnew.FromMM(0.6))
        via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); via.SetNet(ni)
        b.Add(via); nv += 1
# liaison manuelle de la seconde pastille D+ de l'USB-C (A6), que le routeur laisse isolée
def seg(net, layer, x1, y1, x2, y2, w=0.2):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(pcbnew.VECTOR2I(pcbnew.FromMM(50 + x1), pcbnew.FromMM(50 + y1)))
    t.SetEnd(pcbnew.VECTOR2I(pcbnew.FromMM(50 + x2), pcbnew.FromMM(50 + y2)))
    t.SetWidth(pcbnew.FromMM(w)); t.SetLayer(layer); t.SetNet(b.FindNet(net)); b.Add(t)
def addvia(net, x, y, d=0.6, h=0.3):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pcbnew.VECTOR2I(pcbnew.FromMM(50 + x), pcbnew.FromMM(50 + y)))
    v.SetDrill(pcbnew.FromMM(h)); v.SetWidth(pcbnew.FromMM(d))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu); v.SetNet(b.FindNet(net)); b.Add(v)
# plan de masse en face supérieure, puis vias de couture entre les deux plans
z = pcbnew.ZONE(b)
z.SetLayer(pcbnew.F_Cu); z.SetNetCode(b.FindNet("GND").GetNetCode())
o = z.Outline(); o.NewOutline()
for x, y in ((0.5, 0.5), (149.5, 0.5), (149.5, 99.5), (0.5, 99.5)):
    o.Append(pcbnew.FromMM(50 + x), pcbnew.FromMM(50 + y))
z.SetAssignedPriority(0); z.SetMinThickness(pcbnew.FromMM(0.25)); z.SetLocalClearance(pcbnew.FromMM(0.3))
z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
b.Add(z)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
gz = {zz.GetLayer(): zz for zz in b.Zones() if not zz.GetIsRuleArea() and zz.GetNetname() == "GND" and zz.GetAssignedPriority() == 0}
occupied = [(pcbnew.ToMM(v.GetPosition().x) - 50, pcbnew.ToMM(v.GetPosition().y) - 50) for v in b.GetTracks() if v.GetClass() == "PCB_VIA"]
for fp in b.GetFootprints():
    for pad in fp.Pads():
        occupied.append((pcbnew.ToMM(pad.GetPosition().x) - 50, pcbnew.ToMM(pad.GetPosition().y) - 50))
def both(x, y):
    for dx, dy in ((0, 0), (0.9, 0), (-0.9, 0), (0, 0.9), (0, -0.9), (0.65, 0.65), (-0.65, 0.65), (0.65, -0.65), (-0.65, -0.65)):
        p = pcbnew.VECTOR2I(pcbnew.FromMM(50 + x + dx), pcbnew.FromMM(50 + y + dy))
        for lay in (pcbnew.F_Cu, pcbnew.B_Cu):
            if not gz[lay].HitTestFilledArea(lay, p, 0):
                return False
    return all((x - ox) ** 2 + (y - oy) ** 2 > 2.2 ** 2 for ox, oy in occupied)
ns = 0
yy = 2.5
while yy < 98:
    xx = 2.5
    while xx < 148:
        if both(xx, yy) and not (93 < xx < 143 and yy < 8):
            addvia("GND", xx, yy, 0.8, 0.4); occupied.append((xx, yy)); ns += 1
        xx += 3.0
    yy += 3.0
print("vias de couture :", ns)
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(PCB, b)
b = pcbnew.LoadBoard(PCB)
rep = os.path.join(K, "drc.txt")
pcbnew.WriteDRCReport(b, rep, pcbnew.EDA_UNITS_MILLIMETRES, True)
t = open(rep).read()
print("segments de piste :", nt, "| vias ajoutés :", nv)
print([l for l in t.splitlines() if l.startswith("** Found")])
print(collections.Counter(re.findall(r"^\[(\w+)\]", t, re.M)).most_common(15))
un = re.findall(r"\[unconnected_items\].*?\n.*?\n\s+@.*?: (.*?)\n\s+@.*?: (.*?)\n", t, re.S)
na = re.findall(r"\[items_not_allowed\].*?\n.*?\n\s+@.*?: (.*?)\n", t, re.S)
print("interdits :", na[:6])
for u in un[:40]:
    print("  non connecté :", u)
