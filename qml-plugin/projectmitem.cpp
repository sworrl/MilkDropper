#include "projectmitem.h"
#include <QOpenGLFramebufferObjectFormat>
#include <QOpenGLContext>
#include <QOpenGLFunctions>
#include <QQuickWindow>
#include <QRandomGenerator>

#include <pulse/simple.h>
#include <pulse/error.h>
#include <cstdio>
#include <cstring>
#include <QFile>
#include <QFileInfo>
#include <QDateTime>
#include <QDir>
#include <QSettings>

// --- Audio Capture (background thread, PulseAudio/PipeWire) ---

AudioCapture::AudioCapture(QObject *parent) : QThread(parent) {}

AudioCapture::~AudioCapture() {
    stop();
    wait();
}

void AudioCapture::stop() {
    m_running = false;
}

void AudioCapture::run() {
    while (m_running) {
        m_restartRequested = false;

        pa_sample_spec spec{};
        spec.format = PA_SAMPLE_FLOAT32LE;
        spec.rate = 44100;
        spec.channels = 2;

        pa_buffer_attr attr{};
        attr.maxlength = (uint32_t) -1;
        attr.tlength = (uint32_t) -1;
        attr.prebuf = (uint32_t) -1;
        attr.minreq = (uint32_t) -1;
        attr.fragsize = 1024 * sizeof(float); // Low-latency fragment size (~11.6ms)

        // Resolve source: per-screen /tmp/projectm-audio-source-<screen>, explicit /tmp/projectm-audio-source, else default sink monitor
        char device_buf[256] = {};
        const int sIdx = m_screenIndex.load();
        QString perScreenSrc = QString("/tmp/projectm-audio-source-%1").arg(sIdx);
        QFile perScreenFile(perScreenSrc);
        if (perScreenFile.exists() && perScreenFile.open(QIODevice::ReadOnly)) {
            QByteArray src = perScreenFile.readAll().trimmed();
            if (!src.isEmpty())
                qstrncpy(device_buf, src.constData(), sizeof(device_buf));
            perScreenFile.close();
        }
        if (!device_buf[0]) {
            QFile srcFile("/tmp/projectm-audio-source");
            if (srcFile.exists() && srcFile.open(QIODevice::ReadOnly)) {
                QByteArray src = srcFile.readAll().trimmed();
                if (!src.isEmpty())
                    qstrncpy(device_buf, src.constData(), sizeof(device_buf));
                srcFile.close();
            }
        }
        if (!device_buf[0]) {
            if (FILE *fp = popen("pactl get-default-sink", "r")) {
                char sink[200] = {};
                if (fgets(sink, sizeof(sink), fp)) {
                    size_t len = strlen(sink);
                    while (len > 0 && (sink[len-1] == '\n' || sink[len-1] == '\r'))
                        sink[--len] = 0;
                    if (len > 0)
                        snprintf(device_buf, sizeof(device_buf), "%s.monitor", sink);
                }
                pclose(fp);
            }
        }
        const char *device = device_buf[0] ? device_buf : nullptr;
        qInfo("AudioCapture [Screen %d]: connecting to %s", sIdx, device ? device : "(default)");

        int error = 0;
        pa_simple *pa = pa_simple_new(
            nullptr, "projectM-wallpaper",
            PA_STREAM_RECORD, device,
            "Audio Visualizer", &spec,
            nullptr, &attr, &error
        );

        if (!pa) {
            qWarning("AudioCapture [Screen %d]: pa_simple_new failed (%s): %s",
                     sIdx, device ? device : "default", pa_strerror(error));
            QThread::msleep(1000);
            continue;
        }
        qInfo("AudioCapture [Screen %d]: stream open, capturing", sIdx);

        float samples[1024];

        while (m_running && !m_restartRequested) {
            if (pa_simple_read(pa, samples, sizeof(samples), &error) < 0) {
                qWarning("AudioCapture [Screen %d]: pa_simple_read failed: %s", sIdx, pa_strerror(error));
                break;
            }

            // Write into ring buffer (interleaved L,R,L,R,...)
            QMutexLocker lock(&mutex);
            for (int i = 0; i < 1024; i++) {
                ring[writePos] = samples[i];
                writePos = (writePos + 1) % kRingSize;
                // If we overrun the reader, advance reader (drop oldest)
                if (writePos == readPos) {
                    readPos = (readPos + 1) % kRingSize;
                }
            }
        }

        pa_simple_free(pa);
        if (m_restartRequested)
            qInfo("AudioCapture [Screen %d]: restart requested, reconnecting", sIdx);
    }
}

