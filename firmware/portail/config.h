// SPDX-License-Identifier: GPL-3.0-or-later
// Carte portail v0.4 — brochage et réglages. Les drivers DRV8245S se règlent par SPI ; la liaison réutilise les fils
// de la v0.3 (ancien rôle entre parenthèses).
#pragma once
#include <Arduino.h>

// ---------------------------------------------------------------- broches
constexpr int PIN_ISENSE[2] = {1, 2};     // courant moteur 1 / 2 (ADC1)
constexpr int PIN_VSENSE    = 4;          // tension du bus, diviseur 100k/10k
constexpr int PIN_EN[2]     = {6, 8};     // PWM vers EN/IN1 (ex-PH moteur 1, ex-nFAULT moteur 2)
constexpr int PIN_SDO[2]    = {5, 7};     // SPI : données lues, une ligne par driver (ex-EN)
constexpr int PIN_CS[2]     = {18, 15};   // SPI : sélection, bas = actif (ex-nFAULT moteur 1, ex-PH moteur 2)
constexpr int PIN_SDI       = 16;         // SPI : données écrites, commune aux deux drivers (ex-DRVOFF)
constexpr int PIN_SCLK      = 17;         // SPI : horloge, commune (ex-nSLEEP)
constexpr int PIN_PP        = 9;          // entrées optocouplées : bas = contact fermé
constexpr int PIN_FOTO      = 10;
constexpr int PIN_RADIO     = 11;
constexpr int PIN_STOP      = 12;
constexpr int PIN_LAMP      = 13;
constexpr int PIN_AUX       = 14;
constexpr int PIN_BTN_LEARN = 21;         // bas = appuyé
constexpr int PIN_LED       = 38;         // LED d'état (gérée par HomeSpan)
constexpr int PIN_BOOT      = 0;          // bouton BOOT = bouton de contrôle HomeSpan

// ---------------------------------------------------------------- constantes matérielles
constexpr float MV_PER_AMP   = 187.5f;    // IPROPI : 1,2 kΩ × (1/6400) A/A (boîtier VQFN-HR)
constexpr float VBUS_DIVIDER = 11.0f;     // (100k + 10k) / 10k
constexpr int   PWM_HZ       = 20000;
constexpr int   PWM_BITS     = 10;        // 0..1023
constexpr int   TICK_MS      = 2;         // période de la boucle de commande

// ---------------------------------------------------------------- limites fixes de sécurité
constexpr float    VBUS_MIN_V      = 18.0f;   // en dessous : refus de démarrer (ex. alimentation USB seule)
constexpr float    VBUS_MAX_V      = 30.0f;
constexpr uint32_t RUN_MAX_MS      = 120000;  // durée maximale absolue d'un mouvement
constexpr uint32_t STALL_BLANK_MS  = 300;     // courant de démarrage ignoré
constexpr uint32_t STALL_HOLD_MS   = 120;     // durée au-dessus du seuil pour conclure au blocage
constexpr uint32_t APPROACH_HOLD_MS = 40;     // idem en approche lente établie : pas de pointe de démarrage à ignorer,
                                              // et le courant en butée montait à 5-7 A pendant les 120 ms (22 nov. 2026)
constexpr float    END_TOLERANCE   = 0.20f;   // blocage dans les derniers 20 % de la course = butée
constexpr float    OVERRUN         = 0.35f;   // course dépassée de 35 % sans butée = défaut (moteur débrayé ?)
constexpr uint32_t REVERSE_PAUSE_MS = 400;    // pause avant inversion
constexpr uint32_t BACKOFF_MS      = 400;     // recul après obstacle à l'ouverture
constexpr uint32_t IDLE_SLEEP_MS   = 1000;    // sorties des drivers en haute impédance après l'arrêt
constexpr uint32_t DRV_POLL_MS     = 20;      // période de lecture de l'état des drivers pendant un mouvement
