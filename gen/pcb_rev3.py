# SPDX-License-Identifier: GPL-3.0-or-later
"""Révision v0.3 de la carte : part de la carte v0.2 routée et contrôlée (kicad/portail.base-v0.2.kicad_pcb)
et y ajoute les corrections de la relecture, sans refaire le routage existant.
À lancer avec le Python de KiCad 10 (module pcbnew), après gen/build.py (qui écrit intent.json)."""
import json
import math
import os

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
K = os.path.join(HERE, "..", "kicad")
FPDIR = os.environ.get("KICAD_FOOTPRINTS", "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
OX = OY = 50.0
MM, mm = pcbnew.FromMM, pcbnew.ToMM
F, B = pcbnew.F_Cu, pcbnew.B_Cu

b = pcbnew.LoadBoard(os.path.join(K, "portail.base-v0.2.kicad_pcb"))
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
    fp = IO.FootprintLoad(os.path.join(FPDIR, lib + ".pretty"), name)   # pcbnew.FootprintLoad est instable en KiCad 10
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
    return tuple(round(v, 2) for v in (mm(bb.GetLeft()) - OX, mm(bb.GetTop()) - OY, mm(bb.GetRight()) - OX, mm(bb.GetBottom()) - OY))


def del_zone(netname, layer, prio, with_keepout):
    zs = [z for z in b.Zones() if not z.GetIsRuleArea() and z.GetNetname() == netname and z.GetLayer() == layer
          and z.GetAssignedPriority() == prio]
    assert len(zs) == 1, ("zone introuvable", netname, prio, len(zs))
    bb = outline_bbox(zs[0])
    if with_keepout:
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
        o.Append(MM(OX + x), MM(OY + y))
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
            ko.Append(MM(OX + x), MM(OY + y))
        b.Add(k)


def rect(x1, y1, x2, y2):
    return [(x1, y1), (x2, y2 if False else y1), (x2, y2), (x1, y2)]


def silk(text, x, y, size=0.8, rot=0):
    t = pcbnew.PCB_TEXT(b)
    t.SetText(text)
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(0.15))
    t.SetPosition(pt(x, y))
    if rot:
        t.SetTextAngleDegrees(rot)
    b.Add(t)


# ================================================================ 1. valeurs et montage
for ref in ("R4", "R6"):                       # résistances SR : 22 k -> 100 k (50 V/µs)
    b.FindFootprintByReference(ref).SetValue("100k")
for ref in ("C20", "C21", "C22", "C23"):       # antiparasites des sorties moteur : montés
    b.FindFootprintByReference(ref).SetDNP(False)

# ================================================================ 2. céramiques 4,7 µF au plus près des broches VM
for n, (cx, refs) in enumerate(((36.0, ("C25", "C26")), (78.0, ("C27", "C28"))), 1):
    for sx, ref in zip((-1, 1), refs):
        x = cx + sx * 5.3
        fp = add_fp(ref, "Capacitor_SMD:C_1206_3216Metric", "4.7u 50V", x, 65.45, 270)
        (x1, y1), (x2, y2) = pad_xy(ref, 1)[0], pad_xy(ref, 2)[0]
        assert y1 < y2, "la pastille 1 (VM) doit être en haut"
        del_via(cx + sx * 5.0, 67.15)          # ce via tomberait sous la pastille de masse
        add_via("GND", cx + sx * 5.0, 69.2)    # remplacé juste en dessous

# ================================================================ 3. anti-inversion : MOSFET P entre F1 et le bus
YC = 69.85
# la TVS D1 remonte pour laisser la place à Q3 ; sa pastille de masse reste sur son îlot, prolongé vers le haut
d1 = b.FindFootprintByReference("D1")
d1.SetPosition(pt(11.0, 59.6))
add_zone("GND", F, [(14.5, 57.6), (18.8, 57.6), (18.8, 60.4), (14.5, 60.4)], 6)
q = add_fp("Q3", "Package_TO_SOT_SMD:TO-252-2", "IPD90P04P4L-04", 9.85, YC, 270)
g, d, s = pad_xy("Q3", 1)[0], pad_xy("Q3", 2)[0], pad_xy("Q3", 3)[0]
assert d[1] > YC and g[0] > 9.85 and s[0] < 9.85, ("orientation de Q3", g, d, s)
# la colonne VBUS est coupée en deux : en bas +24V_F (sortie de F1, drain de Q3), en haut VBUS (source de Q3)
del_zone("VBUS", F, 3, True)
add_zone("VBUS", F, [(5.5, 38), (71.5, 38), (71.5, 44.6), (14.2, 44.6), (14.2, 63.4), (11.2, 63.4), (11.2, 66.2),
                     (15.2, 66.2), (15.2, 67.4), (5.5, 67.4)], 3, True)
