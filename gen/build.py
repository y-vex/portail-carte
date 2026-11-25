# SPDX-License-Identifier: GPL-3.0-or-later
"""Carte de commande portail : définition du circuit et génération du projet KiCad."""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import Q, dump
from kisch import Schematic

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kicad")
os.makedirs(OUT, exist_ok=True)
PROJECT = "portail"


def g(n):
    return round(n * 2.54, 4)


# ----------------------------------------------------------------- symbole DRV8245S (variante SPI, VQFN-HR 16)
def drv_symbol():
    name = "DRV8245S_VQFN16"
    font = ["effects", ["font", ["size", 1.27, 1.27]]]

    def pin(ptype, x, y, ang, pname, num, hide=False):
        p = ["pin", ptype, "line", ["at", x, y, ang], ["length", 2.54]]
        if hide:
            p.append("hide")
        p += [["name", Q(pname), font], ["number", Q(str(num)), font]]
        return p

    pins = []
    left = [("EN/IN1", 11, "input"), ("PH/IN2", 12, "input"), ("DRVOFF", 10, "input"),
            ("nSLEEP", 3, "input"), ("nFAULT", 1, "open_collector"), ("IPROPI", 2, "passive"),
            ("nSCS", 13, "input"), ("SCLK", 14, "input"), ("SDI", 15, "input"), ("SDO", 16, "output")]
    ys = [12.7, 10.16, 7.62, 5.08, 2.54, -2.54, -5.08, -7.62, -10.16, -12.7]
    for (pname, num, ptype), y in zip(left, ys):
        pins.append(pin(ptype, -15.24, y, 0, pname, num))
    stacks = [("VM", [4], "power_in", 12.7),
              ("OUT1", [8, 9], "output", 5.08),
              ("OUT2", [5, 6], "output", -5.08),
              ("GND", [7], "power_in", -12.7)]
    for pname, nums, ptype, y in stacks:
        for i, num in enumerate(nums):
            pins.append(pin(ptype if i == 0 else "passive", 15.24, y, 180, pname, num, hide=i > 0))
    prop = lambda k, v, x, y, hide=False: ["property", Q(k), Q(v), ["at", x, y, 0],
                                           ["effects", ["font", ["size", 1.27, 1.27]]] + (["hide"] if hide else [])]
    sym = ["symbol", Q(name), ["in_bom", "yes"], ["on_board", "yes"],
           prop("Reference", "U", -12.7, 17.78),
           prop("Value", name, 0, -17.78),
           prop("Footprint", "portail:DRV8245_VQFN-HR-16_RXZ", 0, 0, True),
           prop("Datasheet", "https://www.ti.com/lit/gpn/DRV8245-Q1", 0, 0, True),
           prop("ki_description", "Pont en H 32 A, mesure de courant intégrée, variante SPI (S), VQFN-HR 16 broches", 0, 0, True),
           ["symbol", Q(name + "_0_1"),
            ["rectangle", ["start", -12.7, 15.24], ["end", 12.7, -15.24],
             ["stroke", ["width", 0.254], ["type", "default"]], ["fill", ["type", "background"]]]],
           ["symbol", Q(name + "_1_1")] + pins]
    def simple(sname, refp, desc, plist, w=5.08, h=5.08):
        """Symbole rectangulaire : plist = [(nom, numéro, type, x, y, angle)]."""
        return ["symbol", Q(sname), ["in_bom", "yes"], ["on_board", "yes"],
                prop("Reference", refp, -w, h + 1.27),
                prop("Value", sname, -w, -h - 1.27),
                prop("Footprint", "", 0, 0, True),
                prop("Datasheet", "~", 0, 0, True),
                prop("ki_description", desc, 0, 0, True),
                ["symbol", Q(sname + "_0_1"),
                 ["rectangle", ["start", -w, h], ["end", w, -h],
                  ["stroke", ["width", 0.254], ["type", "default"]], ["fill", ["type", "background"]]]],
                ["symbol", Q(sname + "_1_1")] + [pin(t, x, y, a, n, num) for n, num, t, x, y, a in plist]]

    pmos = simple("PMOS_GDS", "Q", "MOSFET canal P, boitier DPAK : 1 = grille, 2 = drain (languette), 3 = source",
                  [("G", 1, "input", -7.62, 0, 0), ("D", 2, "passive", 7.62, 2.54, 180), ("S", 3, "passive", 7.62, -2.54, 180)])
    tp = simple("TestPoint", "TP", "Pastille de test", [("1", 1, "passive", -5.08, 0, 0)], w=2.54, h=1.27)
    ldo = simple("LDO_SOT223R", "U", "Régulateur 3,3 V SOT-223 brochage R : 1 = GND, 2 = sortie (languette), 3 = entrée",
                 [("VI", 3, "power_in", -7.62, 0, 0), ("VO", 2, "power_out", 7.62, 0, 180), ("GND", 1, "power_in", 0, -7.62, 90)])
    lib = ["kicad_symbol_lib", ["version", 20220914], ["generator", "kicad_symbol_editor"], sym, pmos, tp, ldo]
    with open(os.path.join(OUT, "portail.kicad_sym"), "w", encoding="utf-8") as f:
        f.write(dump(lib) + "\n")


