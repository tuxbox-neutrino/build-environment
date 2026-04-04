# Glossary

Deutsch: [de/GLOSSARY.md](de/GLOSSARY.md)

This glossary explains the most important terms used in this repository.
Definitions are short on purpose and focused on practical usage here.

## Yocto Project

A build framework for creating custom Linux systems.
In this project, Yocto is the base build ecosystem.

## OpenEmbedded (OE)

The build metadata ecosystem used by Yocto.
You can think of OE as the layer/recipe world that defines what gets built.

## BitBake

The task engine that executes recipes and builds artifacts.
When you run image builds, BitBake runs under the hood.

## Layer

A collection of OE metadata (recipes, configs, classes).
Examples in this workspace: `meta-tuxbox`, `meta-neutrino`.

## Recipe (`.bb`)

A build instruction file for one package/component.
It defines source, dependencies, compile/install steps, and package outputs.

## Append (`.bbappend`)

An extension file that modifies a recipe from another layer.
Use this when you want to adjust upstream behavior without forking the recipe.

## Submodule

A Git repository nested inside this repository.
The builder uses submodules for layers to keep versions controlled.

## Pinning

Using exact recorded Git commits for submodules.
In this project, pinned sync is the safe/reproducible default.

## Unpinned Sync

Updating submodules to upstream branch HEAD instead of recorded commits.
Useful for maintainers, risky for normal builds.

## `make update`

Safe default update command.
It fast-forwards the top-level repo, syncs submodule URLs, and then checks out
the pinned submodule commits explicitly.

## `make sync`

Same safe pinned behavior as `make update`.
Use this when you want extra options like `SYNC_EXCLUDE=...`.

## `make update-upstream`

Maintainer command for unpinned submodule updates.
It can leave your tree dirty and move away from reproducible pins.

## MACHINE

Target device identifier used by Yocto/OE metadata.
Example: `hd51`.

## MACHINEBUILD

Vendor/brand-specific machine variant used in this project.
On many devices it equals `MACHINE`, on some it differs.

## DISTRO

The distribution profile selecting policy and package sets.
Default in this repo is typically `tuxbox`.

## sstate Cache

Shared build cache for compiled task outputs.
It speeds up rebuilds dramatically when reused.

## Downloads Cache (`DL_DIR`)

Local cache of downloaded source archives.
Keeps builds faster and more reproducible across repeated runs.

## Feeds

Package feed outputs for runtime package installation/update workflows.
Built via `make feeds ...`.

## SDK

Software Development Kit for building external apps against the target system.
Built via `make sdk ...`.

## QEMU

Virtual machine emulator for quick image smoke tests without hardware.
See [QEMU.md](QEMU.md) for details.

## Init System (`systemd` / `sysvinit`)

Service startup framework inside the target image.
Recipes must install service files that match the active init system.