add_zone("+24V_F", F, [(5.5, 67.8), (14.2, 67.8), (14.2, 82.4), (5.5, 82.4)], 3, True)
for p in b.FindFootprintByReference("F1").Pads():
    if p.GetNumber() == "2":
        p.SetNet(net("+24V_F"))
# grille : tirage à la masse et zener vers la source, à droite de la colonne
add_fp("R36", "Resistor_SMD:R_0603_1608Metric", "10k", 16.2, g[1], 0)
add_fp("D14", "Diode_SMD:D_SOD-123", "BZT52C12", 16.0, 66.95, 0)
r1, r2 = pad_xy("R36", 1)[0], pad_xy("R36", 2)[0]
zk, za = pad_xy("D14", 1)[0], pad_xy("D14", 2)[0]
assert zk[0] < 14.8 < za[0], "la cathode de D14 doit être sur la colonne VBUS"
del_via(17.5, 65.5)
add_track("RP_G", F, [g, r1], 0.3)
add_track("RP_G", F, [r1, (r1[0], za[1]), za], 0.3)
add_via("GND", 18.5, r2[1])
add_track("GND", F, [r2, (18.5, r2[1])], 0.4)

# ================================================================ 4. fusible de la branche logique (convertisseurs, mesure de tension)
del_zone("VBUS", F, 5, False)                  # ancienne prise directe sur le bus
del_via(20.0, 37.1)
rm(find_seg(B, (20.0, 37.1), (19.04, 36.14)))
seg = find_seg(B, (19.04, 36.14), (19.04, 30.84))
if at(seg.GetStart(), 19.04, 36.14):
    seg.SetStart(pt(19.04, 34.8))
else:
    seg.SetEnd(pt(19.04, 34.8))
AUX = "+24V_AUX"
for t in b.GetTracks():
    if t.GetNetname() == "VBUS":
        t.SetNet(net(AUX))
for ref, num in (("U4", "1"), ("U11", "1"), ("R15", "1")):
    for p in b.FindFootprintByReference(ref).Pads():
        if p.GetNumber() == num:
            assert intent["%s.%s" % (ref, num)] == AUX
            p.SetNet(net(AUX))
add_fp("F6", "Fuse:Fuse_1206_3216Metric", "2A T 1206", 20.0, 37.6, 90)
f1, f2 = pad_xy("F6", 1)[0], pad_xy("F6", 2)[0]
if f1[1] < f2[1]:                               # la pastille 1 (VBUS) doit être en bas, sur la barre du bus
    b.FindFootprintByReference("F6").SetOrientationDegrees(270)
    f1, f2 = pad_xy("F6", 1)[0], pad_xy("F6", 2)[0]
assert f1[1] > 38.3 and f2[1] < 36.9, (f1, f2)
add_zone(AUX, F, [(17.6, 34.0), (22.4, 34.0), (22.4, 36.95), (17.6, 36.95)], 5)
add_via(AUX, 19.04, 34.8)

