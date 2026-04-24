/* wasi_stubs.h — POSIX stubs for wasm32-wasi builds
 *
 * Inject via: -include $(pwd)/native/wasi_stubs.h
 *
 * This header provides no-op or minimal implementations of POSIX functions
 * that Graphviz uses but which are absent from WASI libc.  Keeping this in a
 * single stub header means we never have to edit Graphviz source files.
 */

#ifndef WASI_STUBS_H
#define WASI_STUBS_H

#ifdef __wasi__

#include <stdio.h>

/* WASI libc does not provide flockfile / funlockfile.
 * They are only used in lib/util/lockfile.h for debug logging.
 */
static inline void flockfile(FILE *file) { (void)file; }
static inline void funlockfile(FILE *file) { (void)file; }

#endif /* __wasi__ */

#endif /* WASI_STUBS_H */
