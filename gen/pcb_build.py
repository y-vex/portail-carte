# SPDX-License-Identifier: GPL-3.0-or-later
"""Crée le circuit imprimé : contour 150 x 100 mm, empreintes, nets, placement par blocs.

ATTENTION : ce script (avec pcb_route.py, pcb_import.py, pcb_all.py) a produit la carte v0.2 sous KiCad 7 / Linux.
La carte v0.3 n'est PAS régénérée par lui : elle est obtenue par gen/pcb_rev3.py, qui part de la carte v0.2 routée
(kicad/portail.base-v0.2.kicad_pcb) et y applique les corrections. Relancer pcb_all.py referait un routage complet
sans les composants ajoutés en v0.3 (il faudrait d'abord leur donner une position dans POS)."""
import csv
import json
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
K = os.path.join(HERE, "..", "kicad")
FPDIR = "/usr/share/kicad/footprints"
OX, OY = 50.0, 50.0          # origine de la carte sur la feuille
W, H = 150.0, 100.0


def mm(v):
    return pcbnew.FromMM(v)


def pt(x, y):
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


intent = json.load(open(os.path.join(K, "intent.json"), encoding="utf-8"))
parts = {}
for row in csv.DictReader(open(os.path.join(HERE, "..", "nomenclature.csv"), encoding="utf-8"), delimiter=";"):
    for ref in row["Repères"].split(", "):
        parts[ref] = (row["Valeur"], row["Empreinte KiCad"])
for i in range(1, 5):
    parts["H%d" % i] = ("M3", "MountingHole:MountingHole_3.2mm_M3")

board = pcbnew.BOARD()
nets = {}


def net(name):
    if name not in nets:
        n = pcbnew.NETINFO_ITEM(board, name)
        board.Add(n)
        nets[name] = n
    return nets[name]


fps = {}
problems = []
for ref, (value, fpname) in sorted(parts.items()):
    lib, name = fpname.split(":")
    fp = pcbnew.FootprintLoad(os.path.join(FPDIR, lib + ".pretty"), name)
    fp.SetReference(ref)
    fp.SetValue(value)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    board.Add(fp)
    fps[ref] = fp
    padnums = set()
    for pad in fp.Pads():
        num = pad.GetNumber()
        padnums.add(num)
        key = "%s.%s" % (ref, num)
        if key in intent:
            if intent[key]:
                pad.SetNet(net(intent[key]))
        elif num:
            problems.append("pastille sans broche : " + key)
    for key in intent:
        r, p = key.split(".", 1)
        if r == ref and p not in padnums:
            problems.append("broche sans pastille : " + key)

# ----------------------------------------------------------------- contour
for (x1, y1, x2, y2) in ((0, 0, W, 0), (W, 0, W, H), (W, H, 0, H), (0, H, 0, 0)):
    seg = pcbnew.PCB_SHAPE(board)
    seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
    seg.SetStart(pt(x1, y1))
    seg.SetEnd(pt(x2, y2))
    seg.SetLayer(pcbnew.Edge_Cuts)
    seg.SetWidth(mm(0.1))
    board.Add(seg)


# ----------------------------------------------------------------- placement
def bbox(fp):
    b = fp.GetBoundingBox(False, False)
    return (pcbnew.ToMM(b.GetX()) - OX, pcbnew.ToMM(b.GetY()) - OY,
            pcbnew.ToMM(b.GetWidth()), pcbnew.ToMM(b.GetHeight()))


def put(ref, x, y, rot=0):
    fp = fps[ref]
    fp.SetPosition(pt(x, y))
    if rot:
        fp.SetOrientationDegrees(rot)
    placed.add(ref)


def put_corner(ref, x, y, rot=0):
    """Place l'empreinte pour que le coin haut-gauche de son encombrement soit en (x, y)."""
    fp = fps[ref]
    fp.SetPosition(pt(0, 0))
    if rot:
        fp.SetOrientationDegrees(rot)
    bx, by, bw, bh = bbox(fp)
    fp.SetPosition(pt(x - bx, y - by))
    placed.add(ref)
    return bw, bh


