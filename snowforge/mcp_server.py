"""Optional local stdio MCP bridge. Install with `pip install -e '.[mcp]'`.

Important: stdio server is intended to run under an explicitly configured MCP host.
A repository alone does not automatically connect tools to ChatGPT.
"""
from __future__ import annotations
import json
import tempfile
from pathlib import Path
from .model import resolve, revise
from .cli import build


def start():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        raise SystemExit("Install optional MCP dependency: pip install -e '.[mcp]'") from e
    mcp=FastMCP('SnowForge Blueprint Drafting')

    @mcp.tool()
    def analyze_blueprint(spec_json: str) -> str:
        """Resolve parameters and geometry; return actual sizes, assumptions and geometric checks."""
        model=resolve(json.loads(spec_json))
        summary={'title':model['title'],'revision':model['revision'],'units':model['units'],
                 'parameters':model['parameters'],'assumed_parameters':model['assumed_parameters'],
                 'checks':model['checks'],
                 'views':[{'name':v['name'],'bounds':v['bounds'],'entity_count':len(v['entities']),
                           'dimensions':v['dimensions']} for v in model['views']]}
        return json.dumps(summary,ensure_ascii=False)

    @mcp.tool()
    def revise_blueprint(spec_json: str, parameter_changes_json: str, change_note: str='') -> str:
        """Revise existing parametric dimensions while preserving revision history."""
        new_spec=revise(json.loads(spec_json),json.loads(parameter_changes_json),change_note)
        return json.dumps(new_spec,indent=2,ensure_ascii=False)

    @mcp.tool()
    def generate_blueprint_files(spec_json: str) -> str:
        """Generate local vector PDF, DXF, SVG, and PNG. Local file paths require shared filesystem access."""
        loc=Path(tempfile.mkdtemp(prefix='snowforge-'))
        path=loc/'source.json';path.write_text(spec_json,encoding='utf-8')
        summary=build(path,loc/'drawing')
        return json.dumps({'local_directory':str(loc/'drawing'), 'manifest':summary},ensure_ascii=False)

    mcp.run(transport='stdio')

if __name__=='__main__':start()
