# SPDX-License-Identifier: GPL-3.0-or-later
#!/usr/bin/env python3
"""Fichiers d'assemblage au format JLCPCB (composants de surface seulement).
Lit fabrication/portail-nomenclature-eurocircuits.csv et portail-placement.csv,
écrit fabrication/jlcpcb/portail-bom-jlcpcb.csv et portail-cpl-jlcpcb.csv.
Codes LCSC relevés dans le catalogue JLCPCB le 10 nov. 2026."""
import csv, math, os
B = os.path.join(os.path.dirname(__file__), '..', 'fabrication')
LCSC = {  # MPN de la nomenclature -> (code LCSC, pièce réellement montée)
 'CL10B104KB8NNNC': 'C1591', 'CL21B106KOQNNNE': 'C95841', 'CL21B475KOFNNNE': 'C107365',
 'CL10B105KO8NNNC': 'C59782', 'CL10B103KB8NNNC': 'C1589', 'CL31B106KAHNNNE': 'C14860',
 'GRM31CR71H475KA12L': 'C77096', 'SMCJ24A-13-F': 'C135154', 'SS14-E3/61T': 'C2480',
 '1N4148W-7-F': 'C81598', 'SS16-E3/61T': 'C183023', 'APT1608SGC': 'C5875754', 'APT1608EC': 'C5554143',
 'SMAJ15A-13-F': 'C110520', 'BZT52C12-7-F': 'C124196', '0468002.NR': 'C187611', 'USB4105-GF-A': 'C3020560',
 'AO3422': 'C37130', 'IPD50P04P4L11ATMA2': 'C386372',
 'RC0603FR-071K2L': 'C22765', 'RC0603FR-0722KL': 'C31850', 'RC0603FR-07100KL': 'C25803',
 'RC0603FR-0710KL': 'C25804', 'RC0603FR-075K1L': 'C23186', 'RC1206FR-072K2L': 'C114933',
 'RC0603FR-07100RL': 'C22775', 'RC0603FR-071KL': 'C21190', 'TL3342F450QG': 'C2886897',
 'ESP32-S3-WROOM-1-N8': 'C2913198', 'DRV8245SQRXZRQ1': 'C6602055', 'AP7361C-33ER-13': 'C3743528',
 'USBLC6-2SC6': 'C7519', 'LTV-817S-TA1': 'C109227',
}
# Variante « tout monté » : JLCPCB pose aussi les pièces traversantes (stock relevé le 10 nov. 2026).
# Pièces de la nomenclature en stock chez eux :
THT = {'1715721': 'C480516', '1984633': 'C5144867', '61300411121': 'C5184785', '61300611121': 'C5444523',
       'RXEF050': 'C76399', 'RXEF110': 'C3760872', 'UHE1H101MPD': 'C116229', 'TSR 1-2450': 'C6886877',
       '3568': 'C3205378',               # Keystone 3568 (plan 3568-10), 15 en stock : 3 par carte
       # Remplacements, la référence d'origine étant en rupture chez eux :
       'UHE1H471MPD': 'C88733',          # C1, C2 -> Rubycon 50PX470MEFC10X20 (10 x 20 mm, 600 mA à 120 Hz, série ordinaire)
       'TSR 1-24120': 'C5369648',        # U11 -> YLPTEC K7812-1000R3 (même brochage Vin/GND/+Vo, 16 à 36 V, 11,5 x 7,55 x 10,2 mm)
       '1984675': 'C5144867'}            # J4 (8 points) -> deux borniers 4 points 1984633 côte à côte (largeur 14 mm = 4 x 3,5)
SPLIT = {'J4': (('J4A', 0.0), ('J4B', 14.0))}   # repère -> (nouveau repère, décalage en mm le long du bornier)
# Corrections de rotation propres aux modèles JLCPCB (degrés, sens anti-horaire), relevées sur leur aperçu du 10 nov. 2026
ROT = {'U6': -90, 'Q1': 180, 'Q2': 180, 'Q3': -90, 'U5': 180, 'U7': -90, 'U8': -90, 'U9': -90, 'U10': -90, 'J7': 90, 'J8': 90, 'D10': 180, 'D11': 180}
# Pièces traversantes : KiCad les repère par leur broche 1, JLCPCB par leur centre. Centres relevés sur la carte v0.4
# (x, y du fichier de placement, en mm).
CENTER = {'C1': (104.1, -113.5), 'C2': (146.1, -113.5), 'C7': (60.75, -101.0), 'F1': (67.04, -128.3), 'F2': (72.3, -100.46),
          'F3': (114.3, -100.46), 'F4': (96.5, -60.0), 'F5': (110.5, -60.0), 'J1': (66.54, -142.5), 'J2': (86.04, -142.5),
          'J3': (128.04, -142.5), 'J5': (145.25, -143.0), 'J7': (184.0, -65.81), 'J8': (189.5, -68.35), 'U4': (66.54, -64.0),
          'U11': (82.54, -64.0), 'U1': (168.0, -66.37), 'Q3': (59.85, -117.95), 'J6': (194.68, -102.0), 'J4A': (161.25, -143.0), 'J4B': (175.25, -143.0)}


def export(codes, suffix):
    groups, placed = {}, set()
    for r in csv.DictReader(open(os.path.join(B, 'portail-nomenclature-eurocircuits.csv'), encoding='utf-8')):
        code = codes.get(r['MPN'])
        if not code:
            continue                     # pièce non confiée à JLCPCB dans cette variante
        refs = r['Designator'].split(',')
        if suffix:
            refs = [n for x in refs for n in ([s[0] for s in SPLIT[x]] if x in SPLIT else [x])]
        placed.update(refs)
        g = groups.setdefault(code, {'c': r['Value'] + ' ' + r['MPN'], 'd': [], 'f': r['Package']})
        g['d'] += refs
    with open(os.path.join(B, 'jlcpcb', 'portail-bom-jlcpcb%s.csv' % suffix), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Comment', 'Designator', 'Footprint', 'LCSC Part #'])
        for code, g in groups.items():
            w.writerow([g['c'], ','.join(g['d']), g['f'], code])
    n = 0
    with open(os.path.join(B, 'jlcpcb', 'portail-cpl-jlcpcb%s.csv' % suffix), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'])
        for r in csv.DictReader(open(os.path.join(B, 'portail-placement.csv'), encoding='utf-8')):
            parts = SPLIT.get(r['Ref']) if suffix else None
            for ref, off in (parts or ((r['Ref'], 0.0),)):
                if ref not in placed:
                    continue
                a = math.radians(float(r['Rot']))
                x, y = float(r['PosX']) + off * math.cos(a), float(r['PosY']) + off * math.sin(a)
                x, y = CENTER.get(ref, (x, y))
                w.writerow([ref, '%.4fmm' % x, '%.4fmm' % y, 'Top' if r['Side'] == 'top' else 'Bottom',
                            '%g' % ((float(r['Rot']) + ROT.get(ref, 0)) % 360)])
                n += 1
    print(suffix or 'CMS seuls', ':', len(groups), 'lignes,', len(placed), 'composants,', n, 'placements')


export(LCSC, '')
export({**LCSC, **THT}, '-tout-monte')
