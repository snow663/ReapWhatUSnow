"""Resolve parametric source into validated, explicit geometric primitives."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
from .expressions import ExpressionError, numeric, resolve_parameters, xy

SUPPORTED = {'circle','line','rect','polyline','arc','slot','polar_holes','center_mark'}
LAYERS = {'outline', 'cut', 'center', 'detail', 'hidden'}

class ModelError(ValueError):
    pass


def load_spec(path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def expand_entity(ent, p):
    typ = ent.get('type')
    if typ not in SUPPORTED:
        raise ModelError(f'Unsupported geometry type: {typ!r}')
    layer = ent.get('layer', 'cut')
    if layer not in LAYERS:
        raise ModelError(f'Unsupported layer {layer}')
    id_ = ent.get('id', typ)
    base = {'id': id_, 'type': typ, 'layer': layer}
    if typ == 'circle':
        r = numeric(ent['r'], p)
        if r <= 0: raise ModelError(f'{id_}: circle radius must be positive')
        return [{**base, 'center': xy(ent['center'], p), 'r': r}]
    if typ == 'rect':
        a=xy(ent['origin'],p)
        w=numeric(ent['width'],p); h=numeric(ent['height'],p)
        if w <= 0 or h <= 0: raise ModelError(f'{id_}: rectangle dimensions must be positive')
        return [{**base,'origin':a,'width':w,'height':h}]
    if typ == 'line':
        return [{**base,'p1':xy(ent['p1'],p),'p2':xy(ent['p2'],p)}]
    if typ == 'polyline':
        pts = [xy(v,p) for v in ent['points']]
        if len(pts)<2: raise ModelError(f'{id_}: polyline requires >=2 points')
        return [{**base,'points':pts,'closed':bool(ent.get('closed',False))}]
    if typ == 'arc':
        r=numeric(ent['r'],p)
        s=numeric(ent['start_deg'],p); e=numeric(ent['end_deg'],p)
        if r <= 0 or not 0 < (e-s) <=360: raise ModelError(f'{id_}: arc radius and sweep invalid')
        return [{**base,'center':xy(ent['center'],p),'r':r,'start_deg':s,'end_deg':e}]
    if typ == 'slot':
        a=xy(ent['p1'],p); b=xy(ent['p2'],p); w=numeric(ent['width'],p)
        if w<=0 or math.dist(a,b)<=1e-9: raise ModelError(f'{id_}: slot requires separated centers and positive width')
        return [{**base,'p1':a,'p2':b,'width':w}]
    if typ == 'polar_holes':
        n=numeric(ent['count'],p)
        if int(n)!=n or not 1<=n<=1000: raise ModelError(f'{id_}: invalid integer count')
        r=numeric(ent['pitch_radius'],p); hr=numeric(ent['hole_radius'],p)
        a=numeric(ent.get('start_deg',0),p)
        if r < 0 or hr<=0: raise ModelError(f'{id_}: invalid pitch or hole radius')
        ctr=xy(ent.get('center',[0,0]),p)
        return [ {'id':f'{id_}_{k+1:03d}','parent':id_,'type':'circle','layer':layer,
                  'center':(ctr[0]+r*math.cos(math.radians(a+360*k/n)),ctr[1]+r*math.sin(math.radians(a+360*k/n))),
                  'r':hr} for k in range(int(n))]
    if typ == 'center_mark':
        return [{**base, 'center':xy(ent['center'],p), 'size':numeric(ent.get('size',0.25),p)}]
    raise AssertionError(typ)


def bounds_ent(g):
    typ=g['type']
    if typ=='circle':
        x,y=g['center'];r=g['r'];return x-r,y-r,x+r,y+r
    if typ=='rect':
        x,y=g['origin'];return x,y,x+g['width'],y+g['height']
    if typ=='line':
        x,y=g['p1']; X,Y=g['p2'];return min(x,X),min(y,Y),max(x,X),max(y,Y)
    if typ=='polyline':
        pts=g['points'];return min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)
    if typ=='arc':
        cx,cy=g['center'];r=g['r'];s=g['start_deg'];e=g['end_deg']
        angles=[s,e]+[a for a in range(-720,1081,90) if s <= a <=e]
        pts=[(cx+r*math.cos(math.radians(a)),cy+r*math.sin(math.radians(a))) for a in angles]
        return min(v[0] for v in pts),min(v[1] for v in pts),max(v[0] for v in pts),max(v[1] for v in pts)
    if typ=='slot':
        a=g['p1']; b=g['p2']; r=g['width']/2
        return min(a[0],b[0])-r,min(a[1],b[1])-r,max(a[0],b[0])+r,max(a[1],b[1])+r
    if typ=='center_mark':
        x,y=g['center'];d=g['size'];return x-d,y-d,x+d,y+d
    raise ModelError(f'No bounds for {typ}')


def resolve(spec):
    if spec.get('schema') != 'snowforge.blueprint/v1':
        raise ModelError('Unrecognized blueprint schema; expected snowforge.blueprint/v1')
    if spec.get('units') not in ('in','mm'):
        raise ModelError('units must be in or mm')
    p=resolve_parameters(spec.get('parameters',{}))
    if not spec.get('views'):
        raise ModelError('At least one view is required')
    views=[]
    for view in spec['views']:
        shapes=[]
        for ent in view.get('entities',[]):
            shapes.extend(expand_entity(ent,p))
        if not shapes: raise ModelError(f"View {view.get('name','?')} has no geometry")
        boxes=[bounds_ent(g) for g in shapes]
        bound=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
        if bound[2]-bound[0]<=0 or bound[3]-bound[1]<=0:
            raise ModelError('Zero-sized view bounds')
        dims=[]
        for d in view.get('dimensions',[]):
            dtype=d['type']
            common={'type':dtype,'id':d.get('id',dtype)}
            if dtype=='linear':
                p1,p2=xy(d['p1'],p),xy(d['p2'],p)
                mode=d.get('mode','aligned')
                if mode not in ('horizontal','vertical','aligned'):raise ModelError('invalid dimension mode')
                length={'horizontal':abs(p1[0]-p2[0]),'vertical':abs(p1[1]-p2[1]),'aligned':math.dist(p1,p2)}[mode]
                dims.append({**common,'p1':p1,'p2':p2,'mode':mode,'offset':numeric(d.get('offset',0.7),p),'value':length,'prefix':d.get('prefix',''), 'suffix':d.get('suffix','')})
            elif dtype in ('diameter','radius'):
                ref=d['entity']
                found=next((g for g in shapes if g['id']==ref and g['type']=='circle'),None)
                if not found: raise ModelError(f'Dimension references unknown circle {ref}')
                dims.append({**common,'center':found['center'],'r':found['r'], 'value':found['r']*(2 if dtype=='diameter' else 1),
                             'angle':numeric(d.get('angle_deg',45),p),'reach':numeric(d.get('reach',0.9),p),
                             'prefix':d.get('prefix',''), 'suffix':d.get('suffix','')})
            elif dtype=='leader':
                dims.append({**common,'anchor':xy(d['anchor'],p),'text_at':xy(d['text_at'],p),'text':str(d['text'])})
            elif dtype=='hole_pattern':
                ref=d['entity']
                matched=[g for g in shapes if g.get('parent')==ref]
                if not matched:raise ModelError(f'Unknown polar hole pattern: {ref}')
                raw=next(e for e in view['entities'] if e.get('id')==ref)
                dims.append({**common,'anchor':matched[0]['center'], 'count':len(matched),
                             'hole_dia':matched[0]['r']*2,'pcd':numeric(raw['pitch_radius'],p)*2,
                             'text_at':xy(d['text_at'],p)})
            else:raise ModelError(f'Unsupported dimension type: {dtype}')
        views.append({'name':view.get('name','VIEW'), 'entities':shapes,'dimensions':dims,'bounds':bound})
    checks=[]
    for c in spec.get('checks',[]):
        val=numeric(c['expression'],p); low=numeric(c['minimum'],p) if 'minimum' in c else None
        high=numeric(c['maximum'],p) if 'maximum' in c else None
        ok=(low is None or val >= low-1e-9) and (high is None or val <= high+1e-9)
        checks.append({'name':c['name'],'value':val,'minimum':low,'maximum':high,'passed':ok})
    assumed=[k for k,v in spec.get('parameter_status',{}).items() if v not in ('confirmed','derived')]
    return {'schema':spec['schema'], 'title':spec.get('title','Untitled'),
            'drawing_number':spec.get('drawing_number','SF-000'), 'revision':spec.get('revision','A'),
            'units':spec['units'], 'parameters':p, 'parameter_status':spec.get('parameter_status',{}),
            'assumed_parameters':assumed, 'views':views, 'checks':checks,
            'notes':spec.get('notes',[]), 'revision_history':spec.get('revision_history',[])}


def revise(spec, changes, note=''):
    if not changes: raise ModelError('No parameter changes provided')
    old=resolve(spec)
    new=copy.deepcopy(spec)
    before={}
    for key,value in changes.items():
        if key not in new['parameters']:
            raise ModelError(f'Cannot revise nonexistent parameter: {key}')
        before[key]=new['parameters'][key]
        new['parameters'][key]=value
        new.setdefault('parameter_status',{})[key]='confirmed'
    new_rev=next_revision(new.get('revision','A'))
    new['revision']=new_rev
    from datetime import datetime, timezone
    new.setdefault('revision_history',[]).append({'revision':new_rev,'timestamp_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
      'changes':{k:{'from':before[k],'to':v} for k,v in changes.items()},'note':note})
    resolve(new) # never accept a broken change
    return new


def next_revision(rev):
    # Excel-style A..Z, AA..AZ... makes arbitrary revision sequence possible.
    if not rev or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' for c in rev):
        raise ModelError('Revisions must contain A-Z only')
    n=0
    for c in rev: n=n*26+ord(c)-64
    n+=1; out=''
    while n: n,r=divmod(n-1,26);out=chr(65+r)+out
    return out
