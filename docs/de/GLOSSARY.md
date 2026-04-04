# Glossar

English: [../GLOSSARY.md](../GLOSSARY.md)

Dieses Glossar erklärt die wichtigsten Begriffe aus diesem Repository.
Die Definitionen sind bewusst kurz und auf die Praxis hier ausgerichtet.

## Yocto Project

Ein Build-Framework für angepasste Linux-Systeme.
In diesem Projekt ist Yocto die Basis des Build-Ökosystems.

## OpenEmbedded (OE)

Das Metadaten-Ökosystem unter Yocto.
Vereinfacht: die Layer- und Recipe-Welt, die definiert, was gebaut wird.

## BitBake

Die Task-Engine, die Rezepte ausführt und Artefakte baut.
Wenn du Images baust, läuft BitBake im Hintergrund.

## Layer

Eine Sammlung von OE-Metadaten (Rezepte, Konfigurationen, Klassen).
Beispiele in diesem Workspace: `meta-tuxbox`, `meta-neutrino`.

## Recipe (`.bb`)

Eine Build-Anleitung für eine Komponente/ein Paket.
Sie definiert Quellen, Abhängigkeiten, Build-/Install-Schritte und Paketausgaben.

## Append (`.bbappend`)

Eine Erweiterungsdatei, die ein Recipe aus einem anderen Layer ergänzt.
So passt du Upstream-Verhalten an, ohne das Ursprungs-Recipe zu forken.

## Submodule

Ein Git-Repository innerhalb dieses Repositories.
Der Builder nutzt Submodule für Layer, damit Versionen kontrolliert bleiben.

## Pinning

Die Nutzung exakt aufgezeichneter Git-Commits für Submodule.
In diesem Projekt ist gepinnter Sync der sichere/reproduzierbare Standard.

## Unpinned Sync

Submodule werden auf Upstream-Branch-HEAD statt auf aufgezeichnete Commits gesetzt.
Das ist für Maintainer nützlich, für normale Builds aber riskant.

## `make update`

Sicheres Standard-Update-Kommando.
Es fast-forwardet das Top-Level-Repo, synchronisiert die Submodul-URLs und
setzt danach die gepinnten Submodul-Commits explizit.

## `make sync`

Gleiches sicheres gepinntes Verhalten wie `make update`.
Nutze es, wenn du Optionen wie `SYNC_EXCLUDE=...` brauchst.

## `make update-upstream`

Maintainer-Kommando für unpinned Submodule-Updates.
Es kann den Tree dirty machen und von reproduzierbaren Pins wegführen.

## MACHINE

Zielgeräte-Kennung in Yocto/OE-Metadaten.
Beispiel: `hd51`.

## MACHINEBUILD

Hersteller-/Brand-spezifische Maschinenvariante in diesem Projekt.
Bei vielen Geräten identisch mit `MACHINE`, bei manchen unterschiedlich.

## DISTRO

Distributionsprofil mit Policies und Paketumfang.
Standard in diesem Repo ist typischerweise `tuxbox`.

## sstate-Cache

Geteilter Build-Cache für kompilierte Task-Ergebnisse.
Wiederverwendung beschleunigt Rebuilds deutlich.

## Downloads-Cache (`DL_DIR`)

Lokaler Cache für heruntergeladene Quellarchive.
Macht wiederholte Builds schneller und stabiler.

## Feeds

Paket-Feed-Ausgaben für Runtime-Paketinstallation/-Updates.
Baust du mit `make feeds ...`.

## SDK

Software Development Kit für externe Apps gegen das Zielsystem.
Baust du mit `make sdk ...`.

## QEMU

Virtuelle Maschine für schnelle Image-Smoke-Tests ohne Hardware.
Details in [QEMU.md](QEMU.md).

## Init-System (`systemd` / `sysvinit`)

Service-Startsystem im Zielimage.
Recipes müssen Service-Dateien passend zum aktiven Init-System installieren.