drv_symbol()
sch = Schematic(PROJECT, "Carte de commande portail - 2 moteurs 24 V DC", "0.4", paper="A2")
sch.lib.add_file("portail", os.path.join(OUT, "portail.kicad_sym"))

# ----------------------------------------------------------------- empreintes
FP = dict(
    r0603="Resistor_SMD:R_0603_1608Metric", r1206="Resistor_SMD:R_1206_3216Metric",
    c0603="Capacitor_SMD:C_0603_1608Metric", c0805="Capacitor_SMD:C_0805_2012Metric",
    c1206="Capacitor_SMD:C_1206_3216Metric",
    cp10="Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", cp8="Capacitor_THT:CP_Radial_D8.0mm_P3.50mm",
    smc="Diode_SMD:D_SMC", sma="Diode_SMD:D_SMA", sod123="Diode_SMD:D_SOD-123",
    led="LED_SMD:LED_0603_1608Metric",
    sot23="Package_TO_SOT_SMD:SOT-23", sot223="Package_TO_SOT_SMD:SOT-223-3_TabPin2",
    sot236="Package_TO_SOT_SMD:SOT-23-6",
    vqfn="portail:DRV8245_VQFN-HR-16_RXZ",
    esp="RF_Module:ESP32-S3-WROOM-1",
    tsr="Converter_DCDC:Converter_DCDC_TRACO_TSR-1_THT",
    opto="Package_DIP:SMDIP-4_W9.53mm",
    usbc="Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal",
    blade="Fuse:Fuseholder_Blade_Mini_Keystone_3568",
    ptc="Capacitor_THT:C_Disc_D10.5mm_W5.0mm_P5.00mm",
    tb2="TerminalBlock_Phoenix:TerminalBlock_Phoenix_MKDS-1,5-2-5.08_1x02_P5.08mm_Horizontal",
    tb8="TerminalBlock_Phoenix:TerminalBlock_Phoenix_PT-1,5-8-3.5-H_1x08_P3.50mm_Horizontal",
    tb4="TerminalBlock_Phoenix:TerminalBlock_Phoenix_PT-1,5-4-3.5-H_1x04_P3.50mm_Horizontal",
    hdr4="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",
    hdr6="Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical",
    sw="Button_Switch_SMD:SW_SPST_TL3342",
    hole="MountingHole:MountingHole_3.2mm_M3",
    dpak="Package_TO_SOT_SMD:TO-252-2", fuse1206="Fuse:Fuse_1206_3216Metric", tp="TestPoint:TestPoint_Pad_D1.5mm",
)


def R(ref, val, x, y, a, b, fp="r0603", **kw):
    sch.place(ref, "Device:R", val, FP[fp], x, y, {1: a, 2: b}, **kw)


def C(ref, val, x, y, a, b, fp="c0603", **kw):
    sch.place(ref, "Device:C", val, FP[fp], x, y, {1: a, 2: b}, **kw)


