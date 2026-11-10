import json
with open('bone_data.json') as f:
    data = json.load(f)

arms = ['J_Bip_L_Shoulder', 'J_Bip_L_UpperArm', 'J_Bip_L_LowerArm', 'J_Bip_L_Hand',
        'J_Bip_R_Shoulder', 'J_Bip_R_UpperArm', 'J_Bip_R_LowerArm', 'J_Bip_R_Hand']

for name in arms:
    if name in data:
        b = data[name]
        h, t = b['head'], b['tail']
        dx = t[0]-h[0]
        dy = t[1]-h[1]
        dz = t[2]-h[2]
        print(f"{name}:")
        print(f"  head={h}  tail={t}")
        print(f"  rest euler deg={b['rest_euler_deg']}")
        print(f"  bone direction: dx={dx:.4f} dy={dy:.4f} dz={dz:.4f}")
        print()
