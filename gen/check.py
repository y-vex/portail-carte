# SPDX-License-Identifier: GPL-3.0-or-later
"""Contrôle : la netlist exportée par KiCad doit correspondre au circuit voulu,
puis quelques règles électriques simples sont vérifiées."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sexpr import parse, find, first

K = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "kicad")
intent = json.load(open(os.path.join(K, "intent.json"), encoding="utf-8"))
net = parse(open(os.path.join(K, "portail.net"), encoding="utf-8").read())

actual, types, members = {}, {}, {}
for n in find(first(net, "nets"), "net"):
    name = str(first(n, "name")[1]).lstrip("/")
    for node in find(n, "node"):
        key = "%s.%s" % (first(node, "ref")[1], first(node, "pin")[1])
        actual[key] = name
        pt = first(node, "pintype")
        types[key] = str(pt[1]) if pt else "?"
        members.setdefault(name, []).append(key)

errors = []
for key, want in sorted(intent.items()):
    if key.startswith("#"):
        continue
    got = actual.get(key)
    if want is None:
        if got is not None and not got.startswith("unconnected-"):
            errors.append("%s devrait être libre, trouvé sur %s" % (key, got))
    elif got != want:
        errors.append("%s : voulu %s, trouvé %s" % (key, want, got))
for key in actual:
    if key not in intent and not key.startswith("#"):
        errors.append("%s présent dans la netlist mais pas dans le circuit voulu" % key)

# règles simples
flags = {v for k, v in intent.items() if k.startswith("#FLG")}
for name, keys in sorted(members.items()):
    if name.startswith("unconnected-"):
        continue
    real = [k for k in keys if not k.startswith("#")]
    if len(real) < 2:
        errors.append("net %s : une seule broche (%s)" % (name, real))
    outs = [k for k in real if types[k] in ("output", "power_out")]
    if len(outs) > 1:
        errors.append("net %s : plusieurs sorties %s" % (name, outs))
    pin_in = [k for k in real if types[k] == "power_in"]
    if pin_in and not outs and name not in flags:
        errors.append("net %s : entrée d'alimentation %s sans source ni PWR_FLAG" % (name, pin_in))

comps = find(first(net, "components"), "comp")
print("composants dans la netlist :", len(comps))
print("nets :", len([m for m in members if not m.startswith("unconnected-")]),
      "| broches comparées :", len([k for k in intent if not k.startswith("#")]))
if errors:
    print("ERREURS :")
    for e in errors:
        print("  -", e)
    sys.exit(1)
print("OK : netlist KiCad identique au circuit voulu, règles simples respectées")
