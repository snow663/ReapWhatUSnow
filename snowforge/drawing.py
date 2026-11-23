"""Deterministic SVG blueprint pages and true-scale editable DXF model geometry."""
from __future__ import annotations
import html
import math
from pathlib import Path

PAGE_W, PAGE_H = 1700, 1100  # 17x11-inch ANSI B sheet at 100 viewport px/in
PALETTES = {
  'print': dict(bg='#ffffff', ink='#182d42', main='#145b92', center='#6693ad', accent='#e4f0f6',
                dim='#455e75', frame='#b3c4cc', muted='#697985', warn='#9e540c'),
  'blueprint': dict(bg='#071e34', ink='#eaf8ff', main='#90d5ff', center='#508eac', accent='#123957',
                    dim='#9bb6c8', frame='#39627a', muted='#8dabbd', warn='#ffcc84'),
}


def fmt(v, units):
    # Avoid hardcoded dimensions; consistently formatted measured output.
    dp=4 if units=='in' else 2
    result=f'{v:.{dp}f}'.rstrip('0').rstrip('.')
    if result.startswith('0.') and units=='in': result=result[1:]
    if result.startswith('-0.') and units=='in': result='-'+result[2:]
    return result or '0'


def slot_polygon(a,b,w,n=18):
    x1,y1=a; x2,y2=b; r=w/2
    angle=math.atan2(y2-y1,x2-x1)
    points=[]
    for i in range(n+1):
        t=angle+math.pi/2-math.pi*i/n
        points.append((x2+r*math.cos(t),y2+r*math.sin(t)))
    for i in range(n+1):
        t=angle-math.pi/2-math.pi*i/n
        points.append((x1+r*math.cos(t),y1+r*math.sin(t)))
    return points


class Panel:
    def __init__(self,view,frame):
        self.view=view; self.frame=frame
        x,y,w,h=frame
        a,b,c,d=view['bounds']
        ww=max(c-a,1e-9); hh=max(d-b,1e-9)
        self.scale=min((w-125)/ww,(h-135)/hh)
        self.mx=(a+c)/2; self.my=(b+d)/2
        self.cx=x+w/2; self.cy=y+h/2+10
    def pos(self,p):
        return (self.cx+(p[0]-self.mx)*self.scale,self.cy-(p[1]-self.my)*self.scale)
    def radius(self,r):return r*self.scale


