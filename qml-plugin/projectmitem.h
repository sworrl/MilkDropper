#pragma once

#include <QQuickFramebufferObject>
#include <QOpenGLFramebufferObject>
#include <QTimer>
#include <QThread>
#include <QMutex>
#include <QQmlEngine>
#include <atomic>

#include <projectM-4/projectM.h>
#include <projectM-4/playlist.h>

class AudioCapture : public QThread {
    Q_OBJECT
public:
    AudioCapture(QObject *parent = nullptr);
    ~AudioCapture();
    void stop();
    void requestRestart() { m_restartRequested = true; }
    void setScreenIndex(int idx) { m_screenIndex = idx; }

    // Ring buffer of interleaved stereo PCM (L,R,L,R,...)
    QMutex mutex;
    static constexpr int kRingSize = 16384; // ~92ms of stereo @ 44.1k
    float ring[kRingSize] = {};
    int writePos = 0;
    int readPos = 0;

    // Returns floats available (writePos - readPos, wrapped)
    int available() const;
    // Read up to `maxFloats` into `out`, returns actual floats read
    int read(float *out, int maxFloats);

protected:
    void run() override;

private:
    std::atomic<bool> m_running{true};
    std::atomic<bool> m_restartRequested{false};
    std::atomic<int> m_screenIndex{0};
};


class ProjectMRenderer : public QQuickFramebufferObject::Renderer {
public:
    ProjectMRenderer();
    ~ProjectMRenderer();

    void render() override;
    QOpenGLFramebufferObject *createFramebufferObject(const QSize &size) override;
    void synchronize(QQuickFramebufferObject *item) override;

private:
    void initProjectM();
    void teardown();

    projectm_handle m_projectM = nullptr;
    projectm_playlist_handle m_playlist = nullptr;

    QString m_presetPath;
    QString m_texturePath;
    int m_meshX = 64;
    int m_meshY = 36;
    int m_presetDuration = 30;
    bool m_shuffle = true;
    bool m_hardCutEnabled = false;
    bool m_needsInit = true;
    bool m_needsResize = false;
    int m_width = 0;
    int m_height = 0;

    float m_pcmBatch[4096]; // batch read from ring buffer
    int m_audioFloats = 0;

    // Per-instance, not static: one renderer exists per screen.
    int m_frameCount = 0;
    int m_totalAudioFrames = 0;
};


class ProjectMItem : public QQuickFramebufferObject {
    Q_OBJECT
    QML_ELEMENT

    Q_PROPERTY(int screenIndex READ screenIndex WRITE setScreenIndex NOTIFY screenIndexChanged)

public:
    explicit ProjectMItem(QQuickItem *parent = nullptr);
    ~ProjectMItem();

    Q_INVOKABLE void sendKey(bool pressed, int qtKey, int qtModifiers);
    Q_INVOKABLE void nextPreset();
    Q_INVOKABLE void prevPreset();
    Q_INVOKABLE void randomPreset();
    Q_INVOKABLE void lockPreset(bool locked);

    // Poll a command file (~10Hz) to receive external commands
    void pollCommandFile();

    Renderer *createRenderer() const override;

protected:
    void itemChange(ItemChange change, const ItemChangeData &value) override;

public:
    int screenIndex() const { return m_screenIndex; }
    void setScreenIndex(int idx);

    QString presetPath() const { return m_presetPath; }
    void setPresetPath(const QString &path);

    QString texturePath() const { return m_texturePath; }
    void setTexturePath(const QString &path);

    int fps() const { return m_fps; }
    void setFps(int fps);

    int meshX() const { return m_meshX; }
    void setMeshX(int v);

    int meshY() const { return m_meshY; }
    void setMeshY(int v);

    int presetDuration() const { return m_presetDuration; }
    void setPresetDuration(int v);

    bool shuffle() const { return m_shuffle; }
    void setShuffle(bool v);

    bool hardCutEnabled() const { return m_hardCutEnabled; }
    void setHardCutEnabled(bool v);

    // Audio capture thread feeds data here for renderer sync
    AudioCapture *audioCapture() { return &m_audio; }

    // Command queue drained by the renderer on the render thread.
    // projectM 4 has no key handler, so keys are mapped to playlist actions here.
    struct Command {
        enum Type { Next, Prev, Random, Lock } type;
        bool boolVal = false;
    };
    QMutex cmdMutex;
    QList<Command> pendingCmds;

signals:
    void screenIndexChanged();
    void presetPathChanged();
    void texturePathChanged();
    void fpsChanged();
    void meshXChanged();
    void meshYChanged();
    void presetDurationChanged();
    void shuffleChanged();
    void hardCutEnabledChanged();

private:
    void queueCommand(const Command &cmd);

    int m_screenIndex = 0;
    QString m_presetPath;
    QString m_texturePath;
    int m_fps = 60;
    int m_meshX = 64;
    int m_meshY = 36;
    int m_presetDuration = 30;
    bool m_shuffle = true;
    bool m_hardCutEnabled = false;
    bool m_presetLocked = false;
    QTimer m_cmdTimer;
    AudioCapture m_audio;
    qint64 m_cmdFileMtime = 0;
    QMetaObject::Connection m_frameDriver;
};
