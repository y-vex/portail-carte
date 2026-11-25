# SPDX-License-Identifier: GPL-3.0-or-later
"""Révision v0.4 de la carte : part de la carte v0.3 (kicad/portail.base-v0.3.kicad_pcb) et remplace les pièces
introuvables : drivers DRV8245S en VQFN-HR (réglages par SPI sur les fils existants), régulateur AP7361C-33ER,
MOSFET IPD50P04P4L-11. Coordonnées en millimètres dans le repère de la feuille (carte = feuille - 50).
À lancer avec le Python de KiCad 10 (module pcbnew), après gen/build.py (qui écrit intent.json)."""
import json
import math
import os

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
K = os.path.join(HERE, "..", "kicad")
FPDIR = os.environ.get("KICAD_FOOTPRINTS", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
OX = OY = 0.0
MM, mm = pcbnew.FromMM, pcbnew.ToMM
F, B = pcbnew.F_Cu, pcbnew.B_Cu

b = pcbnew.LoadBoard(os.path.join(K, "portail.base-v0.3.kicad_pcb"))
intent = json.load(open(os.path.join(K, "intent.json"), encoding="utf-8"))
IO = pcbnew.PCB_IO_KICAD_SEXPR()


GRAVE = []


def rm(item):
    """Retire un objet de la carte en le gardant référencé : sinon le ramasse-miettes de Python le détruit
    pendant le script et pcbnew 10 se met à renvoyer des objets inutilisables."""
    GRAVE.append(item)
    b.Remove(item)


def pt(x, y):
    return pcbnew.VECTOR2I(MM(OX + x), MM(OY + y))


def xy(v):
    return (mm(v.x) - OX, mm(v.y) - OY)


NETS = {str(k): v for k, v in b.GetNetsByName().items()}   # pris une fois : FindNet rend parfois un objet inutilisable


def net(name):
    if name not in NETS:
        NETS[name] = pcbnew.NETINFO_ITEM(b, name)
        b.Add(NETS[name])
    return NETS[name]


def at(v, x, y, tol=0.03):
    px, py = xy(v)
    return abs(px - x) < tol and abs(py - y) < tol


def del_via(x, y):
    hit = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and at(t.GetPosition(), x, y)]
    assert len(hit) == 1, ("via introuvable", x, y, len(hit))
    rm(hit[0])


def find_seg(layer, a, c):
    hit = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLayer() == layer and
           ((at(t.GetStart(), *a) and at(t.GetEnd(), *c)) or (at(t.GetStart(), *c) and at(t.GetEnd(), *a)))]
    assert len(hit) == 1, ("piste introuvable", a, c, len(hit))
    return hit[0]


def add_via(netname, x, y, d=0.8, h=0.4):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(pt(x, y))
    v.SetDrill(MM(h))
    try:
        v.SetWidth(F, MM(d))
    except TypeError:
        v.SetWidth(MM(d))
    v.SetLayerPair(F, B)
    v.SetNet(net(netname))
    b.Add(v)


def add_track(netname, layer, pts, w=0.4):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetStart(pt(x1, y1))
        t.SetEnd(pt(x2, y2))
        t.SetWidth(MM(w))
        t.SetLayer(layer)
        t.SetNet(net(netname))
        b.Add(t)


def add_fp(ref, fpname, value, x, y, rot=0, rename=None):
    lib, name = fpname.split(":")
    fp = IO.FootprintLoad(os.path.join(K if lib == "portail" else FPDIR, lib + ".pretty"), name)   # pcbnew.FootprintLoad est instable en KiCad 10
    assert fp, fpname
    fp.SetReference(ref)
    fp.SetValue(value)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    fp.SetPosition(pt(x, y))
    if rot:
        fp.SetOrientationDegrees(rot)
    b.Add(fp)
    nums = set()
    for pad in fp.Pads():
        if rename and pad.GetNumber() in rename:
            pad.SetNumber(rename[pad.GetNumber()])
        num = pad.GetNumber()
        if not num:
            continue
        nums.add(num)
        key = "%s.%s" % (ref, num)
        assert key in intent, "pastille sans broche au schéma : " + key
        if intent[key]:
            pad.SetNet(net(intent[key]))
    for key in intent:
        r, p = key.split(".", 1)
        assert r != ref or p in nums, "broche sans pastille : " + key
    return fp