int AudioCapture::available() const {
    int diff = writePos - readPos;
    if (diff < 0) diff += kRingSize;
    return diff;
}

int AudioCapture::read(float *out, int maxFloats) {
    QMutexLocker lock(&mutex);
    int avail = available();
    // Flush any accumulated audio backlog to maintain real-time low latency (<30ms)
    if (avail > 2048) {
        int drop = avail - 1024;
        readPos = (readPos + drop) % kRingSize;
    }
    int n = 0;
    while (n < maxFloats && readPos != writePos) {
        out[n++] = ring[readPos];
        readPos = (readPos + 1) % kRingSize;
    }
    return n;
}

// --- Renderer (runs on render thread) ---

ProjectMRenderer::ProjectMRenderer() {
    memset(m_pcmBatch, 0, sizeof(m_pcmBatch));
}

ProjectMRenderer::~ProjectMRenderer() {
    teardown();
}

void ProjectMRenderer::teardown() {
    // Playlist must go first — it holds a callback registration on the instance.
    if (m_playlist) {
        projectm_playlist_destroy(m_playlist);
        m_playlist = nullptr;
    }
    if (m_projectM) {
        projectm_destroy(m_projectM);
        m_projectM = nullptr;
    }
}

QOpenGLFramebufferObject *ProjectMRenderer::createFramebufferObject(const QSize &size) {
    m_width = size.width();
    m_height = size.height();

    // projectM 4 can be resized in place; only a missing instance needs a full init.
    if (m_projectM)
        m_needsResize = true;

    QOpenGLFramebufferObjectFormat fmt;
    fmt.setAttachment(QOpenGLFramebufferObject::CombinedDepthStencil);
    fmt.setSamples(0);
    return new QOpenGLFramebufferObject(size, fmt);
}

// projectM's built-in GL resolver assumes GLX; Qt Quick on Wayland runs on EGL,
// so hand projectM the context's own resolver instead.
static void *qtGlGetProcAddress(const char *name, void *) {
    QOpenGLContext *ctx = QOpenGLContext::currentContext();
    return ctx ? reinterpret_cast<void *>(ctx->getProcAddress(name)) : nullptr;
}

void ProjectMRenderer::initProjectM() {
    if (QOpenGLContext *ctx = QOpenGLContext::currentContext()) {
        const QSurfaceFormat f = ctx->format();
        qInfo("ProjectMRenderer: GL context %d.%d %s (%s)",
              f.majorVersion(), f.minorVersion(),
              f.profile() == QSurfaceFormat::CoreProfile ? "core"
                : f.profile() == QSurfaceFormat::CompatibilityProfile ? "compat" : "none",
              ctx->isOpenGLES() ? "GLES" : "desktop GL");
    } else {
        qWarning("ProjectMRenderer: no current QOpenGLContext — scene graph is not "
                 "running on the OpenGL RHI backend; projectM cannot render here.");
        return;
    }

    m_projectM = projectm_create_with_opengl_load_proc(qtGlGetProcAddress, nullptr);
    if (!m_projectM) {
        qWarning("ProjectMRenderer: projectm_create() failed — OpenGL context insufficient?");
        return;
    }
    if (char *ver = projectm_get_version_string()) {
        qInfo("ProjectMRenderer: projectM %s instance created at %dx%d", ver, m_width, m_height);
        projectm_free_string(ver);
    }

    projectm_set_window_size(m_projectM, m_width, m_height);
    projectm_set_mesh_size(m_projectM, m_meshX, m_meshY);
    projectm_set_fps(m_projectM, 60);
    projectm_set_preset_duration(m_projectM, m_presetDuration);
    projectm_set_soft_cut_duration(m_projectM, 5.0);
    projectm_set_hard_cut_enabled(m_projectM, m_hardCutEnabled);
    projectm_set_hard_cut_duration(m_projectM, 30.0);
    projectm_set_hard_cut_sensitivity(m_projectM, 2.0f);
    projectm_set_beat_sensitivity(m_projectM, 2.5f);
    projectm_set_aspect_correction(m_projectM, true);
    projectm_set_easter_egg(m_projectM, 0.0f);

    if (!m_texturePath.isEmpty()) {
        const QByteArray tex = m_texturePath.toUtf8();
        const char *paths[] = { tex.constData() };
        projectm_set_texture_search_paths(m_projectM, paths, 1);
    }

    // The playlist library drives preset switching: creating it against the
    // instance registers the preset-switch-requested callback for us.
    m_playlist = projectm_playlist_create(m_projectM);
    if (!m_playlist) {
        qWarning("ProjectMRenderer: projectm_playlist_create() failed");
        return;
    }
    projectm_playlist_set_shuffle(m_playlist, m_shuffle);

    const QByteArray path = m_presetPath.toUtf8();
    const uint32_t added = projectm_playlist_add_path(m_playlist, path.constData(),
                                                      /*recurse_subdirs=*/true,
                                                      /*allow_duplicates=*/false);
    qInfo("ProjectMRenderer: loaded %u presets from %s", added, path.constData());

    if (added > 0)
        projectm_playlist_play_next(m_playlist, /*hard_cut=*/true);
}