def CP(ref, val, x, y, plus, minus, fp="cp10", **kw):
    sch.place(ref, "Device:C_Polarized", val, FP[fp], x, y, {1: plus, 2: minus}, **kw)


def FLAG(n, x, y, net):
    sch.place("#FLG%02d" % n, "power:PWR_FLAG", "PWR_FLAG", "", x, y, {1: net}, in_bom=False, stub=5.08)


GND, V33, VBUS = "GND", "+3V3", "VBUS"

# ================================================================= ALIMENTATION
X, Y = g(12), g(22)
sch.text("ALIMENTATION 24 V DC  -  protections, 12 V, 5 V, 3,3 V", g(8), g(12))
sch.place("J1", "Connector:Screw_Terminal_01x02", "24V DC IN", FP["tb2"], X, Y, {1: "+24V_IN", 2: GND},
          note="Bornier à vis 2 points, pas 5,08 mm")
sch.place("F1", "Device:Fuse", "15A lame mini", FP["blade"], X + g(10), Y, {1: "+24V_IN", 2: "+24V_F"},
          note="Porte-fusible lame mini + fusible 15 A")
sch.place("D1", "Device:D_Zener", "SMCJ24A", FP["smc"], X + g(19), Y, {"K": VBUS, "A": GND}, mpn="SMCJ24A",
          note="TVS 1500 W, 24 V, côté carte ; l'anti-inversion est assurée par Q3")
CP("C7", "100u 50V", X + g(28), Y, VBUS, GND, fp="cp8")
sch.place("F2", "Device:Fuse", "10A lame mini", FP["blade"], X + g(37), Y, {1: VBUS, 2: "VM1"},
          note="Porte-fusible lame mini + fusible 10 A")
sch.place("F3", "Device:Fuse", "10A lame mini", FP["blade"], X + g(46), Y, {1: VBUS, 2: "VM2"},
          note="Porte-fusible lame mini + fusible 10 A")
sch.place("F4", "Device:Polyfuse", "RXEF050", FP["ptc"], X + g(55), Y, {1: "+12V", 2: "+12V_ACC"}, mpn="RXEF050",
          note="Fusible réarmable 0,5 A / 72 V, radial pas 5 mm ; empreinte à valider")
sch.place("F5", "Device:Polyfuse", "RXEF110", FP["ptc"], X + g(64), Y, {1: "+12V", 2: "+12V_OUT"}, mpn="RXEF110",
          note="Fusible réarmable 1,1 A, radial pas 5 mm ; empreinte à valider")
FLAG(1, X + g(2), Y + g(8), "+24V_IN")
FLAG(2, X + g(10), Y + g(8), GND)
FLAG(3, X + g(19), Y + g(8), VBUS)
FLAG(4, X + g(37), Y + g(8), "VM1")
FLAG(5, X + g(46), Y + g(8), "VM2")

Y2 = Y + g(20)
sch.place("U4", "Regulator_Switching:TSR_1-2450", "TSR 1-2450", FP["tsr"], X + g(4), Y2,
          {"Vin": "+24V_AUX", "GND": GND, "Vout": "+5V"}, mpn="TSR 1-2450",
          note="Convertisseur 6,5-36 V vers 5 V / 1 A, SIP-3")
C("C8", "10u 16V", X + g(16), Y2, "+5V", GND, fp="c0805")
sch.place("D2", "Device:D_Schottky", "SS14", FP["sma"], X + g(25), Y2, {"K": "VLDO", "A": "+5V"}, mpn="SS14")
sch.place("D3", "Device:D_Schottky", "SS14", FP["sma"], X + g(34), Y2, {"K": "VLDO", "A": "USB_VBUS"}, mpn="SS14")
C("C9", "4.7u 16V", X + g(43), Y2, "VLDO", GND, fp="c0805")
sch.place("U5", "portail:LDO_SOT223R", "AP7361C-33ER", FP["sot223"], X + g(54), Y2,
          {"VI": "VLDO", "GND": GND, "VO": V33}, mpn="AP7361C-33ER-13", note="LDO 3,3 V / 1 A, SOT-223 brochage R : 1 = GND, 2 = sortie, 3 = entrée")
