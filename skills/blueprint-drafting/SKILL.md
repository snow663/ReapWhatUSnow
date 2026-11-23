---
name: snowforge-blueprint-drafting
description: Convert plain-language descriptions of mechanical parts into explicit, editable geometry and dimensioned drawing packages; revise them deterministically.
---

# SnowForge Blueprint Drafting

## The critical distinction
Natural-language interpretation is the assistant's job. SnowForge is a deterministic parametric geometry, dimensioning, validation, and drawing export engine; it does not itself autonomously infer detailed mechanical shape from unrestricted prose. Do not invent dimensions without flagging them as assumptions.

## Workflow
1. Extract explicit dimensions and units, interface requirements, assembly relationships, material, tolerances, and loads from the user's description. Mark anything unprovided as `assumed`, `derived`, or list it as `unspecified` in notes; never mark derived or assumed dimensions as confirmed.
2. Express that geometry in `snowforge.blueprint/v1` JSON. Select front/top/side or part views that avoid ambiguous geometry. Use formulas beginning `=` to relate coordinates to `parameters`.
3. Generate a drawing using `python -m snowforge build --input my-part.json --out output/my-part`. Outputs: printable PDF, SVG, SVG blueprint, PNG preview, editable 1:1 model-space DXF, source and resolved JSON, manifest.
4. Check that each visible dimension is derived from geometry, inspect PDF/PNG, run validations, and flag unresolved fits or physical checks. This is a technical drawing draft, not structural certification or a manufacturing approval.
5. For requested alterations, change only named parameters; use `python -m snowforge revise --input current.json --set hole_dia=0.625 --out-spec next.json --note 'Increased diameter' --render-out output/next`. This increments revision and regenerates dependent geometry and dimensions.
6. Never erase source revisions; preserve original specs and resulting files in Git version history.

## Primitive schema
- `circle`: `center:[x,y],r`
- `rect`: `origin:[x,y],width,height`
- `line`: `p1:[x,y],p2:[x,y]`
- `polyline`: `points:[[x,y],...],closed`
- `arc`: `center,r,start_deg,end_deg` (positive CCW sweep <= 360)
- `slot`: `p1,p2,width` (p1/p2 are end-cap centers)
- `polar_holes`: `center,pitch_radius,hole_radius,count,start_deg`
- `center_mark`: `center,size`
Every entity may have `id` and layer: `outline`, `cut`, `center`, `detail`, or `hidden`.

## Dimensions
- `linear`: `p1,p2,mode` (horizontal, vertical, aligned), `offset`, optional `prefix`,`suffix`. Value computed from geometry.
- `diameter` or `radius`: `entity` referencing a circular entity, optional `angle_deg`,`reach`,`prefix`,`suffix`.
- `hole_pattern`: `entity` referencing `polar_holes`, `text_at`.
- `leader`: `anchor`,`text_at`,`text`.

## Modeling limitations (v0.1)
2D orthographic views are separate explicit sketches, not automatically generated from a 3D solid. No inferred mass properties, tolerance stacks, bearing fits, weld design, kinematics, or code compliance. The 2D DXF is editable and dimensioned but does not contain an automatically generated 3D assembly. No AI prose parsing happens in the CLI; the assistant creates the JSON model.