void ProjectMRenderer::synchronize(QQuickFramebufferObject *item) {
    auto *pi = static_cast<ProjectMItem *>(item);

    if (pi->presetPath() != m_presetPath) {
        m_presetPath = pi->presetPath();
        m_needsInit = true;
    }
    if (pi->texturePath() != m_texturePath) {
        m_texturePath = pi->texturePath();
        m_needsInit = true;
    }
    if (pi->meshX() != m_meshX || pi->meshY() != m_meshY) {
        m_meshX = pi->meshX();
        m_meshY = pi->meshY();
        if (m_projectM)
            projectm_set_mesh_size(m_projectM, m_meshX, m_meshY);
    }
    if (pi->presetDuration() != m_presetDuration) {
        m_presetDuration = pi->presetDuration();
        if (m_projectM)
            projectm_set_preset_duration(m_projectM, m_presetDuration);
    }
    if (pi->shuffle() != m_shuffle) {
        m_shuffle = pi->shuffle();
        if (m_playlist)
            projectm_playlist_set_shuffle(m_playlist, m_shuffle);
    }
    if (pi->hardCutEnabled() != m_hardCutEnabled) {
        m_hardCutEnabled = pi->hardCutEnabled();
        if (m_projectM)
            projectm_set_hard_cut_enabled(m_projectM, m_hardCutEnabled);
    }

    // Drain audio ring buffer into batch (all available data)
    auto *audio = pi->audioCapture();
    m_audioFloats = 0;
    {
        QMutexLocker lock(&audio->mutex);
        m_audioFloats = audio->read(m_pcmBatch, sizeof(m_pcmBatch) / sizeof(float));
    }

    // Recreate the instance when the preset/texture source changed. Must happen
    // before commands are drained so they act on the new playlist.
    if (m_needsInit && m_width > 0 && m_height > 0 && !m_presetPath.isEmpty()) {
        teardown();
        initProjectM();
        m_needsInit = false;
        m_needsResize = false;
    } else if (m_needsResize && m_projectM) {
        projectm_set_window_size(m_projectM, m_width, m_height);
        m_needsResize = false;
    }

    // Process queued commands
    if (m_projectM && m_playlist) {
        QMutexLocker lock(&pi->cmdMutex);
        for (const auto &cmd : pi->pendingCmds) {
            switch (cmd.type) {
                case ProjectMItem::Command::Next:
                    projectm_playlist_play_next(m_playlist, true);
                    break;
                case ProjectMItem::Command::Prev:
                    projectm_playlist_play_previous(m_playlist, true);
                    break;
                case ProjectMItem::Command::Random: {
                    const uint32_t size = projectm_playlist_size(m_playlist);
                    if (size > 0)
                        projectm_playlist_set_position(
                            m_playlist, QRandomGenerator::global()->bounded(size), true);
                    break;
                }
                case ProjectMItem::Command::Lock:
                    projectm_set_preset_locked(m_projectM, cmd.boolVal);
                    break;
            }
        }
        pi->pendingCmds.clear();
    }
}

void ProjectMRenderer::render() {
    if (!m_projectM)
        return;

    m_frameCount++;

    if (m_audioFloats > 1) {
        // count is per-channel samples (frames), not floats — interleaved LRLR.
        const int frames = m_audioFloats / 2;
        const int maxFrames = static_cast<int>(projectm_pcm_get_max_samples());
        for (int off = 0; off < frames; off += maxFrames) {
            const int len = qMin(maxFrames, frames - off);
            projectm_pcm_add_float(m_projectM, m_pcmBatch + off * 2,
                                   len, PROJECTM_STEREO);
        }
        m_totalAudioFrames += frames;
    }
    m_audioFloats = 0;

    if (m_frameCount % 1800 == 0) {
        qInfo("ProjectMRenderer: frames=%d audioFrames/interval=%d playlist=%u",
              m_frameCount, m_totalAudioFrames,
              m_playlist ? projectm_playlist_size(m_playlist) : 0);
        m_totalAudioFrames = 0;
    }

    // Render into the FBO Qt Quick gave us. projectM binds its own FBOs
    // internally and would otherwise restore to the default framebuffer.
    QOpenGLFramebufferObject *fbo = framebufferObject();
    projectm_opengl_render_frame_fbo(m_projectM, fbo ? fbo->handle() : 0);
}