C("C10", "10u 16V", X + g(66), Y2, V33, GND, fp="c0805")
C("C11", "100n 50V", X + g(75), Y2, V33, GND)
FLAG(6, X + g(43), Y2 + g(8), "VLDO")

Y3 = Y2 + g(18)
sch.text("Mesure de la tension du bus après F6 (30 V = 2,73 V)", X - g(4), Y3 - g(6), 2.0)
R("R15", "100k 1%", X, Y3, "+24V_AUX", "VSENSE")
R("R16", "10k 1%", X + g(9), Y3, "VSENSE", GND)
C("C19", "100n 50V", X + g(18), Y3, "VSENSE", GND)
sch.text("Anti-inversion (Q3) et fusible de la branche logique (F6)", X + g(36), Y3 - g(6), 2.0)
# protection contre l'inversion de polarité : MOSFET P en série, passant seulement si l'entrée est dans le bon sens
sch.place("Q3", "portail:PMOS_GDS", "IPD50P04P4L-11", FP["dpak"], X + g(34), Y3, {"G": "RP_G", "D": "+24V_F", "S": VBUS},
          stub=5.08, mpn="IPD90P04P4L-04", note="MOSFET P 40 V anti-inversion, drain côté entrée, source côté carte")
R("R36", "10k", X + g(48), Y3, "RP_G", GND, note="Tirage de grille de Q3")
sch.place("D14", "Device:D_Zener", "BZT52C12", FP["sod123"], X + g(57), Y3, {"K": VBUS, "A": "RP_G"}, mpn="BZT52C12",
          note="Zener 12 V : limite la tension grille-source de Q3")
sch.place("F6", "Device:Fuse", "2A T 1206", FP["fuse1206"], X + g(66), Y3, {1: VBUS, 2: "+24V_AUX"}, mpn="0468002.NR",
          note="Fusible CMS 1206 2 A temporisé, 63 V : protège la branche des convertisseurs")
FLAG(8, X + g(66), Y3 + g(7), "+24V_AUX")


Y4 = Y3 + g(16)
sch.text("Rail 12 V des accessoires et des sorties (1 A, 12 W)", X - g(4), Y4 - g(6), 2.0)
sch.place("U11", "Regulator_Switching:TSR_1-24120", "TSR 1-24120", FP["tsr"], X + g(4), Y4,
          {"Vin": "+24V_AUX", "GND": GND, "Vout": "+12V"}, mpn="TSR 1-24120",
          note="Convertisseur 15-36 V vers 12 V / 1 A, SIP-3")
C("C24", "10u 25V", X + g(16), Y4, "+12V", GND, fp="c1206")
sch.place("D12", "Device:D_Zener", "SMAJ15A", FP["sma"], X + g(27), Y4, {"K": "+12V_ACC", "A": GND}, mpn="SMAJ15A",
          note="TVS 15 V sur le départ accessoires (câbles extérieurs)")
sch.place("D13", "Device:D_Zener", "SMAJ15A", FP["sma"], X + g(38), Y4, {"K": "+12V_OUT", "A": GND}, mpn="SMAJ15A",
          note="TVS 15 V sur le départ des sorties (câbles extérieurs)")

# ================================================================= USB
XU, YU = g(12), g(96)
sch.text("USB-C  -  flashage et alimentation de la logique sur table", g(8), g(86))
sch.place("J6", "Connector:USB_C_Receptacle_USB2.0_16P", "USB-C", FP["usbc"], XU + g(4), YU + g(6),
          {"VBUS": "USB_VBUS", "GND": GND, "SHIELD": GND, "CC1": "USB_CC1", "CC2": "USB_CC2",
           "D+": "USB_DP", "D-": "USB_DM"}, nc=["SBU1", "SBU2"], mpn="USB4105-GF-A", note="Embase USB-C 16 broches USB 2.0 (GCT, distribuée en Europe)")
