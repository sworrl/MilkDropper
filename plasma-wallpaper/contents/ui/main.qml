import QtQuick
import org.kde.plasma.plasmoid
import org.projectm.renderer 1.0

WallpaperItem {
    id: root

    Rectangle {
        anchors.fill: parent
        color: "black"
        z: -1
    }

    ProjectMItem {
        id: visualizer
        anchors.fill: parent
        // presetPath/texturePath are deliberately not set here: the plugin
        // discovers them (env override, ~/.config/milkdropper/milkdropper.conf,
        // then the usual install locations). Hardcoding a path here would break
        // every machine but the one it was written on.
        fps: 60
        meshX: 64
        meshY: 36
        presetDuration: 30
        shuffle: true
        focus: true

        Keys.onPressed: function(event) {
            visualizer.sendKey(true, event.key, event.modifiers);
            event.accepted = true;
        }
        Keys.onReleased: function(event) {
            visualizer.sendKey(false, event.key, event.modifiers);
            event.accepted = true;
        }
    }

    // Click to focus for keyboard input
    MouseArea {
        anchors.fill: parent
        onClicked: visualizer.forceActiveFocus()
        propagateComposedEvents: true
    }
}
