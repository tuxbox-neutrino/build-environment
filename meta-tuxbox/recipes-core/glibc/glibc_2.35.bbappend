# Drop OE-Alliance patch that no longer applies cleanly on Kirkstone glibc
SRC_URI:remove = "file://0004-sunrpc-use-snprintf-instead-of-an-implied-length-gua.patch"
SRC_URI:remove = "file://stdlib-canonicalize-realpath_stk-dest-maybe-uninit.patch"
