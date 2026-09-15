# Optional WebDAV mounts with davfs2

Deutsch: [de/DAVFS2.md](de/DAVFS2.md)

The builder provides davfs2 1.7.3 as an optional package. It is not installed in
the standard image. Current Tuxbox receiver images use systemd; installing the
package adds and enables `davfs2.service`. A Tuxbox append extends the
OE-Alliance recipe. The append is deliberately tied to its `1.5.4` filename,
while the built package is 1.7.3. An OE-Alliance recipe rename requires
reviewing and renaming the append.

## Build and install

On the build host, build the package for your receiver (H7 example):

```sh
make bb MACHINE=h7 TARGET=davfs2 BB_TASK=package_write_ipk
```

The package appears below `builds/h7/tmp/deploy/ipk/`. Publish it through your
configured package feed following the [local feed guide](../README.md#local-ipk-feed).
On the receiver, after that feed contains this version:

```sh
opkg update
opkg install davfs2
```

The receiver kernel must provide FUSE, either built in or through
`kernel-module-fuse`. Coda is not supported by this davfs2 version.

## Configure a share

Edit `/etc/davfs2/davfs2.mount.list` as root. Each entry has exactly two fields:

```text
https://cloud.example.com/remote.php/dav/files/alice /mnt/dav/cloud
```

Replace the example with your server URL and mountpoint. The mountpoint must be
an absolute path other than `/`. Blank lines and comments, including indented
comments, are allowed. Whitespace within either field, extra fields and URLs
containing credentials are rejected. URL characters such as spaces must be
URL-encoded; mountpoint names containing spaces are unsupported.

Store credentials in `/etc/davfs2/secrets`, using the davfs2 secrets format:

```text
/mnt/dav/cloud alice "your-password"
```

Keep that file owned by root and mode `0600`. Follow the installed davfs2
manual for escaping quotes or backslashes in passwords. Do not put credentials
in the mount list. Automatic mounting reads no interactive answers and does
not print server URLs or the mount helper's output into its diagnostics.

Use normal trusted HTTPS certificates. For a private CA or a pinned server
certificate, obtain the certificate through a trusted channel, place it in
`/etc/davfs2/certs/`, and configure `trust_ca_cert` or `trust_server_cert` in
`davfs2.conf`. Restrict a server certificate to its mountpoint section, e.g.:

```text
[/mnt/dav/cloud]
trust_server_cert cloud.pem
```

Never establish trust solely by downloading an unverified certificate from the
same connection that failed verification.

## Start, verify and recover

Tuxbox receiver images use systemd. The package supplies and enables
`davfs2.service`; its empty default list mounts nothing. The service waits for
`network-online.target`. The image's network manager must provide a suitable
wait-online service for that target to reflect actual connectivity.

After configuration, run:

```sh
systemctl restart davfs2.service
systemctl status davfs2.service
findmnt --mountpoint /mnt/dav/cloud
```

The mount must show the expected WebDAV source and `fuse` (or `fuse.davfs`). Test reading
and writing with disposable files in a dedicated test share before relying on
it. The inherited Tuxbox defaults enable compression, disable WebDAV locks and
use `backup` as the backup directory; review the lock setting before using
concurrent writers.

On failure, consult `journalctl -u davfs2.service`. Diagnostics identify the
configuration line, without exposing credentials. Correct network access,
credentials or certificate trust, then run `systemctl restart davfs2.service`.
There is no automatic retry. A failed start cleans up successfully mounted
entries through the stop-post command. Unmount failures are reported too.

`systemctl stop davfs2.service` unmounts only matching WebDAV mounts named in
the current list. Stop the service **before removing or changing entries**;
otherwise an old mount is no longer listed for cleanup. Foreign mounts are
left untouched and cause an error rather than being unmounted.

The append remains safe to parse for legacy uClibc/SysVinit configurations,
where it deliberately supplies no automatic service. This compatibility path
is not the init system used by current receiver images.

## Migrate from ignore_cert

The old third field `ignore_cert` is rejected. Existing configuration files are
preserved as package configuration files; they are not silently rewritten.
Configure certificate trust as described above, remove `ignore_cert` from the
entry, then restart the service. Entries still containing it are not mounted.
Inspect any package-manager-generated replacement configuration before merging
it with your local settings.

## Maintainer checks

Run the isolated lifecycle tests (no real mounts):

```sh
python3 meta-tuxbox/recipes-filesystems/davfs2/tests/test_mount_list.py
```

Before publication, verify BitBake recipe/append selection, H7 systemd package
QA and contents, legacy SysVinit packaging without a unit, and a standard image
manifest without davfs2. A test receiver must additionally pass WebDAV
read/write/unmount, invalid credentials, untrusted certificate and unavailable
network tests.