// --- Preset/texture discovery ---
//
// Nothing here may be hardcoded to one machine: the same build ships in a .deb.
// Order: explicit env override, then the shared config file (also read by the
// Python tray controller), then the usual install locations.

static QString firstExistingDir(const QStringList &candidates) {
    for (const QString &c : candidates) {
        if (!c.isEmpty() && QFileInfo(c).isDir())
            return c;
    }
    return QString();
}

static QString configuredPath(const char *key) {
    const QString conf = QDir::home().filePath(".config/milkdropper/milkdropper.conf");
    if (!QFileInfo::exists(conf))
        return QString();
    QSettings s(conf, QSettings::IniFormat);
    return s.value(QStringLiteral("Paths/%1").arg(QLatin1String(key))).toString();
}

static QString discoverDir(const char *envVar, const char *confKey,
                           const QStringList &extraCandidates) {
    QStringList candidates;
    candidates << QString::fromLocal8Bit(qgetenv(envVar))
               << configuredPath(confKey)
               << extraCandidates;
    return firstExistingDir(candidates);
}

static QString discoverPresetPath() {
    const QString home = QDir::homePath();
    return discoverDir("MILKDROPPER_PRESET_PATH", "Presets", {
        home + "/.local/share/milkdropper/presets",
        home + "/.local/share/Steam/steamapps/common/projectM/presets",
        home + "/.steam/steam/steamapps/common/projectM/presets",
        "/usr/share/milkdropper/presets",
        "/usr/share/projectM/presets",
        "/usr/local/share/projectM/presets",
    });
}

static QString discoverTexturePath() {
    const QString home = QDir::homePath();
    return discoverDir("MILKDROPPER_TEXTURE_PATH", "Textures", {
        home + "/.local/share/milkdropper/textures",
        home + "/.local/share/Steam/steamapps/common/projectM/textures",
        home + "/.steam/steam/steamapps/common/projectM/textures",
        "/usr/share/milkdropper/textures",
        "/usr/share/projectM/textures",
        "/usr/local/share/projectM/textures",
    });
}

// --- QML Item (runs on GUI thread) ---

ProjectMItem::ProjectMItem(QQuickItem *parent)
    : QQuickFramebufferObject(parent)
{
    // Defaults, so QML need not hardcode anything. An explicit QML assignment
    // still wins, since it runs after construction.
    m_presetPath = discoverPresetPath();
    m_texturePath = discoverTexturePath();
    if (m_presetPath.isEmpty())
        qWarning("ProjectMItem: no preset directory found — set Paths/Presets in "
                 "~/.config/milkdropper/milkdropper.conf or $MILKDROPPER_PRESET_PATH");
    else
        qInfo("ProjectMItem: presets=%s textures=%s",
              qPrintable(m_presetPath), qPrintable(m_texturePath));

    setMirrorVertically(true);
    setTextureFollowsItemSize(true);
    setFlag(ItemHasContents, true);

    // Seed the mtime cache with whatever is already in the command file, so a
    // stale command from before this instance existed is not replayed on load.
    {
        QFileInfo fi("/tmp/projectm-cmd");
        if (fi.exists())
            m_cmdFileMtime = fi.lastModified().toMSecsSinceEpoch();
    }

    connect(&m_cmdTimer, &QTimer::timeout, this, &ProjectMItem::pollCommandFile);
    m_cmdTimer.start(100);

    m_audio.start();
}

void ProjectMItem::itemChange(ItemChange change, const ItemChangeData &data) {
    QQuickFramebufferObject::itemChange(change, data);
    if (change == ItemSceneChange) {
        if (m_frameDriver)
            disconnect(m_frameDriver);
        if (data.window) {
            // Drive rendering at the display's vsync rate instead of a free-running
            // timer. afterAnimating fires on the GUI thread once per frame, just
            // before scene-graph sync, so update() is legal here (unlike
            // afterRendering, which runs on the render thread and is rejected).
            // Marking the item dirty schedules the next frame, so the loop
            // self-sustains and throttles itself to the compositor's pace.
            m_frameDriver = connect(data.window, &QQuickWindow::afterAnimating,
                                    this, &QQuickItem::update);
        }
    }
}

ProjectMItem::~ProjectMItem() {
    m_audio.stop();
    m_audio.wait();
}

QQuickFramebufferObject::Renderer *ProjectMItem::createRenderer() const {
    return new ProjectMRenderer();
}

