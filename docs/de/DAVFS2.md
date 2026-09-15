# Optionale WebDAV-Mounts mit davfs2

English: [../DAVFS2.md](../DAVFS2.md)

Der Builder stellt davfs2 1.7.3 als optionales Paket bereit. Es ist nicht im
Standardimage installiert. Die aktuellen Tuxbox-Receiver-Images verwenden
systemd; mit der Paketinstallation wird `davfs2.service` installiert und
aktiviert. Ein Tuxbox-Append ergänzt das OE-Alliance-Rezept. Das Append ist
bewusst an dessen Dateinamen mit `1.5.4` gebunden; das gebaute Paket hat Version
1.7.3. Wird das OE-Alliance-Rezept umbenannt, muss das Append geprüft und
passend umbenannt werden.

## Bauen und installieren

Auf dem Build-Host das Paket für den Empfänger bauen (Beispiel H7):

```sh
make bb MACHINE=h7 TARGET=davfs2 BB_TASK=package_write_ipk
```

Das Paket liegt unter `builds/h7/tmp/deploy/ipk/`. Über den konfigurierten
Paketfeed bereitstellen; siehe
[lokaler IPK-Feed](../../README.de.md#lokaler-ipk-feed).
Sobald diese Version im Feed liegt, auf dem Empfänger ausführen:

```sh
opkg update
opkg install davfs2
```

Der Kernel muss FUSE bereitstellen, fest eingebaut oder als
`kernel-module-fuse`. Coda wird von dieser davfs2-Version nicht unterstützt.

## Freigabe einrichten

Als root `/etc/davfs2/davfs2.mount.list` bearbeiten. Jeder Eintrag hat genau
zwei Felder:

```text
https://cloud.example.com/remote.php/dav/files/alice /mnt/dav/cloud
```

URL und Mountpunkt durch eigene Werte ersetzen. Der Mountpunkt muss ein
absoluter Pfad außer `/` sein. Leerzeilen und auch eingerückte Kommentare sind
erlaubt. Leerraum innerhalb eines Feldes, zusätzliche Felder und Zugangsdaten
in URLs werden abgewiesen. Leerzeichen in URLs müssen URL-kodiert werden;
Mountpunktnamen mit Leerzeichen werden nicht unterstützt.

Zugangsdaten im davfs2-Secrets-Format in `/etc/davfs2/secrets` hinterlegen:

```text
/mnt/dav/cloud alice "dein-passwort"
```

Die Datei muss root gehören und Modus `0600` haben. Für Anführungszeichen und
Backslashes in Passwörtern die Escape-Regeln des installierten davfs2-Handbuchs
beachten. Zugangsdaten gehören nicht in die Mount-Liste. Automatisches Mounten
liest keine interaktiven Antworten; Server-URLs und Ausgaben des Mount-Helfers
werden nicht in die Diagnose übernommen.

Normalerweise vertrauenswürdige HTTPS-Zertifikate verwenden. Bei privater CA
oder fest hinterlegtem Serverzertifikat das Zertifikat über einen
vertrauenswürdigen Kanal beschaffen, unter `/etc/davfs2/certs/` ablegen und
`trust_ca_cert` oder `trust_server_cert` in `davfs2.conf` konfigurieren.
Ein Serverzertifikat auf den Abschnitt seines Mountpunkts beschränken:

```text
[/mnt/dav/cloud]
trust_server_cert cloud.pem
```

Ein Zertifikat nicht allein dadurch als vertrauenswürdig einstufen, dass es
über dieselbe ungeprüfte Verbindung heruntergeladen wurde.

## Starten, prüfen und Fehler beheben

Tuxbox-Receiver-Images verwenden systemd. Das Paket liefert und aktiviert
`davfs2.service`; die leere Standardliste mountet nichts. Der Dienst wartet auf
`network-online.target`. Der Netzwerkmanager des Images muss einen passenden
Wait-online-Dienst bereitstellen, damit das Ziel tatsächliche Netzbereitschaft
anzeigt.

Nach dem Einrichten:

```sh
systemctl restart davfs2.service
systemctl status davfs2.service
findmnt --mountpoint /mnt/dav/cloud
```

Der Mount muss die erwartete WebDAV-Quelle und `fuse` (oder `fuse.davfs`) anzeigen. Lesen und
Schreiben zunächst mit entbehrlichen Dateien auf einer eigenen Testfreigabe
prüfen. Die bisherigen Tuxbox-Defaults aktivieren Kompression, deaktivieren
WebDAV-Locks und verwenden `backup` als Backup-Verzeichnis. Vor parallelen
Schreibzugriffen die Lock-Einstellung prüfen.

Bei Fehlern `journalctl -u davfs2.service` aufrufen. Meldungen nennen die
Konfigurationszeile, ohne Zugangsdaten auszugeben. Netzwerk, Zugangsdaten oder
Zertifikatsvertrauen korrigieren und `systemctl restart davfs2.service`
ausführen. Es gibt keine automatische Wiederholung. Nach fehlgeschlagenem
Start räumt der Stop-post-Befehl erfolgreich gemountete Einträge auf.
Auch Unmount-Fehler werden gemeldet.

`systemctl stop davfs2.service` hängt nur passende WebDAV-Mounts aus der
aktuellen Liste aus. Den Dienst **vor dem Entfernen oder Ändern von Einträgen
stoppen**; sonst fehlt ein alter Mount in der Liste zum Aufräumen.
Fremde Mounts bleiben unberührt und führen zu einer Fehlermeldung.

Das Append bleibt für alte uClibc-/SysVinit-Konfigurationen auswertbar und
liefert dort bewusst keinen Autostart-Dienst. Dieser Kompatibilitätspfad ist
nicht das Init-System der aktuellen Receiver-Images.

## Migration von ignore_cert

Das bisherige dritte Feld `ignore_cert` wird abgewiesen. Bestehende
Konfigurationsdateien bleiben als Paket-Konfigurationsdateien geschützt und
werden nicht stillschweigend umgeschrieben. Zertifikatsvertrauen wie oben
einrichten, `ignore_cert` aus dem Eintrag entfernen und den Dienst neu starten.
Einträge mit diesem Feld werden nicht gemountet. Vom Paketmanager abgelegte
neue Konfigurationsvorlagen vor dem Zusammenführen mit lokalen Einstellungen
prüfen.

## Prüfungen für Maintainer

Isolierte Lifecycle-Tests ohne echte Mounts:

```sh
python3 meta-tuxbox/recipes-filesystems/davfs2/tests/test_mount_list.py
```

Vor Veröffentlichung Rezept-/Append-Auswahl, H7-systemd-Paket-QA und
Paketinhalt, alte SysVinit-Paketierung ohne Unit sowie ein
Standardimage-Manifest ohne davfs2 prüfen. Zusätzlich sind auf einem
Testempfänger WebDAV-Lesen/Schreiben/Unmount, falsche Zugangsdaten, nicht
vertrauenswürdige Zertifikate und fehlendes Netzwerk zu testen.
