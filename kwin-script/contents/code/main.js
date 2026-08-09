function setupProjectMWindow(window) {
    if (window.resourceClass === "projectmsdl" || window.resourceName === "projectmsdl") {
        // windowType is read-only in KWin's scripting API, so the window cannot
        // be turned into a true Desktop window from here; keepBelow + the skip
        // flags is the closest scriptable approximation.
        window.keepBelow = true;
        window.skipTaskbar = true;
        window.skipPager = true;
        window.skipSwitcher = true;
        window.noBorder = true;
        window.onAllDesktops = true;
    }
}

// Handle existing windows
var clients = workspace.windowList();
for (var i = 0; i < clients.length; i++) {
    setupProjectMWindow(clients[i]);
}

// Handle new windows
workspace.windowAdded.connect(setupProjectMWindow);