void ProjectMItem::setScreenIndex(int idx) {
    if (m_screenIndex != idx) {
        m_screenIndex = idx;
        m_audio.setScreenIndex(idx);
        emit screenIndexChanged();
        update();
    }
}

void ProjectMItem::setPresetPath(const QString &path) {
    if (m_presetPath != path) {
        m_presetPath = path;
        emit presetPathChanged();
        update();
    }
}

void ProjectMItem::setTexturePath(const QString &path) {
    if (m_texturePath != path) {
        m_texturePath = path;
        emit texturePathChanged();
        update();
    }
}

void ProjectMItem::setFps(int fps) {
    if (m_fps != fps && fps > 0) {
        m_fps = fps;
        emit fpsChanged();
        // Rendering is vsync-driven via QQuickWindow::afterRendering;
        // fps property is kept for API compatibility but no longer clocks the render loop.
    }
}

void ProjectMItem::setMeshX(int v) {
    if (m_meshX != v) { m_meshX = v; emit meshXChanged(); update(); }
}

void ProjectMItem::setMeshY(int v) {
    if (m_meshY != v) { m_meshY = v; emit meshYChanged(); update(); }
}

void ProjectMItem::setPresetDuration(int v) {
    if (m_presetDuration != v) { m_presetDuration = v; emit presetDurationChanged(); update(); }
}

void ProjectMItem::setShuffle(bool v) {
    if (m_shuffle != v) { m_shuffle = v; emit shuffleChanged(); update(); }
}

void ProjectMItem::setHardCutEnabled(bool v) {
    if (m_hardCutEnabled != v) { m_hardCutEnabled = v; emit hardCutEnabledChanged(); update(); }
}

void ProjectMItem::queueCommand(const Command &cmd) {
    {
        QMutexLocker lock(&cmdMutex);
        pendingCmds.append(cmd);
    }
    update();
}

// projectM 4 dropped the key handler, so keys map onto playlist actions here.
void ProjectMItem::sendKey(bool pressed, int qtKey, int qtModifiers) {
    Q_UNUSED(qtModifiers)
    if (!pressed)
        return;

    switch (qtKey) {
        case Qt::Key_N: case Qt::Key_Right: case Qt::Key_Down:
            nextPreset();
            break;
        case Qt::Key_P: case Qt::Key_Left: case Qt::Key_Up:
            prevPreset();
            break;
        case Qt::Key_R: case Qt::Key_Space:
            randomPreset();
            break;
        case Qt::Key_L:
            m_presetLocked = !m_presetLocked;
            lockPreset(m_presetLocked);
            break;
        default:
            break;
    }
}

void ProjectMItem::nextPreset()  { queueCommand({Command::Next}); }
void ProjectMItem::prevPreset()  { queueCommand({Command::Prev}); }
void ProjectMItem::randomPreset() { queueCommand({Command::Random}); }

void ProjectMItem::lockPreset(bool locked) {
    m_presetLocked = locked;
    queueCommand({Command::Lock, locked});
}

void ProjectMItem::pollCommandFile() {
    static const char *PATH = "/tmp/projectm-cmd";
    QFileInfo fi(PATH);
    if (!fi.exists()) return;
    qint64 mtime = fi.lastModified().toMSecsSinceEpoch();
    if (mtime == m_cmdFileMtime) return;
    m_cmdFileMtime = mtime;

    QFile f(PATH);
    if (!f.open(QIODevice::ReadOnly)) return;
    QByteArray rawData = f.readAll().trimmed();
    f.close();

    if (rawData.isEmpty()) return;

    QString cmdStr = QString::fromUtf8(rawData);
    int targetScreen = -1; // -1 means all screens
    QString action = cmdStr;

    if (cmdStr.contains(':')) {
        QStringList parts = cmdStr.split(':');
        bool ok = false;
        int sIdx = parts[0].toInt(&ok);
        if (ok) {
            targetScreen = sIdx;
            action = parts.mid(1).join(':');
        } else if (parts[0] == "all") {
            targetScreen = -1;
            action = parts.mid(1).join(':');
        }
    }

    if (targetScreen != -1 && targetScreen != m_screenIndex) {
        return; // Command is targeted at a different screen
    }

    qInfo("ProjectMItem [Screen %d]: command '%s'", m_screenIndex, qPrintable(action));

    if (action == "next")        nextPreset();
    else if (action == "prev")   prevPreset();
    else if (action == "random") randomPreset();
    else if (action == "lock")   lockPreset(true);
    else if (action == "unlock") lockPreset(false);
    else if (action == "reload-audio") m_audio.requestRestart();
}
