// Where each surface of the deployment lives, from the build environment. Everything
// defaults to today's layout, so a deployment that configures nothing never notices this
// file. Paths only — whatever enters the bundle is published to whoever loads it.
//
// /api is deliberately not configurable: this backend serves it and no deployment moves it.

// The router basename, without a trailing slash and empty for the root. Substituted by
// vite from the same DOCTION_APP_PATH that sets the build's `base`.
export const APP_BASE = __DOCTION_APP_BASE__

export const MCP_PATH = __DOCTION_MCP_PATH__
