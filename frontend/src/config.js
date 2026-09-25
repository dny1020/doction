// Where each surface lives, from the build environment; defaults to today's layout. Paths
// only: the bundle is public. /api is not configurable.

// The router basename, without a trailing slash and empty for the root. Substituted by
// vite from the same DOCTION_APP_PATH that sets the build's `base`.
export const APP_BASE = __DOCTION_APP_BASE__

export const MCP_PATH = __DOCTION_MCP_PATH__