R("R20", "5.1k", XU + g(24), YU, "USB_CC1", GND)
R("R21", "5.1k", XU + g(33), YU, "USB_CC2", GND)
sch.place("U6", "Power_Protection:USBLC6-2SC6", "USBLC6-2SC6", FP["sot236"], XU + g(48), YU + g(2),
          {1: "USB_DP", 6: "USB_DP", 3: "USB_DM", 4: "USB_DM", 5: "USB_VBUS", 2: GND}, mpn="USBLC6-2SC6",
          note="Protection ESD des lignes USB")
FLAG(7, XU + g(24), YU + g(10), "USB_VBUS")

# ================================================================= ESP32
XE, YE = g(108), g(46)
sch.text("MICROCONTROLEUR  ESP32-S3-WROOM-1-N8", g(88), g(12))
sch.place("U1", "RF_Module:ESP32-S3-WROOM-1", "ESP32-S3-WROOM-1-N8", FP["esp"], XE, YE, {
    "3V3": V33, "GND": GND, "EN": "EN",
    "IO0": "BOOT", "IO1": "ISENSE1", "IO2": "ISENSE2", "IO4": "VSENSE",
    "IO5": "SDO1", "IO6": "M1_EN", "IO7": "SDO2", "IO15": "CS2_N",
    "IO16": "SPI_SDI", "IO17": "SPI_SCLK", "IO18": "CS1_N", "IO8": "M2_EN",
    "IO9": "PP_N", "IO10": "FOTO_N", "IO11": "RADIO_N", "IO12": "STOP_N",
    "IO13": "OUT_LAMP", "IO14": "OUT_AUX", "IO21": "BTN_LEARN", "IO38": "LED_STATUS",
    "IO19": "USB_DM", "IO20": "USB_DP", "TXD0": "UART_TX", "RXD0": "UART_RX",
    "IO39": "EXT_IO39", "IO40": "EXT_IO40", "IO41": "EXT_IO41", "IO42": "EXT_IO42",
}, nc=["IO3", "IO45", "IO46", "IO35", "IO36", "IO37", "IO47", "IO48"], stub=5.08,
    mpn="ESP32-S3-WROOM-1-N8", note="Module Wi-Fi, 8 Mo de flash, antenne intégrée")
YE2 = YE + g(34)
C("C12", "10u 16V", XE - g(22), YE2, V33, GND, fp="c0805")
C("C13", "100n 50V", XE - g(13), YE2, V33, GND)
R("R17", "10k", XE - g(4), YE2, V33, "EN")
C("C14", "1u 16V", XE + g(5), YE2, "EN", GND)
sch.place("SW2", "Switch:SW_Push", "RESET", FP["sw"], XE + g(16), YE2, {1: "EN", 2: GND})
R("R18", "10k", XE - g(22), YE2 + g(12), V33, "BOOT")
sch.place("SW1", "Switch:SW_Push", "BOOT", FP["sw"], XE - g(10), YE2 + g(12), {1: "BOOT", 2: GND})
R("R19", "10k", XE + g(2), YE2 + g(12), V33, "BTN_LEARN")
sch.place("SW3", "Switch:SW_Push", "APPRENTISSAGE", FP["sw"], XE + g(14), YE2 + g(12), {1: "BTN_LEARN", 2: GND})
YE3 = YE2 + g(26)
R("R34", "1k", XE - g(22), YE3, V33, "LED_PWR_A")
sch.place("D10", "Device:LED", "verte", FP["led"], XE - g(13), YE3, {"A": "LED_PWR_A", "K": GND}, note="LED alimentation")
R("R35", "1k", XE - g(2), YE3, "LED_STATUS", "LED_ST_A")
sch.place("D11", "Device:LED", "rouge", FP["led"], XE + g(9), YE3, {"A": "LED_ST_A", "K": GND},
          note="LED état ; rouge car une bleue (3,3 V) ne s'allume pas sur une sortie 3,3 V")