class Svg:
    def __init__(self,model,theme):
        self.m=model; self.p=PALETTES[theme];self.theme=theme;self.parts=[]
    def add(self,text):self.parts.append(text)
    def line(self,a,b,cls='main', extra=''):
        self.add(f'<line class="{cls}" x1="{a[0]:.3f}" y1="{a[1]:.3f}" x2="{b[0]:.3f}" y2="{b[1]:.3f}" {extra}/>')
    def txt(self,x,y,s,cls='label',size=None,anchor='start',extra=''):
        s=html.escape(str(s))
        style=f'font-size:{size}px;' if size else ''
        self.add(f'<text class="{cls}" x="{x:.3f}" y="{y:.3f}" text-anchor="{anchor}" style="{style}" {extra}>{s}</text>')
    def circle(self,p,r,cls='main'):
        self.add(f'<circle class="{cls}" cx="{p[0]:.3f}" cy="{p[1]:.3f}" r="{r:.3f}"/>')
    def poly(self,pts,cls='main',closed=False):
        coords=' '.join(f'{x:.3f},{y:.3f}' for x,y in pts)
        self.add(f'<{"polygon" if closed else "polyline"} class="{cls}" points="{coords}"/>')
    def arrow(self,at,to):
        dx=to[0]-at[0];dy=to[1]-at[1]; d=math.hypot(dx,dy)
        if d<1e-9:return
        ux,uy=dx/d,dy/d
        poly=[at,(at[0]+ux*13-uy*3.5,at[1]+uy*13+ux*3.5),(at[0]+ux*13+uy*3.5,at[1]+uy*13-ux*3.5)]
        self.add('<polygon class="arrow" points="'+' '.join(f'{x:.2f},{y:.2f}' for x,y in poly)+'"/>')
    def render_geom(self,g,panel):
        tp=g['type'];cl={'center':'center','hidden':'hidden','detail':'detail'}.get(g['layer'],'main')
        pos=panel.pos
        if tp=='circle':
            self.circle(pos(g['center']),panel.radius(g['r']),cl)
        elif tp=='rect':
            x,y=g['origin'];q=pos((x,y+g['height']))
            self.add(f'<rect class="{cl}" x="{q[0]:.3f}" y="{q[1]:.3f}" width="{panel.radius(g["width"]):.3f}" height="{panel.radius(g["height"]):.3f}"/>')
        elif tp=='line':self.line(pos(g['p1']),pos(g['p2']),cl)
        elif tp=='polyline':self.poly([pos(x) for x in g['points']],cl,g['closed'])
        elif tp=='arc':
            cx,cy=g['center'];rr=g['r'];st=g['start_deg'];en=g['end_deg']
            radius=panel.radius(rr)
            def point(theta):
                return pos((cx+rr*math.cos(math.radians(theta)),cy+rr*math.sin(math.radians(theta))))
            swe=en-st
            if abs(swe-360)<1e-9:
                pts=[point(st),point(st+180),point(st+360)]
                path=f'M {pts[0][0]:.4f},{pts[0][1]:.4f} A {radius:.4f},{radius:.4f} 0 0 0 {pts[1][0]:.4f},{pts[1][1]:.4f} A {radius:.4f},{radius:.4f} 0 0 0 {pts[2][0]:.4f},{pts[2][1]:.4f}'
            else:
                p0,p1=point(st),point(en)
                large=1 if swe>180 else 0
                path=f'M {p0[0]:.4f},{p0[1]:.4f} A {radius:.4f},{radius:.4f} 0 {large} 0 {p1[0]:.4f},{p1[1]:.4f}'
            self.add(f'<path class="{cl}" d="{path}"/>')
        elif tp=='slot':
            a,b=g['p1'],g['p2'];r=g['width']/2
            theta=math.atan2(b[1]-a[1],b[0]-a[0]); nx,ny=-math.sin(theta),math.cos(theta)
            top_a=pos((a[0]+nx*r,a[1]+ny*r));top_b=pos((b[0]+nx*r,b[1]+ny*r))
            bot_a=pos((a[0]-nx*r,a[1]-ny*r));bot_b=pos((b[0]-nx*r,b[1]-ny*r))
            sr=panel.radius(r)
            path=(f'M {top_a[0]:.4f},{top_a[1]:.4f} L {top_b[0]:.4f},{top_b[1]:.4f} '
                  f'A {sr:.4f},{sr:.4f} 0 0 1 {bot_b[0]:.4f},{bot_b[1]:.4f} '
                  f'L {bot_a[0]:.4f},{bot_a[1]:.4f} '
                  f'A {sr:.4f},{sr:.4f} 0 0 1 {top_a[0]:.4f},{top_a[1]:.4f} Z')
            self.add(f'<path class="{cl}" d="{path}"/>')
        elif tp=='center_mark':
            x,y=g['center'];sz=g['size'];self.line(pos((x-sz,y)),pos((x+sz,y)),'center')
            self.line(pos((x,y-sz)),pos((x,y+sz)),'center')
    def render_dimension(self,d,panel):
        pos=panel.pos; units=self.m['units'];typ=d['type']
        if typ=='linear':
            a,b=d['p1'],d['p2']; off=d['offset']
            if d['mode']=='horizontal':
                target=(max(a[1],b[1])+off) if off>=0 else (min(a[1],b[1])+off)
                v1=(a[0],target);v2=(b[0],target)
            elif d['mode']=='vertical':
                target=(max(a[0],b[0])+off) if off>=0 else (min(a[0],b[0])+off)
                v1=(target,a[1]);v2=(target,b[1])
            else:
                dx=b[0]-a[0];dy=b[1]-a[1];L=math.hypot(dx,dy)
                if not L:return
                n=(-dy/L*off,dx/L*off)
                v1=(a[0]+n[0],a[1]+n[1]);v2=(b[0]+n[0],b[1]+n[1])
            aa,bb=pos(a),pos(b);q1,q2=pos(v1),pos(v2)
            vec=lambda a,b: ((b[0]-a[0]),(b[1]-a[1]))
            for base,at in ((aa,q1),(bb,q2)):
                v=vec(base,at); L=math.hypot(*v) or 1
                ext=(at[0]+v[0]/L*9,at[1]+v[1]/L*9)
                self.line(base,ext,'extension')
            self.line(q1,q2,'dimension')
            self.arrow(q1,q2);self.arrow(q2,q1)
            tx,ty=(q1[0]+q2[0])/2,(q1[1]+q2[1])/2
            text=d['prefix']+fmt(d['value'],units)+d['suffix']
            if d['mode']=='vertical': self.txt(tx+13,ty,text,'dimension-text',17)
            else: self.txt(tx,ty-10,text,'dimension-text',17,anchor='middle')
        elif typ in ('diameter','radius'):
            theta=math.radians(d['angle']);cx,cy=d['center'];r=d['r']
            a=(cx+r*math.cos(theta),cy+r*math.sin(theta))
            b=(cx+(r+d['reach'])*math.cos(theta),cy+(r+d['reach'])*math.sin(theta))
            pa,pb=pos(a),pos(b);self.line(pa,pb,'dimension')
            self.arrow(pa,pb)
            s=('Ø' if typ=='diameter' else 'R') + fmt(d['value'],units)
            self.txt(pb[0]+(10 if math.cos(theta)>=0 else -10),pb[1]-8,d['prefix']+s+d['suffix'],'dimension-text',17,
                     anchor='start' if math.cos(theta)>=0 else 'end')
        elif typ in ('leader','hole_pattern'):
            a=pos(d['anchor']); b=pos(d['text_at']);self.line(a,b,'dimension');self.arrow(a,b)
            if typ=='leader':
                self.txt(b[0]+8,b[1]-7,d['text'],'dimension-text',16)
            else:
                self.txt(b[0]+8,b[1]-13,f"{d['count']}X Ø{fmt(d['hole_dia'],units)} THRU",'dimension-text',16)
                self.txt(b[0]+8,b[1]+10,f"Ø{fmt(d['pcd'],units)} B.C.",'dimension-text',16)
    def page(self):
        p=self.p;m=self.m
        units='INCHES' if m['units']=='in' else 'MILLIMETERS'
        self.add(f'''<svg xmlns="http://www.w3.org/2000/svg" width="17in" height="11in" viewBox="0 0 {PAGE_W} {PAGE_H}" role="img" aria-label="{html.escape(m['title'])}">
        <style>
        .sheet{{fill:{p['bg']};}} .main{{fill:none;stroke:{p['main']};stroke-width:2.5;stroke-linejoin:round;stroke-linecap:round;}}
        .center{{fill:none;stroke:{p['center']};stroke-width:1.4;stroke-dasharray:18 7 3 7;}} .hidden{{fill:none;stroke:{p['center']};stroke-width:1.4;stroke-dasharray:8 6;}}
        .detail{{fill:none;stroke:{p['main']};stroke-width:1.5;}}.dimension{{fill:none;stroke:{p['dim']};stroke-width:1.5;}}
        .extension{{fill:none;stroke:{p['dim']};stroke-width:1.1;}}.arrow{{fill:{p['dim']};stroke:none;}}
        .label,.heading,.dimension-text,.muted,.warn{{font-family:Arial,Helvetica,sans-serif;fill:{p['ink']};}}
        .heading{{font-size:32px;font-weight:700;letter-spacing:1.3px;}} .label{{font-size:20px;font-weight:600;}}
        .dimension-text{{fill:{p['dim']};font-size:16px;stroke:none;}}
        .muted{{fill:{p['muted']};font-size:15px;}} .warn{{fill:{p['warn']};font-size:16px;font-weight:700;}}
        .rule{{stroke:{p['frame']};stroke-width:1.5;fill:none;}}
        </style>''')
        self.add('<rect width="1700" height="1100" class="sheet"/>')
        self.add('<rect x="30" y="30" width="1640" height="1040" class="rule"/>')
        self.txt(62,91,'SNOWFORGE  /  PARAMETRIC ENGINEERING DRAWING','heading',29)
        self.txt(63,118,m['title'],'muted',19)
        self.line((62,139),(1638,139),'rule')
        n=len(m['views'])
        if n==1:frames=[(65,171,1568,690)]
        elif n==2:frames=[(65,172,925,688),(1015,172,620,688)]
        else:
            frames=[]
            for i in range(n):
                cols=2; rows=(n+1)//2
                w= (1570-25)/cols; h=685/rows
                frames.append((67+(i%2)*(w+25),169+(i//2)*h,w,h-15))
        for index,(view,frame) in enumerate(zip(m['views'],frames)):
            x,y,w,h=frame; self.add(f'<rect class="rule" x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}"/>')
            self.txt(x+20,y+34,f"{index+1:02d}  {view['name'].upper()}",'label',19)
            panel=Panel(view,(x,y+38,w,h-45))
            for g in view['entities']:self.render_geom(g,panel)
            for d in view['dimensions']:self.render_dimension(d,panel)
            self.txt(x+w-16,y+h-13,'VIEW FIT TO SHEET - REFER TO DIMENSIONS','muted',12,anchor='end')
        self.line((62,887),(1638,887),'rule')
        self.txt(70,916,'NOTES / VALIDATION','label',18)
        notes=list(m['notes'])[:4]
        failures=[c for c in m['checks'] if not c['passed']]
        if failures:
            notes.append('GEOMETRY CHECK FAILED: '+', '.join(c['name'] for c in failures[:2]))
        elif m['checks']:
            notes.append(f"GEOMETRY CHECKS: {len(m['checks'])} PASS / 0 FAIL (details in manifest)")
        for i,note in enumerate(notes[:5]):self.txt(71,944+i*21,'• '+note,'muted',15)
        self.line((65,1040),(1636,1040),'rule')
        self.line((1080,889),(1080,1040),'rule'); self.line((1410,889),(1410,1040),'rule')
        self.txt(1098,921,'DRAWING NUMBER','muted',14)
        self.txt(1098,958,m['drawing_number'],'label',26)
        self.txt(1098,999,'UNITS: '+units,'muted',17)
        self.txt(1429,921,'REVISION','muted',14)
        self.txt(1429,958,m['revision'],'label',27)
        self.txt(1429,998,'STATUS: '+('CHECK FAILED' if any(not c['passed'] for c in m['checks']) else 'UNVERIFIED'),'warn',16)
        if m['assumed_parameters']:
            self.txt(71,1060,'ASSUMED / UNCONFIRMED: '+', '.join(m['assumed_parameters']),'warn',13)
        else:self.txt(71,1060,'DIMENSIONAL MODEL ONLY - VERIFY TOLERANCES, FIT, MATERIAL, LOADS','muted',13)
        self.add('</svg>')
        return '\n'.join(self.parts)


def save_svg(model,path,theme='print'):
    data=Svg(model,theme).page()
    Path(path).write_text(data,encoding='utf-8')
    return data


def save_dxf(model,path):
    """Model-space geometry stays at 1:1 in input units; separate views are laid out horizontally."""
    import ezdxf
    doc=ezdxf.new('R2010',setup=True)
    doc.header['$INSUNITS']=1 if model['units']=='in' else 4
    layer_info={'OUTLINE':(7,'CONTINUOUS'),'CUT':(3,'CONTINUOUS'), 'CENTER':(4,'CENTER'),
                'HIDDEN':(8,'DASHED'), 'DETAIL':(5,'CONTINUOUS'), 'DIM':(2,'CONTINUOUS'),'TEXT':(7,'CONTINUOUS')}
    for layer,(color,linetype) in layer_info.items():
        doc.layers.new(layer,dxfattribs={'color':color,'linetype':linetype})
    ms=doc.modelspace()
    next_left=0
    unit_scale=1 if model['units']=='in' else 25.4
    label_height=0.22*unit_scale
    for view in model['views']:
        min_x,min_y,max_x,max_y=view['bounds']
        delta=next_left-min_x
        T=lambda p:(p[0]+delta,p[1])
        for g in view['entities']:
            layer={'outline':'OUTLINE','cut':'CUT','center':'CENTER','detail':'DETAIL','hidden':'HIDDEN'}[g['layer']]
            tp=g['type'];att={'layer':layer}
            if tp=='circle':ms.add_circle(T(g['center']),g['r'],dxfattribs=att)
            elif tp=='line':ms.add_line(T(g['p1']),T(g['p2']),dxfattribs=att)
            elif tp=='rect':
                x,y=g['origin'];w,h=g['width'],g['height']
                ms.add_lwpolyline([T(q) for q in ((x,y),(x+w,y),(x+w,y+h),(x,y+h))],close=True,dxfattribs=att)
            elif tp=='polyline':ms.add_lwpolyline([T(q) for q in g['points']],close=g['closed'],dxfattribs=att)
            elif tp=='arc':ms.add_arc(T(g['center']),g['r'],g['start_deg'],g['end_deg'],dxfattribs=att)
            elif tp=='slot':
                p1,p2=g['p1'],g['p2'];rad=g['width']/2
                dx,dy=p2[0]-p1[0],p2[1]-p1[1];L=math.hypot(dx,dy); nx,ny=-dy/L,dx/L
                for sign in [-1,1]:
                    a=(p1[0]+sign*nx*rad,p1[1]+sign*ny*rad)
                    b=(p2[0]+sign*nx*rad,p2[1]+sign*ny*rad)
                    ms.add_line(T(a),T(b),dxfattribs=att)
                theta=math.degrees(math.atan2(dy,dx))
                ms.add_arc(T(p2),rad,theta-90,theta+90,dxfattribs=att)
                ms.add_arc(T(p1),rad,theta+90,theta+270,dxfattribs=att)
            elif tp=='center_mark':
                cx,cy=g['center'];s=g['size']
                ms.add_line(T((cx-s,cy)),T((cx+s,cy)),dxfattribs=att)
                ms.add_line(T((cx,cy-s)),T((cx,cy+s)),dxfattribs=att)
        # 1:1 annotations use native CAD DIMENSIONs where possible.
        for dim in view['dimensions']:
            tp=dim['type']
            if tp=='linear':
                a,b=dim['p1'],dim['p2'];ofs=dim['offset'];mode=dim['mode']
                ov={'dimtxt':label_height*0.8,'dimasz':label_height*.45,'dimexo':label_height*.25,
                    'dimexe':label_height*.35,'dimdec':4 if model['units']=='in' else 2}
                if mode=='horizontal':
                    Y=(max(a[1],b[1])+ofs) if ofs>=0 else (min(a[1],b[1])+ofs)
                    d=ms.add_linear_dim(base=(a[0]+delta,Y),p1=T(a),p2=T(b),angle=0,override=ov)
                elif mode=='vertical':
                    X=(max(a[0],b[0])+ofs) if ofs>=0 else (min(a[0],b[0])+ofs)
                    d=ms.add_linear_dim(base=(X+delta,a[1]),p1=T(a),p2=T(b),angle=90,override=ov)
                else:
                    theta=math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))
                    n=(-math.sin(math.radians(theta))*ofs, math.cos(math.radians(theta))*ofs)
                    d=ms.add_linear_dim(base=(a[0]+n[0]+delta,a[1]+n[1]),p1=T(a),p2=T(b),angle=theta,override=ov)
                d.render()
            elif tp in ('diameter','radius'):
                center=dim['center'];r=dim['r'];t=math.radians(dim['angle']);reach=dim['reach']
                pt=(center[0]+(r+reach)*math.cos(t)+delta,center[1]+(r+reach)*math.sin(t))
                txt=('%%c' if tp=='diameter' else 'R')+fmt(dim['value'],model['units'])
                ms.add_text(txt,dxfattribs={'height':label_height,'layer':'DIM','insert':pt})
            elif tp in ('leader','hole_pattern'):
                anchor=T(dim['anchor']); at=T(dim['text_at'])
                ms.add_line(anchor,at,dxfattribs={'layer':'DIM'})
                if tp=='leader':s=dim['text']
                else:s=f"{dim['count']}X %%c{fmt(dim['hole_dia'],model['units'])} THRU, %%c{fmt(dim['pcd'],model['units'])} B.C."
                ms.add_text(s,dxfattribs={'height':label_height*.8,'layer':'DIM','insert':at})
        ms.add_text(view['name'].upper(),dxfattribs={'height':label_height*1.5,'layer':'TEXT', 'insert':(min_x+delta,max_y+label_height*2)})
        next_left=delta+max_x+(2.5*unit_scale)
    doc.saveas(path)
