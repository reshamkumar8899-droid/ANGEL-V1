"""
Use Blender to pose the VRM model and export the exact bone rotations needed.
This creates proper animation poses for the Three.js VRM viewer.
"""
import bpy
import os
import json
import math
from mathutils import Euler, Quaternion, Vector

VRM_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "angel.vrm")

# Clear and import
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=VRM_PATH)

# Find armature
armature = None
for obj in bpy.data.objects:
    if obj.type == 'ARMATURE':
        armature = obj
        break

if not armature:
    print("ERROR: No armature")
    quit()

# Set active and enter pose mode
bpy.context.view_layer.objects.active = armature
bpy.ops.object.mode_set(mode='POSE')

# VRM humanoid bone name mapping for this model (VRoid Studio naming)
VRM_BONES = {
    'hips': 'J_Bip_C_Hips',
    'spine': 'J_Bip_C_Spine',
    'chest': 'J_Bip_C_Chest',
    'upperChest': 'J_Bip_C_UpperChest',
    'neck': 'J_Bip_C_Neck',
    'head': 'J_Bip_C_Head',
    'leftShoulder': 'J_Bip_L_Shoulder',
    'leftUpperArm': 'J_Bip_L_UpperArm',
    'leftLowerArm': 'J_Bip_L_LowerArm',
    'leftHand': 'J_Bip_L_Hand',
    'rightShoulder': 'J_Bip_R_Shoulder',
    'rightUpperArm': 'J_Bip_R_UpperArm',
    'rightLowerArm': 'J_Bip_R_LowerArm',
    'rightHand': 'J_Bip_R_Hand',
}

def get_pose_bone(vrm_name):
    blender_name = VRM_BONES.get(vrm_name, vrm_name)
    return armature.pose.bones.get(blender_name)

def set_bone_rotation(vrm_name, x_deg, y_deg, z_deg):
    pb = get_pose_bone(vrm_name)
    if pb:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (math.radians(x_deg), math.radians(y_deg), math.radians(z_deg))

def read_bone_world_pos(vrm_name):
    pb = get_pose_bone(vrm_name)
    if pb:
        return list(armature.matrix_world @ pb.head)
    return None

# First, get T-pose hand positions
print("\n=== T-POSE (default) ===")
lhand_tpose = read_bone_world_pos('leftHand')
rhand_tpose = read_bone_world_pos('rightHand')
print(f"Left hand:  {lhand_tpose}")
print(f"Right hand: {rhand_tpose}")

# Now create the IDLE pose (arms at sides)
# In VRM 0.x after GLTF import, we need to figure out which axis lowers the arm
# Let's test: rotate rightUpperArm on each axis and see where the hand moves

results = {}

print("\n=== TESTING ROTATION AXES ===")
axes = [('X', 45, 0, 0), ('Y', 0, 45, 0), ('Z', 0, 0, 45),
        ('X', -45, 0, 0), ('Y', 0, -45, 0), ('Z', 0, 0, -45),
        ('Z', 90, 0, 0), ('Z', 0, 0, -90)]

for label, x, y, z in axes:
    # Reset all poses
    for pb in armature.pose.bones:
        pb.rotation_mode = 'XYZ'
        pb.rotation_euler = (0, 0, 0)
    
    # Apply test rotation
    set_bone_rotation('rightUpperArm', x, y, z)
    bpy.context.view_layer.update()
    
    rhand_pos = read_bone_world_pos('rightHand')
    if rhand_pos and rhand_tpose:
        dx = rhand_pos[0] - rhand_tpose[0]
        dy = rhand_pos[1] - rhand_tpose[1]
        dz = rhand_pos[2] - rhand_tpose[2]
        print(f"  rightUpperArm rot({x},{y},{z}) => hand moved: dx={dx:.3f} dy={dy:.3f} dz={dz:.3f}")
        results[f"test_R_{label}_{x}_{y}_{z}"] = {
            "hand_pos": [round(v,4) for v in rhand_pos],
            "hand_delta": [round(dx,4), round(dy,4), round(dz,4)]
        }

# Reset
for pb in armature.pose.bones:
    pb.rotation_mode = 'XYZ'
    pb.rotation_euler = (0, 0, 0)

# Now test left arm
print("\n=== LEFT ARM TESTS ===")
for label, x, y, z in axes:
    for pb in armature.pose.bones:
        pb.rotation_euler = (0, 0, 0)
    
    set_bone_rotation('leftUpperArm', x, y, z)
    bpy.context.view_layer.update()
    
    lhand_pos = read_bone_world_pos('leftHand')
    if lhand_pos and lhand_tpose:
        dx = lhand_pos[0] - lhand_tpose[0]
        dy = lhand_pos[1] - lhand_tpose[1]
        dz = lhand_pos[2] - lhand_tpose[2]
        print(f"  leftUpperArm rot({x},{y},{z}) => hand moved: dx={dx:.3f} dy={dy:.3f} dz={dz:.3f}")

# Now create the actual IDLE pose
print("\n=== CREATING IDLE POSE ===")
for pb in armature.pose.bones:
    pb.rotation_euler = (0, 0, 0)

# Based on the tests above, we'll know which axis brings arms down
# For now, try the likely candidate: X rotation brings arm forward/down in VRM
# Z rotation should bring it toward/away body

# Create ideal idle: arms slightly in front, at sides
# We need X positive = forward pitch, Z = toward body
set_bone_rotation('rightUpperArm', 10, 0, 70)
set_bone_rotation('rightLowerArm', 5, 0, 0)
set_bone_rotation('leftUpperArm', 10, 0, -70)
set_bone_rotation('leftLowerArm', 5, 0, 0)

bpy.context.view_layer.update()

rhand_idle = read_bone_world_pos('rightHand')
lhand_idle = read_bone_world_pos('leftHand')
print(f"Right hand idle: {rhand_idle}")
print(f"Left hand idle:  {lhand_idle}")

# Save the test results
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pose_tests.json")
with open(out, "w") as f:
    json.dump(results, f, indent=2)

print(f"\n[OK] Results saved to {out}")
print("DONE")
