# Firmware de la carte portail

Écrit pour la carte v0.4 (brochage dans `config.h` ; drivers DRV8245S réglés par SPI, pilote dans `drv8245.h`). **En service sur un portail coulissant à deux vantaux depuis novembre 2026** (deux moteurs 24 V DC, alimentation 24 V régulée).

## Compiler et flasher

```bash
arduino-cli compile -b esp32:esp32:esp32s3:CDCOnBoot=cdc,FlashSize=8M,PartitionScheme=default_8MB .
arduino-cli upload  -b esp32:esp32:esp32s3:CDCOnBoot=cdc,FlashSize=8M,PartitionScheme=default_8MB -p /dev/cu.usbmodemXXXX .
arduino-cli monitor -p /dev/cu.usbmodemXXXX -c baudrate=115200
```

Outils utilisés : arduino-cli, cœur `esp32:esp32` 3.3.12, bibliothèque HomeSpan 2.1.8.

## Console série

Commandes HomeSpan habituelles (`?` pour la liste, `W` pour le Wi-Fi, `S` pour le code d'appairage, `O` pour le mot de passe OTA), plus :

| Commande | Effet |
| --- | --- |
| `@e` | état, position estimée, courants, entrées |
| `@o` `@f` `@x` | ouvrir, fermer, arrêter |
| `@s` | pas à pas (comme le bouton poussoir ou la télécommande) |
| `@a` | apprentissage en cinq courses : trois lentes, puis une ouverture et une fermeture à vitesse normale |
| `@p` | affiche les réglages ; `@p nom valeur` en modifie un |
| `@m 1 30 1000` | essai sur banc : moteur 1 à 30 % pendant 1000 ms (négatif = autre sens) |

Bouton APPRENTISSAGE de la carte : appui court = pas à pas, appui de 3 s = apprentissage.

## Page web

`http://<adresse de la carte>:8080/` (le port 80 est pris par HomeKit). État, mesures, commandes (ouvrir, arrêt, fermer,
pas à pas, apprentissage) et tous les réglages de `@p`. Code dans `web.h`. **Sans mot de passe** : tout appareil du réseau
local peut commander le portail. Mise à jour par le Wi-Fi :
`arduino-cli upload -b <même carte> -p <adresse> --protocol network --upload-field password=<mot de passe OTA> .`

## Réglages (`@p`)

`inv1`, `inv2` sens de chaque moteur · `cruise`, `slow` rapports cycliques en % (croisière à 100 % par défaut : sans
découpage, pour limiter l'échauffement des drivers ; ne la baisser qu'après avoir mesuré leur température) · `ramp` rampe en ms ·
`zone` part de la course au ralenti en % · `seuil1`, `seuil2` seuil de blocage en A (recalculé par l'apprentissage) ·
`fotoOn`, `fotoNC`, `stopOn`, `stopNC` entrées de sécurité · `clignote` (1 : la carte fait clignoter, 0 : sortie fixe) ·
`preavis` ms · `autoferme` s (0 = non).

Par défaut FOTO et STOP sont attendus **normalement fermés** : sans photocellule ni bouton d'arrêt branchés,
le portail refuse de fermer / de bouger. Sur banc : `@p fotoOn 0` et `@p stopOn 0`.

## Principe

- Boucle de commande toutes les 2 ms dans une tâche séparée de HomeKit, surveillée par un chien de garde.
- Pas de capteur : la position est estimée par le temps, pondéré par le rapport cyclique, et recalée à chaque butée.
- Blocage = courant au-dessus du seuil pendant 120 ms. Dans les derniers 20 % de la course : butée. Avant : obstacle
  (à la fermeture : réouverture complète ; à l'ouverture : court recul puis arrêt).
- Position inconnue (première mise sous tension, coupure pendant un mouvement, deux obstacles de suite) :
  mouvement lent, et le premier blocage est pris pour la butée.
- Course dépassée de 35 % sans blocage : défaut (moteur débrayé).
- Au repos les sorties des drivers sont en haute impédance (bit S_DRVOFF). Au démarrage, après un plantage ou après une coupure du 24 V, un driver non reconfiguré par SPI garde ses sorties coupées : sa broche DRVOFF n'est pas câblée et un tirage interne la maintient au niveau haut.

## Limites connues

- La distinction butée / obstacle repose sur une estimation par le temps : elle se dégrade si la tension ou les
  frottements changent beaucoup. Les seuils par défaut (5 A, 40 % au ralenti) sont des points de départ à régler sur le portail.
- Ce firmware ne remplace pas les sécurités exigées pour un portail motorisé (photocellules, effort limité vérifié à l'instrument).

## Journal et alertes HomeKit (20 nov. 2026)

- `journal.h` : les 20 derniers événements sont gardés en mémoire permanente (démarrages avec leur cause, défauts et
  obstacles avec courants, tension et état des drivers, reconnexions Wi-Fi). Affichés dans la section « Journal » de la
  page web ; `GET /api/journal` les renvoie en JSON. L'heure vient de `pool.ntp.org` (fuseau de Paris).
- Deux capteurs de contact HomeKit dans le même accessoire, « ouvert » = alerte active :
  « Défaut portail » (carte en état DEFAUT) et « Portail resté ouvert » (courses apprises et portail pas fermé depuis
  plus de `alerteouv` minutes, 10 par défaut, 0 = jamais ; réglage `@p alerteouv`).
- Une commande HomeKit reçue en défaut, en apprentissage ou en essai sur banc est refusée (Maison affiche un échec).

## Confort d'usage (20 nov. 2026)

- Réglages enregistrés un par un sous leur nom (`params.h`) : ajouter un réglage ne remet plus les autres à zéro.
  L'ancien bloc unique est repris une fois au premier démarrage (`ParamsV0`, structure figée).
- Page web : bouton « Acquitter le défaut » (commande `k`, ne lance jamais de mouvement ; aussi `@k` en console),
  date de compilation du firmware, « Effacer le journal », « Sauvegarder… » / « Restaurer… » les réglages
  (`GET` / `POST /api/reglages`, JSON plat ; restauration refusée en mouvement).
- Nom réseau : `http://portail.local:8080/`.

## Apprentissage en cinq courses (essayé au portail le 22 nov. 2026)

Trois courses lentes comme avant, puis une ouverture et une fermeture à vitesse normale qui calent les durées de
course (la vitesse n'est pas proportionnelle au rapport cyclique). Le seuil de blocage tient compte du plus fort
courant vu en marche à vitesse normale. Détail et mesures dans `gate.h` (section apprentissage).

## Ménager les moteurs (essayé au portail le 22 nov. 2026)

- **Arrêt progressif** : un arrêt ou une inversion commandés (page web, Maison, télécommande, bouton) font d'abord
  décélérer les moteurs sur `arret` ms (300 par défaut, 0 = arrêt net comme avant) au lieu de les freiner d'un coup.
  Un second ordre d'arrêt pendant la décélération arrête net. Les arrêts de sécurité (obstacle, entrée STOP,
  défaut) restent immédiats. La photocellule coupée pendant une fermeture fait décélérer sur 150 ms, puis rouvrir.
- **Seuil réduit en approche lente** : `seuilL1`, `seuilL2` (A, 0 = inactif, valeur par défaut). Quand la position est
  connue et que le vantail roule à la vitesse lente établie depuis 200 ms, c'est ce seuil qui décide du blocage : le
  moteur appuie moins fort sur la butée. Il n'est jamais appliqué pendant l'apprentissage.
- Pour le régler : la page affiche « Pointe en approche lente (dernier mouvement) », le plus fort courant vu dans cette
  phase, montée en butée exclue (300 dernières ms). Prendre une marge nette au-dessus de cette pointe.
- En approche lente établie, le blocage est confirmé au bout de 40 ms au lieu de 120 (`APPROACH_HOLD_MS`). Mesuré au
  portail : 2,9 à 3,5 A en butée avec `seuilL1 = seuilL2 = 2,8`, contre 5,1 à 7,3 A avant.