def pack(refs, x0, y0, x1, y1, gap=1.0):
    """Rangement en étagères dans le rectangle donné."""
    x, y, rowh = x0, y0, 0
    for ref in refs:
        fp = fps[ref]
        fp.SetPosition(pt(0, 0))
        bx, by, bw, bh = bbox(fp)
        if bw > bh * 1.6 and bw > 6 and ref[0] in "RCD":
            pass
        if x + bw > x1 and x > x0:
            x, y, rowh = x0, y + rowh + gap, 0
        if y + bh > y1:
            problems.append("bloc trop petit pour " + ref)
        fp.SetPosition(pt(x - bx, y - by))
        placed.add(ref)
        x += bw + gap
        rowh = max(rowh, bh)


placed = set()
CX1, CX2 = 36.0, 78.0
POS = {
    "H1": (4.5, 4.5), "H2": (145.5, 4.5), "H3": (4.5, 95.5), "H4": (145.5, 95.5),
    "J1": (14, 92.5), "J2": (CX1 - 2.5, 92.5), "J3": (CX2 - 2.5, 92.5), "J5": (90, 93), "J4": (106, 93),
    "F1": (22, 80), "D1": (11, 62), "C7": (9, 51),
    "R13": (53, 47.5), "R14": (56.6, 47.5),
    "U4": (14, 14), "U11": (30, 14), "C8": (16.5, 20), "C24": (33, 20.5),
    "D2": (16, 25), "D3": (25, 25), "C9": (31, 25), "U5": (40, 26), "C10": (47.5, 24), "C11": (47.5, 27),
    "F4": (44, 10), "F5": (58, 10), "R15": (22, 31), "R16": (25.6, 31), "C19": (29.2, 31),
    "Q1": (92, 81), "Q2": (99, 81), "R30": (90.5, 76.5), "R32": (94.1, 76.5), "R31": (97.7, 76.5), "R33": (101.3, 76.5),
    "D8": (93, 72), "D9": (101, 72),
    "U7": (112, 80), "U8": (126, 80), "U9": (112, 72.5), "U10": (126, 72.5),
    "R22": (107, 85), "R23": (113, 85), "R24": (119, 85), "R25": (125, 85),
    "D4": (107, 67), "D5": (113, 67), "D6": (119, 67), "D7": (125, 67),
    "R26": (107, 63.5), "R27": (110.6, 63.5), "R28": (114.2, 63.5), "R29": (117.8, 63.5),
    "U1": (118, 12.75), "C12": (104.5, 13), "C13": (104.5, 16), "R17": (104.5, 19), "C14": (104.5, 21.5),
    "SW2": (100, 43), "SW1": (112, 43), "SW3": (124, 43), "R18": (106, 48), "R19": (118, 48),
    "R34": (133, 31), "D10": (137, 31), "R35": (133, 34), "D11": (137, 34),
    "J7": (134, 12), "J8": (139.5, 12),
    "J6": (146.0, 52), "U6": (130.5, 52), "R20": (131, 45.5), "R21": (131, 58.5),
}
ROT = {"J6": 90, "F1": 180, "F2": 270, "F3": 270, "C4": 270, "C6": 270}
DRV = [(CX1, "U2", "F2", "C1", "C3", "C4", ["R4", "R7", "R3", "R1", "C15", "R9"], ["R11", "C17", "C20", "C21"]),
       (CX2, "U3", "F3", "C2", "C5", "C6", ["R6", "R8", "R5", "R2", "C16", "R10"], ["R12", "C18", "C22", "C23"])]
for cx, u, f, cb, ca, cc, row1, row2 in DRV:
    POS[u] = (cx, 64)
    POS[f] = (cx - 12, 45.5)
    POS[cb] = (cx + 15.6, 63.5)
    POS[ca] = (cx - 7.9, 56.2)
    POS[cc] = (cx + 11.3, 64.8)
    for k, r in enumerate(row1):
        POS[r] = (cx - 5 + 3.6 * k, 53)
    for k, r in enumerate(row2):
        POS[r] = (cx - 5 + 3.6 * k, 50.5)
    POS[row2[2]] = (cx - 5.9, 82.5)      # antiparasite sortie A, au bord du couloir
    POS[row2[3]] = (cx + 5.9, 82.5)      # antiparasite sortie B
    ROT[row2[3]] = 180
