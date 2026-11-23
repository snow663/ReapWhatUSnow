import copy
import json
import math
from pathlib import Path
import pytest
from snowforge.model import load_spec, resolve, revise, ModelError
from snowforge.expressions import evaluate, ExpressionError, resolve_parameters
from snowforge.cli import build

SAMPLE=Path(__file__).resolve().parent.parent/'examples'/'8_on_6_5_mounting_flange.json'


def test_sample_geometry_and_pattern():
    m=resolve(load_spec(SAMPLE));v=m['views'][0]
    assert m['parameters']['outer_diameter']==pytest.approx(8.56)
    holes=[x for x in v['entities'] if x.get('parent')=='bolt_holes']
    assert len(holes)==8
    assert all(math.hypot(*h['center'])==pytest.approx(3.25) for h in holes)
    assert all(h['r']==pytest.approx(9/32) for h in holes)
    assert all(c['passed'] for c in m['checks'])
    assert set(m['assumed_parameters'])=={'thickness','bolt_start_angle'}


def test_revision_recomputes_hole_dia_and_checks():
    s=load_spec(SAMPLE)
    n=revise(s,{'bolt_hole_diameter':0.625},'Increase bolt hole diameter')
    assert n['revision']=='B'
    assert s['revision']=='A' # immutable source
    assert n['revision_history'][-1]['changes']['bolt_hole_diameter']['from']==0.5625
    m=resolve(n)
    assert next(x for x in m['views'][0]['dimensions'] if x['type']=='hole_pattern')['hole_dia']==pytest.approx(.625)
    assert all(c['passed'] for c in m['checks'])


def test_cyclic_and_hostile_expression_rejected():
    with pytest.raises(ExpressionError): resolve_parameters({'a':'=b+1','b':'=a+1'})
    with pytest.raises(ExpressionError):evaluate("=__import__('os').system('id')",{})
    with pytest.raises(ExpressionError):evaluate('=foo.bar',{})


def test_check_fails_for_invalid_land():
    s=load_spec(SAMPLE)
    s['parameters']['outer_diameter']=6.0
    assert not resolve(s)['checks'][0]['passed']


def test_dxf_exactly_matches_geometry_and_pdf_page(tmp_path):
    import ezdxf
    from pypdf import PdfReader
    manifest=build(SAMPLE,tmp_path)
    assert manifest['geometry_count']==15
    doc=ezdxf.readfile(tmp_path/'model.dxf')
    assert doc.header['$INSUNITS']==1
    circles=list(doc.modelspace().query('CIRCLE'))
    assert len(circles)==11
    assert sum(abs(c.dxf.radius-0.28125)<1e-9 for c in circles)==8
    pdf=PdfReader(tmp_path/'drawing.pdf')
    assert len(pdf.pages)==1
    assert float(pdf.pages[0].mediabox.width)==pytest.approx(1224)
    assert float(pdf.pages[0].mediabox.height)==pytest.approx(792)
    for fname in ('drawing.pdf','model.dxf','blueprint.png','blueprint.svg','drawing.svg','manifest.json'):
        assert (tmp_path/fname).stat().st_size>200


def test_exact_arc_and_slot_exports(tmp_path):
    import ezdxf
    s=load_spec(SAMPLE)
    s['views'][0]['entities'] += [
        {'id':'slot_test','type':'slot','p1':[0,1.5],'p2':[1,1.5],'width':0.3},
        {'id':'arc_test','type':'arc','center':[0,0],'r':5.2,'start_deg':0,'end_deg':180},
    ]
    p=tmp_path/'test.json';p.write_text(json.dumps(s))
    manifest=build(p,tmp_path/'generated')
    doc=ezdxf.readfile(tmp_path/'generated'/'model.dxf')
    assert len(doc.modelspace().query('ARC'))==3  # one circular arc plus two exact slot caps
    assert ' A ' in (tmp_path/'generated'/'drawing.svg').read_text()


def test_reject_huge_exponents():
    with pytest.raises(ExpressionError):evaluate('=10**999999',{})
