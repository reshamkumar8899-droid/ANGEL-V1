/* ═══════════════════════════════════════════════════
   A.N.G.E.L — 3-D Avatar Engine
   Three.js + @pixiv/three-vrm
   ═══════════════════════════════════════════════════ */
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { VRMLoaderPlugin, VRMUtils } from '@pixiv/three-vrm';

// ── Setup scene ──────────────────────────────────────
const canvas  = document.getElementById('vrm-canvas');
const panel   = document.getElementById('avatarPanel');
const tag     = document.getElementById('avatarStateTag');
const speechEl = document.getElementById('speechIndicator');

const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.2;

const scene  = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(22, 1, 0.1, 100);
camera.position.set(0, 1.3, 3.5);
camera.lookAt(0, 1.1, 0);

// ── Lighting ─────────────────────────────────────────
// Main front light
const mainLight = new THREE.DirectionalLight(0xffffff, 1.8);
mainLight.position.set(0.5, 2, 3);
scene.add(mainLight);

// Cyan rim light from behind-left
const rimLight = new THREE.DirectionalLight(0x00d4ff, 0.8);
rimLight.position.set(-2, 1.5, -1);
scene.add(rimLight);

// Fill from below
const fillLight = new THREE.DirectionalLight(0x00d4ff, 0.3);
fillLight.position.set(0, -1, 2);
scene.add(fillLight);

// Ambient
scene.add(new THREE.AmbientLight(0x334466, 0.6));

// ── State tracking ───────────────────────────────────
let currentVrm  = null;
let clock        = new THREE.Clock();
let mouseX       = 0;
let mouseY       = 0;
let currentState = 'LISTENING';
let breathPhase  = 0;
let speakPhase   = 0;
let blinkTimer   = 0;
let blinkDuration = 0;
let isBlinking   = false;

// ── Mouse tracking ───────────────────────────────────
panel.addEventListener('mousemove', (e) => {
  const rect = panel.getBoundingClientRect();
  mouseX = ((e.clientX - rect.left) / rect.width  - 0.5) * 2;
  mouseY = ((e.clientY - rect.top)  / rect.height - 0.5) * 2;
});

// Mouse drag rotation
let isDragging = false;
let dragStartX = 0;
let modelRotY  = 0;
let dragBaseRot = 0;

panel.addEventListener('mousedown', (e) => {
  isDragging = true;
  dragStartX = e.clientX;
  dragBaseRot = modelRotY;
});
window.addEventListener('mouseup', () => { isDragging = false; });
window.addEventListener('mousemove', (e) => {
  if (isDragging) {
    modelRotY = dragBaseRot + (e.clientX - dragStartX) * 0.005;
  }
});

