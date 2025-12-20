
# Documentation for `metaversion.bbclass`
#
# Overview
#
# The `metaversion.bbclass` file within the project provides a function
# `get_meta_version` to retrieve the current Git version (number of commits) of a
# specified repository. This function is used to dynamically set the `META_VERSION`
# variable during the build process.
#
# Function: `get_meta_version`
#
# Description
#
# `get_meta_version` is a Python function that calculates the number of commits in the
# current branch of the specified Git repository. It utilizes the Yocto Project's BitBake
# environment variables `COREBASE` and `META_NAME` to locate the repository.
#
# Syntax
#
# def get_meta_version():
#     # ... function implementation ...
#
# Parameters
#
# - None
#
# Returns
#
# - String: A string representing the number of commits in the current Git branch of the
#   specified repository.
# - If an error occurs or if the necessary variables are not set, it returns an empty string.
#
# Usage
#
# To use `get_meta_version`, ensure that `metaversion.bbclass` is inherited in your recipe
# (`.bb` file or local.conf). The function sets `META_VERSION` in the BitBake data store (`d`).
#
# Example
#
# In a BitBake recipe file:
#
# inherit metaversion
#
# The `META_VERSION` variable is automatically set by the function within the class.
#
# Error Handling
#
# - If `COREBASE` or `META_NAME` are not set, a warning is logged, and an empty string is returned.
# - If the Git command fails (e.g., due to an invalid path or repository), an error is logged with
#   the output from Git.
# - If Git is not installed or not found in the PATH, an error is logged.
#
# Dependencies
#
# - Git must be installed and accessible in the build environment's PATH.
#
# Example in local.conf
#
# inherit metaversion
# IMAGE_VERSION_SUFFIX=".${META_VERSION}"

python () {
    import subprocess
    import os

    def get_meta_version():
        corebase = d.getVar('COREBASE', True)
        meta_name = d.getVar('META_NAME', True)

        if not corebase or not meta_name:
            bb.warn("COREBASE or META_NAME is not set. Cannot determine git version.")
            return ''

        git_path = os.path.join(corebase, meta_name)
        try:
            # Change into meta layer dir and execute git
            git_command = ['git', '-C', git_path, 'rev-list', '--count', 'HEAD']
            version = subprocess.check_output(git_command, stderr=subprocess.STDOUT).strip()
            return version.decode()
        except subprocess.CalledProcessError as e:
            bb.error(f"Git command failed: {e.output.decode()}")
            return ''
        except FileNotFoundError:
            bb.error("Git is not found. Ensure git is installed and available in PATH.")
            return ''

    # Set variable META_VERSION
    d.setVar('META_VERSION', get_meta_version())
}
