# Connect ReapWhatUSnow / SnowForge to ChatGPT

## Current status (2026-11-23)

- The GitHub repository and GitHub Actions drawing renderer are working.
- `snowforge/mcp_server.py` is a **local stdio-only** MCP prototype. It is not yet reachable from ChatGPT web.
- The existing three tool actions are `analyze_blueprint`, `revise_blueprint`, and `generate_blueprint_files`.
- `generate_blueprint_files` currently returns **local filesystem paths**; this must change to retrievable artifacts when hosted.
- Do not enter GitHub tokens or other credentials in chat or repository files.

## Route A: Personal plugin hosted on ChatGPT Sites (preferred for an individual ChatGPT account)

Open ChatGPT **Plugins** and install **Plugin Creator** (if not already installed).
Start a **Work** task with `@plugin-creator` and provide the prompt in the next section.
Plugin Creator can arrange Sites hosting and the plugin installation/connection flow, subject to account access.
An MCP-enabled Site must actually implement the SnowForge tool endpoints; simply linking a repository does not execute Python.

### Handoff prompt for Plugin Creator

> Create a personal plugin called "ReapWhatUSnow Blueprints" that lets ChatGPT turn my plain-English mechanical design descriptions into accurate parametric blueprint specifications, validate them, render drawings, and revise those drawings without losing design history.
>
> The authoritative implementation is the public GitHub repository https://github.com/snow663/ReapWhatUSnow (branch main). Start with its README.md, skills/blueprint-drafting/SKILL.md, snowforge/model.py, snowforge/cli.py, snowforge/drawing.py, examples/blank_template.json and snowforge/mcp_server.py. Reuse the actual Python geometry, validation, and rendering logic rather than generating illustrations in its place.
>
> Expose these callable MCP tools, with well-documented JSON parameters:
> 1. analyze_blueprint — parse and validate a snowforge.blueprint/v1 spec, return actual units, resolved dimensions, assumptions and geometric checks.
> 2. generate_blueprint_files — render the spec to DXF, SVG, PNG and PDF, plus source JSON and a validation manifest; **return actual retrievable artifact links or downloadable files, not temporary server-local paths**.
> 3. revise_blueprint — accept the current spec, parametric changes and revision note; produce the incremented editable spec, verify it and optionally render updated files.
>
> Host through ChatGPT Sites and create an MCP-enabled plugin. Preserve `confirmed`, `derived`, and `assumed` dimension status. Never invent load ratings or tolerances. Treat failures of geometric constraints as failures, not approvals.
>
> If Sites cannot run the existing Python dependencies (ezdxf and CairoSVG) directly, tell me exactly what deployment/gateway is needed; do **not** replace the engine with a visually plausible but dimensionally unverified mock. Keep API secrets in connection settings only. Publish the Site, install/connect its plugin and verify each of the three tool calls against the sample flange.
>
> The specification, computed geometry and revision history must remain usable as files in my GitHub repository. Ask before overwriting existing designs.

### Test in a new ChatGPT conversation

1. Select `@ReapWhatUSnow Blueprints`.
2. "Analyze the sample 8-on-6.5 flange from ReapWhatUSnow and give me its measured geometry and assumptions."
3. "Generate the DXF and PDF and show me the resulting download links."
4. "Revise the hole diameter to 5/8 inch and create revision B."
5. Inspect the original/updated source specs, artifact links and geometric checks.

## Route B: Connect your own remote MCP server (workspace-dependent)

The current OpenAI help documentation says direct custom MCP connections in ChatGPT web are available to **Business and Enterprise/Edu** workspaces with the right permissions. They are configured in **Plugins > + > Add custom MCP server**. Personal accounts may instead use Route A (Sites-hosted plugin).

For a custom remote server, deployment requires:
- Converting `snowforge/mcp_server.py` from stdio to a stateless **Streamable HTTP** endpoint at `https://your-host.example/mcp`.
- TLS and access control (OAuth 2.1 for user authentication; do **not** publish an unauthenticated drawing service).
- Artifact persistence / signed downloads, limits on request size and compute resources, validation tests and logs.
- A compatible host (container/VM with Python, ezdxf, CairoSVG, and required Cairo libraries).
- Adding the endpoint URL to ChatGPT's custom server connection settings.
- Verify the MCP Inspector can initialize, list tools, call a test tool and handle errors before installing the plugin.

Hosting the repo on GitHub or running Actions **does not by itself publish an MCP endpoint**. GitHub Actions is retained as the tested fallback for rendering drawings without a hosted MCP service.

### References

- https://help.openai.com/en/articles/20001256-plugins-in-chatgpt
- https://help.openai.com/en/articles/20001547-hosting-a-plugin-with-chatgpt-sites
- https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt
- https://developers.openai.com/plugins/build/mcp-server
