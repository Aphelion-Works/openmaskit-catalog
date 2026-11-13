# OpenMaskit Catalog

A public catalog of MCP servers for OpenMaskit. The entries live in git. GitHub Pages serves the three files OpenMaskit already fetches, so the catalog does not need its own server.

This is a community list. It is not the hosted Maskit catalog, and it does not use `auth.maskitmcp.com`.

## Use it

Point OpenMaskit at this site and turn marketplace calls on:

```
OPENMASKIT_MARKETPLACE_API_URL=https://aphelion-works.github.io/openmaskit-catalog
OPENMASKIT_DISABLE_MARKETPLACE=0
```

Leave the auth address unset. Install then stays on the machine that runs OpenMaskit.

A personal catalog is a fork of this repository. Enable GitHub Pages on the fork from the `main` branch and the root folder, then point `OPENMASKIT_MARKETPLACE_API_URL` at that fork's Pages site. The site has to stay publicly readable. OpenMaskit requests it with no GitHub login, so a private repository answers 404.

## Add a server

Copy one of the files in `examples/` into `servers/`, change the host, and run:

```
python3 scripts/build.py
```

Commit `servers/` and the rebuilt `api/` files. The check workflow rejects a catalog that was not rebuilt.

An entry needs a stable `id`, a `handle`, a name, and a description. `official` stays false. Remote servers use `transport_type: "http"` and an `https` `mcp_host`. OAuth entries set `oauth_mode` to `byo` or `dcr`. Bring-your-own asks the person for a client id and secret at install time. Direct registration talks to the provider from their machine. Header entries declare the header name and leave the value for install time.

Client secrets, tokens, and hosted-broker entries do not belong in this repository. An entry with no `oauth_mode` would send the browser to the hosted broker, so the builder rejects that combination. `docker`, `podman`, `finch`, and `nerdctl` are rejected as commands because those programs are not part of the OpenMaskit container.

## What the site serves

Pages ignores `page`, `size`, and `q` and returns the same files every time. The published list is one page, and search shows that whole page.

| Path | File |
| --- | --- |
| `/api/marketplace/catalog` | every entry, plus `meta.total_pages` of 1 |
| `/api/marketplace/servers/<id>` | that entry |
| `/api/version_check` | this version is supported and no update is required |

These files do not read headers. The OpenMaskit fork does not send an installation id or an OpenMaskit version when it fetches them.
