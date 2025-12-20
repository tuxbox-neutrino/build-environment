# gitpkgv.bbclass provides the GITPKGV and GITPKGVTAG variables, which
# are to be used in PKGV, as described below:
#
# - GITPKGV is a sortable version with the format NN+GITHASH, for
#   use in PKGV, where
#
#   NN corresponds to the total number of revisions up to SRCREV
#   GITHASH is the (full) hash of SRCREV
#
# - GITPKGVTAG is the output of 'git describe', enabling
#   automatic versioning
#
# Important: Use ${GITPKGV} and ${GITPKGVTAG} exclusively with PKGV, not with PV!
#
# The gitpkgv.bbclass assumes a Git repository has been cloned and contains SRCREV.
# Therefore, it is crucial to use ${GITPKGV} and ${GITPKGVTAG} only in PKGV.
# These variables are compatible with SRCREV = ${AUTOREV} as well as with fixed Git hash values
# in the form of SRCREV = "<a specific fixed Git hash>".
# Using ${GITPKGV} and ${GITPKGVTAG} in conjunction with PV can lead to inconsistencies.
# PV is essential for internal build processes, whereas PKGV mainly affects the naming of
# the generated packages, which are stored in the deployment area.
# This is exactly the main objective of GITPKGV and GITPKGVTAG.
#
# WARNING: If the upstream repository always uses a consistent and
# sortable tag naming scheme, you can get a sortable version including the tag
# name with ${GITPKGVTAG}, but be aware that for example, a tag sequence "v1.0,
# v1.2, xtest, v2.0" will force you to increase PE to get an upgradeable
# path to the v2.0 revisions
# 
# If ${GITPKGVTAG} is applied to a Git repository without tags, it will not function as expected.
# In this case, there will be an automatic fallback to the PV entry defined for the recipe or to default
# values for PV. The build system will then issue warnings.
# To avoid such issues, ${GITPKGV} can be used as an alternative.
# If a recipe includes multiple Git repositories in SRC_URI,
# ideally, the first repository should contain tags.
# Note that warnings may still be issued.
# These can usually be ignored as long as the final result meets expectations.

#
# use example:
#
# inherit gitpkgv
#
# PKGV = "1.0+gitr${GITPKGV}"  # expands also to something like 1.0+gitr31337+4c1c21d7d
#
# or
#
# inherit gitpkgv
#
# PKGV = "${GITPKGVTAG}"  # expands to something like 1.0-31337+g4c1c21d
#                           if there is tag v1.0 before this revision or
#                           ver1.0-31337+g4c1c21d if there is tag ver1.0
#
# Additionally, this class introduces a mechanism to control warning messages
# when Git tags are missing in the repository. This is particularly useful
# in cases where the absence of tags is expected and should not trigger warnings.
#
# - GITPKGVTAG_NO_WARN_ON_NO_TAG: This variable controls the emission of warnings
#   when GITPKGVTAG is used but no Git tags are found in the repository.
#   By default, it is set to "0", which means warnings are enabled.
#   Set this variable to "1" to suppress these warnings.
#
#   Example usage in a recipe:
#   GITPKGVTAG_NO_WARN_ON_NO_TAG = "1"  # Suppresses warning for this recipe
#
#   It can also be set globally in local.conf or layer.conf, or for a specific recipe:
#   GITPKGVTAG_NO_WARN_ON_NO_TAG:pn-myrecipe = "1"  # Suppresses warning for 'myrecipe'
#
# NOTE Suppressing warnings should only be done when you are certain that the
# absence of Git tags will not negatively impact the build process or package versioning.

GITPKGVTAG_NO_WARN_ON_NO_TAG = "0"

GITPKGV = "${@get_git_pkgv(d, 0)}"
GITPKGVTAG = "${@get_git_pkgv(d, 1)}"

def gitpkgv_drop_tag_prefix(version):
    import re
    if re.match("v\d", version):
        return version[1:]
    else:
        return version

SRCPV_WORKSPACE ?= "999"