sch.place("J7", "Connector_Generic:Conn_01x04", "DEBUG UART", FP["hdr4"], XE + g(28), YE2 + g(2),
          {1: V33, 2: "UART_TX", 3: "UART_RX", 4: GND})
sch.place("J8", "Connector_Generic:Conn_01x06", "EXTENSION", FP["hdr6"], XE + g(28), YE2 + g(16),
          {1: V33, 2: "EXT_IO39", 3: "EXT_IO40", 4: "EXT_IO41", 5: "EXT_IO42", 6: GND})


# ================================================================= DRIVERS
def driver(n, x0, y0, refs):
    U, Jm, Cb, Ca, Cc, Ri, Rt, Rs, Rd, Rser, Rpu, Cip, Cadc, Cs1, Cs2, Cv1, Cv2 = refs
    vm, a, b = "VM%d" % n, "M%d_A" % n, "M%d_B" % n
    ip, isn, nf = "IPROPI%d" % n, "ISENSE%d" % n, "NFAULT%d" % n
    sch.text("MOTEUR %d  -  pont en H DRV8245S (réglages par SPI), limitation 10,6 A" % n, x0, y0 - g(4))
    ux, uy = x0 + g(18), y0 + g(10)
    # OUT2 est à gauche du boîtier VQFN : il reprend le cuivre de l'ancienne sortie A (sens inversé dans le firmware).
    # nSLEEP au +3V3 (pas de veille), PH/IN2 à la masse (sens donné par registre), DRVOFF et nFAULT non câblés.
    sch.place(U, "portail:DRV8245S_VQFN16", "DRV8245SQRXZRQ1", FP["vqfn"], ux, uy, {
        "EN/IN1": "M%d_EN" % n, "PH/IN2": GND, "nSLEEP": V33, "IPROPI": ip,
        "nSCS": "CS%d_N" % n, "SCLK": "SPI_SCLK", "SDI": "SPI_SDI", "SDO": "SDO%d" % n,
        "VM": vm, "OUT1": b, "OUT2": a, "GND": GND}, nc=["DRVOFF", "nFAULT"],
        stub=5.08, mpn="DRV8245SQRXZRQ1", note="Pont en H 32 A, variante SPI (S), VQFN-HR 16")
    sch.place(Jm, "Connector:Screw_Terminal_01x02", "MOTEUR %d" % n, FP["tb2"], ux + g(26), uy,
              {1: a, 2: b}, note="Bornier à vis 2 points, pas 5,08 mm")
    CP(Cb, "470u 50V", ux + g(38), uy, vm, GND)
    C(Ca, "100n 50V", ux + g(47), uy, vm, GND)
    C(Cc, "100n 50V", ux + g(56), uy, vm, GND)
    C(Cv1, "4.7u 50V", ux + g(47), uy - g(8), vm, GND, fp="c1206", mpn="GRM31CR71H475KA12", note="Céramique X7R au plus près des broches VM (côté gauche)")
    C(Cv2, "4.7u 50V", ux + g(56), uy - g(8), vm, GND, fp="c1206", mpn="GRM31CR71H475KA12", note="Céramique X7R au plus près des broches VM (côté droit)")
    yr = y0 + g(24)
    R(Ri, "1.2k 1%", x0 + g(2), yr, ip, GND)
    C(Cip, "10n 50V", x0 + g(11), yr, ip, GND)
    R(Rser, "10k", x0 + g(20), yr, ip, isn)
    C(Cadc, "100n 50V", x0 + g(29), yr, isn, GND)
    if Rpu:
        R(Rpu, "10k", x0 + g(65), yr, V33, "CS%d_N" % n, note="Tirage de la sélection SPI")
    C(Cs1, "10n 50V", x0 + g(74), yr, a, GND, note="Antiparasite de sortie moteur")
    C(Cs2, "10n 50V", x0 + g(83), yr, b, GND, note="Antiparasite de sortie moteur")


