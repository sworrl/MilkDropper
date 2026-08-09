# libprojectm4-gles Debian packaging

Copy this `debian/` directory into a clean checkout of
[projectM](https://github.com/projectM-visualizer/projectm) (master, with the
`vendor/projectm-eval` submodule), then:

    dpkg-buildpackage -us -uc -b

Produces `libprojectm4-gles` and `libprojectm4-gles-dev`: an OpenGL ES build of
libprojectM 4 in the private prefix `/usr/lib/milkdropper`, which the
`milkdropper` package depends on. The `milkdropper-standalone` package bundles
the same library and needs none of this.
