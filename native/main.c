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
    free(ptr);
}

char* graphviz_render(const char* dot, const char* format, const char* engine,
                      size_t* out_len)
{
    char* result = NULL;
    char* render_data = NULL;
    size_t render_len = 0;

    if (out_len) *out_len = 0;
    last_error[0] = '\0';

    GVC_t* gvc = gvContextPlugins(lt_preloaded_symbols, 1);
    if (!gvc) {
        strncpy(last_error, "Failed to create Graphviz context", sizeof(last_error) - 1);
        return NULL;
    }

    agseterr(AGERR);
    agseterrf(viz_errorf);

    Agraph_t* graph = agmemread(dot);
    if (!graph) {
        strncpy(last_error, "Failed to parse DOT source", sizeof(last_error) - 1);
        gvFreeContext(gvc);
        return NULL;
    }

    if (gvLayout(gvc, graph, engine) != 0) {
        strncpy(last_error, "Layout failed", sizeof(last_error) - 1);
        agclose(graph);
        gvFreeContext(gvc);
        return NULL;
    }

    if (gvRenderData(gvc, graph, format, &render_data, &render_len) != 0) {
        strncpy(last_error, "Render failed", sizeof(last_error) - 1);
        gvFreeLayout(gvc, graph);
        agclose(graph);
        gvFreeContext(gvc);
        return NULL;
    }

    if (render_data && render_len > 0) {
        result = (char*)malloc(render_len);
        if (result) {
            memcpy(result, render_data, render_len);
            if (out_len) *out_len = render_len;
        }
    }

    gvFreeRenderData(render_data);
    gvFreeLayout(gvc, graph);
    agclose(graph);
    gvFinalize(gvc);
    gvFreeContext(gvc);

    return result;
}

/* Dummy main to satisfy zig cc wasm32-wasi libc startup. */
int main(void) { return 0; }
