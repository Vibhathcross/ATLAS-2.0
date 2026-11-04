/**
 * ATLAS 2.0 - 3D Cellular Organic Rotating Blob
 * Powered by Three.js
 */

class CellularBlob {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.state = "idle";
    this.audioAmplitude = 0;
    this.time = 0;
    
    if (!this.container || typeof THREE === "undefined") {
      console.warn("[CellularBlob] Three.js not loaded or container not found. Skipping 3D initialization.");
      return;
    }
    
    // State Color Themes - Calm, Controlled Organic Reactor
    this.themes = {
      idle: {
        coreColor: 0x00f2fe,
        cellColor: 0x4facfe,
        glowColor: 0x0088ff,
        rotationSpeed: 0.005,
        noiseScale: 0.10,
        noiseSpeed: 0.65
      },
      listening: {
        coreColor: 0x10b981,
        cellColor: 0x34d399,
        glowColor: 0x059669,
        rotationSpeed: 0.008,
        noiseScale: 0.16,
        noiseSpeed: 1.1
      },
      processing: {
        coreColor: 0xf59e0b,
        cellColor: 0xfbbf24,
        glowColor: 0xd97706,
        rotationSpeed: 0.012,
        noiseScale: 0.20,
        noiseSpeed: 1.4
      },
      speaking: {
        coreColor: 0x8b5cf6,
        cellColor: 0xa78bfa,
        glowColor: 0x6d28d9,
        rotationSpeed: 0.009,
        noiseScale: 0.16,
        noiseSpeed: 1.1
      },
      denied: {
        coreColor: 0xef4444,
        cellColor: 0xf87171,
        glowColor: 0xdc2626,
        rotationSpeed: 0.012,
        noiseScale: 0.18,
        noiseSpeed: 1.3
      }
    };

    this.currentTheme = { ...this.themes.idle };
    this.targetTheme = { ...this.themes.idle };