# ================================================================ 5. TVS 15 V sur les deux départs 12 V vers l'extérieur
# Placées à la sortie des fusibles réarmables F4/F5, au plus près du convertisseur 12 V qu'elles protègent
# (pas de place entre les MOSFET de sortie et les borniers J4/J5).
def tvs(ref, netname, ptc_pad, gnd_via):
    """TVS horizontale au-dessus du fusible réarmable : cathode à la verticale de sa pastille de sortie."""
    px, py = ptc_pad
    for t in list(b.GetTracks()):              # vias de couture qui tomberaient sous les pastilles
        if t.GetClass() == "PCB_VIA" and abs(xy(t.GetPosition())[1] - 5.5) < 0.05 and px - 5.0 < xy(t.GetPosition())[0] < px + 1.6:
            rm(t)
    add_fp(ref, "Diode_SMD:D_SMA", "SMAJ15A", px - 2.0, 5.4, 0)
    k, a = pad_xy(ref, 1)[0], pad_xy(ref, 2)[0]
    if k[0] < a[0]:
        b.FindFootprintByReference(ref).SetOrientationDegrees(180)
        k, a = pad_xy(ref, 1)[0], pad_xy(ref, 2)[0]
    assert abs(k[0] - px) < 0.01 and a[0] < k[0], (k, a)
    add_track(netname, F, [ptc_pad, k], 0.4)
    add_track("GND", F, [a, gnd_via], 0.4)


tvs("D12", "+12V_ACC", (49.0, 10.0), (41.5, 5.5))
tvs("D13", "+12V_OUT", (63.0, 10.0), (56.5, 5.5))

# ================================================================ 5 bis. entrée 24 V élargie entre J1 et F1
# v0.2 : 3,8 mm au plus étroit, trop juste pour le fusible F1 de 15 A. La zone occupe maintenant toute la place libre
# à gauche de J1 et entre F1 et la colonne +24V_F.
IN24 = [(9.0, 83.0), (14.8, 83.0), (14.8, 74.6), (24.4, 74.6), (24.4, 90.8), (16.4, 90.8), (16.4, 96.5), (9.0, 96.5)]
del_zone("+24V_IN", F, 3, True)
for t in list(b.GetTracks()):                  # vias de couture de masse situés dans la nouvelle zone
    if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND":
        x, y = xy(t.GetPosition())
        if (8.4 < x < 17.0 and 82.4 < y < 97.0) or (14.2 < x < 25.0 and 74.0 < y < 91.4 and not (x > 16.9 and y > 91.0)):
            rm(t)
add_zone("+24V_IN", F, IN24, 3, True)

# ================================================================ 5 ter. prise USB-C et LED
# La prise HRO TYPE-C-31-M-12 n'est pas distribuée en Europe : remplacée par la GCT USB4105-GF-A, même implantation des
# pastilles à 0,05 mm près (les pistes existantes aboutissent toujours dans les pastilles), fentes de blindage arrière plus longues.
old = b.FindFootprintByReference("J6")
jx, jy = xy(old.GetPosition())
jrot = old.GetOrientationDegrees()
rm(old)
add_fp("J6", "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal", "USB-C", jx, jy, jrot, rename={"SH": "S1"})
# Les pastilles GCT avancent de 0,2 mm vers le corps de la prise : la liaison D- (A7-B7), qui contournait le bout de la
# pastille D+ à 0,15 mm, est décalée de 0,27 mm.
for a_, c_ in (((141.96, 51.75), (142.93, 51.75)), ((142.93, 51.75), (142.93, 52.75)), ((141.96, 52.75), (142.93, 52.75)),
               ((142.93, 52.75), (144.25, 54.07)), ((143.28, 51.64), (143.04, 51.64)), ((143.04, 51.64), (142.93, 51.75))):
    rm(find_seg(F, a_, c_))
for t in list(b.GetTracks()):                  # segment de longueur nulle laissé par le routeur
    if t.GetClass() == "PCB_TRACK" and t.GetNetname() == "USB_DM" and at(t.GetStart(), 142.93, 52.75) and at(t.GetEnd(), 142.93, 52.75):
        rm(t)
XD = 143.2
add_track("USB_DM", F, [(141.96, 51.75), (XD, 51.75), (XD, 52.75), (141.96, 52.75)], 0.2)
add_track("USB_DM", F, [(XD, 51.75), (143.28, 51.64)], 0.2)
add_track("USB_DM", F, [(XD, 52.75), (144.25, 54.07)], 0.2)
# La fente de blindage avant est décalée de 0,025 mm : le coude de la piste D- voisine recule de 0,03 mm pour garder 0,15 mm.
rm(find_seg(F, (144.25, 54.07), (144.25, 56.57)))
rm(find_seg(F, (144.25, 56.57), (143.74, 57.08)))
add_track("USB_DM", F, [(144.25, 54.07), (144.25, 56.60), (143.77, 57.08), (143.74, 57.08)], 0.2)
# Les quatre pastilles de masse extérieures sont raccourcies de 0,06 mm côté corps pour garder 0,25 mm jusqu'aux trous de centrage.
for p in b.FindFootprintByReference("J6").Pads():
    if p.GetNumber() in ("A1", "A12", "B1", "B12"):
        p.SetSize(F, pcbnew.VECTOR2I(p.GetSizeX(), p.GetSizeY() - MM(0.06))) if p.GetSizeY() > p.GetSizeX() else p.SetSize(F, pcbnew.VECTOR2I(p.GetSizeX() - MM(0.06), p.GetSizeY()))
        px, py = xy(p.GetPosition())
        p.SetPosition(pt(px - 0.03, py))