// ── Resize handler ───────────────────────────────────
function resize() {
  const w = panel.clientWidth;
  const h = panel.clientHeight;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();

// ── Load VRM model ───────────────────────────────────
const loader = new GLTFLoader();
loader.register((parser) => new VRMLoaderPlugin(parser));

loader.load(
  'angel.vrm',
  (gltf) => {
    const vrm = gltf.userData.vrm;
    if (!vrm) {
      console.error('[Angel3D] No VRM data in file');
      tag.textContent = 'MODEL ERROR';
      return;
    }

    VRMUtils.removeUnnecessaryJoints(gltf.scene);
    VRMUtils.removeUnnecessaryVertices(gltf.scene);

    // Rotate model to face camera (VRM faces +Z by default)
    VRMUtils.rotateVRM0(vrm);

    scene.add(vrm.scene);
    currentVrm = vrm;

    // Center camera on head
    camera.position.set(0, 1.35, 2.8);
    camera.lookAt(0, 1.15, 0);

    tag.textContent = 'LISTENING';
    console.log('[Angel3D] VRM model loaded ✓');
  },
  (progress) => {
    if (progress.total > 0) {
      const pct = Math.round(progress.loaded / progress.total * 100);
      tag.textContent = `LOADING... ${pct}%`;
    }
  },
  (error) => {
    console.error('[Angel3D] Load error:', error);
    tag.textContent = 'LOAD FAILED';
  }
);

// ── Expression helpers ───────────────────────────────
function setExpression(name, value) {
  if (!currentVrm || !currentVrm.expressionManager) return;
  try { currentVrm.expressionManager.setValue(name, value); } catch(e) {}
}

function resetExpressions() {
  if (!currentVrm || !currentVrm.expressionManager) return;
  const mgr = currentVrm.expressionManager;
  // Reset all to 0
  ['happy', 'angry', 'sad', 'surprised', 'neutral', 'aa', 'ih', 'ou', 'ee', 'oh', 'blink', 'blinkLeft', 'blinkRight'].forEach(n => {
    try { mgr.setValue(n, 0); } catch(e) {}
  });
}

// ── Blink system ─────────────────────────────────────
function updateBlink(dt) {
  if (!currentVrm) return;

  if (isBlinking) {
    blinkDuration += dt;
    if (blinkDuration < 0.06) {
      setExpression('blink', blinkDuration / 0.06);
    } else if (blinkDuration < 0.12) {
      setExpression('blink', 1.0);
    } else if (blinkDuration < 0.2) {
      setExpression('blink', 1.0 - (blinkDuration - 0.12) / 0.08);
    } else {
      setExpression('blink', 0);
      isBlinking = false;
      blinkTimer = 2 + Math.random() * 4;
    }
  } else {
    blinkTimer -= dt;
    if (blinkTimer <= 0) {
      isBlinking = true;
      blinkDuration = 0;
    }
  }
}

// ── State color map (for glow) ───────────────────────
const STATE_GLOW = {
  LISTENING:  [0, 0.82, 1],
  THINKING:   [0.96, 0.62, 0.04],
  SPEAKING:   [0.06, 0.73, 0.5],
  SEARCHING:  [0.66, 0.33, 0.97],
  WAKING:     [0, 1, 0.8],
  REMINDER:   [0, 1, 0.8],
};

// ── Main animation loop ─────────────────────────────
function animate() {
  requestAnimationFrame(animate);
  const dt = clock.getDelta();

  if (currentVrm) {
    breathPhase += dt;
    speakPhase  += dt;

    // ── Breathing (always) ──
    const breathY = Math.sin(breathPhase * 1.2) * 0.003;
    if (currentVrm.scene) {
      currentVrm.scene.position.y = breathY;
    }

    // ── Mouse rotation ──
    if (!isDragging) {
      // Slowly return to center
      modelRotY *= 0.97;
    }
    if (currentVrm.scene) {
      currentVrm.scene.rotation.y = modelRotY;
    }

    // ── Head look-at (follow mouse) ──
    if (currentVrm.lookAt) {
      const targetX = mouseX * 0.6;
      const targetY = -mouseY * 0.3 + 1.2;
      currentVrm.lookAt.target.set(targetX, targetY, 2);
    }

    // ── Blinking ──
    updateBlink(dt);

    // ── State-specific animations ──
    resetExpressions();

    switch (currentState) {
      case 'LISTENING':
        setExpression('neutral', 0.5);
        break;

      case 'THINKING':
        // Slight head tilt via lookAt offset
        setExpression('neutral', 0.3);
        const thinkSway = Math.sin(breathPhase * 0.8) * 0.08;
        if (currentVrm.lookAt) {
          currentVrm.lookAt.target.x += thinkSway;
        }
        break;

      case 'SPEAKING':
        // Mouth animation — cycle through vowel shapes
        const mouthCycle = Math.sin(speakPhase * 8) * 0.5 + 0.5;
        const mouthAlt   = Math.sin(speakPhase * 12) * 0.5 + 0.5;
        setExpression('aa', mouthCycle * 0.6);
        setExpression('oh', mouthAlt * 0.3);
        setExpression('happy', 0.2);
        // Gentle body bob
        if (currentVrm.scene) {
          currentVrm.scene.position.y = breathY + Math.sin(speakPhase * 3) * 0.004;
        }
        break;

      case 'SEARCHING':
        setExpression('neutral', 0.3);
        break;

      case 'WAKING':
        setExpression('surprised', 0.5);
        setExpression('happy', 0.3);
        break;

      case 'REMINDER':
        setExpression('happy', 0.4);
        // Mouth for speaking reminder
        const remMouth = Math.sin(speakPhase * 8) * 0.5 + 0.5;
        setExpression('aa', remMouth * 0.5);
        break;
    }

    // Re-apply blink on top
    if (isBlinking) {
      const bv = blinkDuration < 0.06 ? blinkDuration / 0.06
               : blinkDuration < 0.12 ? 1.0
               : 1.0 - (blinkDuration - 0.12) / 0.08;
      setExpression('blink', Math.max(0, bv));
    }

    // Update VRM
    currentVrm.update(dt);
  }

  // ── Rim light color follows state ──
  const glow = STATE_GLOW[currentState] || [0, 0.82, 1];
  rimLight.color.setRGB(glow[0], glow[1], glow[2]);

  renderer.render(scene, camera);
}

animate();

// ── Public API for app.js ────────────────────────────
window.setAvatarState = function(state) {
  currentState = state;
  if (tag) tag.textContent = state;

  // Show/hide speech bars
  if (speechEl) {
    speechEl.classList.toggle('active', state === 'SPEAKING' || state === 'REMINDER');
  }

  // Reset speak phase on new state
  if (state === 'SPEAKING' || state === 'REMINDER') {
    speakPhase = 0;
  }
};
