# SPDX-License-Identifier: GPL-3.0-or-later
"""Générateur de schéma KiCad 7 « par étiquettes » : chaque broche reçoit un
court fil et une étiquette de net. Les symboles viennent des bibliothèques
KiCad installées (ou d'une bibliothèque du projet) et sont embarqués dans le
schéma."""
import copy
import os
import uuid

from sexpr import Q, parse, dump, find, first

SYMDIR = "/usr/share/kicad/symbols"
G = 1.27  # demi-pas de grille


def uid(seed):
    return Q(str(uuid.uuid5(uuid.NAMESPACE_DNS, "portail-carte/" + seed)))


class Library:
    def __init__(self):
        self.files = {}
        self.extra = {}
        self.cache = None

    def add_file(self, libname, path):
        self.extra[libname] = path

    def _load(self, libname):
        if libname not in self.files:
            path = self.extra.get(libname) or os.path.join(SYMDIR, libname + ".kicad_sym")
            tree = parse(open(path, encoding="utf-8").read())
            self.files[libname] = {s[1]: s for s in find(tree, "symbol")}
        return self.files[libname]

    def flat(self, lib_id):
        """Symbole aplati (héritage 'extends' résolu), nommé 'Lib:Nom'."""
        libname, name = lib_id.split(":")
        if libname not in self.extra:
            # symboles KiCad 7 d'origine, conservés dans gen/symboles-kicad7.kicad_sym (déjà aplatis) :
            # le schéma se régénère à l'identique quelle que soit la version de KiCad installée
            if self.cache is None:
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "symboles-kicad7.kicad_sym")
                self.cache = {str(c[1]): c for c in find(parse(open(path, encoding="utf-8").read()), "symbol")} if os.path.exists(path) else {}
            if lib_id in self.cache:
                return copy.deepcopy(self.cache[lib_id])
        syms = self._load(libname)
        sym = syms[name]
        ext = first(sym, "extends")
        if ext:
            parent = copy.deepcopy(syms[ext[1]])
            assert not first(parent, "extends"), "héritage à deux niveaux"
            pname = parent[1]
            props = {p[1]: p for p in find(sym, "property")}
            out = []
            seen = set()
            for item in parent:
                if isinstance(item, list) and item[0] == "property":
                    if item[1] in props:
                        out.append(copy.deepcopy(props[item[1]]))
                        seen.add(item[1])
                    else:
                        out.append(item)
                elif isinstance(item, list) and item[0] == "symbol":
                    item[1] = Q(name + item[1][len(pname):])
                    out.append(item)
                else:
                    out.append(item)
            for k, p in props.items():
                if k not in seen:
                    out.insert(len(out) - len(find(out, "symbol")), copy.deepcopy(p))
            sym = out
        else:
            sym = copy.deepcopy(sym)
        sym[1] = Q(lib_id)
        return sym


def pins_of(sym):
    """Liste des broches : dict(number, name, x, y, angle, type, hidden, unit)."""
    res = []
    for sub in find(sym, "symbol"):
        unit = int(sub[1].rsplit("_", 2)[1])
        for p in find(sub, "pin"):
            at = first(p, "at")
            res.append(dict(
                number=str(first(p, "number")[1]),
                name=str(first(p, "name")[1]),
                x=float(at[1]), y=float(at[2]), angle=int(float(at[3])) if len(at) > 3 else 0,
                type=p[1], hidden=("hide" in p), unit=unit))
    return res


def units_of(sym):
    return sorted({int(s[1].rsplit("_", 2)[1]) for s in find(sym, "symbol")} - {0}) or [1]