for ref, (x, y) in POS.items():
    put(ref, x, y, ROT.get(ref, 0))


def pads(ref, num):
    return [((pcbnew.ToMM(p.GetPosition().x) - OX), (pcbnew.ToMM(p.GetPosition().y) - OY))
            for p in fps[ref].Pads() if p.GetNumber() == str(num)]


# ----------------------------------------------------------------- zones et vias de puissance
def zone(netname, layer, pts, prio, full=True):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNetCode(net(netname).GetNetCode())
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(mm(OX + x), mm(OY + y))
    z.SetAssignedPriority(prio)
    z.SetMinThickness(mm(0.25))
    z.SetLocalClearance(mm(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL if full else pcbnew.ZONE_CONNECTION_THERMAL)
    z.SetIsFilled(False)
    board.Add(z)
    if prio == 3:
        # zone interdite aux pistes : le routeur automatique ne doit pas découper le cuivre de puissance
        k = pcbnew.ZONE(board)
        k.SetLayer(layer)
        k.SetIsRuleArea(True)
        k.SetDoNotAllowTracks(True)
        k.SetDoNotAllowVias(False)
        k.SetDoNotAllowCopperPour(False)
        k.SetDoNotAllowPads(False)
        k.SetDoNotAllowFootprints(False)
        ko = k.Outline()
        ko.NewOutline()
        for x, y in pts:
            ko.Append(mm(OX + x), mm(OY + y))
        board.Add(k)


def rect(x1, y1, x2, y2):
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def via(netname, x, y):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pt(x, y))
    v.SetDrill(mm(0.4))
    v.SetWidth(mm(0.8))
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(net(netname))
    board.Add(v)


F, B = pcbnew.F_Cu, pcbnew.B_Cu


def track(netname, layer, x1, y1, x2, y2, w=0.2):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(pt(x1, y1))
    t.SetEnd(pt(x2, y2))
    t.SetWidth(mm(w))
    t.SetLayer(layer)
    t.SetNet(net(netname))
    board.Add(t)


# USB-C : les deux pastilles D+ (A6 et B6) sont reliées par la face inférieure, avant le routage automatique
for yy in (pads("J6", "A6")[0][1], pads("J6", "B6")[0][1]):
    track("USB_DP", F, pads("J6", "A6")[0][0], yy, 138.9, yy)
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pt(138.9, yy))
    v.SetDrill(mm(0.3))
    v.SetWidth(mm(0.6))
    v.SetLayerPair(F, B)
    v.SetNet(net("USB_DP"))
    board.Add(v)
track("USB_DP", B, 138.9, pads("J6", "A6")[0][1], 138.9, pads("J6", "B6")[0][1])
# plans de masse
zone("GND", B, rect(0.5, 0.5, W - 0.5, H - 0.5), 0, full=False)
# entrée 24 V : bornier J1 -> fusible F1
zone("+24V_IN", F, [(11.6, 86.6), (19.6, 86.6), (19.6, 74.6), (24.4, 74.6), (24.4, 90.2), (16.4, 90.2), (16.4, 96.5), (11.6, 96.5)], 3)
# bus 24 V : F1 -> colonne de gauche -> barre horizontale vers F2 et F3
zone("VBUS", F, [(5.5, 38), (CX2 - 6.5, 38), (CX2 - 6.5, 44.6), (14.2, 44.6), (14.2, 82.4), (5.5, 82.4)], 3)
# masse de la diode TVS D1 : petite zone et quatre vias vers le plan inférieur
zone("GND", F, rect(14.5, 60.2, 18.8, 63.8), 4)
for vx in (16.7, 17.9):
    for vy in (61.0, 63.0):
        via("GND", vx, vy)
