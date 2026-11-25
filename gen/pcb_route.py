# SPDX-License-Identifier: GPL-3.0-or-later
"""Routage : export vers Freerouting, import du résultat, remplissage des zones, contrôle des règles."""
import os
import re
import subprocess

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
K = os.path.join(HERE, "..", "kicad")
PCB = os.path.join(K, "portail.kicad_pcb")
b = pcbnew.LoadBoard(PCB)
nc = b.GetDesignSettings().m_NetSettings.m_DefaultNetClass
nc.SetTrackWidth(pcbnew.FromMM(0.2))
nc.SetClearance(pcbnew.FromMM(0.15))
nc.SetViaDiameter(pcbnew.FromMM(0.6))
nc.SetViaDrill(pcbnew.FromMM(0.3))
dsn, ses = os.path.join(K, "portail.dsn"), os.path.join(K, "portail.ses")
assert pcbnew.ExportSpecctraDSN(b, dsn)
s = open(dsn).read()
POWER = ("+24V_IN VBUS VM1 VM2 M1_A M1_B M2_A M2_B GND +12V +12V_ACC +12V_OUT +5V VLDO +3V3 "
         "USB_VBUS LAMP_N AUX_N").split()
m = re.search(r'\(class kicad_default ""(.*?)\(circuit', s, re.S)
names = m.group(1).split()
sig = [n for n in names if n not in POWER]
pw = [n for n in names if n in POWER]
tail = s[m.end() - len("(circuit"):]
via = re.search(r"\(use_via [^)]*\)", tail).group(0)


def cls(name, nets, width):
    return ('(class %s %s\n      (circuit\n        %s\n      )\n      (rule\n        (width %d)\n'
            '        (clearance 150.1)\n      )\n    )\n' % (name, " ".join(nets), via, width))


end = tail.index("(wiring")
open(dsn, "w").write(s[:m.start()] + cls("signal", sig, 200) + "    " + cls("power", pw, 400) + "  )\n  " + tail[end:])
if os.path.exists(ses):
    os.remove(ses)
r = subprocess.run(["xvfb-run", "-a", "java", "-jar", os.path.join(HERE, "..", "tools", "freerouting.jar"),
                    "-de", dsn, "-do", ses, "-mp", "60"], capture_output=True, text=True, timeout=1400)
print(r.stdout[-500:])
print(r.stderr[-300:])
assert os.path.exists(ses), "pas de résultat de routage"
print("fichier de routage écrit")
