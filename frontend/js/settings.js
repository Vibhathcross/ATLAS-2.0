/**
 * ATLAS 2.0 - Settings & Control Center Controller
 */

class SettingsController {
  constructor() {
    this.modal = document.getElementById("settings-modal");
    this.openBtn = document.getElementById("control-panel-btn");
    this.closeBtn = document.getElementById("close-settings-btn");
    this.saveBtn = document.getElementById("save-settings-btn");

    this.recordedSamples = [];
    this.mediaRecorder = null;
    this.isRecording = false;
    this.isTestingMatch = false;

    this.initEvents();
    this.loadConfig();
    this.loadVoices();
    this.loadBiometricsStatus();
  }

  initEvents() {
    // Open / Close Modal
    this.openBtn.addEventListener("click", () => this.open());
    this.closeBtn.addEventListener("click", () => this.close());
    this.modal.addEventListener("click", (e) => {
      if (e.target === this.modal) this.close();
    });

    // Tab Switching
    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
        document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
        btn.classList.add("active");
        const targetTab = document.getElementById(btn.dataset.tab);
        if (targetTab) targetTab.classList.add("active");

        if (btn.dataset.tab === "tab-logs") {
          this.loadLogs();
        }
      });
    });

    // Provider Selector Change
    document.getElementById("llm-provider").addEventListener("change", (e) => {
      this.switchProviderView(e.target.value);
    });

    // Threshold range
    const thresholdInput = document.getElementById("biometrics-threshold");
    const thresholdVal = document.getElementById("threshold-val");
    thresholdInput.addEventListener("input", (e) => {
      thresholdVal.textContent = parseFloat(e.target.value).toFixed(2);
    });

    // Test Buttons
    document.getElementById("test-llm-btn").addEventListener("click", () => this.testLLM());
    document.getElementById("test-voice-btn").addEventListener("click", () => this.testVoice());
    document.getElementById("test-telegram-btn").addEventListener("click", () => this.testTelegram());
    document.getElementById("refresh-logs-btn").addEventListener("click", () => this.loadLogs());
    document.getElementById("clear-logs-btn").addEventListener("click", () => this.clearLogs());

    // Voice Biometrics Recording & Upload
    document.getElementById("record-sample-btn").addEventListener("click", () => this.toggleRecordSample());
    document.getElementById("save-enrollment-btn").addEventListener("click", () => this.submitEnrollment());
    document.getElementById("reset-profile-btn").addEventListener("click", () => this.deleteVoiceProfile());

    // Voice Biometrics Live Match Tester
    const testMatchBtn = document.getElementById("test-match-btn");
    if (testMatchBtn) {
      testMatchBtn.addEventListener("click", () => this.toggleTestVoiceMatch());
    }

    // File upload input for voice samples
    const uploadInput = document.getElementById("voice-upload-input");
    if (uploadInput) {
      uploadInput.addEventListener("change", (e) => this.handleVoiceFileUpload(e));
    }

    // Save All Config
    this.saveBtn.addEventListener("click", () => this.saveConfig());
  }

  open() {
    this.modal.classList.add("active");
    this.loadConfig();
    this.loadBiometricsStatus();
  }

  close() {
    this.modal.classList.remove("active");
  }

  switchProviderView(provider) {
    document.querySelectorAll(".provider-config").forEach(el => el.style.display = "none");
    const active = document.getElementById(`config-${provider}`);
    if (active) active.style.display = "block";
  }

  async loadConfig() {
    try {
      const res = await fetch("/api/config");
      const cfg = await res.json();
      
      // Biometrics
      const bioEnabled = document.getElementById("biometrics-enabled");
      if (bioEnabled) bioEnabled.checked = cfg.biometrics?.enabled || false;

      const commanderToggle = document.getElementById("toggle-commander-focus");
      const commanderDesc = document.getElementById("commander-focus-desc");
      if (commanderToggle) commanderToggle.checked = !!cfg.biometrics?.enabled;
      if (commanderDesc) {
        commanderDesc.textContent = cfg.biometrics?.enabled ? "Owner Locked" : "Voice Lock Off";
        commanderDesc.style.color = cfg.biometrics?.enabled ? "var(--cyan-primary)" : "var(--text-muted)";
      }

      const bioThresh = document.getElementById("biometrics-threshold");
      if (bioThresh) bioThresh.value = cfg.biometrics?.similarity_threshold || 0.72;

      const threshVal = document.getElementById("threshold-val");
      if (threshVal) threshVal.textContent = (cfg.biometrics?.similarity_threshold || 0.72).toFixed(2);

      // LLM
      const prov = cfg.llm?.provider || "gemini";
      document.getElementById("llm-provider").value = prov;
      this.switchProviderView(prov);

      document.getElementById("gemini-api-key").value = cfg.llm?.gemini_api_key || "";
      document.getElementById("gemini-model").value = cfg.llm?.gemini_model || "gemini-1.5-flash";
      document.getElementById("openrouter-api-key").value = cfg.llm?.openrouter_api_key || "";
      document.getElementById("openrouter-model").value = cfg.llm?.openrouter_model || "google/gemini-2.0-flash-exp:free";
      document.getElementById("freellmapi-url").value = cfg.llm?.freellmapi_url || "https://api.freellmapi.com/v1";
      document.getElementById("freellmapi-key").value = cfg.llm?.freellmapi_key || "";
      document.getElementById("freellmapi-model").value = cfg.llm?.freellmapi_model || "gpt-3.5-turbo";
      document.getElementById("ollama-url").value = cfg.llm?.ollama_url || "http://localhost:11434";
      document.getElementById("ollama-model").value = cfg.llm?.ollama_model || "llama3";
      document.getElementById("system-prompt").value = cfg.llm?.system_prompt || "";

      // TTS
      if (cfg.tts?.voice) document.getElementById("tts-voice-select").value = cfg.tts.voice;
      if (cfg.tts?.rate) document.getElementById("tts-rate-select").value = cfg.tts.rate;
      if (cfg.tts?.pitch) document.getElementById("tts-pitch-select").value = cfg.tts.pitch;

      // Telegram
      document.getElementById("telegram-enabled").checked = cfg.telegram?.enabled || false;
      document.getElementById("telegram-token").value = cfg.telegram?.token || "";
      document.getElementById("telegram-chat-id").value = cfg.telegram?.allowed_chat_id || "";

      // Sync top toggles
      const brainToggle = document.getElementById("toggle-brain-mode");
      if (brainToggle) brainToggle.checked = (cfg.brain_mode === "ai");
      const brainDesc = document.getElementById("brain-mode-desc");
      if (brainDesc) brainDesc.textContent = (cfg.brain_mode === "ai" ? "AI Brain" : "Predefined");

      const listenToggle = document.getElementById("toggle-listening-mode");
      if (listenToggle) listenToggle.checked = cfg.listening_mode || false;
      const listenDesc = document.getElementById("listening-mode-desc");
      if (listenDesc) listenDesc.textContent = (cfg.listening_mode ? "Active" : "Off");

      const voiceToggle = document.getElementById("toggle-voice-output");
      if (voiceToggle) voiceToggle.checked = cfg.voice_output !== false;
      const voiceDesc = document.getElementById("voice-output-desc");
      if (voiceDesc) voiceDesc.textContent = (cfg.voice_output !== false ? "Active" : "Muted");

      const queueToggle = document.getElementById("toggle-telegram-queue");
      if (queueToggle) queueToggle.checked = !!cfg.telegram_queue_access;
      const queueDesc = document.getElementById("telegram-queue-desc");
      if (queueDesc) {
        queueDesc.textContent = cfg.telegram_queue_access ? "30s Pace Active" : "Queue Access Off";
        queueDesc.style.color = cfg.telegram_queue_access ? "var(--cyan-primary)" : "var(--text-muted)";
      }

    } catch (e) {
      console.error("Failed to load config:", e);
    }
  }

  async saveConfig() {
    const configPayload = {
      brain_mode: document.getElementById("toggle-brain-mode").checked ? "ai" : "predefined",
      listening_mode: document.getElementById("toggle-listening-mode").checked,
      voice_output: document.getElementById("toggle-voice-output").checked,
      biometrics: {
        enabled: document.getElementById("biometrics-enabled").checked,
        similarity_threshold: parseFloat(document.getElementById("biometrics-threshold").value)
      },
      llm: {
        provider: document.getElementById("llm-provider").value,
        gemini_api_key: document.getElementById("gemini-api-key").value,
        gemini_model: document.getElementById("gemini-model").value,
        openrouter_api_key: document.getElementById("openrouter-api-key").value,
        openrouter_model: document.getElementById("openrouter-model").value,
        freellmapi_url: document.getElementById("freellmapi-url").value,
        freellmapi_key: document.getElementById("freellmapi-key").value,
        freellmapi_model: document.getElementById("freellmapi-model").value,
        ollama_url: document.getElementById("ollama-url").value,
        ollama_model: document.getElementById("ollama-model").value,
        system_prompt: document.getElementById("system-prompt").value
      },
      tts: {
        voice: document.getElementById("tts-voice-select").value,
        rate: document.getElementById("tts-rate-select").value,
        pitch: document.getElementById("tts-pitch-select").value
      },
      telegram: {
        enabled: document.getElementById("telegram-enabled").checked,
        token: document.getElementById("telegram-token").value,
        allowed_chat_id: document.getElementById("telegram-chat-id").value
      },
      antigravity_mode: document.getElementById("toggle-antigravity-mode") ? document.getElementById("toggle-antigravity-mode").checked : false,
      telegram_queue_access: document.getElementById("toggle-telegram-queue") ? document.getElementById("toggle-telegram-queue").checked : false
    };

    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(configPayload)
      });
      if (res.ok) {
        const commanderToggle = document.getElementById("toggle-commander-focus");
        const commanderDesc = document.getElementById("commander-focus-desc");
        const isBio = document.getElementById("biometrics-enabled").checked;
        if (commanderToggle) commanderToggle.checked = isBio;
        if (commanderDesc) {
          commanderDesc.textContent = isBio ? "Owner Locked" : "Voice Lock Off";
          commanderDesc.style.color = isBio ? "var(--cyan-primary)" : "var(--text-muted)";
        }

        this.saveBtn.textContent = "Saved ✓";
        setTimeout(() => { this.saveBtn.textContent = "Save Changes"; this.close(); }, 800);
      }
    } catch (e) {
      alert("Failed to save configuration: " + e.message);
    }
  }

  async loadVoices() {
    try {
      const res = await fetch("/api/voices");
      const data = await res.json();
      const select = document.getElementById("tts-voice-select");
      select.innerHTML = "";
      data.voices.forEach(v => {
        const opt = document.createElement("option");
        opt.value = v.id;
        opt.textContent = `${v.name} (${v.gender})`;
        select.appendChild(opt);
      });
    } catch (e) {
      console.error("Error loading voices:", e);
    }
  }

  async testVoice() {
    const voice = document.getElementById("tts-voice-select").value;
    const rate = document.getElementById("tts-rate-select").value;
    const pitch = document.getElementById("tts-pitch-select").value;
    const btn = document.getElementById("test-voice-btn");
    btn.textContent = "Synthesizing...";
    btn.disabled = true;

    try {
      const res = await fetch("/api/test-voice", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ voice, rate, pitch, text: "Greetings. I am ATLAS 2.0, ready to execute your commands." })
      });
      const data = await res.json();
      if (data.audio_b64) {
        const audio = document.getElementById("tts-player");
        audio.src = `data:audio/mp3;base64,${data.audio_b64}`;
        audio.play();
      }
    } catch (e) {
      alert("Voice test failed: " + e.message);
    } finally {
      btn.textContent = "🔊 Play Test Sample";
      btn.disabled = false;
    }
  }

  async testLLM() {
    const feedback = document.getElementById("llm-test-result");
    const provider = document.getElementById("llm-provider").value;
    feedback.textContent = "Testing...";
    feedback.style.color = "var(--cyan-primary)";

    const payload = {
      provider,
      gemini_api_key: document.getElementById("gemini-api-key").value,
      gemini_model: document.getElementById("gemini-model").value,
      openrouter_api_key: document.getElementById("openrouter-api-key").value,
      freellmapi_url: document.getElementById("freellmapi-url").value,
      freellmapi_key: document.getElementById("freellmapi-key").value,
      ollama_url: document.getElementById("ollama-url").value
    };

    try {
      const res = await fetch("/api/test-llm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      feedback.textContent = data.message;
      feedback.style.color = data.success ? "var(--neon-green)" : "var(--neon-red)";
    } catch (e) {
      feedback.textContent = "Connection error: " + e.message;
      feedback.style.color = "var(--neon-red)";
    }
  }

  async testTelegram() {
    const feedback = document.getElementById("telegram-test-result");
    const token = document.getElementById("telegram-token").value;
    feedback.textContent = "Connecting to Telegram...";
    feedback.style.color = "var(--cyan-primary)";

    try {
      const res = await fetch("/api/test-telegram", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token })
      });
      const data = await res.json();
      feedback.textContent = data.message;
      feedback.style.color = data.success ? "var(--neon-green)" : "var(--neon-red)";
    } catch (e) {
      feedback.textContent = "Error: " + e.message;
      feedback.style.color = "var(--neon-red)";
    }
  }

  // --- Voice Biometrics Studio ---

  async loadBiometricsStatus() {
    try {
      const res = await fetch("/api/biometrics/status");
      const data = await res.json();
      const statusEl = document.getElementById("enrollment-status");
      if (!statusEl) return;
      if (data.enrolled) {
        statusEl.innerHTML = "✅ Voice profile active & enrolled with Resemblyzer.";
        statusEl.style.color = "var(--neon-green)";
      } else {
        statusEl.innerHTML = "⚠️ No voice profile enrolled yet. Record or upload samples below.";
        statusEl.style.color = "var(--neon-amber)";
      }
    } catch (e) {
      console.error(e);
    }
  }

  updateRecordButtonText() {
    const btn = document.getElementById("record-sample-btn");
    if (!btn) return;
    if (this.isRecording) {
      btn.innerHTML = `⏹️ Stop Recording`;
      btn.classList.add("btn-danger");
    } else {
      btn.innerHTML = `🎙️ Record Sample (<span id="sample-count">${this.recordedSamples.length}</span>)`;
      btn.classList.remove("btn-danger");
    }
  }

  async toggleRecordSample() {
    const btn = document.getElementById("record-sample-btn");
    const statusEl = document.getElementById("enrollment-status");

    if (!this.isRecording) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: true
          }
        });

        this.enrollMicStream = stream;
        const AudioContextClass = window.AudioContext || window.webkitAudioContext;
        this.enrollAudioCtx = new AudioContextClass();
        if (this.enrollAudioCtx.state === "suspended") {
          await this.enrollAudioCtx.resume();
        }

        const source = this.enrollAudioCtx.createMediaStreamSource(stream);
        const bufferSize = 4096;
        this.enrollPcmChunks = [];
        this.enrollRecordStart = Date.now();
        this.enrollMaxPeak = 0;

        this.enrollProcessor = this.enrollAudioCtx.createScriptProcessor(bufferSize, 1, 1);
        this.enrollProcessor.onaudioprocess = (e) => {
          if (!this.isRecording) return;
          const input = e.inputBuffer.getChannelData(0);
          const copy = new Float32Array(input.length);
          for (let i = 0; i < input.length; i++) {
            const val = input[i];
            copy[i] = val;
            const abs = Math.abs(val);
            if (abs > this.enrollMaxPeak) this.enrollMaxPeak = abs;
          }
          this.enrollPcmChunks.push(copy);
        };

        source.connect(this.enrollProcessor);
        const silent = this.enrollAudioCtx.createGain();
        silent.gain.value = 0;
        this.enrollProcessor.connect(silent);
        silent.connect(this.enrollAudioCtx.destination);

        this.isRecording = true;
        this.updateRecordButtonText();

        if (statusEl) {
          statusEl.innerHTML = `<span style="color:#00f2fe;">🔴 Recording voice... Speak clearly into your mic!</span>`;
        }

        this.enrollTimer = setInterval(() => {
          if (!this.isRecording) {
            clearInterval(this.enrollTimer);
            return;
          }
          const secs = ((Date.now() - this.enrollRecordStart) / 1000).toFixed(1);
          const peakPct = Math.round(this.enrollMaxPeak * 100);
          btn.innerHTML = `⏹️ Stop Recording (${secs}s · Vol: ${peakPct}%)`;
        }, 100);

      } catch (e) {
        alert("Microphone permission denied or not available: " + e.message);
      }
    } else {
      // STOP RECORDING
      clearInterval(this.enrollTimer);
      this.isRecording = false;
      this.updateRecordButtonText();

      if (this.enrollProcessor) {
        try { this.enrollProcessor.disconnect(); } catch (e) {}
        this.enrollProcessor = null;
      }
      if (this.enrollMicStream) {
        try { this.enrollMicStream.getTracks().forEach(t => t.stop()); } catch (e) {}
        this.enrollMicStream = null;
      }

      const inputSampleRate = this.enrollAudioCtx ? this.enrollAudioCtx.sampleRate : 48000;
      if (this.enrollAudioCtx) {
        try { this.enrollAudioCtx.close(); } catch (e) {}
        this.enrollAudioCtx = null;
      }

      if (statusEl) {
        statusEl.textContent = "Processing and verifying audio quality...";
        statusEl.style.color = "var(--cyan-primary)";
      }

      let totalSamples = 0;
      for (const chunk of this.enrollPcmChunks) totalSamples += chunk.length;

      if (totalSamples < inputSampleRate * 0.7) {
        if (statusEl) {
          statusEl.innerHTML = `⚠️ <b style="color:var(--neon-amber)">Recording too short (< 0.7s).</b> Please speak a phrase for at least 1-3 seconds.`;
        }
        return;
      }

      const merged = new Float32Array(totalSamples);
      let offset = 0;
      for (const chunk of this.enrollPcmChunks) {
        merged.set(chunk, offset);
        offset += chunk.length;
      }

      const peak = this.enrollMaxPeak;
      if (peak < 0.03) {
        if (statusEl) {
          statusEl.innerHTML = `⚠️ <b style="color:var(--neon-amber)">Audio too quiet (Peak: ${Math.round(peak * 100)}%).</b> Please speak louder or closer to the mic.`;
        }
        return;
      }

      // Resample to standard 16,000 Hz Mono
      const targetSr = 16000;
      const ratio = inputSampleRate / targetSr;
      const targetLength = Math.round(totalSamples / ratio);
      const resampled = new Float32Array(targetLength);
      for (let i = 0; i < targetLength; i++) {
        const srcIdx = Math.min(Math.round(i * ratio), totalSamples - 1);
        resampled[i] = merged[srcIdx];
      }

      // Volume normalization for optimal embedding extraction
      let maxVal = 0;
      for (let i = 0; i < resampled.length; i++) {
        const a = Math.abs(resampled[i]);
        if (a > maxVal) maxVal = a;
      }
      if (maxVal > 0.04 && maxVal < 0.8) {
        const boost = 0.85 / maxVal;
        for (let i = 0; i < resampled.length; i++) resampled[i] *= boost;
      }

      // Generate genuine standard 16-bit Mono PCM WAV
      const wavBlob = encodePcmToWavBlob(resampled, targetSr);
      const durationSecs = (resampled.length / targetSr).toFixed(1);
      wavBlob.durationSecs = durationSecs;
      wavBlob.peakVolume = Math.round(peak * 100);

      this.recordedSamples.push(wavBlob);
      this.updateRecordButtonText();
      this.renderSamplesList();

      if (statusEl) {
        statusEl.innerHTML = `✅ Captured sample #${this.recordedSamples.length} (${durationSecs}s · Vol: ${Math.round(peak * 100)}%). Listen to it below or record more!`;
        statusEl.style.color = "var(--neon-green)";
      }
    }
  }

  async handleVoiceFileUpload(e) {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const statusEl = document.getElementById("enrollment-status");
    if (statusEl) {
      statusEl.textContent = "Decoding & converting audio files...";
      statusEl.style.color = "var(--cyan-primary)";
    }

    for (let i = 0; i < files.length; i++) {
      try {
        const wavBlob = await convertBlobToPcmWav(files[i]);
        wavBlob.name = files[i].name;
        this.recordedSamples.push(wavBlob);
      } catch (err) {
        console.warn("Could not resample audio file, keeping original:", files[i].name);
        this.recordedSamples.push(files[i]);
      }
    }

    this.updateRecordButtonText();
    this.renderSamplesList();
    if (statusEl) {
      statusEl.textContent = `Added ${files.length} audio file(s). Ready to enroll!`;
      statusEl.style.color = "var(--neon-green)";
    }
  }

  renderSamplesList() {
    const container = document.getElementById("samples-preview-list");
    if (!container) return;

    if (this.recordedSamples.length === 0) {
      container.innerHTML = "";
      return;
    }

    container.innerHTML = "";
    this.recordedSamples.forEach((sample, index) => {
      const item = document.createElement("div");
      item.className = "sample-preview-item";
      
      const audioUrl = URL.createObjectURL(sample);
      const name = sample.name || `Voice Sample #${index + 1}`;
      const dur = sample.durationSecs ? `${sample.durationSecs}s` : `${Math.round(sample.size / 1024)} KB`;
      const volTag = sample.peakVolume !== undefined ? ` · Vol ${sample.peakVolume}%` : '';

      item.innerHTML = `
        <div class="sample-info" style="display:flex; align-items:center; gap:8px;">
          <span class="sample-title" style="font-weight:600;">🎙️ ${escapeHtml(name)}</span>
          <span style="font-size:11px; color:var(--cyan-primary); background:rgba(0,242,254,0.1); padding:2px 6px; border-radius:4px;">${dur}${volTag}</span>
        </div>
        <div class="sample-actions" style="display:flex; align-items:center; gap:8px; margin-top:6px;">
          <audio src="${audioUrl}" controls preload="auto" style="height:32px; width:260px; outline:none;"></audio>
          <button class="sample-remove-btn btn btn-danger" data-idx="${index}" title="Remove this sample" style="padding:4px 10px; font-size:12px; cursor:pointer;">✕</button>
        </div>
      `;

      container.appendChild(item);
    });

    // Remove handlers
    container.querySelectorAll(".sample-remove-btn").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const idx = parseInt(e.target.dataset.idx);
        this.recordedSamples.splice(idx, 1);
        this.updateRecordButtonText();
        this.renderSamplesList();
      });
    });
  }

  async submitEnrollment() {
    const statusEl = document.getElementById("enrollment-status");
    const saveBtn = document.getElementById("save-enrollment-btn");

    if (this.recordedSamples.length === 0) {
      if (statusEl) {
        statusEl.textContent = "⚠️ Please record at least 1 voice sample or upload an audio file first.";
        statusEl.style.color = "var(--neon-amber)";
      }
      return;
    }

    if (saveBtn) {
      saveBtn.textContent = "Processing ML Embeddings...";
      saveBtn.disabled = true;
    }
    if (statusEl) {
      statusEl.textContent = "Extracting 256-D d-vector embeddings with Resemblyzer ML model...";
      statusEl.style.color = "var(--cyan-primary)";
    }

    const formData = new FormData();
    this.recordedSamples.forEach((blob, i) => {
      const filename = `sample_${i}.wav`;
      formData.append("files", blob, filename);
    });

    try {
      const res = await fetch("/api/biometrics/enroll", {
        method: "POST",
        body: formData
      });
      const data = await res.json();
      if (data.success) {
        if (statusEl) {
          statusEl.textContent = "✅ " + data.message;
          statusEl.style.color = "var(--neon-green)";
        }
        const bioLock = document.getElementById("biometrics-enabled");
        if (bioLock) bioLock.checked = true;

        const commanderToggle = document.getElementById("toggle-commander-focus");
        const commanderDesc = document.getElementById("commander-focus-desc");
        if (commanderToggle) commanderToggle.checked = true;
        if (commanderDesc) {
          commanderDesc.textContent = "Owner Locked";
          commanderDesc.style.color = "var(--cyan-primary)";
        }

        this.recordedSamples = [];
        this.updateRecordButtonText();
        this.renderSamplesList();
        this.loadBiometricsStatus();
      } else {
        if (statusEl) {
          statusEl.textContent = "❌ Enrollment failed: " + data.message;
          statusEl.style.color = "var(--neon-red)";
        }
      }
    } catch (e) {
      console.error(e);
      if (statusEl) {
        statusEl.textContent = "Enrollment error: " + e.message;
        statusEl.style.color = "var(--neon-red)";
      }
    } finally {
      if (saveBtn) {
        saveBtn.textContent = "Enroll Voice Profile";
        saveBtn.disabled = false;
      }
    }
  }

  async deleteVoiceProfile() {
    if (!confirm("Are you sure you want to remove the enrolled voice profile?")) return;
    try {
      const res = await fetch("/api/biometrics/profile", { method: "DELETE" });
      const data = await res.json();

      // Clear recorded samples and preview UI
      this.recordedSamples = [];
      this.updateRecordButtonText();
      this.renderSamplesList();

      // Reset enrollment status
      const statusEl = document.getElementById("enrollment-status");
      if (statusEl) {
        statusEl.innerHTML = "⚠️ Previous voice profile deleted. Ready to record new voice samples below.";
        statusEl.style.color = "var(--neon-amber)";
      }

      // Turn OFF Commander Focus in settings and main panel
      const bioModalCheckbox = document.getElementById("biometrics-enabled");
      if (bioModalCheckbox) bioModalCheckbox.checked = false;
      const commanderToggle = document.getElementById("toggle-commander-focus");
      const commanderDesc = document.getElementById("commander-focus-desc");
      if (commanderToggle) commanderToggle.checked = false;
      if (commanderDesc) {
        commanderDesc.textContent = "Voice Lock Off";
        commanderDesc.style.color = "var(--text-muted)";
      }

      this.loadBiometricsStatus();
    } catch (e) {
      alert("Error: " + e.message);
    }
  }

  // --- Live Voice Match Tester ---

  async toggleTestVoiceMatch() {
    const btn = document.getElementById("test-match-btn");
    const statusEl = document.getElementById("tester-status");
    const gaugeWrap = document.getElementById("match-gauge-container");
    const gaugeFill = document.getElementById("gauge-fill-bar");
    const gaugePin = document.getElementById("gauge-threshold-line");
    const gaugeBadge = document.getElementById("gauge-result-badge");
    const gaugeScore = document.getElementById("gauge-score-text");
    const gaugeDetail = document.getElementById("gauge-detail-msg");
    const gaugeThreshLabel = document.getElementById("gauge-threshold-label");

    if (this.isTestingMatch) return;

    try {
      this.isTestingMatch = true;
      btn.textContent = "Listening... Speak (3s)";
      btn.classList.add("btn-danger");
      if (statusEl) {
        statusEl.textContent = "🎙️ Listening... Say 'Atlas test voice' or any command.";
        statusEl.style.color = "var(--cyan-primary)";
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: true
        }
      });

      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      const testAudioCtx = new AudioContextClass();
      if (testAudioCtx.state === "suspended") await testAudioCtx.resume();

      const source = testAudioCtx.createMediaStreamSource(stream);
      const bufferSize = 4096;
      const chunks = [];
      const testProcessor = testAudioCtx.createScriptProcessor(bufferSize, 1, 1);

      testProcessor.onaudioprocess = (e) => {
        const input = e.inputBuffer.getChannelData(0);
        chunks.push(new Float32Array(input));
      };

      source.connect(testProcessor);
      const silent = testAudioCtx.createGain();
      silent.gain.value = 0;
      testProcessor.connect(silent);
      silent.connect(testAudioCtx.destination);

      // Record for 3.0 seconds
      setTimeout(async () => {
        try { testProcessor.disconnect(); } catch (e) {}
        try { stream.getTracks().forEach(t => t.stop()); } catch (e) {}
        const sampleRate = testAudioCtx.sampleRate || 48000;
        try { testAudioCtx.close(); } catch (e) {}

        btn.textContent = "Analyzing Match...";
        btn.disabled = true;
        if (statusEl) {
          statusEl.textContent = "Computing neural embeddings and cosine similarity...";
        }

        try {
          let totalLen = 0;
          for (const c of chunks) totalLen += c.length;
          const merged = new Float32Array(totalLen);
          let off = 0;
          for (const c of chunks) {
            merged.set(c, off);
            off += c.length;
          }

          // Resample to 16kHz
          const targetSr = 16000;
          const ratio = sampleRate / targetSr;
          const targetLength = Math.round(totalLen / ratio);
          const resampled = new Float32Array(targetLength);
          for (let i = 0; i < targetLength; i++) {
            const srcIdx = Math.min(Math.round(i * ratio), totalLen - 1);
            resampled[i] = merged[srcIdx];
          }

          const wavBlob = encodePcmToWavBlob(resampled, targetSr);
          const formData = new FormData();
          formData.append("file", wavBlob, "test_sample.wav");

          const res = await fetch("/api/biometrics/test", {
            method: "POST",
            body: formData
          });
          const data = await res.json();

          if (gaugeWrap) gaugeWrap.style.display = "block";
          btn.textContent = "🎙️ Test My Voice Match";
          btn.disabled = false;
          btn.classList.remove("btn-danger");
          this.isTestingMatch = false;

          if (!data.success) {
            if (statusEl) {
              statusEl.textContent = data.message;
              statusEl.style.color = "var(--neon-red)";
            }
            return;
          }

          const pct = Math.round(data.similarity * 100);
          const threshPct = Math.round(data.threshold * 100);

          if (gaugePin) gaugePin.style.left = `${threshPct}%`;
          if (gaugeThreshLabel) gaugeThreshLabel.textContent = `Threshold: ${threshPct}%`;
          if (gaugeFill) gaugeFill.style.width = `${Math.min(100, Math.max(0, pct))}%`;
          if (gaugeScore) gaugeScore.textContent = `${pct}% Similarity`;

          if (data.is_match) {
            if (gaugeFill) {
              gaugeFill.style.background = "var(--neon-green)";
              gaugeFill.style.color = "var(--neon-green)";
            }
            if (gaugeBadge) {
              gaugeBadge.textContent = "✅ VERIFIED OWNER";
              gaugeBadge.style.color = "var(--neon-green)";
            }
            if (gaugeDetail) {
              gaugeDetail.innerHTML = `🎉 <b style="color:var(--neon-green)">Match Confirmed!</b> Confidence <b>${data.similarity.toFixed(2)}</b> exceeds threshold <b>${data.threshold.toFixed(2)}</b>. ATLAS recognizes your voice!`;
            }
            if (statusEl) {
              statusEl.textContent = "Voice match confirmed!";
              statusEl.style.color = "var(--neon-green)";
            }
          } else {
            if (gaugeFill) {
              gaugeFill.style.background = pct >= (threshPct - 10) ? "var(--neon-amber)" : "var(--neon-red)";
              gaugeFill.style.color = gaugeFill.style.background;
            }
            if (gaugeBadge) {
              gaugeBadge.textContent = "❌ NO MATCH";
              gaugeBadge.style.color = "var(--neon-red)";
            }
            if (gaugeDetail) {
              gaugeDetail.innerHTML = `⚠️ <b style="color:var(--neon-red)">Below Threshold.</b> Confidence <b>${data.similarity.toFixed(2)}</b> is below required <b>${data.threshold.toFixed(2)}</b>.<br><small style="color:var(--text-muted)">Tip: Speak clearly, record 2-3 varied phrases for enrollment, or adjust threshold slightly.</small>`;
            }
            if (statusEl) {
              statusEl.textContent = "Voice did not meet similarity threshold.";
              statusEl.style.color = "var(--neon-red)";
            }
          }

        } catch (err) {
          if (statusEl) {
            statusEl.textContent = "Verification error: " + err.message;
            statusEl.style.color = "var(--neon-red)";
          }
          btn.textContent = "🎙️ Test My Voice Match";
          btn.disabled = false;
          btn.classList.remove("btn-danger");
          this.isTestingMatch = false;
        }
      }, 3000);

    } catch (err) {
      alert("Microphone error: " + err.message);
      btn.textContent = "🎙️ Test My Voice Match";
      btn.classList.remove("btn-danger");
      this.isTestingMatch = false;
    }
  }
}

