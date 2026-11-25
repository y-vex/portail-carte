# Licences

Copyright © 2026 y-vex

## Matériel

Le schéma, le circuit imprimé, les fichiers de fabrication, la nomenclature et les images de la carte
(`kicad/`, `fabrication/`, `portail-gerber.zip`, `schema.pdf`, `schema-lisible.html`, `nomenclature.csv`, `*.png`)
sont distribués sous la licence **CERN Open Hardware Licence Version 2 – Strongly Reciprocal** (CERN-OHL-S v2).
Texte complet : [`LICENSES/CERN-OHL-S-2.0.txt`](LICENSES/CERN-OHL-S-2.0.txt).

Emplacement de la source : ce dépôt.

Ces sources sont distribuées SANS AUCUNE GARANTIE, EXPRESSE OU IMPLICITE, Y COMPRIS DE QUALITÉ MARCHANDE, DE QUALITÉ
SATISFAISANTE ET D'ADÉQUATION À UN USAGE PARTICULIER. Voir la licence CERN-OHL-S v2 pour les conditions applicables.

## Logiciel

Le firmware (`firmware/`) et les scripts de génération (`gen/*.py`) sont des logiciels libres : vous pouvez les
redistribuer et les modifier selon les termes de la **GNU General Public License**, version 3 ou (à votre choix) toute
version ultérieure. Texte complet : [`LICENSES/GPL-3.0-or-later.txt`](LICENSES/GPL-3.0-or-later.txt).

Ces programmes sont distribués dans l'espoir qu'ils seront utiles, mais SANS AUCUNE GARANTIE, sans même la garantie
implicite de qualité marchande ou d'adéquation à un usage particulier.

## Éléments tiers

- Symboles, empreintes et modèles 3D issus des bibliothèques KiCad (`gen/symboles-kicad7.kicad_sym`,
  `kicad/portail.kicad_sym`, `kicad/portail.pretty/`, `models3d/`) : licence CC-BY-SA 4.0 avec l'exception des
  bibliothèques KiCad, qui en autorise l'usage dans un projet sans contrainte sur ce projet.
- Le firmware dépend de la bibliothèque HomeSpan (licence MIT) et du cœur Arduino-ESP32, qui ne sont pas inclus.
- Freerouting (GPL v3), utilisé pour le routage, n'est pas inclus.
