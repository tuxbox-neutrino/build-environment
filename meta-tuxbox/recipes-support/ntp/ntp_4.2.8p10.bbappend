# Define required user/group creation parameters for ntp daemon
USERADD_PACKAGES = "ntp ntpdate"
USERADD_PARAM:ntp = "--system --home /var/lib/ntp --no-create-home --shell /bin/false ntp"
GROUPADD_PARAM:ntp = "--system ntp"
USERADD_PARAM:ntpdate = "--system --home /var/lib/ntp --no-create-home --shell /bin/false ntp"
GROUPADD_PARAM:ntpdate = "--system ntp"