b.FindFootprintByReference("D11").SetValue("rouge")

# ================================================================ 6. points de test
TP = {"TP1": (58.0, 94.0), "TP2": (50.0, 41.3)}   # masse et bus ; les autres viennent de pcb_tp.py
TP.update(json.load(open(os.path.join(HERE, "tp.json"))) if os.path.exists(os.path.join(HERE, "tp.json")) else {})
for ref, (x, y) in TP.items():
    add_fp(ref, "TestPoint:TestPoint_Pad_D1.5mm", intent[ref + ".1"], x, y)

# ================================================================ 7. sérigraphie de câblage
def labels(ref, names, dy):
    fp = b.FindFootprintByReference(ref)
    for p, name in zip(sorted(fp.Pads(), key=lambda p: p.GetPosition().x), names):
        x, y = xy(p.GetPosition())
        silk(name, x, y + dy)


if os.environ.get("SILK", "1") == "1":
    labels("J1", ["+24V", "GND"], float(os.environ.get("DY508", "6.3")))
    labels("J2", ["M1 A", "M1 B"], float(os.environ.get("DY508", "6.3")))
    labels("J3", ["M2 A", "M2 B"], float(os.environ.get("DY508", "6.3")))
    labels("J4", ["+12V", "+12V", "PP", "FOTO", "RAD", "STOP", "GND", "GND"], float(os.environ.get("DY35", "5.9")))
    labels("J5", ["+12V", "LAMP", "+12V", "AUX"], float(os.environ.get("DY35", "5.9")))
    silk("PORTAIL v0.3  24 V DC", 26.0, 4.0, 1.2)

# repères des composants ajoutés ou déplacés : hors des pastilles voisines
def ref_at(ref, x, y, rot=0, size=0.8):
    t = b.FindFootprintByReference(ref).Reference()
    t.SetPosition(pt(x, y))
    t.SetTextAngleDegrees(rot)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(0.12))


for cx, (cl, cr) in ((36.0, ("C25", "C26")), (78.0, ("C27", "C28"))):
    ref_at(cl, cx - 5.3 - 1.75, 65.45, 90)
    ref_at(cr, cx + 5.3 + 1.75, 65.45, 90)
ref_at("R36", 16.2, 63.55)
ref_at("D14", 16.0, 68.75)
ref_at("D12", 46.0, 3.0)
ref_at("D13", 61.0, 3.0)
ref_at("D1", 3.6, 59.6, 90)
ref_at("Q3", 3.6, 70.0, 90)
ref_at("F6", 22.0, 37.6, 90)

out = os.path.join(K, os.environ.get("OUT", "portail.kicad_pcb"))
pcbnew.ZONE_FILLER(b).Fill(b.Zones())
pcbnew.SaveBoard(out, b)
# SaveBoard réécrit le fichier projet avec les règles par défaut (isolement 0,2 mm) : on remet celles de la carte
pro = os.path.splitext(out)[0] + ".kicad_pro"
if os.path.exists(pro):
    j = json.load(open(pro, encoding="utf-8"))
    for c in j["net_settings"]["classes"]:
        if c["name"] == "Default":
            c.update(clearance=0.15, track_width=0.2, via_diameter=0.6, via_drill=0.3)
    j["board"]["design_settings"]["rules"]["min_track_width"] = 0.0
    json.dump(j, open(pro, "w", encoding="utf-8"), indent=2)
print("carte écrite :", out, "| empreintes :", len(b.GetFootprints()))