XD = g(140)
driver(1, XD, g(16), ["U2", "J2", "C1", "C3", "C4", "R1", None, None, None, "R9", "R11", "C15", "C17", "C20", "C21", "C25", "C26"])
driver(2, XD, g(56), ["U3", "J3", "C2", "C5", "C6", "R2", None, None, None, "R10", None, "C16", "C18", "C22", "C23", "C27", "C28"])
sch.text("Commun aux deux drivers", XD, g(92), 2.0)
R("R14", "100k", XD + g(11), g(98), "SPI_SCLK", GND, note="Horloge SPI au repos à 0")

# ================================================================= ENTREES
XI, YI = g(12), g(130)
sch.text("ENTREES OPTOCOUPLEES  -  contact entre +12V_ACC et l'entrée, actif = niveau bas côté ESP32", g(8), g(119))
sch.place("J4", "Connector:Screw_Terminal_01x08", "ENTREES", FP["tb8"], XI, YI + g(2), {
    1: "+12V_ACC", 2: "+12V_ACC", 3: "IN_PP", 4: "IN_FOTO", 5: "IN_RADIO", 6: "IN_STOP", 7: GND, 8: GND},
    note="Bornier à vis 8 points, pas 3,5 mm")
for i, (name, rs, d, u, rp) in enumerate([
        ("PP", "R22", "D4", "U7", "R26"), ("FOTO", "R23", "D5", "U8", "R27"),
        ("RADIO", "R24", "D6", "U9", "R28"), ("STOP", "R25", "D7", "U10", "R29")]):
    x = XI + g(16) + (i // 2) * g(56)
    y = YI + (i % 2) * g(14)
    R(rs, "2.2k", x, y, "IN_" + name, name + "_A", fp="r1206")
    sch.place(d, "Device:D", "1N4148W", FP["sod123"], x + g(9), y, {"K": name + "_A", "A": GND}, mpn="1N4148W")
    sch.place(u, "Isolator:PC817", "LTV-817S", FP["opto"], x + g(22), y,
              {1: name + "_A", 2: GND, 3: GND, 4: name + "_N"}, stub=5.08, mpn="LTV-817S",
              note="Optocoupleur CMS 4 broches")
    R(rp, "10k", x + g(36), y, V33, name + "_N")

# ================================================================= SORTIES
XO, YO = g(148), g(130)
sch.text("SORTIES 12 V  -  clignotant et auxiliaire (12 W au total avec les accessoires)", XO, g(119))
sch.place("J5", "Connector:Screw_Terminal_01x04", "SORTIES", FP["tb4"], XO + g(2), YO + g(2), {
    1: "+12V_OUT", 2: "LAMP_N", 3: "+12V_OUT", 4: "AUX_N"}, note="Bornier à vis 4 points, pas 3,5 mm")
for i, (name, rg, rpd, q, d) in enumerate([("LAMP", "R30", "R32", "Q1", "D8"), ("AUX", "R31", "R33", "Q2", "D9")]):
    x, y = XO + g(18), YO + i * g(14)
    R(rg, "100R", x, y, "OUT_" + name, name + "_G")
    R(rpd, "100k", x + g(9), y, name + "_G", GND)
    sch.place(q, "Device:Q_NMOS_GSD", "AO3422", FP["sot23"], x + g(22), y,
              {"G": name + "_G", "S": GND, "D": name + "_N"}, stub=5.08, mpn="AO3422",
              note="MOSFET N 55 V, 2,1 A, commande 2,5 V")
    sch.place(d, "Device:D_Schottky", "SS16", FP["sma"], x + g(36), y, {"K": "+12V_OUT", "A": name + "_N"},
              mpn="SS16", note="Diode de roue libre 60 V / 1 A")

# ================================================================= MECANIQUE
for i in range(4):
    sch.place("H%d" % (i + 1), "Mechanical:MountingHole", "M3", FP["hole"], g(12) + i * g(6), g(157), {}, in_bom=False)

sch.text("Points de test", g(40), g(153), 2.0)
# +12V, +5V et +3V3 se mesurent sur des broches traversantes (U11.3, U4.3, J7.1) : pas de pastille dédiée
for i, netname in enumerate([GND, VBUS, "ISENSE1", "ISENSE2"]):
    sch.place("TP%d" % (i + 1), "portail:TestPoint", netname, FP["tp"], g(46) + i * g(9), g(157), {1: netname},
              in_bom=False, stub=5.08, note="Pastille de test : rien à monter")

# ----------------------------------------------------------------- écriture
with open(os.path.join(OUT, PROJECT + ".kicad_sch"), "w", encoding="utf-8") as f:
    f.write(sch.render())
with open(os.path.join(OUT, "sym-lib-table"), "w", encoding="utf-8") as f:
    f.write('(sym_lib_table\n  (lib (name "portail")(type "KiCad")(uri "${KIPRJMOD}/portail.kicad_sym")(options "")(descr "Symboles du projet"))\n)\n')
if not os.path.exists(os.path.join(OUT, PROJECT + ".kicad_pro")):      # ne jamais écraser les règles du projet existant
    with open(os.path.join(OUT, PROJECT + ".kicad_pro"), "w", encoding="utf-8") as f:
        json.dump({"meta": {"filename": PROJECT + ".kicad_pro", "version": 1}}, f, indent=2)
with open(os.path.join(OUT, "intent.json"), "w", encoding="utf-8") as f:
    json.dump({"%s.%s" % k: v for k, v in sch.intent.items()}, f, indent=1, sort_keys=True)

# nomenclature groupée ; fabricant et référence commandable viennent de gen/references.csv (un repère par ligne)
REFS = {}
refpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "references.csv")
if os.path.exists(refpath):
    for r in csv.DictReader(open(refpath, encoding="utf-8"), delimiter=";"):
        REFS[r["Repère"]] = (r["Fabricant"], r["Référence complète"], r["Description"])
