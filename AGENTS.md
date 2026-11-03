# AGENTS.md

This repository is the connector catalog for Cometline. It stores verified MCP metadata and icons. It does not contain the Cometline app or an MCP runtime.

## Source of truth

`connectors/catalog.json` is the file Cometline reads from `main`.

Each connector also has one file in `connectors/`. `connectors/index.json` lists those files. If you edit a connector, update both the individual file and `catalog.json`, or run the verifier with `--write-results` after the check passes.

## Add a connector

1. Add official direct connection details only. Do not add `api.cursor.com` or another vendor proxy.
2. Include `iconSvg` as a complete `<svg>` element. Use the colorful default logo, not a black silhouette. See [Icons](#icons).
3. Use `https://` for remote endpoints.
4. Use the provider's documented command for local servers.
5. Set `auth` to `none`, `token`, or `oauth-or-token`.
6. Run `python3 scripts/verify_catalog.py --handshake --tools`.
7. Open a pull request. GitHub Actions must pass before the connector reaches Cometline.

## Icons

Use the colorful default brand logo. Do not store a black or monochrome silhouette.

Take the icon from theSVG's `default` variant:

```text
https://cdn.jsdelivr.net/gh/glincker/thesvg@main/public/icons/{slug}/default.svg
```

Do not use Simple Icons, or any other single-color black SVG. Those render as a black picture in Cometline.

- `iconSvg` must be one complete `<svg>` element.
- Put the brand color on the shapes. Cometline sets `fill: currentColor` on the `<svg>` element, so a fill only on that tag is ignored and the icon turns black.
- Prefix gradient and clip-path ids with the connector id, such as `gmail-a`. Several icons render on one page, and duplicate ids mix up the colors.
- If `default.svg` is white because it is meant for a dark background, use the same artwork in the brand color so it stays visible on the light settings card. Vercel's default file is white; use the black triangle. Go's default file is a white wordmark; use that artwork in `#00ADD8`. Fly.io's colorful logo is `fly/default.svg`, not `fly-io` or `flydotio`.
- GitHub, Notion, and Vercel publish a black mark. Keep that mark. Do not invent a color for them.

## Verification levels

The CI check has two passes:

- The shape check validates fields, icons, transports, and blocked proxy URLs.
- The handshake check confirms that a remote endpoint responds or a local command speaks MCP.
- A `401` or `403` is a valid result for a server that requires OAuth or a token. It proves the endpoint exists, not that a user has signed in.
- A missing local dependency is reported as a skip. Do not fail the catalog only because Docker or `gopls` is absent on a runner.
- Authenticated tool calls need a provider secret. Do not store tokens in this repository.

## What not to change here

- Do not implement OAuth, token storage, or the Settings page.
- Do not start a connector automatically from a catalog update.
- Do not overwrite a user's saved Cometline MCP configuration from this repository.

## Useful commands

```bash
python3 scripts/verify_catalog.py
python3 scripts/verify_catalog.py --handshake --tools
```
