cmake_minimum_required(VERSION 3.20)
project(projectm-wallpaper-plugin VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(GNUInstallDirs)

find_package(Qt6 6.5 REQUIRED COMPONENTS Quick OpenGL Qml)
qt_standard_project_setup(REQUIRES 6.5)

find_package(PkgConfig REQUIRED)

# Qt Quick on Wayland hands out GLES contexts, so the plugin needs a libprojectM
# built with ENABLE_GLES. That build lives in a private prefix to avoid clashing
# with a system desktop-GL libprojectM of the same SONAME; an RPATH pins it.
set(PROJECTM_PRIVATE_PREFIX "" CACHE PATH
    "Prefix of a private (GLES) libprojectM build to link against, e.g. /usr/lib/milkdropper")
if(PROJECTM_PRIVATE_PREFIX)
    set(ENV{PKG_CONFIG_PATH} "${PROJECTM_PRIVATE_PREFIX}/lib/pkgconfig:$ENV{PKG_CONFIG_PATH}")
    message(STATUS "Using private libprojectM prefix: ${PROJECTM_PRIVATE_PREFIX}")
endif()

pkg_check_modules(PROJECTM REQUIRED IMPORTED_TARGET projectM-4)
pkg_check_modules(PROJECTM_PLAYLIST REQUIRED IMPORTED_TARGET projectM-4-playlist)
pkg_check_modules(PULSE REQUIRED IMPORTED_TARGET libpulse-simple)

# plasmashell only scans Qt's own QML import paths, so the module has to land
# there even when the rest of the project installs under a different prefix.
# Packaging overrides this with -DQML_INSTALL_DIR=... (plus DESTDIR).
if(NOT QML_INSTALL_DIR)
    if(DEFINED QT6_INSTALL_PREFIX AND DEFINED QT6_INSTALL_QML)
        set(QML_INSTALL_DIR "${QT6_INSTALL_PREFIX}/${QT6_INSTALL_QML}")
    else()
        set(QML_INSTALL_DIR "${CMAKE_INSTALL_FULL_LIBDIR}/qt6/qml")
    endif()
endif()
message(STATUS "QML module install dir: ${QML_INSTALL_DIR}")

set(QML_URI org.projectm.renderer)
set(QML_MODULE_SUBDIR org/projectm/renderer)
set(QML_MODULE_BUILD_DIR "${CMAKE_CURRENT_BINARY_DIR}/${QML_MODULE_SUBDIR}")

qt_add_library(projectmrenderer SHARED)

# PLUGIN_TARGET == the library itself, so the module is a single .so next to a
# generated qmldir — matching the layout Plasma expects for an imported module.
qt_add_qml_module(projectmrenderer
    URI ${QML_URI}
    VERSION 1.0
    PLUGIN_TARGET projectmrenderer
    OUTPUT_DIRECTORY "${QML_MODULE_BUILD_DIR}"
    SOURCES
        projectmitem.cpp
        projectmitem.h
)

target_link_libraries(projectmrenderer PRIVATE
    Qt6::Quick
    Qt6::OpenGL
    PkgConfig::PROJECTM
    PkgConfig::PROJECTM_PLAYLIST
    PkgConfig::PULSE
)

if(PROJECTM_PRIVATE_PREFIX)
    set_target_properties(projectmrenderer PROPERTIES
        BUILD_RPATH "${PROJECTM_PRIVATE_PREFIX}/lib"
        INSTALL_RPATH "${PROJECTM_PRIVATE_PREFIX}/lib")
endif()

install(TARGETS projectmrenderer
    LIBRARY DESTINATION "${QML_INSTALL_DIR}/${QML_MODULE_SUBDIR}"
    RUNTIME DESTINATION "${QML_INSTALL_DIR}/${QML_MODULE_SUBDIR}"
)
install(FILES
        "${QML_MODULE_BUILD_DIR}/qmldir"
        "${QML_MODULE_BUILD_DIR}/projectmrenderer.qmltypes"
    DESTINATION "${QML_INSTALL_DIR}/${QML_MODULE_SUBDIR}"
)