def get_git_pkgv(d, use_tags):
    import os
    import bb
    from pipes import quote

    ## Start workaround ########################################################
    import re
    # Check DISTRO_VERSION to see if Workaround is needed
    distro_version = d.getVar('DISTRO_VERSION', True)
    if re.match(r"^([0-4]|[1-4]\.\d+)", distro_version):
      bb.debug(1, f"Used DISTRO_VERSION {distro_version} using a SRCPV_WORKSPACE workaround. See gitpkgv.bbclass.")
    else:
      bb.warn(f"Used DISTRO_VERSION {distro_version} does not need a SRCPV_WORKSPACE workaround. SRCPV should be removed. See gitpkgv.bbclass.")

    # NOTE: This is only a Workaround. SRCPV will be removed in newer versions > 4.x:
    # https://git.yoctoproject.org/poky/commit/?id=62afa02d01794376efab75623f42e7e08af08526
    # https://git.yoctoproject.org/poky/commit/?id=65318019cd8c6db19ae5d4526a0fa2d8c8ef25fa
    workspace_tag = d.getVar('SRCPV_WORKSPACE', True)  # default value as fallback
    ver = d.getVar('SRCPV', True)
    if ver == '999' and ver != workspace_tag:  # Check if the dummy number is set an differ
      bb.debug(1, f"SRCPV is set to dummy value: {ver}, changing to workspace_tag: {workspace_tag}")
      ver = workspace_tag
    elif not ver:  # Additional check if ver is undefined or empty
      bb.warn(f"SRCPV is undefined or empty, setting to default workspace_tag: {workspace_tag} (See workaround within gitpkgv.bbclass)")
      ver = workspace_tag

    return ver  # Ensure the return statement is outside the condition blocks
    ## End workaround ##########################################################

    src_uri = d.getVar('SRC_URI').split()
    fetcher = bb.fetch2.Fetch(src_uri, d)
    ud = fetcher.ud

    #
    # If SRCREV_FORMAT is set respect it for tags
    #
    format = d.getVar('SRCREV_FORMAT')
    if not format:
        names = []
        for url in ud.values():
            if url.type == 'git' or url.type == 'gitsm':
                names.extend(url.revisions.keys())
        if len(names) > 0:
            format = '_'.join(names)
        else:
            format = 'default'

    found = False

    for url in ud.values():
        if url.type == 'git' or url.type == 'gitsm':
            for name, rev in url.revisions.items():
                if not os.path.exists(url.localpath):
                    return None

                commits = "0"
                found = True

                vars = { 'repodir' : quote(url.localpath),
                         'rev' : quote(rev) }

                rev = bb.fetch2.get_srcrev(d).split('+')[1]
                rev_file = os.path.join(url.localpath, "oe-gitpkgv_" + rev)

                if not os.path.exists(rev_file) or os.path.getsize(rev_file)==0:
                    commits = bb.fetch2.runfetchcmd(
                        "git -C %(repodir)s rev-list %(rev)s -- 2> /dev/null "
                        "| wc -l" % vars,
                        d, quiet=True).strip().lstrip('0')

                    if commits != "":
                        oe.path.remove(rev_file, recurse=False)
                        with open(rev_file, "w") as f:
                            f.write("%d\n" % int(commits))
                    else:
                        commits = "0"
                else:
                    with open(rev_file, "r") as f:
                        commits = f.readline(128).strip()

                if use_tags:
                    try:
                        ver = "0"
                        output = bb.fetch2.runfetchcmd("git -C %(repodir)s describe --tags 2>/dev/null" % vars, d, quiet=True).strip()
                        ver = gitpkgv_drop_tag_prefix(output)
                    except Exception as e:
                        warn_on_no_tag = d.getVar('GITPKGVTAG_NO_WARN_ON_NO_TAG', False)
                        if warn_on_no_tag == "0":
                          bb.warn("Missing Git tags, falling back to presets or defaults! GITPKGVTAG will be overridden")

                ver = str(ver) if ver is not None else "0"
                format = format.replace(name, ver)

    if found:
        return format

    return workspace_tag