# prise du bus 24 V pour les convertisseurs et la mesure de tension (accessible au routeur)
zone("VBUS", F, rect(17, 36.2, 23, 38.4), 5)
via("VBUS", 20, 37.1)
for n, (cx, u, f, cb, ca, cc, row1, row2) in enumerate(DRV, 1):
    vm, a, b = "VM%d" % n, "M%d_A" % n, "M%d_B" % n
    y_vm = (62.72, 64.52)
    y_out = (64.76, 66.5)
    y_gnd = (66.72, 68.5)
    # VM : fusible -> broches gauches, et broches droites -> condensateur réservoir
    zone(vm, F, [(cx - 15.6, 53.4), (cx - 8.4, 53.4), (cx - 8.4, y_vm[0]), (cx - 2.1, y_vm[0]), (cx - 2.1, y_vm[1]), (cx - 15.6, y_vm[1])], 3)
    zone(vm, F, rect(cx + 2.1, y_vm[0], cx + 16.6, y_vm[1]), 3)
    # liaison VM gauche-droite par la face inférieure, au-dessus de la puce
    zone(vm, B, [(cx - 15.2, 58.6), (cx + 11.8, 58.6), (cx + 11.8, 64.4), (cx + 8.0, 64.4), (cx + 8.0, 60.6), (cx - 15.2, 60.6)], 3)
    for dx in (-14.2, -12.6, -11.0):
        via(vm, cx + dx, 59.6)
    for dx in (8.9, 10.5):
        via(vm, cx + dx, 63.55)
    # sorties moteur : broches -> couloir -> bornier
    zone(a, F, [(cx - 10, y_out[0]), (cx - 2.1, y_out[0]), (cx - 2.1, y_out[1]), (cx - 6.5, y_out[1]), (cx - 6.5, 85),
                (cx - 0.25, 85), (cx - 0.25, 96.5), (cx - 10, 96.5)], 3)
    zone(b, F, [(cx + 2.1, y_out[0]), (cx + 10, y_out[0]), (cx + 10, 96.5), (cx + 0.25, 96.5), (cx + 0.25, 85),
                (cx + 6.5, 85), (cx + 6.5, y_out[1]), (cx + 2.1, y_out[1])], 3)
    # masse de la puce : broches -> vias vers le plan inférieur, et vias thermiques sous la puce
    zone("GND", F, rect(cx - 5.7, y_gnd[0], cx - 2.1, y_gnd[1]), 4)
    zone("GND", F, rect(cx + 2.1, y_gnd[0], cx + 5.7, y_gnd[1]), 4)
    for sx in (-1, 1):
        via("GND", cx + sx * 5.0, 67.15)
        via("GND", cx + sx * 5.0, 68.1)
    for dy in (-1.8, 0, 1.8):
        via("GND", cx, 64 + dy)

# recouvrements d'encombrement
boxes = {}
for ref, fp in fps.items():
    bx, by, bw, bh = bbox(fp)
    if ref == "U1":
        bx, by, bw, bh = 118 - 9.6, 0, 19.2, 26.4
    boxes[ref] = (bx, by, bx + bw, by + bh)
    if ref != "U1" and (bx < 0.3 or by < 0.3 or bx + bw > W - 0.3 or by + bh > H - 0.3):
        problems.append("hors carte : %s %s" % (ref, [round(v, 1) for v in boxes[ref]]))
refs = sorted(boxes)
for i, a in enumerate(refs):
    for b in refs[i + 1:]:
        A, B = boxes[a], boxes[b]
        if A[0] < B[2] - 0.05 and B[0] < A[2] - 0.05 and A[1] < B[3] - 0.05 and B[1] < A[3] - 0.05:
            problems.append("chevauchement : %s / %s" % (a, b))

missing = sorted(set(fps) - placed)
if missing:
    problems.append("non placés : %s" % missing)

out = os.path.join(K, "portail.kicad_pcb")
pcbnew.SaveBoard(out, board)
print("empreintes :", len(fps), "| nets :", len(nets))
for p in problems:
    print("  !", p)
