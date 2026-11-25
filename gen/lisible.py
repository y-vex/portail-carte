# SPDX-License-Identifier: GPL-3.0-or-later
"""Schémas « lisibles » : dessins tracés à la main, bloc par bloc, fidèles à la netlist v0.2."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))


class D:
    def __init__(self, w, h, label):
        self.w, self.h, self.label, self.e = w, h, label, []

    def wire(self, *pts, cls="w"):
        d = "M" + " L".join("%g %g" % p for p in pts)
        self.e.append('<path class="%s" d="%s"/>' % (cls, d))

    def dot(self, x, y):
        self.e.append('<circle class="dot" cx="%g" cy="%g" r="3"/>' % (x, y))

    def t(self, s, x, y, cls="t", anchor="start"):
        self.e.append('<text class="%s" x="%g" y="%g" text-anchor="%s">%s</text>' % (cls, x, y, anchor, s))

    def box(self, x, y, w, h, title="", sub="", cls="box"):
        self.e.append('<rect class="%s" x="%g" y="%g" width="%g" height="%g" rx="4"/>' % (cls, x, y, w, h))
        if title:
            self.t(title, x + w / 2, y + (h / 2 + 4 if not sub else h / 2 - 3), "tb", "middle")
        if sub:
            self.t(sub, x + w / 2, y + h / 2 + 12, "s", "middle")

    def term(self, x, y, s="", side="above"):
        self.e.append('<circle class="term" cx="%g" cy="%g" r="5"/>' % (x, y))
        if s:
            if side == "above":
                self.t(s, x, y - 11, "s", "middle")
            elif side == "below":
                self.t(s, x, y + 20, "s", "middle")
            elif side == "left":
                self.t(s, x - 10, y + 4, "s", "end")
            else:
                self.t(s, x + 10, y + 4, "s")

    def rh(self, x, y, name, val):
        self.e.append('<rect class="c" x="%g" y="%g" width="28" height="10"/>' % (x - 14, y - 5))
        self.t(name, x, y - 10, "s", "middle")
        self.t(val, x, y + 19, "s", "middle")

    def rv(self, x, y, name, val):
        self.e.append('<rect class="c" x="%g" y="%g" width="10" height="28"/>' % (x - 5, y - 14))
        self.t(name, x + 11, y - 2, "s")
        self.t(val, x + 11, y + 11, "s")

    def fh(self, x, y, name, val):
        self.rh(x, y, name, val)
        self.wire((x - 14, y), (x + 14, y), cls="c")

    def fv(self, x, y, name, val):
        self.rv(x, y, name, val)
        self.wire((x, y - 14), (x, y + 14), cls="c")

    def cv(self, x, y, name, val):
        self.wire((x - 9, y - 3), (x + 9, y - 3), cls="c2")
        self.wire((x - 9, y + 3), (x + 9, y + 3), cls="c2")
        self.t(name, x + 14, y - 2, "s")
        self.t(val, x + 14, y + 11, "s")

    def dh(self, x, y, name, val):  # anode à gauche, cathode à droite
        self.e.append('<path class="cf" d="M%g %g L%g %g L%g %g Z"/>' % (x - 7, y - 7, x - 7, y + 7, x + 7, y))
        self.wire((x + 7, y - 7), (x + 7, y + 7), cls="c2")
        self.t(name, x, y - 12, "s", "middle")
        self.t(val, x, y + 21, "s", "middle")

    def dv_up(self, x, y, name, val):  # anode en bas, cathode en haut
        self.e.append('<path class="cf" d="M%g %g L%g %g L%g %g Z"/>' % (x - 7, y + 7, x + 7, y + 7, x, y - 7))
        self.wire((x - 7, y - 7), (x + 7, y - 7), cls="c2")
        self.t(name, x + 12, y - 2, "s")
        self.t(val, x + 12, y + 11, "s")

    def gnd(self, x, y):
        self.wire((x, y), (x, y + 6))
        for i, half in enumerate((9, 6, 3)):
            self.wire((x - half, y + 6 + i * 4), (x + half, y + 6 + i * 4), cls="c2")

    def circ(self, x, y, r, s):
        self.e.append('<circle class="c" cx="%g" cy="%g" r="%g"/>' % (x, y, r))
        self.t(s, x, y + 5, "tb", "middle")

    def svg(self):
        return ('<svg viewBox="0 0 %d %d" width="%d" height="%d" role="img" aria-label="%s">%s</svg>'
                % (self.w, self.h, self.w, self.h, self.label, "".join(self.e)))


def vue_ensemble():
    d = D(640, 372, "Ce qui se branche sur la carte")
    d.box(210, 30, 220, 322, cls="board")
    d.t("CARTE", 320, 62, "tb", "middle")
    d.t("ESP32 : Wi-Fi, HomeKit", 320, 80, "s", "middle")
    left = [(60, "Alimentation 24 V DC", "MeanWell LRS-450-24", "J1"),
            (120, "Ordinateur (USB-C)", "flashage du firmware", "J6"),
            (190, "Bouton poussoir", "", "J4 · PP"),
            (235, "Photocellules", "alimentées en 12 V", "J4 · FOTO"),
            (280, "Récepteur radio", "contact sec", "J4 · RADIO"),
            (325, "Arrêt (option)", "", "J4 · STOP")]
    for y, a, b, j in left:
        d.box(14, y - 18, 150, 36, a, b)
        d.wire((164, y), (210, y))
        d.term(210, y)
        d.t(j, 220, y + 4, "s")
    right = [(60, "Moteur vantail 1", "24 V, 4 A", "J2"),
             (120, "Moteur vantail 2", "24 V, 4 A", "J3"),
             (235, "Clignotant", "12 V, 9 W max", "J5 · LAMP"),
             (300, "Auxiliaire", "12 V", "J5 · AUX")]
    for y, a, b, j in right:
        d.box(476, y - 18, 150, 36, a, b)
        d.wire((430, y), (476, y))
        d.term(430, y)
        d.t(j, 420, y + 4, "s", "end")
    return d


def alimentation():
    d = D(640, 440, "Chaîne d'alimentation de la carte")
    d.term(30, 60, "J1 +24 V")
    d.wire((35, 60), (76, 60))
    d.fh(90, 60, "F1", "15 A")
    d.wire((104, 60), (600, 60))
    d.t("bus 24 V", 596, 50, "s", "end")
    # TVS
    d.dot(180, 60)
    d.wire((180, 60), (180, 93))
    d.dv_up(180, 100, "D1 TVS", "SMCJ24A")
    d.wire((180, 107), (180, 130))
    d.gnd(180, 130)
    # C7
    d.dot(260, 60)
    d.wire((260, 60), (260, 97))
    d.cv(260, 100, "C7", "100 µF")
    d.wire((260, 103), (260, 130))
    d.gnd(260, 130)
    # F2 / F3
    for x, f, name in ((390, "F2", "Driver moteur 1"), (530, "F3", "Driver moteur 2")):
        d.dot(x, 60)
        d.wire((x, 60), (x, 86))
        d.fv(x, 100, f, "10 A")
        d.wire((x, 114), (x, 140))
        d.box(x - 60, 140, 120, 34, name, "24 V puissance")
    # tronc
    d.dot(130, 60)
    d.wire((130, 60), (130, 370))
    # 5 V -> 3,3 V
    d.dot(130, 240)
    d.wire((130, 240), (150, 240))
    d.box(150, 220, 120, 40, "U4 TSR 1-2450", "24 V vers 5 V")
    d.wire((270, 240), (293, 240))
    d.dh(300, 240, "D2", "")
    d.wire((307, 240), (370, 240))
    d.dot(340, 240)
    d.box(370, 220, 120, 40, "U5 AP7361C", "5 V vers 3,3 V")
    d.wire((490, 240), (525, 240))
    d.term(530, 240, "3,3 V logique", "right")
    d.gnd(210, 260)
    d.gnd(430, 260)
    # USB
    d.term(240, 300, "USB-C 5 V", "left")
    d.wire((245, 300), (293, 300))
    d.dh(300, 300, "D3", "")
    d.wire((307, 300), (340, 300), (340, 240))
    d.t("secours : l'USB alimente la logique sans le 24 V", 360, 304, "s")
    # 12 V
    d.wire((130, 370), (150, 370))
    d.box(150, 350, 120, 40, "U11 TSR 1-24120", "24 V vers 12 V")
    d.gnd(210, 390)
    d.wire((270, 370), (336, 370))
    d.dot(300, 370)
    d.fh(350, 370, "F4", "0,5 A")
    d.wire((364, 370), (415, 370))
    d.term(420, 370, "12 V accessoires (J4)", "right")
    d.wire((300, 370), (300, 415), (336, 415))
    d.fh(350, 415, "F5", "1,1 A")
    d.wire((364, 415), (415, 415))
    d.term(420, 415, "12 V sorties (J5)", "right")
    return d


def driver():
    d = D(640, 410, "Commande d'un moteur")
    d.box(16, 40, 114, 270, cls="box")
    d.t("ESP32-S3", 73, 30, "tb", "middle")
    d.box(330, 40, 140, 290, cls="boxa")
    d.t("U2 DRV8245H", 400, 30, "tb", "middle")
    rows = [(70, "IO5", "EN", "vitesse (PWM)"), (100, "IO6", "PH", "sens"),
            (130, "IO16", "DRVOFF", "coupure d'urgence"), (160, "IO17", "nSLEEP", "réveil, acquittement"),
            (190, "IO18", "nFAULT", "défaut")]
    for y, a, b, lab in rows:
        d.t(a, 122, y + 4, "s", "end")
        d.t(b, 338, y + 4, "s")
        d.wire((130, y), (330, y))
        d.t(lab, 230, y - 6, "s", "middle")
    # pull-up nFAULT
    d.dot(165, 190)
    d.wire((165, 190), (165, 204))
    d.rv(165, 218, "R11", "10 kΩ")
    d.wire((165, 232), (165, 242))
    d.t("3,3 V", 165, 255, "s", "middle")
    # IPROPI
    y = 285
    d.t("IO1", 122, y + 4, "s", "end")
    d.t("IPROPI", 338, y + 4, "s")
    d.wire((130, y), (201, y))
    d.rh(215, y, "R9 10 kΩ", "")
    d.wire((229, y), (330, y))
    d.t("mesure du courant", 215, y + 19, "s", "middle")
    d.dot(278, y)
    d.wire((278, y), (278, 316))
    d.rv(278, 330, "R1", "1,2 kΩ")
    d.wire((278, 344), (278, 358))
    d.gnd(278, 358)
    d.dot(150, y)
    d.wire((150, y), (150, 327))
    d.cv(150, 330, "C17", "100 nF")
    d.wire((150, 333), (150, 358))
    d.gnd(150, 358)
    # réglages
    for x, pin, r, val in ((345, "ITRIP", "R3", "22 kΩ"), (400, "SR", "R4", "22 kΩ"), (455, "DIAG", "R7", "100 kΩ")):
        d.t(pin, x, 322, "xs", "middle")
        d.wire((x, 330), (x, 346))
        d.rv(x, 360, r, val)
        d.wire((x, 374), (x, 384))
        d.gnd(x, 384)
    # côté puissance
    d.t("VM", 462, 74, "s", "end")
    d.wire((470, 70), (625, 70))
    d.t("24 V via F2 (10 A)", 625, 60, "s", "end")
    d.dot(520, 70)
    d.wire((520, 70), (520, 97))
    d.cv(520, 100, "C1", "470 µF")
    d.wire((520, 103), (520, 122))
    d.gnd(520, 122)
    d.t("OUT1", 462, 174, "s", "end")
    d.t("OUT2", 462, 224, "s", "end")
    d.wire((470, 170), (535, 170))
    d.wire((470, 220), (535, 220))
    d.term(540, 170, "J2", "above")
    d.term(540, 220)
    d.wire((545, 170), (590, 170), (590, 175))
    d.wire((545, 220), (590, 220), (590, 215))
    d.circ(590, 195, 20, "M")
    d.t("moteur (hors carte)", 630, 250, "s", "end")
    d.t("GND", 462, 284, "s", "end")
    d.wire((470, 280), (500, 280))
    d.gnd(500, 280)
    return d


def entree():
    d = D(640, 250, "Une entrée optocouplée")
    d.term(40, 90, "J4 +12 V", "above")
    d.wire((45, 90), (80, 90))
    d.wire((80, 90), (112, 76), cls="c2")
    d.wire((116, 90), (150, 90))
    d.t("contact", 98, 112, "s", "middle")
    d.t("(hors carte)", 98, 125, "s", "middle")
    d.term(155, 90, "J4 entrée", "above")
    d.wire((160, 90), (196, 90))
    d.rh(210, 90, "R22", "2,2 kΩ")
    d.wire((224, 90), (300, 90))
    d.dot(262, 90)
    d.wire((262, 90), (262, 113))
    d.dv_up(262, 120, "", "")
    d.t("D4", 244, 124, "s", "end")
    d.wire((262, 127), (262, 150))
    d.dot(262, 150)
    d.wire((262, 150), (300, 150))
    d.gnd(262, 150)
    d.box(300, 60, 120, 120, cls="boxa")
    d.t("U7 optocoupleur", 360, 50, "tb", "middle")
    # LED interne
    d.wire((300, 90), (328, 90), (328, 113))
    d.e.append('<path class="cf" d="M321 113 L335 113 L328 127 Z"/>')
    d.wire((321, 127), (335, 127), cls="c2")
    d.wire((328, 127), (328, 150), (300, 150))
    d.t("lumière", 360, 124, "xs", "middle")
    d.wire((342, 130), (378, 130), cls="c2")
    d.wire((372, 126), (378, 130), (372, 134), cls="c2")
    # transistor interne
    d.wire((392, 100), (392, 140), cls="c2")
    d.wire((392, 110), (406, 90), (420, 90))
    d.wire((392, 130), (406, 150), (420, 150))
    d.wire((420, 90), (560, 90))
    d.dot(480, 90)
    d.wire((480, 90), (480, 74))
    d.rv(480, 60, "R26", "10 kΩ")
    d.wire((480, 46), (480, 36))
    d.t("3,3 V", 480, 30, "s", "middle")
    d.box(560, 70, 66, 40, "ESP32", "IO9")
    d.wire((420, 150), (450, 150))
    d.gnd(450, 150)
    d.wire((360, 196), (360, 236), cls="dash")
    d.t("côté 12 V", 350, 228, "s", "end")
    d.t("côté 3,3 V", 370, 228, "s")
    return d


def sortie():
    d = D(640, 270, "Une sortie 12 V")
    d.box(14, 150, 76, 40, "ESP32", "IO13")
    d.wire((90, 170), (136, 170))
    d.rh(150, 170, "R30", "100 Ω")
    d.wire((164, 170), (250, 170))
    d.dot(205, 170)
    d.wire((205, 170), (205, 196))
    d.rv(205, 210, "R32", "100 kΩ")
    d.wire((205, 224), (205, 236))
    d.gnd(205, 236)
    d.box(250, 140, 70, 60, "Q1", "AO3422", cls="boxa")
    d.t("grille", 246, 162, "xs", "end")
    d.wire((285, 200), (285, 236))
    d.gnd(285, 236)
    d.wire((285, 140), (285, 110), (435, 110))
    d.term(440, 110, "J5 LAMP", "below")
    d.t("12 V sorties (via F5)", 150, 44, "s")
    d.wire((150, 50), (435, 50))
    d.term(440, 50, "J5 +12 V", "above")
    d.dot(360, 50)
    d.dot(360, 110)
    d.wire((360, 50), (360, 73))
    d.dv_up(360, 80, "D8", "SS16")
    d.wire((360, 87), (360, 110))
    d.wire((445, 50), (510, 50), (510, 62))
    d.wire((445, 110), (510, 110), (510, 98))
    d.circ(510, 80, 18, "")
    d.wire((498, 68), (522, 92), cls="c2")
    d.wire((522, 68), (498, 92), cls="c2")
    d.t("clignotant 12 V", 536, 78, "s")
    d.t("(hors carte)", 536, 91, "s")
    return d


ALL = [("ensemble", vue_ensemble), ("alim", alimentation), ("driver", driver), ("entree", entree), ("sortie", sortie)]

if __name__ == "__main__":
    import sys
    import cairosvg
    out = sys.argv[1]
    css = ("<style>.w{stroke:#2a5db0;stroke-width:1.6;fill:none}.c{stroke:#222;stroke-width:1.6;fill:#fff}"
           ".c2{stroke:#222;stroke-width:1.6;fill:none}.cf{stroke:#222;stroke-width:1.6;fill:#222}"
           ".dot{fill:#2a5db0}.term{stroke:#222;stroke-width:1.6;fill:#fff}.box{stroke:#222;stroke-width:1.4;fill:#f3f3f3}"
           ".boxa{stroke:#b5651d;stroke-width:1.8;fill:#fdf1e3}.board{stroke:#b5651d;stroke-width:2;fill:#fdf1e3}"
           ".dash{stroke:#888;stroke-dasharray:4 4;fill:none}"
           "text{font-family:sans-serif;fill:#111}.t{font-size:13px}.tb{font-size:13px;font-weight:700}"
           ".s{font-size:11.5px}.xs{font-size:10px}</style>")
    for name, fn in ALL:
        s = fn().svg().replace("<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1).replace('">', '">' + css + '<rect width="100%" height="100%" fill="#fff"/>', 1)
        cairosvg.svg2png(bytestring=s.encode(), write_to=os.path.join(out, "lis_%s.png" % name), scale=1.6)
    print("ok")
