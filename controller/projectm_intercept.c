/*
 * LD_PRELOAD shim for projectMSDL:
 *  - Right-click → cycle display mode (desktop/borderless/window)
 *  - Middle-click → quit projectM
 *  - Prevents SDL from hiding the cursor
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <signal.h>

/* SDL2 event types and structs (avoids requiring SDL2-devel) */
#define SDL_QUIT            0x100
#define SDL_MOUSEBUTTONDOWN 0x401
#define SDL_MOUSEBUTTONUP   0x402
#define SDL_BUTTON_MIDDLE   2
#define SDL_BUTTON_RIGHT    3

typedef union {
    uint32_t type;
    struct {
        uint32_t type;
        uint32_t timestamp;
        uint32_t windowID;
        uint32_t which;
        uint8_t  button;
        uint8_t  state;
        uint8_t  clicks;
        uint8_t  padding1;
        int32_t  x;
        int32_t  y;
    } button;
    uint8_t padding[128];
} SDL_Event;

static int  (*real_SDL_PollEvent)(SDL_Event *) = NULL;
static int  (*real_SDL_WaitEvent)(SDL_Event *) = NULL;
static int  (*real_SDL_ShowCursor)(int) = NULL;
static int  (*real_SDL_SetRelativeMouseMode)(int) = NULL;

static void init_real_funcs(void) {
    if (!real_SDL_PollEvent) {
        real_SDL_PollEvent = dlsym(RTLD_NEXT, "SDL_PollEvent");
        real_SDL_WaitEvent = dlsym(RTLD_NEXT, "SDL_WaitEvent");
        real_SDL_ShowCursor = dlsym(RTLD_NEXT, "SDL_ShowCursor");
        real_SDL_SetRelativeMouseMode = dlsym(RTLD_NEXT, "SDL_SetRelativeMouseMode");
    }
}

static void run_cycle(void) {
    if (fork() == 0) {
        system("exec $HOME/.local/share/projectM-wallpaper/cycle-mode.sh");
        _exit(0);
    }
}

static void run_quit(void) {
    /* Send ourselves SIGTERM for a clean shutdown */
    kill(getpid(), SIGTERM);
}

int SDL_PollEvent(SDL_Event *event) {
    init_real_funcs();
    int ret = real_SDL_PollEvent(event);
    if (ret && event) {
        if (event->type == SDL_MOUSEBUTTONDOWN) {
            if (event->button.button == SDL_BUTTON_RIGHT) {
                run_cycle();
                event->type = 0; /* eat it */
            } else if (event->button.button == SDL_BUTTON_MIDDLE) {
                run_quit();
                event->type = 0;
            }
        }
        if (event->type == SDL_MOUSEBUTTONUP) {
            if (event->button.button == SDL_BUTTON_RIGHT ||
                event->button.button == SDL_BUTTON_MIDDLE) {
                event->type = 0;
            }
        }
    }
    return ret;
}

/* Prevent cursor hiding */
int SDL_ShowCursor(int toggle) {
    init_real_funcs();
    if (real_SDL_ShowCursor)
        return real_SDL_ShowCursor(1);
    return 1;
}

int SDL_SetRelativeMouseMode(int enabled) {
    (void)enabled;
    return 0;
}