/**
 * Encodes Float32 PCM samples into a genuine 16-bit Mono PCM WAV Blob.
 */
function encodePcmToWavBlob(samples, sampleRate = 16000) {
  const byteLength = samples.length * 2;
  const wavBuffer = new ArrayBuffer(44 + byteLength);
  const view = new DataView(wavBuffer);

  function writeString(offset, str) {
    for (let i = 0; i < str.length; i++) {
      view.setUint8(offset + i, str.charCodeAt(i));
    }
  }

  writeString(0, 'RIFF');
  view.setUint32(4, 36 + byteLength, true);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); // PCM format
  view.setUint16(22, 1, true); // 1 channel (Mono)
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true); // block align
  view.setUint16(34, 16, true); // 16 bits per sample
  writeString(36, 'data');
  view.setUint32(40, byteLength, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }

  return new Blob([wavBuffer], { type: 'audio/wav' });
}

/**
 * Converts arbitrary browser Audio Blob to genuine 16kHz Mono 16-bit PCM WAV Blob using Web Audio API.
 */
async function convertBlobToPcmWav(blob) {
  const arrayBuffer = await blob.arrayBuffer();
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);

  const targetSampleRate = 16000;
  const numChannels = 1;
  const length = Math.ceil(audioBuffer.duration * targetSampleRate);

  const offlineCtx = new OfflineAudioContext(numChannels, length, targetSampleRate);
  const source = offlineCtx.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(offlineCtx.destination);
  source.start(0);

  const renderedBuffer = await offlineCtx.startRendering();
  const channelData = renderedBuffer.getChannelData(0);

  audioCtx.close();
  return encodePcmToWavBlob(channelData, targetSampleRate);
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

window.encodePcmToWavBlob = encodePcmToWavBlob;
window.convertBlobToPcmWav = convertBlobToPcmWav;
window.escapeHtml = escapeHtml;
