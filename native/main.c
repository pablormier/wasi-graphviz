/* native/main.c — Plain C wrapper for Graphviz, targeting wasm32-wasi.
 *
 * Exposes a minimal C ABI:
 *   char* graphviz_render(const char* dot, const char* format,
 *                         const char* engine, size_t* out_len);
 *   const char* graphviz_last_error(void);
 *   const char* graphviz_version(void);
 *   void graphviz_free(char* ptr);
 *
 * No Emscripten APIs.  Standard Graphviz C library calls only.
 */

#include <stdlib.h>
#include <string.h>

#include "gvc.h"
#include "gvplugin.h"
#include "graphviz_version.h"

/* ------------------------------------------------------------------ */
/* Plugin preloading — only the engines and renderers we need.        */
/* ------------------------------------------------------------------ */

extern gvplugin_library_t gvplugin_dot_layout_LTX_library;
extern gvplugin_library_t gvplugin_neato_layout_LTX_library;
extern gvplugin_library_t gvplugin_core_LTX_library;

lt_symlist_t lt_preloaded_symbols[] = {
    {"gvplugin_dot_layout_LTX_library",   &gvplugin_dot_layout_LTX_library},
    {"gvplugin_neato_layout_LTX_library", &gvplugin_neato_layout_LTX_library},
    {"gvplugin_core_LTX_library",         &gvplugin_core_LTX_library},
    {0, 0}
};

/* ------------------------------------------------------------------ */
/* Error handling                                                      */
/* ------------------------------------------------------------------ */

static char last_error[4096];

static int viz_errorf(char *buf)
{
    if (buf) {
        strncpy(last_error, buf, sizeof(last_error) - 1);
        last_error[sizeof(last_error) - 1] = '\0';
    } else {
        last_error[0] = '\0';
    }
    return 0;
}

/* ------------------------------------------------------------------ */
/* Exported ABI                                                        */
/* ------------------------------------------------------------------ */

const char* graphviz_version(void)
{
    return PACKAGE_VERSION;
}

const char* graphviz_last_error(void)
{
    return last_error;
}

void graphviz_free(char* ptr)
{
    if (ptr) gvFreeRenderData(ptr);
}

static GVC_t* g_gvc = NULL;

static GVC_t* get_context(void)
{
    if (!g_gvc) {
        g_gvc = gvContextPlugins(lt_preloaded_symbols, 1);
        if (g_gvc) {
            agseterr(AGERR);
            agseterrf(viz_errorf);
        }
    }
    return g_gvc;
}

char* graphviz_render(const char* dot, const char* format, const char* engine,
                      size_t* out_len)
{
    char* render_data = NULL;
    size_t render_len = 0;

    if (out_len) *out_len = 0;
    last_error[0] = '\0';

    GVC_t* gvc = get_context();
    if (!gvc) {
        strncpy(last_error, "Failed to create Graphviz context", sizeof(last_error) - 1);
        return NULL;
    }

    Agraph_t* graph = agmemread(dot);
    if (!graph) {
        strncpy(last_error, "Failed to parse DOT source", sizeof(last_error) - 1);
        return NULL;
    }

    if (gvLayout(gvc, graph, engine) != 0) {
        strncpy(last_error, "Layout failed", sizeof(last_error) - 1);
        agclose(graph);
        return NULL;
    }

    if (gvRenderData(gvc, graph, format, &render_data, &render_len) != 0) {
        strncpy(last_error, "Render failed", sizeof(last_error) - 1);
        gvFreeLayout(gvc, graph);
        agclose(graph);
        return NULL;
    }

    gvFreeLayout(gvc, graph);
    agclose(graph);

    if (out_len) *out_len = render_len;
    return render_data;
}

/* Dummy main to satisfy zig cc wasm32-wasi libc startup. */
int main(void) { return 0; }