class Schematic:
    def __init__(self, project, title, rev, paper="A2"):
        self.project = project
        self.title, self.rev, self.paper = title, rev, paper
        self.lib = Library()
        self.libsyms = {}
        self.items = []
        self.root = uid("root")
        self.intent = {}      # (ref, pin number) -> net ou None
        self.parts = []       # nomenclature
        self._wires = set()
        self._labels = set()
        self._nc = set()
        self._n = 0

    def _id(self, tag):
        self._n += 1
        return uid("%s-%d" % (tag, self._n))

    def text(self, s, x, y, size=3.0):
        self.items.append(["text", Q(s), ["at", x, y, 0],
                           ["effects", ["font", ["size", size, size]], ["justify", "left", "bottom"]],
                           ["uuid", self._id("t")]])

    def box(self, x1, y1, x2, y2):
        self.items.append(["rectangle", ["start", x1, y1], ["end", x2, y2],
                           ["stroke", ["width", 0.2], ["type", "dash"]], ["fill", ["type", "none"]],
                           ["uuid", self._id("r")]])

    def _wire(self, x1, y1, x2, y2):
        key = (round(x1, 3), round(y1, 3), round(x2, 3), round(y2, 3))
        if key in self._wires:
            return
        self._wires.add(key)
        self.items.append(["wire", ["pts", ["xy", x1, y1], ["xy", x2, y2]],
                           ["stroke", ["width", 0], ["type", "default"]], ["uuid", self._id("w")]])

    def _label(self, net, x, y, angle, just):
        key = (net, round(x, 3), round(y, 3))
        if key in self._labels:
            return
        self._labels.add(key)
        self.items.append(["label", Q(net), ["at", x, y, angle],
                           ["effects", ["font", ["size", 1.27, 1.27]], ["justify", just, "bottom"]],
                           ["uuid", self._id("l")]])

    def _noconnect(self, x, y):
        key = (round(x, 3), round(y, 3))
        if key in self._nc:
            return
        self._nc.add(key)
        self.items.append(["no_connect", ["at", x, y], ["uuid", self._id("nc")]])

    def place(self, ref, lib_id, value, footprint, x, y, nets, nc=(), stub=2.54,
              dnp=False, in_bom=True, mpn="", note=""):
        """nets : {numéro ou nom de broche: net}. nc : broches laissées libres."""
        if lib_id not in self.libsyms:
            self.libsyms[lib_id] = self.lib.flat(lib_id)
        sym = self.libsyms[lib_id]
        pins = pins_of(sym)
        assert units_of(sym) == [1], "%s : symbole multi-unités non géré" % lib_id
        numbers = {p["number"] for p in pins}
        assign = {}
        for key, net in nets.items():
            key = str(key)
            if key in numbers:
                targets = [key]
            else:
                targets = [p["number"] for p in pins if p["name"] == key]
                assert targets, "%s : broche '%s' inconnue dans %s" % (ref, key, lib_id)
            for t in targets:
                assert t not in assign, "%s : broche %s affectée deux fois" % (ref, t)
                assign[t] = net
        for key in nc:
            key = str(key)
            targets = [key] if key in numbers else [p["number"] for p in pins if p["name"] == key]
            assert targets, "%s : broche NC '%s' inconnue" % (ref, key)
            for t in targets:
                assert t not in assign, "%s : broche %s à la fois NC et connectée" % (ref, t)
                assign[t] = None
        missing = sorted(numbers - set(assign))
        assert not missing, "%s (%s) : broches non traitées %s" % (ref, lib_id, missing)

        # les broches superposées doivent porter le même net
        at_pos = {}
        for p in pins:
            pos = (p["x"], p["y"])
            net = assign[p["number"]]
            if pos in at_pos:
                assert at_pos[pos] == net, "%s : broches superposées en %s sur des nets différents" % (ref, pos)
            at_pos[pos] = net

        for p in pins:
            net = assign[p["number"]]
            self.intent[(ref, p["number"])] = net
            px, py = x + p["x"], y - p["y"]
            if net is None:
                self._noconnect(px, py)
                continue
            a = p["angle"]
            if a == 0:      # corps à droite, fil vers la gauche
                ex, ey, la, lj = px - stub, py, 180, "right"
            elif a == 180:
                ex, ey, la, lj = px + stub, py, 0, "left"
            elif a == 90:   # corps au-dessus, fil vers le bas
                ex, ey, la, lj = px, py + stub, 0, "left"
            else:           # 270 : corps en dessous, fil vers le haut
                ex, ey, la, lj = px, py - stub, 0, "left"
            self._wire(px, py, ex, ey)
            self._label(net, ex, ey, la, lj)

        xs = [p["x"] for p in pins] or [0]
        ys = [p["y"] for p in pins] or [0]
        vertical = pins and all(p["angle"] in (90, 270) for p in pins)
        if vertical:
            rx, ry, vx, vy = x + 2.54, y - 1.27, x + 2.54, y + 1.27
        else:
            rx, ry = x + min(xs) + 2.54, y - max(ys) - 3.81
            vx, vy = x + min(xs) + 2.54, y - min(ys) + 3.81
        eff = ["effects", ["font", ["size", 1.27, 1.27]], ["justify", "left"]]
        hid = ["effects", ["font", ["size", 1.27, 1.27]], "hide"]
        node = ["symbol", ["lib_id", Q(lib_id)], ["at", x, y, 0], ["unit", 1],
                ["in_bom", "yes" if in_bom else "no"], ["on_board", "yes"], ["dnp", "yes" if dnp else "no"],
                ["uuid", uid("sym-" + ref)],
                ["property", Q("Reference"), Q(ref), ["at", rx, ry, 0], copy.deepcopy(eff)],
                ["property", Q("Value"), Q(value), ["at", vx, vy, 0], copy.deepcopy(eff)],
                ["property", Q("Footprint"), Q(footprint), ["at", x, y, 0], copy.deepcopy(hid)],
                ["property", Q("Datasheet"), Q("~"), ["at", x, y, 0], copy.deepcopy(hid)]]
        if mpn:
            node.append(["property", Q("MPN"), Q(mpn), ["at", x, y, 0], copy.deepcopy(hid)])
        for p in pins:
            node.append(["pin", Q(p["number"]), ["uuid", uid("pin-%s-%s" % (ref, p["number"]))]])
        node.append(["instances", ["project", Q(self.project),
                                   ["path", Q("/" + self.root), ["reference", Q(ref)], ["unit", 1]]]])
        self.items.append(node)
        if not ref.startswith("#"):
            self.parts.append(dict(ref=ref, value=value, footprint=footprint, mpn=mpn, dnp=dnp, note=note))

    def render(self):
        libs = ["lib_symbols"] + [self.libsyms[k] for k in sorted(self.libsyms)]
        top = ["kicad_sch", ["version", 20230121], ["generator", "eeschema"],
               ["uuid", self.root], ["paper", Q(self.paper)],
               ["title_block", ["title", Q(self.title)], ["date", Q("2026-11-10")], ["rev", Q(self.rev)]],
               libs]
        top += self.items
        top.append(["sheet_instances", ["path", Q("/"), ["page", Q("1")]]])
        return dump(top) + "\n"
