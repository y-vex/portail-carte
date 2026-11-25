# SPDX-License-Identifier: GPL-3.0-or-later
"""Enchaîne placement, routage et import ; relance le routeur tant qu'il reste des liaisons non faites."""
import os, re, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
K = os.path.join(HERE, "..", "kicad")
best = None
for attempt in range(5):
    for script in ("pcb_build.py", "pcb_route.py", "pcb_import.py"):
        r = subprocess.run([sys.executable, os.path.join(HERE, script)], capture_output=True, text=True)
        if r.returncode:
            print(script, "a échoué :", r.stdout[-400:], r.stderr[-400:]); sys.exit(1)
    t = open(os.path.join(K, "drc.txt")).read()
    un = len(re.findall(r"^\[unconnected_items\]", t, re.M))
    cl = len(re.findall(r"^\[(clearance|hole_clearance|shorting_items|tracks_crossing|hole_near_hole)\]", t, re.M))
    print("essai", attempt + 1, ": non connectés", un, "| erreurs d'isolement", cl)
    if best is None or (un + cl) < best:
        best = un + cl
        shutil.copy(os.path.join(K, "portail.kicad_pcb"), os.path.join(K, "portail.best.kicad_pcb"))
        shutil.copy(os.path.join(K, "drc.txt"), os.path.join(K, "drc.best.txt"))
    if best == 0:
        break
shutil.copy(os.path.join(K, "portail.best.kicad_pcb"), os.path.join(K, "portail.kicad_pcb"))
shutil.copy(os.path.join(K, "drc.best.txt"), os.path.join(K, "drc.txt"))
print("meilleur résultat :", best)