groups = {}
for p in sch.parts:
    if p["ref"].startswith(("TP", "H")):
        continue                                   # pastilles de test et trous : rien à monter
    fab, full, desc = REFS.get(p["ref"], ("", p["mpn"], ""))
    key = (p["value"], p["footprint"], fab, full, p["dnp"], p["note"] or desc, desc)
    groups.setdefault(key, []).append(p["ref"])


def refkey(r):
    head = r.rstrip("0123456789")
    return (head, int(r[len(head):] or 0))


EXTRA = [("(F1)", 1, "Fusible lame Mini 15 A", "Littelfuse", "0297015.WXNV", "à insérer à la main dans F1"),
         ("(F2, F3)", 2, "Fusible lame Mini 10 A", "Littelfuse", "0297010.WXNV", "à insérer à la main dans F2 et F3")]
rows = sorted(((sorted(refs, key=refkey), k) for k, refs in groups.items()), key=lambda t: refkey(t[0][0]))
missing = [refs for refs, k in rows if not k[3]]
with open(os.path.join(OUT, "..", "nomenclature.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f, delimiter=";")
    w.writerow(["Repères", "Qté", "Valeur", "Fabricant", "Référence fabricant", "Empreinte KiCad", "Monté", "Remarque"])
    for refs, (value, fp, fab, full, dnp, note, desc) in rows:
        w.writerow([", ".join(refs), len(refs), value, fab, full, fp, "non" if dnp else "oui", note])
    for refs, qty, value, fab, full, note in EXTRA:
        w.writerow([refs, qty, value, fab, full, "", "à la main", note])
# nomenclature d'assemblage au format demandé par Eurocircuits (CSV à virgules : repères, quantité, valeur, description,
# boîtier, fabricant, référence fabricant)
fab_dir = os.path.join(OUT, "..", "fabrication")
os.makedirs(fab_dir, exist_ok=True)
with open(os.path.join(fab_dir, "portail-nomenclature-eurocircuits.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Quantity", "Value", "Description", "Package", "Manufacturer", "MPN"])
    for refs, (value, fp, fab, full, dnp, note, desc) in rows:
        if not dnp:
            w.writerow([",".join(refs), len(refs), value, desc or note, fp.split(":")[1], fab, full])
print("composants :", len(sch.parts), "| lignes de nomenclature :", len(rows), "| sans référence :", missing)