def pad_xy(ref, num):
    return [xy(p.GetPosition()) for p in b.FindFootprintByReference(ref).Pads() if p.GetNumber() == str(num)]


def outline_bbox(z):
    bb = z.GetBoundingBox()
    return tuple(round(v, 2) for v in (mm(bb.GetLeft()), mm(bb.GetTop()), mm(bb.GetRight()), mm(bb.GetBottom())))


def del_zone_at(netname, layer, left, top):
    """Supprime la zone (et sa zone interdite jumelle) dont le coin haut gauche du contour est (left, top)."""
    zs = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == netname and z.GetLayer() == layer
          and abs(outline_bbox(z)[0] - left) < 0.02 and abs(outline_bbox(z)[1] - top) < 0.02]
    assert len(zs) == 1, ("zone introuvable", netname, left, top, len(zs))
    bb = outline_bbox(zs[0])
    ks = [k for k in b.Zones() if k.GetIsRuleArea() and k.GetLayer() == layer and outline_bbox(k) == bb]
    assert len(ks) == 1, ("zone interdite introuvable", bb, len(ks))
    rm(ks[0])
    rm(zs[0])


def add_zone(netname, layer, pts, prio, keepout=False):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    z.SetNetCode(net(netname).GetNetCode())
    o = z.Outline()
    o.NewOutline()
    for x, y in pts:
        o.Append(MM(x), MM(y))
    z.SetAssignedPriority(prio)
    z.SetMinThickness(MM(0.25))
    z.SetLocalClearance(MM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    b.Add(z)
    if keepout:
        k = pcbnew.ZONE(b)
        k.SetLayer(layer)
        k.SetIsRuleArea(True)
        k.SetDoNotAllowTracks(True)
        k.SetDoNotAllowVias(False)
        k.SetDoNotAllowZoneFills(False) if hasattr(k, "SetDoNotAllowZoneFills") else k.SetDoNotAllowCopperPour(False)
        k.SetDoNotAllowPads(False)
        k.SetDoNotAllowFootprints(False)
        ko = k.Outline()
        ko.NewOutline()
        for x, y in pts:
            ko.Append(MM(x), MM(y))
        b.Add(k)


def rect(x1, y1, x2, y2):
    return [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]


def del_segs(layer, spec):
    """spec : 'x1,y1>x2,y2 x1,y1>x2,y2 ...' (coordonnées relevées sur la carte v0.3)."""
    for s in spec.split():
        a, c = s.split(">")
        rm(find_seg(layer, tuple(map(float, a.split(","))), tuple(map(float, c.split(",")))))


def del_fp(ref):
    rm(b.FindFootprintByReference(ref))


def shift(pts, dx):
    return [(x + dx, y) for x, y in pts]


SIG = 0.2
# ------------------------------------------------------------------ 1. nouveaux noms des fils réutilisés
RENAME = {"M1_EN": "SDO1", "M1_PH": "M1_EN", "NFAULT1": "CS1_N", "M2_EN": "SDO2", "M2_PH": "CS2_N", "NFAULT2": "M2_EN",
          "DRVOFF": "SPI_SDI", "NSLEEP": "SPI_SCLK"}
todo = [(t, RENAME[t.GetNetname()]) for t in b.GetTracks() if t.GetNetname() in RENAME]
for t, new in todo:
    t.SetNet(net(new))
for t in [t for t in b.GetTracks() if t.GetNetname() in ("SR1", "DIAG1", "ITRIP1", "SR2", "DIAG2", "ITRIP2")]:
    rm(t)

# ------------------------------------------------------------------ 2. composants retirés
for ref in ("U2", "U3", "R3", "R4", "R5", "R6", "R7", "R8", "R12", "R13"):
    del_fp(ref)
CY = 114.8
for cx in (86.0, 128.0):
    for v in [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"
              and abs(mm(t.GetPosition().x) - cx) < 1.7 and 111.0 < mm(t.GetPosition().y) < 117.3]:
        rm(v)
# liaison de masse de l'ancienne broche 27 (MODE)
del_segs(F, "90.35,111.07>89.71,110.42 89.71,110.42>88.88,110.42")
del_via(90.35, 111.07)
del_segs(F, "131.64,110.42>130.88,110.42 132.03,110.04>131.64,110.42 132.03,108.14>132.03,110.04")
del_via(132.03, 108.14)
# retours de masse des résistances de réglage retirées (R3 à R8)
del_segs(F, "81.94,103.12>81.83,103.0 85.43,102.99>85.42,103.0 82.72,103.12>81.94,103.12 89.18,103.15>89.03,103.0 "
            "86.3,102.99>85.43,102.99 89.9,103.15>89.18,103.15 128.28,102.99>127.43,102.99 127.43,102.99>127.42,103.0 "
            "131.89,103.15>131.18,103.15 124.71,103.25>124.07,103.25 124.07,103.25>123.83,103.0 131.18,103.15>131.03,103.0")
for x, y in ((86.3, 102.99), (89.9, 103.15), (82.72, 103.12), (128.28, 102.99), (124.71, 103.25), (131.89, 103.15)):
    del_via(x, y)
# vias VM qui rejoignaient l'ancienne liaison VM de la face inférieure (déplacée sous le boîtier)
for x in (71.8, 73.4, 75.0, 113.8, 115.4, 117.0):
    del_via(x, 109.6)

# ------------------------------------------------------------------ 3. anciennes arrivées des signaux
# driver 1
del_segs(F, "81.68,111.61>82.44,112.38 79.47,100.04>79.47,104.92 103.09,96.77>82.74,96.77 104.8,97.46>103.87,97.46 "
            "103.87,97.46>103.83,97.5 82.44,112.38>83.12,112.38 81.68,107.12>81.68,111.61 82.74,96.77>79.47,100.04 "
            "79.47,104.92>81.68,107.12 103.83,97.5>103.09,96.77")                       # ex-DRVOFF
del_via(104.8, 97.46)
del_segs(F, "98.76,112.38>98.88,112.25 88.88,112.38>98.76,112.38")                       # ex-NSLEEP
del_via(98.88, 112.25)
find_seg(B, (98.88, 112.25), (98.88, 104.08)).SetStart(pt(98.88, 108.5)) if at(find_seg(B, (98.88, 112.25), (98.88, 104.08)).GetStart(), 98.88, 112.25) \
    else find_seg(B, (98.88, 112.25), (98.88, 104.08)).SetEnd(pt(98.88, 108.5))
del_segs(F, "82.09,111.32>82.49,111.72 82.66,107.3>82.09,107.87 82.09,107.87>82.09,111.32 82.49,111.72>83.12,111.72")   # ex-M1_EN
del_via(82.66, 107.3)
del_segs(B, "82.16,106.79>82.66,107.3")
del_segs(F, "83.8,111.08>83.12,111.08 86.38,107.33>86.38,108.5 86.38,108.5>83.8,111.08")  # ex-M1_PH
del_via(86.38, 107.33)
del_segs(B, "88.78,104.92>86.38,107.33")
del_segs(F, "90.97,103.77>90.97,111.25 90.5,111.72>88.88,111.72 90.97,111.25>90.5,111.72")   # IPROPI1
del_segs(F, "84.48,103.19>87.77,106.49 88.2,111.08>88.88,111.08 87.77,106.49>87.77,110.65 83.55,101.86>83.82,101.86 "
            "83.82,101.86>84.48,102.51 87.77,110.65>88.2,111.08 84.48,102.51>84.48,103.19")   # ex-NFAULT1
# driver 2
del_segs(F, "125.12,112.38>120.21,112.38 120.21,112.38>120.09,112.25")
del_via(120.09, 112.25)
del_segs(F, "152.58,112.18>131.07,112.18 131.07,112.18>130.88,112.38 157.39,107.37>152.58,112.18")
del_segs(F, "123.3,110.58>123.3,105.32 123.3,105.32>121.47,103.5 123.02,101.0>123.02,100.16 125.12,111.72>124.44,111.72 "
            "121.47,103.5>121.47,102.55 124.44,111.72>123.3,110.58 121.47,102.55>123.02,101.0 123.02,100.16>124.47,98.7")
del_segs(F, "126.57,110.31>125.8,111.08 126.57,108.08>126.57,110.31 125.8,111.08>125.12,111.08")
del_via(126.57, 108.08)
del_segs(F, "132.97,110.31>132.97,104.54 131.56,111.72>132.97,110.31 130.88,111.72>131.56,111.72")
del_segs(F, "124.42,100.5>123.83,100.5 126.55,107.28>126.55,102.62 124.55,100.63>124.42,100.5 130.2,111.08>127.12,107.99 "
            "126.55,102.62>124.55,100.63 124.55,100.63>125.87,99.31 127.12,107.85>126.55,107.28 130.88,111.08>130.2,111.08 "
            "127.12,107.99>127.12,107.85")
s = find_seg(F, (125.87, 99.31), (154.91, 99.31))
(s.SetStart if at(s.GetStart(), 125.87, 99.31) else s.SetEnd)(pt(139.4, 99.31))

# ------------------------------------------------------------------ 4. zones de cuivre autour des drivers
for dx, n in ((0.0, "1"), (42.0, "2")):
    vm, ma, mb = "VM" + n, "M%s_A" % n, "M%s_B" % n
    del_zone_at(vm, F, 70.4 + dx, 103.4)
    del_zone_at(vm, F, 88.1 + dx, 112.72)
    del_zone_at(vm, B, 70.8 + dx, 108.6)
    del_zone_at(ma, F, 76.0 + dx, 114.76)
    del_zone_at(mb, F, 86.25 + dx, 114.76)
    # VM : la languette se rétrécit près du boîtier pour laisser passer IPROPI et +3V3, puis recouvre la barre VM
    add_zone(vm, F, shift([(70.4, 103.4), (77.6, 103.4), (77.6, 112.72), (82.3, 112.72), (82.3, 113.75), (86.0, 113.75),
                           (86.0, 114.5), (70.4, 114.52)], dx), 3, keepout=True)
    add_zone(vm, F, shift([(86.0, 113.75), (89.6, 113.75), (89.6, 112.72), (102.6, 112.72), (102.6, 114.52), (86.0, 114.5)], dx), 4, keepout=True)
    add_zone(vm, B, shift(rect(77.8, 112.6, 97.8, 114.6), dx), 3, keepout=True)      # liaison VM sous le boîtier
    add_zone(ma, F, shift([(76.0, 114.76), (85.9, 114.76), (85.9, 116.5), (79.5, 116.5), (79.5, 135.0), (85.75, 135.0),
                           (85.75, 146.5), (76.0, 146.5)], dx), 3, keepout=True)
    add_zone(mb, F, shift([(86.1, 114.76), (96.0, 114.76), (96.0, 146.5), (86.25, 146.5), (86.25, 135.0), (92.5, 135.0),
                           (92.5, 116.5), (86.1, 116.5)], dx), 3, keepout=True)
    add_zone("GND", F, shift(rect(83.6, 116.45, 88.4, 119.4), dx), 6)                # masse sous la barre GND du boîtier
    for x, y in ((84.4, 118.5), (86.6, 118.5), (87.7, 118.5)):
        add_via("GND", x + dx, y, 0.6, 0.3)
    for x, y in ((83.3, 114.12), (88.7, 114.12), (78.4, 113.2), (78.4, 114.0), (79.2, 113.6)):
        add_via(vm, x + dx, y, 0.6, 0.3)

# ------------------------------------------------------------------ 5. nouveaux drivers et leurs liaisons
add_fp("U2", "portail:DRV8245_VQFN-HR-16_RXZ", "DRV8245SQRXZRQ1", 86.0, CY)
add_fp("U3", "portail:DRV8245_VQFN-HR-16_RXZ", "DRV8245SQRXZRQ1", 128.0, CY)
PY = CY - 2.625
# driver 1
add_track("SPI_SDI", F, [(85.75, PY), (85.75, 107.4), (98.5, 107.4), (99.0, 106.9), (99.0, 105.0), (105.42, 105.0), (106.11, 104.31)], SIG)
add_via("SPI_SDI", 106.11, 104.31, 0.6, 0.3)
add_track("SPI_SCLK", F, [(86.25, PY), (86.25, 107.9), (98.28, 107.9), (98.88, 108.5)], SIG)
add_via("SPI_SCLK", 98.88, 108.5, 0.6, 0.3)
add_track("SDO1", F, [(85.25, PY), (85.25, 111.3), (84.45, 110.5)], SIG)
add_via("SDO1", 84.45, 110.5, 0.6, 0.3)
add_track("SDO1", B, [(82.16, 106.79), (82.16, 108.21), (84.45, 110.5)], SIG)
add_track("CS1_N", F, [(86.75, PY), (86.75, 111.3), (87.55, 110.5)], SIG)
add_via("CS1_N", 87.55, 110.5, 0.6, 0.3)
add_track("CS1_N", B, [(83.55, 101.86), (85.6, 103.91), (85.6, 108.55), (87.55, 110.5)], SIG)
add_track("M1_EN", F, [(87.625, CY - 1.875), (88.9, CY - 1.875), (89.3, 112.525), (89.3, 111.6)], SIG)
add_via("M1_EN", 89.3, 111.6, 0.6, 0.3)
add_track("M1_EN", B, [(88.78, 104.92), (88.78, 110.6), (89.3, 111.12), (89.3, 111.6)], SIG)
add_track("GND", F, [(87.625, CY - 2.375), (88.45, CY - 2.375)], SIG)
add_track("IPROPI1", F, [(90.97, 103.77), (90.14, 104.6), (83.8, 104.6), (83.2, 105.2), (83.2, CY - 1.875), (84.375, CY - 1.875)], SIG)
add_track("+3V3", F, [(80.17, 100.5), (80.17, 103.4), (82.6, 105.83), (82.6, CY - 1.375), (84.375, CY - 1.375)], SIG)
# driver 2
add_track("SDO2", F, [(127.25, PY), (127.25, 111.2), (126.25, 110.2), (126.0, 110.2)], SIG)
add_via("SDO2", 126.0, 110.2, 0.6, 0.3)
add_via("SDO2", 124.47, 98.7, 0.6, 0.3)
add_track("SDO2", B, [(124.47, 98.7), (124.47, 108.67), (126.0, 110.2)], SIG)
add_track("SPI_SDI", F, [(127.75, PY), (127.75, 110.6), (127.3, 110.15), (127.3, 109.7)], SIG)
add_via("SPI_SDI", 127.3, 109.7, 0.6, 0.3)
add_track("SPI_SDI", B, [(120.09, 112.25), (125.5, 112.25), (127.3, 110.45), (127.3, 109.7)], SIG)
add_track("SPI_SCLK", F, [(128.25, PY), (128.25, 107.9), (156.86, 107.9), (157.39, 107.37)], SIG)
add_track("CS2_N", F, [(128.75, PY), (128.75, 111.2), (129.55, 110.4), (129.9, 110.4)], SIG)
add_via("CS2_N", 129.9, 110.4, 0.6, 0.3)
add_track("CS2_N", B, [(126.57, 108.08), (126.87, 108.38), (128.9, 108.38), (129.9, 109.38), (129.9, 110.4)], SIG)
add_track("M2_EN", F, [(129.625, CY - 1.875), (130.9, CY - 1.875), (131.3, 112.525), (131.3, 111.6)], SIG)
add_via("M2_EN", 131.3, 111.6, 0.6, 0.3)
add_via("M2_EN", 139.4, 99.31, 0.6, 0.3)
add_track("M2_EN", B, [(139.4, 99.31), (139.4, 99.6), (137.0, 102.0), (137.0, 104.5), (133.5, 108.0), (133.5, 109.4), (131.3, 111.6)], SIG)
add_track("GND", F, [(129.625, CY - 2.375), (130.45, CY - 2.375)], SIG)
add_track("IPROPI2", F, [(132.97, 104.54), (125.8, 104.54), (125.2, 105.14), (125.2, CY - 1.875), (126.375, CY - 1.875)], SIG)
add_track("+3V3", F, [(122.17, 100.5), (122.17, 103.0), (124.6, 105.43), (124.6, CY - 1.375), (126.375, CY - 1.375)], SIG)

# ------------------------------------------------------------------ 6. régulateur 3,3 V au brochage R (1 GND, 2 sortie, 3 entrée)
del_segs(F, "86.85,73.7>81.35,73.7 81.35,73.7>80.05,75.0 86.85,78.3>95.42,78.3 95.42,78.3>96.72,77.0")
del_segs(F, "88.01,74.95>87.9,74.95 92.1,74.95>93.15,76.0 87.9,74.95>86.85,76.0 91.64,74.95>92.1,74.95")   # la languette n'est plus à la masse
del_via(88.01, 74.95)
del_via(91.64, 74.95)
add_track("+3V3", F, [(86.85, 76.0), (93.15, 76.0)], 0.4)
add_track("VLDO", F, [(80.05, 75.0), (80.05, 76.5), (81.85, 78.3), (86.85, 78.3)], 0.4)
add_track("+3V3", F, [(93.15, 76.0), (95.72, 76.0), (96.72, 77.0)], 0.4)
add_track("GND", F, [(86.85, 73.7), (85.3, 73.7)], 0.4)
add_via("GND", 85.3, 73.7, 0.6, 0.3)
b.FindFootprintByReference("U5").SetValue("AP7361C-33ER")
b.FindFootprintByReference("Q3").SetValue("IPD50P04P4L-11")

# ------------------------------------------------------------------ 7. toutes les pastilles reprennent le net du schéma
for fp in b.GetFootprints():
    for pad in fp.Pads():
        key = "%s.%s" % (fp.GetReference(), pad.GetNumber())
        if pad.GetNumber() and key in intent:
            want = intent[key]
            if want and pad.GetNetname() != want:
                pad.SetNet(net(want))
            elif not want and pad.GetNetname() and not pad.GetNetname().startswith("unconnected"):
                pad.SetNetCode(0)

for d in b.GetDrawings():
    if d.GetClass() == "PCB_TEXT" and "v0.3" in d.GetText():
        d.SetText(d.GetText().replace("v0.3", "v0.4"))
for ref, cx in (("U2", 86.0), ("U3", 128.0)):
    t = b.FindFootprintByReference(ref).Reference()
    t.SetPosition(pt(cx, 120.6))
    t.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
    t.SetTextThickness(MM(0.12))

out = os.path.join(K, os.environ.get("OUT", "portail.kicad_pcb"))
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(out, b)
pro = os.path.splitext(out)[0] + ".kicad_pro"
if os.path.exists(pro):
    j = json.load(open(pro, encoding="utf-8"))
    for c in j["net_settings"]["classes"]:
        if c["name"] == "Default":
            c.update(clearance=0.15, track_width=0.2, via_diameter=0.6, via_drill=0.3)
    j["board"]["design_settings"]["rules"]["min_track_width"] = 0.0
    json.dump(j, open(pro, "w", encoding="utf-8"), indent=2)
print("carte écrite :", out, "| empreintes :", len(b.GetFootprints()))
