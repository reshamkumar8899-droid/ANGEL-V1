"""
Inspect VRM bone structure using Blender.
VRM is GLTF-based, so we import as GLTF.
Run: "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" --background --python inspect_vrm.py
"""
import bpy
import os
import json
import math

VRM_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "angel.vrm")

# Clear default scene
bpy.ops.wm.read_factory_settings(use_empty=True)

print(f"\n{'='*60}")
print(f"  Loading: {VRM_PATH}")
print(f"{'='*60}")

# Import as GLTF (VRM is GLTF-based)
bpy.ops.import_scene.gltf(filepath=VRM_PATH)

# Find armature
armature = None
for obj in bpy.data.objects:
    print(f"  Object: {obj.name} (type: {obj.type})")
    if obj.type == 'ARMATURE':
        armature = obj

if not armature:
    print("ERROR: No armature found!")
    quit()

print(f"\n{'='*60}")
print(f"  ARMATURE: {armature.name}")
print(f"  Total bones: {len(armature.data.bones)}")
print(f"{'='*60}")

# Key bone names we care about
KEY_TERMS = ['upper_arm', 'upperarm', 'lower_arm', 'lowerarm', 'hand',
             'head', 'neck', 'spine', 'chest', 'hips',
             'shoulder', 'arm', 'finger']

bone_data = {}

print("\nALL BONES:")
print("-" * 80)
for bone in armature.data.bones:
    depth = 0
    p = bone.parent
    while p:
        depth += 1
        p = p.parent
    
    indent = "  " * depth
    # Get rest rotation as euler
    mat = bone.matrix_local
    rot = mat.to_euler('XYZ')
    rx, ry, rz = math.degrees(rot.x), math.degrees(rot.y), math.degrees(rot.z)
    
    is_key = any(term in bone.name.lower() for term in KEY_TERMS)
    marker = " ★" if is_key else ""
    
    print(f"{indent}{'├─'} {bone.name}{marker}")
    
    if is_key:
        h = bone.head_local
        t = bone.tail_local
        print(f"{indent}   rest euler: ({rx:.1f}°, {ry:.1f}°, {rz:.1f}°)")
        print(f"{indent}   head: ({h.x:.4f}, {h.y:.4f}, {h.z:.4f})")
        print(f"{indent}   tail: ({t.x:.4f}, {t.y:.4f}, {t.z:.4f})")
        print(f"{indent}   length: {bone.length:.4f}")
    
    bone_data[bone.name] = {
        "parent": bone.parent.name if bone.parent else None,
        "rest_euler_deg": [round(rx, 2), round(ry, 2), round(rz, 2)],
        "rest_euler_rad": [round(rot.x, 4), round(rot.y, 4), round(rot.z, 4)],
        "head": [round(bone.head_local.x, 4), round(bone.head_local.y, 4), round(bone.head_local.z, 4)],
        "tail": [round(bone.tail_local.x, 4), round(bone.tail_local.y, 4), round(bone.tail_local.z, 4)],
        "length": round(bone.length, 4),
    }

# Print summary of important bones
print(f"\n{'='*60}")
print("  KEY BONES SUMMARY (for animation)")
print(f"{'='*60}")

for bone in armature.data.bones:
    name_lower = bone.name.lower()
    if any(k in name_lower for k in ['upper_arm', 'upperarm', 'lower_arm', 'lowerarm',
                                       'hand', 'head', 'neck', 'spine', 'chest']):
        mat = bone.matrix_local
        rot = mat.to_euler('XYZ')
        
        # Calculate the axis direction (tail - head)
        h = bone.head_local
        t = bone.tail_local
        dx = t.x - h.x
        dy = t.y - h.y
        dz = t.z - h.z
        
        print(f"\n  {bone.name}:")
        print(f"    Parent: {bone.parent.name if bone.parent else 'NONE'}")
        print(f"    Rest rotation: x={math.degrees(rot.x):.1f}° y={math.degrees(rot.y):.1f}° z={math.degrees(rot.z):.1f}°")
        print(f"    Direction: dx={dx:.4f} dy={dy:.4f} dz={dz:.4f}")
        print(f"    Is left: {'left' in name_lower}")

# Save to JSON
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bone_data.json")
with open(out, "w") as f:
    json.dump(bone_data, f, indent=2)
print(f"\n[OK] Full bone data saved to: {out}")
print("DONE")
