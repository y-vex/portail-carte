# SPDX-License-Identifier: GPL-3.0-or-later
"""Lecture / écriture minimale des S-expressions KiCad."""


class Q(str):
    """Chaîne qui doit être écrite entre guillemets."""


def parse(text):
    pos = 0
    n = len(text)
    stack = [[]]
    while pos < n:
        c = text[pos]
        if c in " \t\r\n":
            pos += 1
        elif c == "(":
            new = []
            stack[-1].append(new)
            stack.append(new)
            pos += 1
        elif c == ")":
            stack.pop()
            pos += 1
        elif c == '"':
            pos += 1
            buf = []
            while text[pos] != '"':
                if text[pos] == "\\":
                    pos += 1
                    esc = text[pos]
                    buf.append({"n": "\n", "t": "\t", "r": "\r"}.get(esc, esc))
                else:
                    buf.append(text[pos])
                pos += 1
            pos += 1
            stack[-1].append(Q("".join(buf)))
        else:
            start = pos
            while pos < n and text[pos] not in ' \t\r\n()"':
                pos += 1
            stack[-1].append(text[start:pos])
    assert len(stack) == 1, "parenthèses non équilibrées"
    return stack[0][0]


def _atom(a):
    if isinstance(a, Q):
        s = a.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
        return '"' + s + '"'
    if isinstance(a, float):
        s = ("%.4f" % a).rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    return str(a)


def dump(node, indent=0):
    if not isinstance(node, list):
        return _atom(node)
    flat = "(" + " ".join(dump(x) for x in node) + ")"
    if len(flat) <= 110 and "\n" not in flat:
        return flat
    pad = "  " * (indent + 1)
    head = []
    rest = list(node)
    while rest and not isinstance(rest[0], list):
        head.append(_atom(rest.pop(0)))
    out = "(" + " ".join(head)
    for x in rest:
        out += "\n" + pad + dump(x, indent + 1)
    out += "\n" + "  " * indent + ")"
    return out


def find(node, name):
    return [x for x in node if isinstance(x, list) and x and x[0] == name]


def first(node, name):
    r = find(node, name)
    return r[0] if r else None
