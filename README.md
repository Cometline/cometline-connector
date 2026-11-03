# cometline-connector

Verified default MCP connector catalog for [Cometline](https://github.com/Cometline/cometline).

This repository stores connector metadata only. It does not contain an MCP client, an OAuth implementation, or a connector runtime. Cometline reads a pinned version of this catalog and uses its existing MCP client to connect.

## What belongs here

- Official remote MCP endpoints
- Official local MCP commands
- Authentication requirements
- Local dependency requirements
- Source links and verification dates
- Short user guidance

## What does not belong here

- Cometline settings UI
- MCP connection code
- Token storage
- Vendor-hosted proxy URLs, including `api.cursor.com/rest-mcp/...`
- Community servers that are not published by the service provider

## Catalog format

Each connector is a JSON file in `connectors/`. `index.json` lists the current files. A connector can offer more than one official connection mode. Cometline decides which mode to offer and never overwrites a user-edited configuration during a catalog update.

## Verification

The checked-in endpoints and commands were verified against the provider documentation listed in each file. Verification does not mean that every authentication flow has already been tested inside Cometline.