    this.initScene();
    this.createCellularMesh();
    this.setupResize();
    this.animate();
  }

  initScene() {
    this.scene = new THREE.Scene();
    
    const width = this.container.clientWidth || window.innerWidth;
    const height = this.container.clientHeight || window.innerHeight;

    this.camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
    this.camera.position.z = 6.2;

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setSize(width, height);
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.container.appendChild(this.renderer.domElement);

    // Dynamic Lighting
    this.ambientLight = new THREE.AmbientLight(0x111625, 2.0);
    this.scene.add(this.ambientLight);

    this.pointLight1 = new THREE.PointLight(this.currentTheme.coreColor, 3, 20);
    this.pointLight1.position.set(4, 4, 4);
    this.scene.add(this.pointLight1);

    this.pointLight2 = new THREE.PointLight(this.currentTheme.glowColor, 2, 20);
    this.pointLight2.position.set(-4, -4, -4);
    this.scene.add(this.pointLight2);
  }

  createCellularMesh() {
    this.group = new THREE.Group();
    this.scene.add(this.group);

    // 1. Cellular 3D Translucent Organic Blob (Outer)
    const cellularGeom = new THREE.IcosahedronGeometry(1.30, 24);
    this.originalCellularVertices = cellularGeom.attributes.position.clone();

    this.cellularMaterial = new THREE.MeshPhysicalMaterial({
      color: this.currentTheme.cellColor,
      emissive: this.currentTheme.glowColor,
      emissiveIntensity: 0.35,
      roughness: 0.2,
      metalness: 0.1,
      clearcoat: 0.9,
      clearcoatRoughness: 0.15,
      wireframe: false,
      transparent: true,
      opacity: 0.40,
      blending: THREE.NormalBlending
    });
    this.cellularMesh = new THREE.Mesh(cellularGeom, this.cellularMaterial);
    this.group.add(this.cellularMesh);

    // 2. Cybernetic Cellular Points / Nodes
    const pointsGeom = new THREE.IcosahedronGeometry(1.40, 16);
    this.originalPointsVertices = pointsGeom.attributes.position.clone();
    this.pointsMaterial = new THREE.PointsMaterial({
      color: this.currentTheme.coreColor,
      size: 0.042,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending
    });
    this.pointsMesh = new THREE.Points(pointsGeom, this.pointsMaterial);
    this.group.add(this.pointsMesh);

    // 3. Subtle Orbital Rim / Ring
    const ringGeom = new THREE.TorusGeometry(1.78, 0.015, 16, 100);
    this.ringMaterial = new THREE.MeshBasicMaterial({
      color: this.currentTheme.coreColor,
      transparent: true,
      opacity: 0.45,
      blending: THREE.AdditiveBlending
    });
    this.ringMesh = new THREE.Mesh(ringGeom, this.ringMaterial);
    this.ringMesh.rotation.x = Math.PI / 3;
    this.group.add(this.ringMesh);
  }

  // Simplex-inspired 3D harmonic deformation with strict anti-clipping clamp
  deformGeometry(geometry, originalVertices, time, scale, intensity) {
    const pos = geometry.attributes.position;
    const orig = originalVertices;
    const count = pos.count;

    for (let i = 0; i < count; i++) {
      const u = orig.getX(i);
      const v = orig.getY(i);
      const w = orig.getZ(i);

      // Multi-frequency harmonic wave noise
      const wave1 = Math.sin(u * scale + time) * Math.cos(v * scale + time * 0.8);
      const wave2 = Math.sin(w * scale * 1.5 + time * 1.2) * 0.5;
      
      // Strict dampening: prevents any over-reaction or bloated distortions
      const rawDisplacement = (wave1 + wave2) * intensity;
      const displacement = Math.max(Math.min(rawDisplacement, 0.08), -0.08);

      pos.setXYZ(
        i,
        u + u * displacement,
        v + v * displacement,
        w + w * displacement
      );
    }
    pos.needsUpdate = true;
    geometry.computeVertexNormals();
  }

  setState(newState, detail = "") {
    if (this.themes[newState]) {
      this.state = newState;
      this.targetTheme = this.themes[newState];
    }
  }

  setAudioAmplitude(amp) {
    const clamped = Math.min(Math.max(amp, 0), 1.0);
    if (clamped > this.audioAmplitude) {
      // Fast attack: react immediately to external sounds & spoken words
      this.audioAmplitude += (clamped - this.audioAmplitude) * 0.45;
    } else {
      // Smooth decay: gentle organic easing back
      this.audioAmplitude += (clamped - this.audioAmplitude) * 0.14;
    }
  }

  pulse(magnitude = 0.35) {
    this.audioAmplitude = Math.min(this.audioAmplitude + magnitude, 0.85);
  }

  setupResize() {
    window.addEventListener("resize", () => {
      const width = this.container.clientWidth || window.innerWidth;
      const height = this.container.clientHeight || window.innerHeight;
      this.camera.aspect = width / height;
      this.camera.updateProjectionMatrix();
      this.renderer.setSize(width, height);
    });
  }

  lerp(start, end, amt) {
    return (1 - amt) * start + amt * end;
  }

  lerpColor(c1, c2, amt) {
    const col1 = new THREE.Color(c1);
    const col2 = new THREE.Color(c2);
    col1.lerp(col2, amt);
    return col1;
  }

  animate = () => {
    requestAnimationFrame(this.animate);

    // Smoothly interpolate theme transitions
    const lerpRate = 0.05;
    this.currentTheme.rotationSpeed = this.lerp(this.currentTheme.rotationSpeed, this.targetTheme.rotationSpeed, lerpRate);
    this.currentTheme.noiseScale = this.lerp(this.currentTheme.noiseScale, this.targetTheme.noiseScale, lerpRate);
    this.currentTheme.noiseSpeed = this.lerp(this.currentTheme.noiseSpeed, this.targetTheme.noiseSpeed, lerpRate);

    const activeColor = this.lerpColor(this.cellularMaterial.color, this.targetTheme.cellColor, lerpRate);
    const activeGlow = this.lerpColor(this.pointsMaterial.color, this.targetTheme.coreColor, lerpRate);
    
    this.cellularMaterial.color.copy(activeColor);
    this.cellularMaterial.emissive.copy(activeGlow);
    this.pointsMaterial.color.copy(activeGlow);
    this.ringMaterial.color.copy(activeGlow);
    this.pointLight1.color.copy(activeGlow);

    // Update time & rotation
    const delta = 0.016;
    this.time += delta * this.currentTheme.noiseSpeed;

    this.group.rotation.y += this.currentTheme.rotationSpeed;
    this.group.rotation.x += this.currentTheme.rotationSpeed * 0.5;
    this.pointsMesh.rotation.z -= this.currentTheme.rotationSpeed * 0.6;
    this.ringMesh.rotation.z += this.currentTheme.rotationSpeed * 1.2;

    // Dynamic sound pulsation on cellular blob, points, and orbital rim
    const audioAmp = this.audioAmplitude;
    const blobPulse = 1.0 + (audioAmp * 0.28);
    this.cellularMesh.scale.set(blobPulse, blobPulse, blobPulse);

    const pointsPulse = 1.0 + (audioAmp * 0.32);
    this.pointsMesh.scale.set(pointsPulse, pointsPulse, pointsPulse);

    const ringPulse = 1.0 + (audioAmp * 0.16);
    this.ringMesh.scale.set(ringPulse, ringPulse, ringPulse);

    // Audio-reactive emissive glow flare
    this.cellularMaterial.emissiveIntensity = 0.35 + (audioAmp * 0.65);
    this.pointLight1.intensity = 3.0 + (audioAmp * 4.0);

    // Controlled, light organic surface deformation
    const intensity = this.currentTheme.noiseScale + (audioAmp * 0.22);

    // Deform cellular 3D blob and points lightly with external sound
    this.deformGeometry(
      this.cellularMesh.geometry,
      this.originalCellularVertices,
      this.time,
      1.3,
      intensity * 0.18
    );

    this.deformGeometry(
      this.pointsMesh.geometry,
      this.originalPointsVertices,
      this.time,
      1.3,
      intensity * 0.18
    );

    this.renderer.render(this.scene, this.camera);
  };
}
