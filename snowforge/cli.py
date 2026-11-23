"""CLI: build, validate, and revise editable mechanical drawing specifications."""
from __future__ import annotations
import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from .model import ModelError, load_spec, resolve, revise
from .drawing import save_svg, save_dxf


def build(spec_file, output_dir):
    from cairosvg import svg2pdf, svg2png
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    src=load_spec(spec_file);model=resolve(src)
    printable=out/'drawing.svg'; blueprint=out/'blueprint.svg'
    save_svg(model,printable,'print'); save_svg(model,blueprint,'blueprint')
    save_dxf(model,out/'model.dxf')
    svg2pdf(bytestring=printable.read_bytes(),write_to=str(out/'drawing.pdf'))
    svg2png(bytestring=blueprint.read_bytes(),write_to=str(out/'blueprint.png'),output_width=2040,output_height=1320)
    (out/'source_spec.json').write_text(json.dumps(src,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (out/'resolved_geometry.json').write_text(json.dumps(model,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    manifest={
        'generated_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'drawing_number':model['drawing_number'], 'title':model['title'],
        'revision':model['revision'], 'units':model['units'],
        'parameters':model['parameters'],'parameter_status':model['parameter_status'],
        'assumed_parameters':model['assumed_parameters'], 'checks':model['checks'],
        'geometry_count':sum(len(v['entities']) for v in model['views']),
        'view_names':[v['name'] for v in model['views']],
        'outputs':{'print_svg':'drawing.svg','blueprint_svg':'blueprint.svg','preview_png':'blueprint.png',
                   'editable_cad_dxf':'model.dxf','printable_pdf':'drawing.pdf','source':'source_spec.json',
                   'resolved_geometry':'resolved_geometry.json'},
        'status':'CHECK_FAILED' if any(not c['passed'] for c in model['checks']) else 'DRAFT_UNVERIFIED',
        'disclaimer':'Geometry and calculated dimensions only. Tolerances, structural strength, material, safety, and fit require engineering review.'
    }
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return manifest


def main(argv=None):
    ap=argparse.ArgumentParser(prog='snowforge',description='Parametric engineering blueprint generator')
    sub=ap.add_subparsers(dest='cmd',required=True)
    buildp=sub.add_parser('build',help='Render the drawing to SVG, PDF, PNG, and editable DXF')
    buildp.add_argument('--input',required=True); buildp.add_argument('--out',required=True)
    valp=sub.add_parser('validate',help='Validate the source model and constraints')
    valp.add_argument('--input',required=True)
    revp=sub.add_parser('revise',help='Change dimensions and automatically increment drawing revision')
    revp.add_argument('--input',required=True)
    revp.add_argument('--set',action='append',required=True,metavar='PARAM=NUMBER_OR_FORMULA')
    revp.add_argument('--out-spec',required=True);revp.add_argument('--note',default='')
    revp.add_argument('--render-out',default=None)
    args=ap.parse_args(argv)
    try:
        if args.cmd=='build':
            mf=build(args.input,args.out)
            print(json.dumps(mf,indent=2,ensure_ascii=False))
            return 2 if mf['status']=='CHECK_FAILED' else 0
        if args.cmd=='validate':
            m=resolve(load_spec(args.input))
            print(json.dumps({'valid_geometry':True,'revision':m['revision'],'parameters':m['parameters'],
                              'checks':m['checks'], 'assumed_parameters':m['assumed_parameters']},indent=2))
            return 2 if any(not x['passed'] for x in m['checks']) else 0
        if args.cmd=='revise':
            changes={}
            for entry in args.set:
                if '=' not in entry:raise ModelError(f'Expected PARAM=value, got: {entry}')
                key,val=entry.split('=',1)
                key=key.strip()
                if not key:raise ModelError('Empty parameter name')
                if val.strip().startswith('='):
                    value=val.strip()
                else:
                    try:value=float(val)
                    except ValueError:raise ModelError(f'Numeric parameter expected for {key}; formulas must start with =')
                changes[key]=value
            spec=revise(load_spec(args.input),changes,args.note)
            dst=Path(args.out_spec);dst.parent.mkdir(parents=True,exist_ok=True)
            dst.write_text(json.dumps(spec,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
            print(f'Revision {spec["revision"]} -> {dst}')
            if args.render_out:
                mf=build(dst,args.render_out)
                print(f'Blueprint generated: {args.render_out}')
                return 2 if mf['status']=='CHECK_FAILED' else 0
            return 0
    except (ModelError,ValueError,KeyError,TypeError,FileNotFoundError) as exc:
        print(f'SnowForge error: {exc}',file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
