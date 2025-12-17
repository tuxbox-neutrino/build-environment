# Tuxbox Version Information Class
#
# Generates /etc/image-version file with build metadata

# Image version generation
TUXBOX_IMAGEBUILD ??= "${DATETIME}"
TUXBOX_IMAGEBUILD[vardepsexclude] = "DATETIME"

ROOTFS_POSTPROCESS_COMMAND += "tuxbox_generate_version_info; "

python tuxbox_generate_version_info() {
    import time

    deploy_dir = d.getVar('DEPLOY_DIR_IMAGE')
    imagename = d.getVar('IMAGE_NAME')
    machine = d.getVar('MACHINE')
    distro = d.getVar('DISTRO')
    distro_name = d.getVar('DISTRO_NAME')
    distro_version = d.getVar('DISTRO_VERSION')
    distro_codename = d.getVar('DISTRO_CODENAME')
    build_date = d.getVar('TUXBOX_IMAGEBUILD')
    image_version = d.getVar('IMAGE_VERSION')

    rootfs = d.getVar('IMAGE_ROOTFS')
    version_file = os.path.join(rootfs, 'etc', 'image-version')

    os.makedirs(os.path.dirname(version_file), exist_ok=True)

    with open(version_file, 'w') as f:
        f.write(f"distro={distro}\n")
        f.write(f"distro_name={distro_name}\n")
        f.write(f"distro_version={distro_version}\n")
        f.write(f"distro_codename={distro_codename}\n")
        f.write(f"machine={machine}\n")
        f.write(f"image_name={imagename}\n")
        f.write(f"image_version={image_version}\n")
        f.write(f"build_date={build_date}\n")
        f.write(f"creator=Tuxbox-OS Builder\n")

        # Git information if available
        try:
            import subprocess
            git_hash = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'],
                                               stderr=subprocess.DEVNULL).decode().strip()
            f.write(f"git_hash={git_hash}\n")
        except:
            pass

    # Make it readable
    os.chmod(version_file, 0o644)

    bb.note(f"Generated {version_file}")
}
