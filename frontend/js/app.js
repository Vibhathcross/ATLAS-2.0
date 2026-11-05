/**
 * ATLAS 2.0 - Main Frontend Application
 */

class AtlasApp {
  constructor() {
    this.ws = null;
    this.blob = null;
    this.settings = null;
    this.speechRecognition = null;
    this.audioContext = null;
    this.audioAnalyser = null;
    this.micStream = null;
    this.isListeningActive = false;
    this.isVoiceTypingOnly = false;
    this.isSpeaking = false;
    this.isBargeInEnabled = true;
    this.currentPostActionCallback = null;

    // UI elements
    this.stateBar = document.getElementById("state-bar");
    this.stateText = document.getElementById("state-text");
    this.stateDetail = document.getElementById("state-detail");
    this.ttsPlayer = document.getElementById("tts-player");
    this.cmdInput = document.getElementById("atlas-cmd-input");
    this.wormholeBtn = document.getElementById("wormhole-icon");
    this.stopBtn = document.getElementById("stop-processing-btn");
    this.micTypingBtn = document.getElementById("search-icon");
    this.currentState = "idle";

    // Drawers
    this.drawerLeft = document.getElementById("drawer-left");
    this.drawerRight = document.getElementById("drawer-right");
    this.arrowLeft = document.getElementById("drawer-toggle-left");
    this.arrowRight = document.getElementById("drawer-toggle-right");
    this.closeLeft = document.getElementById("close-drawer-left");
    this.closeRight = document.getElementById("close-drawer-right");
    this.chatContainer = document.getElementById("chat-messages-container");
    this.clearChatBtn = document.getElementById("clear-chat-btn");

    this.initBlob();
    this.initSettings();
    this.initToggles();
    this.initTypingInput();
    this.initImageAttachment();
    this.initDrawers();
    this.initWebSocket();
    this.initAudioAnalyzer();
    this.initMiaFloatingDot();
    this.initFloatingMiaFlyout();
    this.loadRecentChatHistory();

    // Audio context unlock & background wake-word listening
    const unlockAudio = async () => {
      if (this.audioContext && this.audioContext.state === "suspended") {
        try { await this.audioContext.resume(); } catch (e) {}
      }
    };
    document.addEventListener("click", unlockAudio);
    document.addEventListener("keydown", unlockAudio);

    const startWakeListening = () => {
      unlockAudio();
      this.setListeningMode(this.isAlwaysListening);
    };
    document.addEventListener("click", startWakeListening, { once: true });
    setTimeout(() => {
      unlockAudio();
      this.setListeningMode(this.isAlwaysListening);
    }, 600);
  }

  initBlob() {
    this.blob = new CellularBlob("blob-canvas-container");
  }

  initSettings() {
    this.settings = new SettingsController();
  }

  toggleFullScreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(err => {
        console.warn("Fullscreen request error:", err);
      });
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().catch(err => {
          console.warn("Exit fullscreen error:", err);
        });
      }
    }
  }

  initToggles() {
    const expandBtn = document.getElementById("toggles-expand-btn");
    const container = document.getElementById("quick-toggles");

    expandBtn.addEventListener("click", (e) => {
      if (e.target.closest("#quick-fullscreen-btn")) return;
      container.classList.toggle("expanded");
    });

    // Toggle 1: Full Screen Mode (Toggle at 1st position)
    const fsToggle = document.getElementById("toggle-fullscreen");
    const fsDesc = document.getElementById("fullscreen-mode-desc");
    const fsBtn = document.getElementById("quick-fullscreen-btn");
    const fsIconEnter = fsBtn ? fsBtn.querySelector(".fs-icon-enter") : null;
    const fsIconExit = fsBtn ? fsBtn.querySelector(".fs-icon-exit") : null;

    const updateFsState = (isFs) => {
      if (fsToggle) fsToggle.checked = isFs;
      if (fsDesc) {
        fsDesc.textContent = isFs ? "Full Screen" : "Windowed";
        fsDesc.style.color = isFs ? "var(--cyan-primary)" : "var(--text-muted)";
      }
      if (fsIconEnter && fsIconExit) {
        fsIconEnter.style.display = isFs ? "none" : "block";
        fsIconExit.style.display = isFs ? "block" : "none";
      }
      if (fsBtn) {
        fsBtn.title = isFs ? "Exit Full Screen" : "Enter Full Screen (F11)";
      }
    };

    if (fsToggle) {
      fsToggle.addEventListener("change", () => {
        this.toggleFullScreen();
      });
    }

    if (fsBtn) {
      fsBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        this.toggleFullScreen();
      });
    }

    document.addEventListener("fullscreenchange", () => {
      updateFsState(!!document.fullscreenElement);
    });

    // Toggle 2: Brain Mode
    const brainToggle = document.getElementById("toggle-brain-mode");
    const brainDesc = document.getElementById("brain-mode-desc");
    brainToggle.addEventListener("change", (e) => {
      const mode = e.target.checked ? "ai" : "predefined";
      brainDesc.textContent = e.target.checked ? "AI Brain" : "Predefined";
      this.sendWsAction("toggle_setting", { key: "brain_mode", value: mode });
    });

    // Toggle 2: Listening Mode
    const listenToggle = document.getElementById("toggle-listening-mode");
    const listenDesc = document.getElementById("listening-mode-desc");
    listenToggle.addEventListener("change", (e) => {
      const active = e.target.checked;
      listenDesc.textContent = active ? "Always Active" : "Wake Word ('Atlas')";
      listenDesc.style.color = active ? "var(--cyan-primary)" : "var(--text-muted)";
      this.setListeningMode(active);
      this.sendWsAction("toggle_setting", { key: "listening_mode", value: active });
    });

    // Toggle 3: Voice Output
    const voiceToggle = document.getElementById("toggle-voice-output");
    const voiceDesc = document.getElementById("voice-output-desc");
    voiceToggle.addEventListener("change", (e) => {
      const active = e.target.checked;
      voiceDesc.textContent = active ? "Active" : "Muted";
      this.sendWsAction("toggle_setting", { key: "voice_output", value: active });
    });

    // Toggle 4: Commander Focus Mode (Voice Biometrics Lock & Cosine Similarity Cross-Check)
    const focusToggle = document.getElementById("toggle-commander-focus");
    const focusDesc = document.getElementById("commander-focus-desc");
    focusToggle.addEventListener("change", async (e) => {
      const active = e.target.checked;

      // If enabling, verify that voice profile is enrolled
      if (active) {
        try {
          const res = await fetch("/api/biometrics/status");
          const data = await res.json();
          if (!data.enrolled) {
            alert("⚠️ No voice profile found!\n\nPlease open Settings -> Voice Security and enroll 1-3 voice samples first so ATLAS can cross-check your cosine similarity.");
            e.target.checked = false;
            return;
          }
        } catch (err) {
          console.warn("Could not check biometrics status:", err);
        }

        focusDesc.textContent = "Owner Locked";
        focusDesc.style.color = "var(--cyan-primary)";
        this.updateState("processing", "Boss Focus Armed");
        setTimeout(() => this.updateState("idle", "Ready (Owner Protected)"), 1400);
      } else {
        focusDesc.textContent = "Voice Lock Off";
        focusDesc.style.color = "var(--text-muted)";
        this.updateState("idle", "Voice Security Deactivated");
      }

      this.sendWsAction("toggle_setting", { key: "biometrics.enabled", value: active });
      
      // Keep Settings modal checkbox in sync
      const bioModalCheckbox = document.getElementById("biometrics-enabled");
      if (bioModalCheckbox) bioModalCheckbox.checked = active;
    });

    // Toggle 5: Voice Barge-in / Interruption Mode
    const bargeToggle = document.getElementById("toggle-barge-in");
    const bargeDesc = document.getElementById("barge-in-desc");
    if (bargeToggle) {
      bargeToggle.addEventListener("change", (e) => {
        const active = e.target.checked;
        this.isBargeInEnabled = active;
        if (bargeDesc) {
          bargeDesc.textContent = active ? "Active" : "Off";
          bargeDesc.style.color = active ? "var(--cyan-primary)" : "var(--text-muted)";
        }
        this.updateState("processing", active ? "Voice Barge-in Armed" : "Barge-in Deactivated");
        setTimeout(() => {
          if (!this.isAlwaysListening) {
            this.updateState("idle", "Standby · Call 'Atlas'");
          } else {
            this.updateState("listening", "Always Active");
          }
        }, 1200);
        this.sendWsAction("toggle_setting", { key: "voice_barge_in", value: active });
      });
    }

    // Toggle 6: Antigravity Mode (Direct Agent Dictation)
    const agyToggle = document.getElementById("toggle-antigravity-mode");
    const agyDesc = document.getElementById("antigravity-mode-desc");
    if (agyToggle) {
      agyToggle.addEventListener("change", (e) => {
        const active = e.target.checked;
        this.isAntigravityMode = active;
        if (agyDesc) {
          agyDesc.textContent = active ? "Relay to Agent" : "Direct to Agent Off";
          agyDesc.style.color = active ? "var(--cyan-primary)" : "var(--text-muted)";
        }
        this.updateState("processing", active ? "Antigravity Relay Active" : "Relay Deactivated");
        setTimeout(() => {
          if (!this.isAlwaysListening) {
            this.updateState("idle", "Standby · Call 'Atlas'");
          } else {
            this.updateState("listening", "Always Active");
          }
        }, 1200);
        this.sendWsAction("toggle_setting", { key: "antigravity_mode", value: active });
      });
    }

    // Toggle 7: Message Queue Access (30s Paced Queue Processing)
    const queueToggle = document.getElementById("toggle-telegram-queue");
    const queueDesc = document.getElementById("telegram-queue-desc");
    if (queueToggle) {
      queueToggle.addEventListener("change", (e) => {
        const active = e.target.checked;
        this.isTelegramQueueAccess = active;
        if (queueDesc) {
          queueDesc.textContent = active ? "30s Pace Active" : "Queue Access Off";
          queueDesc.style.color = active ? "var(--cyan-primary)" : "var(--text-muted)";
        }
        this.updateState("processing", active ? "Message Queue Active (30s Gap)" : "Message Queue Paused");
        setTimeout(() => {
          if (!this.isAlwaysListening) {
            this.updateState("idle", "Standby · Call 'Atlas'");
          } else {
            this.updateState("listening", "Always Active");
          }
        }, 1400);
        this.sendWsAction("toggle_setting", { key: "telegram_queue_access", value: active });
      });
    }
  }

  initTypingInput() {
    // Enter key submits command
    this.cmdInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        this.submitTypedCommand();
      }
    });

    // Clicking the wormhole sends the command
    this.wormholeBtn.addEventListener("click", () => {
      this.submitTypedCommand();
    });

    // Clicking the Stop button immediately halts processing/speaking/listening
    if (this.stopBtn) {
      this.stopBtn.addEventListener("click", () => {
        this.emergencyStop("Emergency Stop Triggered");
      });
    }

    // Escape key immediately halts any active state
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        this.emergencyStop("Operation Cancelled (Esc)");
      }
    });

    // Clicking the microphone icon toggles live voice typing into the input
    this.micTypingBtn.addEventListener("click", () => {
      this.toggleVoiceTyping();
    });
  }

  initDrawers() {
    // Toggle Left Drawer (Predefined Catalog)
    this.arrowLeft.addEventListener("click", () => {
      this.drawerLeft.classList.toggle("open");
      if (this.drawerLeft.classList.contains("open")) {
        this.drawerRight.classList.remove("open");
      }
    });
    this.closeLeft.addEventListener("click", () => {
      this.drawerLeft.classList.remove("open");
    });

    // Toggle Right Drawer (Chat & Response Stream)
    this.arrowRight.addEventListener("click", () => {
      this.arrowRight.classList.remove("has-security-alert");
      this.drawerRight.classList.toggle("open");
      if (this.drawerRight.classList.contains("open")) {
        this.drawerLeft.classList.remove("open");
        this.scrollToBottom();
      }
    });
    this.closeRight.addEventListener("click", () => {
      this.drawerRight.classList.remove("open");
    });

    // Click on Predefined Command Cards to auto-execute
    document.querySelectorAll(".command-card").forEach(card => {
      card.addEventListener("click", () => {
        const cmd = card.dataset.cmd;
        if (cmd) {
          this.cmdInput.value = cmd;
          this.submitTypedCommand();
          this.drawerLeft.classList.remove("open");
        }
      });
    });

    // Clear chat stream
    this.clearChatBtn.addEventListener("click", () => {
      this.chatContainer.innerHTML = `
        <div class="chat-placeholder">
          <div class="placeholder-icon">🛰️</div>
          <p>Chat stream cleared.<br>Type in the cosmic bar or speak a voice command!</p>
        </div>
      `;
    });
  }

  initImageAttachment() {
    this.attachImgBtn = document.getElementById("attach-img-btn");
    this.imgFileInput = document.getElementById("chat-img-file-input");
    this.imgPreviewBar = document.getElementById("chat-img-preview-bar");
    this.imgPreviewThumb = document.getElementById("chat-img-preview-thumb");
    this.imgPreviewName = document.getElementById("chat-img-preview-name");
    this.removeImgBtn = document.getElementById("remove-img-preview-btn");

    this.currentAttachedImageBase64 = null;
    this.currentAttachedImageName = null;

    if (this.attachImgBtn && this.imgFileInput) {
      this.attachImgBtn.addEventListener("click", () => {
        this.imgFileInput.click();
      });

      this.imgFileInput.addEventListener("change", (e) => {
        const file = e.target.files && e.target.files[0];
        if (file) {
          this.handleImageFileSelected(file);
        }
      });
    }

    if (this.removeImgBtn) {
      this.removeImgBtn.addEventListener("click", () => {
        this.clearImageAttachment();
      });
    }

    // Support clipboard paste (Ctrl+V) directly into command input
    if (this.cmdInput) {
      this.cmdInput.addEventListener("paste", (e) => {
        if (!e.clipboardData || !e.clipboardData.items) return;
        const items = e.clipboardData.items;
        for (let i = 0; i < items.length; i++) {
          if (items[i].type && items[i].type.indexOf("image") !== -1) {
            const blob = items[i].getAsFile();
            if (blob) {
              e.preventDefault();
              this.handleImageFileSelected(blob, "pasted_screenshot.png");
              break;
            }
          }
        }
      });
    }
  }

  handleImageFileSelected(file, defaultName = null) {
    const reader = new FileReader();
    const name = file.name || defaultName || "image.png";
    reader.onload = (event) => {
      this.currentAttachedImageBase64 = event.target.result;
      this.currentAttachedImageName = name;
      if (this.imgPreviewThumb) this.imgPreviewThumb.src = this.currentAttachedImageBase64;
      if (this.imgPreviewName) this.imgPreviewName.textContent = name;
      if (this.imgPreviewBar) this.imgPreviewBar.style.display = "flex";
      this.cmdInput.focus();
    };
    reader.readAsDataURL(file);
  }

  clearImageAttachment() {
    this.currentAttachedImageBase64 = null;
    this.currentAttachedImageName = null;
    if (this.imgFileInput) this.imgFileInput.value = "";
    if (this.imgPreviewBar) this.imgPreviewBar.style.display = "none";
    if (this.imgPreviewThumb) this.imgPreviewThumb.src = "";
  }

  addImageChatMessage(sender, imageBase64, caption, route = "text") {
    const msgDiv = document.createElement("div");
    msgDiv.className = `chat-message ${sender}-message`;

    let html = `<div class="chat-bubble ${sender}-bubble">`;
    html += `<img src="${imageBase64}" style="max-width: 220px; max-height: 160px; border-radius: 8px; margin-bottom: 6px; display: block; border: 1px solid rgba(0, 242, 254, 0.4);" />`;
    if (caption) {
      html += `<div class="bubble-text">${this.escapeHtml(caption)}</div>`;
    }
    html += `<div class="bubble-meta"><span class="meta-source">${route}</span></div>`;
    html += `</div>`;

    msgDiv.innerHTML = html;
    this.chatContainer.appendChild(msgDiv);
    this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
  }

  submitTypedCommand() {
    const text = this.cmdInput.value.trim();
    const imageB64 = this.currentAttachedImageBase64;
    const imageName = this.currentAttachedImageName;

    if (!text && !imageB64) return;

    if (imageB64) {
      this.addImageChatMessage("user", imageB64, text, "text");
    } else {
      this.addChatMessage("user", text, "text");
    }

    this.dispatchCommand(text, "text", null, imageB64, imageName);
    this.cmdInput.value = "";
    this.clearImageAttachment();
    this.cmdInput.blur();
  }

  toggleVoiceTyping() {
    if (this.isVoiceTypingOnly) {
      this.stopVoiceTyping();
    } else {
      this.startVoiceTyping();
    }
  }

  async startVoiceTyping() {
    this.isVoiceTypingOnly = true;
    this.isAwake = true;
    this.micTypingBtn.classList.add("voice-typing-active");
    this.cmdInput.placeholder = "Listening... Speak your command";
    this.cmdInput.focus();
    await this.startMicrophone();
    this.startSpeechRecognition();
    this.updateState("listening", "Listening... Speak command");
  }

  stopVoiceTyping() {
    this.isVoiceTypingOnly = false;
    this.micTypingBtn.classList.remove("voice-typing-active");
    this.cmdInput.placeholder = "Command ATLAS or explore...";
    if (!this.isAlwaysListening) {
      this.isAwake = false;
      this.updateState("idle", "Standby · Call 'Atlas'");
    }
  }

  initWebSocket() {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = `${protocol}//${window.location.host}/ws`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log("Connected to ATLAS 2.0 Core.");
      this.updateState("idle", "SYSTEM ONLINE");
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        this.handleWsEvent(msg.event, msg.data);
      } catch (e) {
        console.error("WS Parse error:", e);
      }
    };

    this.ws.onclose = () => {
      this.updateState("denied", "CORE DISCONNECTED");
      setTimeout(() => this.initWebSocket(), 3000);
    };
  }

  sendWsAction(action, payload = {}) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ action, ...payload }));
    }
  }

  initMiaFloatingDot() {
    const dot = document.getElementById("mia-floating-error-dot");
    if (dot) {
      dot.addEventListener("click", () => {
        if (this.settings) {
          this.settings.open();
          const miaTabBtn = document.getElementById("tab-btn-mia");
          if (miaTabBtn) miaTabBtn.click();
        }
      });
    }
    this.checkMiaStatus();
  }

  updateMiaFloatingStatus(hasLlm, message) {
    const dot = document.getElementById("mia-floating-error-dot");
    if (!dot) return;
    if (hasLlm === false) {
      dot.style.display = "flex";
      dot.title = message || "MIA Warning: No LLM configured. Click to configure.";
    } else {
      dot.style.display = "none";
    }
  }

  async checkMiaStatus() {
    try {
      const res = await fetch("/api/mia/status");
      const data = await res.json();
      this.updateMiaFloatingStatus(data.has_llm, data.llm_message);
      if (data.stats) {
        this.handleMiaLiveStats({ stats: data.stats, has_llm: data.has_llm, llm_message: data.llm_message });
      }
    } catch (e) {}
  }

  playPopSound() {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.type = "sine";
      // Crisp bubbly frequency drop
      osc.frequency.setValueAtTime(860, ctx.currentTime);
      osc.frequency.exponentialRampToValueAtTime(320, ctx.currentTime + 0.11);

      gain.gain.setValueAtTime(0.32, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.13);

      osc.connect(gain);
      gain.connect(ctx.destination);

      osc.start();
      osc.stop(ctx.currentTime + 0.14);
    } catch (e) {
      console.warn("Pop sound error:", e);
    }
  }

  initFloatingMiaFlyout() {
    const btn = document.getElementById("mia-floating-btn");
    const panel = document.getElementById("mia-flyout-panel");
    const closeBtn = document.getElementById("mia-flyout-close");
    const refreshBtn = document.getElementById("mia-flyout-refresh");
    const openHubBtn = document.getElementById("mia-flyout-open-hub");

    if (btn && panel) {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isHidden = panel.style.display === "none" || !panel.style.display;
        if (isHidden) {
          panel.style.display = "flex";
          this.loadRecentMiaSummaries();
        } else {
          panel.style.display = "none";
        }
      });

      if (closeBtn) {
        closeBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          panel.style.display = "none";
        });
      }

      if (refreshBtn) {
        refreshBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          this.loadRecentMiaSummaries();
        });
      }

      if (openHubBtn) {
        openHubBtn.addEventListener("click", (e) => {
          e.stopPropagation();
          panel.style.display = "none";
          const cpBtn = document.getElementById("control-panel-btn");
          if (cpBtn) cpBtn.click();
          const miaTabBtn = document.getElementById("tab-btn-mia");
          if (miaTabBtn) miaTabBtn.click();
        });
      }

      // Close when clicking outside panel
      document.addEventListener("click", (e) => {
        if (panel.style.display === "flex" && !panel.contains(e.target) && !btn.contains(e.target)) {
          panel.style.display = "none";
        }
      });
    }
  }

  async loadRecentMiaSummaries() {
    const listContainer = document.getElementById("mia-recent-list");
    if (!listContainer) return;

    listContainer.innerHTML = '<div class="mia-loading-skeleton">Loading latest email digests from MongoDB...</div>';

    try {
      const res = await fetch("/api/mia/recent?limit=5");
      const data = await res.json();
      const emails = data.emails || [];

      if (emails.length === 0) {
        listContainer.innerHTML = '<div class="mia-empty-state">No emails recorded yet in MongoDB Atlas.</div>';
        return;
      }

      const escapeHtml = (str) => {
        if (!str) return "";
        return String(str).replace(/[&<>"']/g, (m) => ({
          "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
        }[m]));
      };

      const formatTime = (isoStr) => {
        if (!isoStr) return "";
        try {
          const d = new Date(isoStr);
          if (isNaN(d.getTime())) return isoStr;
          const now = new Date();
          const diffMs = now - d;
          const diffMins = Math.floor(diffMs / 60000);
          if (diffMins < 1) return "Just now";
          if (diffMins < 60) return `${diffMins}m ago`;
          const diffHours = Math.floor(diffMins / 60);
          if (diffHours < 24) return `${diffHours}h ago`;
          return d.toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
        } catch {
          return isoStr;
        }
      };

      listContainer.innerHTML = emails.map(em => {
        const senderName = em.sender_name || (em.sender_email ? em.sender_email.split("@")[0] : "Unknown");
        const senderDomain = em.sender_domain || (em.sender_email && em.sender_email.includes("@") ? em.sender_email.split("@")[1] : "");
        const initial = (senderName.trim()[0] || "M").toUpperCase();
        const subject = em.subject ? em.subject.trim() : "(No Subject)";
        const summary = em.summary ? em.summary.trim() : "Summary extraction in progress...";
        const topic = em.main_topic || "General";
        const timeStr = formatTime(em.received_at);

        return `
          <div class="mia-mail-card">
            <div class="mia-mail-top-row">
              <div class="mia-mail-sender-box">
                <div class="mia-avatar-circle">${escapeHtml(initial)}</div>
                <div class="mia-sender-details">
                  <span class="mia-mail-sender" title="${escapeHtml(em.sender_email || '')}">${escapeHtml(senderName)}</span>
                  ${senderDomain ? `<span class="mia-mail-domain">@${escapeHtml(senderDomain)}</span>` : ""}
                </div>
              </div>
              <span class="mia-mail-time" title="${escapeHtml(em.received_at || '')}">
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 4px; vertical-align: -1px;">
                  <circle cx="12" cy="12" r="10"></circle>
                  <polyline points="12 6 12 12 16 14"></polyline>
                </svg>${escapeHtml(timeStr)}
              </span>
            </div>

            <div class="mia-mail-subject" title="${escapeHtml(subject)}">
              ${escapeHtml(subject)}
            </div>

            <div class="mia-mail-summary">
              <span class="mia-summary-label">DIGEST</span>
              ${escapeHtml(summary)}
            </div>

            <div class="mia-mail-bottom-row">
              <span class="mia-mail-topic">📁 ${escapeHtml(topic)}</span>
              <span class="mia-mail-status-tag">✓ Ingested</span>
            </div>
          </div>
        `;
      }).join("");
    } catch (e) {
      console.warn("Failed to load recent MIA emails:", e);
      listContainer.innerHTML = '<div class="mia-empty-state" style="color: #ef4444;">Error fetching from MongoDB. Ensure connection is active.</div>';
    }
  }

  handleMiaLiveStats(data) {
    if (!data) return;
    const stats = data.stats;
    if (stats) {
      const count = stats.total_emails;
      
      // Update floating top-right badge
      const floatBadge = document.getElementById("mia-floating-badge");
      if (floatBadge && count !== undefined) {
        floatBadge.textContent = count;
      }

      // Check for incoming new mail arrival
      if (count !== undefined && this._lastKnownEmailCount !== undefined && count > this._lastKnownEmailCount) {
        this.playPopSound();
        const floatBtn = document.getElementById("mia-floating-btn");
        if (floatBtn) {
          floatBtn.classList.remove("new-mail-blink");
          void floatBtn.offsetWidth; // Trigger reflow
          floatBtn.classList.add("new-mail-blink");
          setTimeout(() => floatBtn.classList.remove("new-mail-blink"), 5500);
        }

        // Live refresh the flyout card if it's currently open
        const flyout = document.getElementById("mia-flyout-panel");
        if (flyout && flyout.style.display === "flex") {
          this.loadRecentMiaSummaries();
        }
      }
      if (count !== undefined) {
        this._lastKnownEmailCount = count;
      }

      const badgeCount = document.getElementById("mia-badge-count");
      if (badgeCount && count !== undefined) {
        const prev = badgeCount.dataset.count;
        badgeCount.textContent = `${count} Emails`;
        badgeCount.dataset.count = count;
        if (prev && prev !== String(count)) {
          badgeCount.classList.add("pulse-update");
          setTimeout(() => badgeCount.classList.remove("pulse-update"), 1500);
        }
      }

      const emailStat = document.getElementById("mia-stat-emails");
      if (emailStat && count !== undefined) emailStat.textContent = count;

      const embStat = document.getElementById("mia-stat-embeddings");
      if (embStat && stats.total_embeddings !== undefined) embStat.textContent = stats.total_embeddings;

      const backendStat = document.getElementById("mia-stat-backend");
      if (backendStat) {
        backendStat.textContent = stats.backend === "mongodb_atlas" ? "Storage: MongoDB Atlas ☁️" : "Storage: SQLite";
      }

      const badgeStatus = document.getElementById("mia-badge-status");
      if (badgeStatus) {
        badgeStatus.textContent = stats.backend === "mongodb_atlas" ? "Cloud 24/7 Active" : "Local SQLite";
      }
    }

    if (data.has_llm !== undefined) {
      this.updateMiaFloatingStatus(data.has_llm, data.llm_message || data.message);
    }
  }

  handleWsEvent(event, data) {
    if (event === "reload_page") {
      window.location.reload();
      return;
    }
    if (event === "connected") {
      this.syncConfigToggles(data.config || data);
      if (data.mia_has_llm !== undefined) {
        this.updateMiaFloatingStatus(data.mia_has_llm, data.mia_llm_message);
      }
      if (data.mia_stats) {
        this.handleMiaLiveStats({ stats: data.mia_stats, has_llm: data.mia_has_llm, llm_message: data.mia_llm_message });
      }
    } else if (event === "config_updated") {
      this.syncConfigToggles(data.config || data);
      this.checkMiaStatus();
    } else if (event === "mia_status_changed" || event === "mia_stats_updated") {
      this.handleMiaLiveStats(data);
    } else if (event === "state_change") {
      this.updateState(data.state, data.detail);
    } else if (event === "command_result") {
      this.handleCommandResult(data);
    } else if (event === "antigravity_completed") {
      this.handleAntigravityCompleted(data);
    } else if (event === "remote_command") {
      this.addChatMessage("user", data.command, data.source || "telegram");
      if (data.response) {
        this.addChatMessage("atlas", data.response, "remote");
      }
      if (data.audio_b64) {
        this.playTTSAudio(data.audio_b64);
      } else {
        this.updateState("processing", `Remote: ${data.command}`);
        setTimeout(() => this.updateState("idle", "Completed"), 1500);
      }
    }
  }

  syncConfigToggles(cfg) {
    if (!cfg) return;
    if (cfg.brain_mode) {
      const bToggle = document.getElementById("toggle-brain-mode");
      const bDesc = document.getElementById("brain-mode-desc");
      if (bToggle) bToggle.checked = (cfg.brain_mode === "ai");
      if (bDesc) bDesc.textContent = (cfg.brain_mode === "ai") ? "AI Brain" : "Predefined";
    }
    if (cfg.listening_mode !== undefined) {
      const lToggle = document.getElementById("toggle-listening-mode");
      const lDesc = document.getElementById("listening-mode-desc");
      const active = !!cfg.listening_mode;
      if (lToggle) lToggle.checked = active;
      if (lDesc) {
        lDesc.textContent = active ? "Always Active" : "Wake Word ('Atlas')";
        lDesc.style.color = active ? "var(--cyan-primary)" : "var(--text-muted)";
      }
      this.setListeningMode(active);
    }
    if (cfg.voice_output !== undefined) {
      const vToggle = document.getElementById("toggle-voice-output");
      const vDesc = document.getElementById("voice-output-desc");
      if (vToggle) vToggle.checked = !!cfg.voice_output;
      if (vDesc) vDesc.textContent = cfg.voice_output ? "Active" : "Muted";
    }
    if (cfg.biometrics) {
      const bioActive = !!cfg.biometrics.enabled;
      const fToggle = document.getElementById("toggle-commander-focus");
      const fDesc = document.getElementById("commander-focus-desc");
      if (fToggle) fToggle.checked = bioActive;
      if (fDesc) {
        fDesc.textContent = bioActive ? "Owner Locked" : "Voice Lock Off";
        fDesc.style.color = bioActive ? "var(--cyan-primary)" : "var(--text-muted)";
      }
    }
    if (cfg.voice_barge_in !== undefined) {
      const bToggle = document.getElementById("toggle-barge-in");
      const bDesc = document.getElementById("barge-in-desc");
      const active = !!cfg.voice_barge_in;
      if (bToggle) bToggle.checked = active;
      if (bDesc) {
        bDesc.textContent = active ? "Active" : "Off";
        bDesc.style.color = active ? "var(--cyan-primary)" : "var(--text-muted)";
      }
      this.isBargeInEnabled = active;
    }
    if (cfg.antigravity_mode !== undefined) {
      const aToggle = document.getElementById("toggle-antigravity-mode");
      const aDesc = document.getElementById("antigravity-mode-desc");
      const active = !!cfg.antigravity_mode;
      if (aToggle) aToggle.checked = active;
      if (aDesc) {
        aDesc.textContent = active ? "Relay to Agent" : "Direct to Agent Off";
        aDesc.style.color = active ? "var(--cyan-primary)" : "var(--text-muted)";
      }
      this.isAntigravityMode = active;
    }
    if (cfg.telegram_queue_access !== undefined) {
      const qToggle = document.getElementById("toggle-telegram-queue");
      const qDesc = document.getElementById("telegram-queue-desc");
      const active = !!cfg.telegram_queue_access;
      if (qToggle) qToggle.checked = active;
      if (qDesc) {
        qDesc.textContent = active ? "30s Pace Active" : "Queue Access Off";
        qDesc.style.color = active ? "var(--cyan-primary)" : "var(--text-muted)";
      }
      this.isTelegramQueueAccess = active;
    }
  }

  updateState(state, detail = "") {
    const validStates = ["idle", "listening", "processing", "speaking", "denied"];
    validStates.forEach(s => this.stateBar.classList.remove(`state-${s}`));
    
    const targetState = validStates.includes(state) ? state : "idle";
    this.currentState = targetState;
    this.stateBar.classList.add(`state-${targetState}`);

    if (this.stopBtn) {
      if (targetState === "processing" || targetState === "speaking") {
        this.stopBtn.classList.add("pulse-active");
      } else {
        this.stopBtn.classList.remove("pulse-active");
      }
    }

    if (this.blob) {
      this.blob.setState(targetState, detail);
    }

    const stateLabels = {
      idle: "SYSTEM READY",
      listening: "LISTENING...",
      processing: "PROCESSING...",
      speaking: "ATLAS RESPONDING",
      denied: "ACCESS DENIED"
    };

    this.stateText.textContent = stateLabels[targetState] || state.toUpperCase();
    this.stateDetail.textContent = detail ? `· ${detail}` : "";
  }

  handleAntigravityCompleted(data) {
    console.log("Antigravity generation completed:", data);
    
    // 1. Play subtle audio notification chime
    this.playWakeSound();

    // 2. Add notification bubble to chat with full content if available
    const fullBody = data.full_content || (data.preview ? `> ${data.preview}` : "Task finished successfully.");
    const stepTag = (data.step_index !== undefined && data.step_index >= 0) ? ` (Step ${data.step_index})` : "";
    this.addChatMessage(
      "atlas",
      `🛰️ Antigravity Completed Generation${stepTag}\n\n${fullBody}`,
      "antigravity_agent"
    );

    // 3. Pulse the 3D Cellular Core with a vibrant energy ripple
    if (this.blob && typeof this.blob.pulse === "function") {
      this.blob.pulse(0.9);
    }

    // 4. Update state banner
    this.updateState("listening", "Antigravity: Done · Ready, Boss");

    // 5. Play voice audio if provided
    if (data.audio_b64) {
      this.playTTSAudio(data.audio_b64);
    } else {
      setTimeout(() => {
        if (!this.isAlwaysListening) {
          this.updateState("idle", "Standby · Call 'Atlas'");
        } else {
          this.updateState("listening", "Always Active");
        }
      }, 3000);
    }
  }

  handleCommandResult(result) {
    if (result.speaker_verified === false) {
      // Biometric rejection: unauthorized voice - STRICTLY NO AUDIO OUTPUT!
      this.addChatMessage("atlas", result.response, "security_mismatch", result.latency_ms);
      this.updateState("denied", `Security Mismatch (${Math.round((result.confidence || 0) * 100)}%)`);

      // Highlight right drawer toggle arrow if closed to indicate security mismatch in chat
      if (!this.drawerRight.classList.contains("open")) {
        this.arrowRight.classList.add("has-security-alert");
      }

      setTimeout(() => {
        if (this.isAlwaysListening) {
          this.updateState("listening", "Always Active");
        } else {
          this.updateState("idle", "Standby · Call 'Atlas'");
        }
      }, 2500);
      return;
    }

    if (result.response) {
      const bioTag = (result.confidence !== undefined && result.confidence < 1.0)
        ? ` · Voice ${Math.round(result.confidence * 100)}%`
        : "";
      const routeLabel = `${result.route}${bioTag}`;
      this.addChatMessage("atlas", result.response, routeLabel, result.latency_ms);

      const confText = (result.confidence !== undefined && result.confidence < 1.0)
        ? `Cosine ${Math.round(result.confidence * 100)}% · `
        : "";
      this.updateState(result.success ? "speaking" : "denied", `${confText}${result.response.slice(0, 32)}`);
    }

    const postAction = result.post_action;

    if (postAction === "toggle_fullscreen" || result.route === "predefined:toggle_fullscreen") {
      this.toggleFullScreen();
    }

    if (result.audio_b64 || result.response) {
      this.playTTSAudio(result.audio_b64, () => {
        if (postAction) {
          console.log(`Response speech completed. Executing post action: ${postAction}`);
          this.sendWsAction("execute_post_action", { post_action: postAction });
          if (postAction === "self_refresh") {
            setTimeout(() => window.location.reload(), 2400);
          }
        }
      }, result.response);
    } else {
      if (postAction) {
        setTimeout(() => {
          console.log(`Executing post action (non-TTS): ${postAction}`);
          this.sendWsAction("execute_post_action", { post_action: postAction });
          if (postAction === "self_refresh") {
            setTimeout(() => window.location.reload(), 2400);
          }
        }, 1500);
      }
      setTimeout(() => {
        if (this.isAlwaysListening) {
          this.updateState("listening", "Always Active");
        } else {
          this.updateState("idle", "Standby · Call 'Atlas'");
        }
      }, 2500);
    }
  }

  playTTSAudio(audioBase64, onCompleteCallback = null, fallbackText = null) {
    if (audioBase64) {
      this.isSpeaking = true;
      this.currentPostActionCallback = onCompleteCallback;
      this.updateState("speaking", "Voice output");
      const mime = (audioBase64.startsWith("UklGR") || audioBase64.startsWith("data:audio/wav")) ? "audio/wav" : "audio/mp3";
      this.ttsPlayer.src = audioBase64.startsWith("data:") ? audioBase64 : `data:${mime};base64,${audioBase64}`;
      this.ttsPlayer.onended = () => {
        this.isSpeaking = false;
        this.lastSpeakingEndTime = Date.now();
        if (this.currentPostActionCallback) {
          try { this.currentPostActionCallback(); } catch (e) { console.error("Post-action callback error:", e); }
          this.currentPostActionCallback = null;
        }
        if (this.isAlwaysListening) {
          this.updateState("listening", "Always Active");
        } else {
          this.updateState("idle", "Standby · Call 'Atlas'");
        }
      };
      this.ttsPlayer.onerror = () => {
        if (fallbackText) {
          this.speakNativeBrowser(fallbackText, onCompleteCallback);
        } else {
          this.isSpeaking = false;
          if (onCompleteCallback) onCompleteCallback();
        }
      };
      this.ttsPlayer.play().catch(e => {
        console.warn("Autoplay audio blocked or format error, engaging browser speech fallback:", e);
        if (fallbackText) {
          this.speakNativeBrowser(fallbackText, onCompleteCallback);
        } else {
          this.isSpeaking = false;
          if (onCompleteCallback) onCompleteCallback();
        }
      });
      return;
    }

    if (fallbackText) {
      this.speakNativeBrowser(fallbackText, onCompleteCallback);
      return;
    }

    if (onCompleteCallback) onCompleteCallback();
  }

  speakNativeBrowser(text, onCompleteCallback = null) {
    if (!('speechSynthesis' in window) || !text) {
      if (onCompleteCallback) onCompleteCallback();
      return;
    }
    try {
      window.speechSynthesis.cancel();
      const clean = text.replace(/[*_#`>]/g, "").trim();
      const utt = new SpeechSynthesisUtterance(clean);
      utt.rate = 1.05;
      utt.pitch = 0.95;
      this.isSpeaking = true;
      this.updateState("speaking", "Voice output");
      utt.onend = () => {
        this.isSpeaking = false;
        this.lastSpeakingEndTime = Date.now();
        if (onCompleteCallback) onCompleteCallback();
        if (this.isAlwaysListening) {
          this.updateState("listening", "Always Active");
        } else {
          this.updateState("idle", "Standby · Call 'Atlas'");
        }
      };
      utt.onerror = () => {
        this.isSpeaking = false;
        if (onCompleteCallback) onCompleteCallback();
      };
      window.speechSynthesis.speak(utt);
    } catch (e) {
      this.isSpeaking = false;
      if (onCompleteCallback) onCompleteCallback();
    }
  }

  stopSpeechOutput() {
    if (this.isSpeaking || (this.ttsPlayer && !this.ttsPlayer.paused)) {
      console.log("Halting Atlas speech output immediately...");
      this.isSpeaking = false;
      this.currentPostActionCallback = null; // Cancel deferred action if user interrupted
      if (this.ttsPlayer) {
        this.ttsPlayer.pause();
        this.ttsPlayer.currentTime = 0;
        this.ttsPlayer.removeAttribute("src");
      }
    }
  }

  emergencyStop(reason = "Emergency Stop") {
    console.log(`[ATLAS Emergency Stop] Reason: ${reason}`);

    // 1. Immediately cut off any spoken audio / TTS playback
    this.stopSpeechOutput();

    // 2. Clear all speech timers
    clearTimeout(this.pauseTimer);
    clearTimeout(this.wakeTimeout);
    this.pauseTimer = null;
    this.wakeTimeout = null;

    // 3. Reset speech state & inputs
    this.isAwake = false;
    this.currentUtterance = "";
    this.cmdInput.value = "";
    this.cmdInput.placeholder = "Command ATLAS or explore...";

    // 4. Recycle speech recognition session so no buffered audio triggers commands
    if (this.speechRecognition) {
      try {
        this.speechRecognition.abort();
      } catch (e) {}
    }

    // 5. Notify backend to cancel any pending long-running processing
    this.sendWsAction("cancel_processing", { reason: reason });

    // 6. Clean state bar to idle
    this.updateState("idle", reason);
  }

  // --- Chat Stream Management ---

  addChatMessage(sender, text, routeOrSource = "", latency = 0) {
    const placeholder = this.chatContainer.querySelector(".chat-placeholder");
    if (placeholder) placeholder.remove();

    const bubble = document.createElement("div");
    bubble.className = `chat-bubble chat-${sender}`;
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const formattedContent = this.formatChatContent(text);

    if (sender === "user") {
      bubble.innerHTML = `
        <div class="chat-meta">
          <span>YOU (${escapeHtml(routeOrSource)})</span>
          <span>${timeStr}</span>
        </div>
        <div class="chat-text">${formattedContent}</div>
      `;
    } else if (routeOrSource === "security_mismatch" || routeOrSource === "biometrics_denied") {
      bubble.classList.add("chat-security-denied");
      bubble.innerHTML = `
        <div class="chat-meta">
          <span class="chat-route security-badge">🛡️ SECURITY MISMATCH</span>
          <span>${timeStr}</span>
        </div>
        <div class="chat-text security-mismatch-text">${formattedContent}</div>
      `;
    } else {
      const metaInfo = latency > 0 ? `${routeOrSource} · ${latency}ms` : routeOrSource;
      bubble.innerHTML = `
        <div class="chat-meta">
          <span class="chat-route">ATLAS (${escapeHtml(metaInfo)})</span>
          <span>${timeStr}</span>
        </div>
        <div class="chat-text">${formattedContent}</div>
      `;
    }

    this.chatContainer.appendChild(bubble);
    this.scrollToBottom();
  }

  formatChatContent(str) {
    if (!str) return "";
    let html = str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    // Bold: **text**
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong style="color: #fff; font-weight: 600;">$1</strong>');
    // Italic: *text*
    html = html.replace(/\*([^*\n]+?)\*/g, '<em style="color: #7dd3fc; font-style: normal;">$1</em>');
    // Inline code: `code`
    html = html.replace(/`([^`]+)`/g, '<code style="background: rgba(255,255,255,0.08); padding: 2px 6px; border-radius: 4px; font-family: monospace; font-size: 12px; color: var(--cyan-primary);">$1</code>');
    return html;
  }

  scrollToBottom() {
    this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
  }

  async loadRecentChatHistory() {
    try {
      const res = await fetch("/api/logs?limit=15");
      const data = await res.json();
      if (data.logs && data.logs.length > 0) {
        const placeholder = this.chatContainer.querySelector(".chat-placeholder");
        if (placeholder) placeholder.remove();

        // Render in chronological order
        const sorted = data.logs.reverse();
        sorted.forEach(log => {
          this.addChatMessage("user", log.command, log.source);
          if (log.response) {
            this.addChatMessage("atlas", log.response, log.route, log.latency_ms);
          }
        });
      }
    } catch (e) {
      console.warn("Failed to load chat history:", e);
    }
  }

  // --- Voice Activity & Speech Recognition ---

  async initAudioAnalyzer() {
    try {
      window.AudioContext = window.AudioContext || window.webkitAudioContext;
      if (!this.audioContext) {
        this.audioContext = new AudioContext();
      }
      if (this.audioContext.state === "suspended") {
        await this.audioContext.resume();
      }
    } catch (e) {
      console.warn("AudioContext init error:", e);
    }
  }

  playWakeSound() {
    try {
      const ctx = this.audioContext || new (window.AudioContext || window.webkitAudioContext)();
      if (ctx.state === "suspended") ctx.resume();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
      osc.frequency.exponentialRampToValueAtTime(880.00, ctx.currentTime + 0.10); // A5
      gain.gain.setValueAtTime(0.06, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.14);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.14);
    } catch (e) {}
  }

  async setListeningMode(enabled) {
    this.isAlwaysListening = !!enabled;
    this.isListeningActive = true; // Keep background audio stream active

    if (enabled) {
      this.isAwake = true;
      clearTimeout(this.wakeTimeout);
      clearTimeout(this.pauseTimer);
      await this.startMicrophone();
      this.startSpeechRecognition();
      this.updateState("listening", "Always Listening");
      this.cmdInput.placeholder = "Listening... Speak any command";
    } else {
      this.isAwake = false;
      clearTimeout(this.wakeTimeout);
      clearTimeout(this.pauseTimer);
      await this.startMicrophone();
      this.startSpeechRecognition();
      this.updateState("idle", "Standby · Call 'Atlas'");
      this.cmdInput.placeholder = "Command ATLAS or explore...";
    }
  }

  async startMicrophone() {
    if (this.micStream && this.micStream.active) return;
    try {
      // Use clean uncompressed natural audio settings identical to Enrollment Studio and Tester
      this.micStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: true
        }
      });
      if (!this.audioContext) {
        window.AudioContext = window.AudioContext || window.webkitAudioContext;
        this.audioContext = new AudioContext();
      }
      if (this.audioContext.state === "suspended") {
        await this.audioContext.resume();
      }
      const source = this.audioContext.createMediaStreamSource(this.micStream);
      this.audioAnalyser = this.audioContext.createAnalyser();
      this.audioAnalyser.fftSize = 64;
      source.connect(this.audioAnalyser);

      this.trackAudioVolume();
      this.setupPcmAudioCapture(source);
    } catch (e) {
      console.warn("Microphone access prompt or error:", e);
    }
  }

  setupPcmAudioCapture(sourceNode) {
    try {
      this.pcmSampleRate = this.audioContext ? this.audioContext.sampleRate : 48000;
      this.maxPcmSamples = this.pcmSampleRate * 8; // 8-second circular buffer
      this.pcmRingBuffer = new Float32Array(this.maxPcmSamples);
      this.pcmWriteIndex = 0;
      this.pcmTotalRecorded = 0;
      this.speechHistory = [];
      this.lastSpeechTimestamp = 0;

      const bufferSize = 4096;
      this.scriptProcessor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);
      this.scriptProcessor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        const len = inputData.length;
        let sumSq = 0;
        for (let i = 0; i < len; i++) {
          const val = inputData[i];
          sumSq += val * val;
          this.pcmRingBuffer[this.pcmWriteIndex] = val;
          this.pcmWriteIndex = (this.pcmWriteIndex + 1) % this.maxPcmSamples;
          if (this.pcmTotalRecorded < this.maxPcmSamples) {
            this.pcmTotalRecorded++;
          }
        }

        const rms = Math.sqrt(sumSq / len);
        if (rms > 0.008) {
          this.lastSpeechTimestamp = Date.now();
          // Store active speech chunks for speaker verification
          this.speechHistory.push(new Float32Array(inputData));
          if (this.speechHistory.length > 70) { // keep up to ~6 seconds of active speech
            this.speechHistory.shift();
          }
        }
      };

      sourceNode.connect(this.scriptProcessor);

      // Connect through a zero-gain node to prevent feedback while avoiding GC
      const silentGain = this.audioContext.createGain();
      silentGain.gain.value = 0;
      this.scriptProcessor.connect(silentGain);
      silentGain.connect(this.audioContext.destination);
    } catch (e) {
      console.warn("Error initializing PCM buffer capture:", e);
    }
  }

  resetCommandAudioCapture() {
    // Preserve speech history so both wake-word and command audio are available for verification
  }

  async getPcmWavBase64() {
    try {
      const sourceSr = this.pcmSampleRate || 48000;
      const targetSr = 16000;
      let rawAudio = null;

      // Strategy A: If active speech frames were detected via VAD, merge them directly
      if (this.speechHistory && this.speechHistory.length >= 6) {
        let totalLen = 0;
        for (const c of this.speechHistory) totalLen += c.length;
        rawAudio = new Float32Array(totalLen);
        let off = 0;
        for (const c of this.speechHistory) {
          rawAudio.set(c, off);
          off += c.length;
        }
        this.speechHistory = [];
      } else {
        // Strategy B: Fallback to circular ring buffer, extracting the last 3.5 seconds
        if (!this.pcmRingBuffer || this.pcmTotalRecorded < 2000) return null;
        const fallbackSamples = Math.min(this.pcmTotalRecorded, Math.round(sourceSr * 3.5));
        rawAudio = new Float32Array(fallbackSamples);
        let readIdx = (this.pcmWriteIndex - fallbackSamples + this.maxPcmSamples) % this.maxPcmSamples;
        for (let i = 0; i < fallbackSamples; i++) {
          rawAudio[i] = this.pcmRingBuffer[readIdx];
          readIdx = (readIdx + 1) % this.maxPcmSamples;
        }
      }

      if (!rawAudio || rawAudio.length < 3200) return null;

      // Resample to standard 16,000 Hz Mono
      const ratio = sourceSr / targetSr;
      const targetLength = Math.round(rawAudio.length / ratio);
      const resampled = new Float32Array(targetLength);
      for (let i = 0; i < targetLength; i++) {
        const srcIdx = Math.min(Math.round(i * ratio), rawAudio.length - 1);
        resampled[i] = rawAudio[srcIdx];
      }

      // Volume normalization to peak 0.85 (identical to Enrollment Studio & Tester)
      let maxVal = 0;
      for (let i = 0; i < resampled.length; i++) {
        const a = Math.abs(resampled[i]);
        if (a > maxVal) maxVal = a;
      }
      if (maxVal > 0.02 && maxVal < 0.85) {
        const boost = 0.85 / maxVal;
        for (let i = 0; i < resampled.length; i++) resampled[i] *= boost;
      }

      // Build 16-bit Mono WAV Blob
      const encodeFn = window.encodePcmToWavBlob || encodePcmToWavBlob;
      const wavBlob = encodeFn(resampled, targetSr);

      // Fast non-blocking Base64 encoding
      const buf = await wavBlob.arrayBuffer();
      const bytes = new Uint8Array(buf);
      let binary = "";
      const chunkSize = 8192;
      for (let i = 0; i < bytes.length; i += chunkSize) {
        binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
      }
      return window.btoa(binary);
    } catch (e) {
      console.warn("Error converting audio to WAV Base64:", e);
      return null;
    }
  }

  stopMicrophone() {
    if (this.micStream) {
      this.micStream.getTracks().forEach(track => track.stop());
      this.micStream = null;
    }
    if (this.blob) {
      this.blob.setAudioAmplitude(0);
    }
  }

  trackAudioVolume = () => {
    if (!this.audioAnalyser) return;

    const dataArray = new Uint8Array(this.audioAnalyser.frequencyBinCount);
    this.audioAnalyser.getByteFrequencyData(dataArray);

    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      sum += dataArray[i];
    }
    const avg = sum / dataArray.length;

    // Filter out low electrical noise floor (~10), scale cleanly so talking/sound gives 0.2 - 0.95
    const noiseFloor = 10.0;
    let normalized = 0;
    if (avg > noiseFloor) {
      normalized = Math.min((avg - noiseFloor) / 50.0, 1.0);
    }

    if (this.blob) {
      this.blob.setAudioAmplitude(normalized);
    }

    requestAnimationFrame(this.trackAudioVolume);
  };

  startSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      console.warn("Web Speech API is not supported in this browser.");
      return;
    }

    if (!this.speechRecognition) {
      this.speechRecognition = new SpeechRecognition();
      this.speechRecognition.continuous = true;
      this.speechRecognition.interimResults = true;
      this.speechRecognition.lang = "en-US";

      this.isAwake = false;
      this.wakeTimeout = null;
      this.pauseTimer = null;
      this.currentUtterance = "";
      this.lastSpeakingEndTime = 0;

      this.speechRecognition.onresult = (event) => {
        let activeTranscript = "";
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          activeTranscript += event.results[i][0].transcript + " ";
        }
        activeTranscript = activeTranscript.trim();
        if (!activeTranscript) return;

        // Anti-self-disturbance guard: ignore lingering speaker reverberations for 350ms after speech output ends
        if (Date.now() - this.lastSpeakingEndTime < 350) {
          return;
        }

        // =========================================================================
        // 1. Interruption Handler (While ATLAS is speaking or processing)
        // STRICT RULE: Only the wake word "Atlas" / "Call Atlas" OR "Abandon" will interrupt!
        // No self-disturbance from speaker echo or ambient noise will interrupt!
        // =========================================================================
        if (this.isSpeaking || this.currentState === "processing") {
          // Check for emergency abort command: "Abandon" / "Abort" / "Cancel"
          if (/\b(?:atlas\s+)?(?:abandon|abort|cancel|stop)\b/i.test(activeTranscript)) {
            console.log("Voice Interruption: 'Abandon' command received! Halting immediately...");
            this.emergencyStop("Operation Abandoned");
            this.addChatMessage("atlas", "Operation abandoned, Boss.", "system");
            return;
          }

          // Check for wake word interruption: "Atlas" / "Call Atlas" / "Hey Atlas" / "Ok Atlas"
          const wakeMatch = activeTranscript.match(/\b(?:(?:call|hey|ok|okay)\s+)?atlas\b/i);
          if (wakeMatch) {
            console.log("Voice Barge-In: Wake word 'Atlas' heard! Halting speech immediately...");
            this.stopSpeechOutput();
            this.isAwake = true;
            this.playWakeSound();
            this.updateState("listening", "Atlas Active · Say Command");
            this.cmdInput.placeholder = "Listening... Speak your command";

            // Check if user spoke a new command in the same breath
            const matchEnd = wakeMatch.index + wakeMatch[0].length;
            const remainder = activeTranscript.slice(matchEnd).replace(/^[,.\s]+/, "").trim();

            if (remainder) {
              if (/\b(?:abandon|abort|cancel|stop)\b/i.test(remainder)) {
                this.emergencyStop("Operation Abandoned");
                this.addChatMessage("atlas", "Operation abandoned, Boss.", "system");
                return;
              }
              this.currentUtterance = remainder;
              this.cmdInput.value = remainder;
              this.updateState("listening", remainder.slice(0, 30));
              this.resetPauseTimer();
            } else {
              this.currentUtterance = "";
              this.cmdInput.value = "";
              this.startWakeTimeout();
            }
          }
          // Strictly drop any other audio while speaking/processing to prevent self-disturbance
          return;
        }

        // =========================================================================
        // 2. Normal Standby / Listening Mode (Not currently speaking or processing)
        // =========================================================================

        // Check for direct "Abandon" command at any time
        if (/\b(?:atlas\s+)?(?:abandon|abort)\b/i.test(activeTranscript.trim())) {
          console.log("Direct Abandon command spoken! Halting immediately...");
          this.emergencyStop("Operation Abandoned");
          this.addChatMessage("atlas", "Operation abandoned, Boss.", "system");
          return;
        }

        // --- MODE A: Standby Mode (Wake Word Required when Always-Listening is OFF) ---
        if (!this.isAlwaysListening) {
          if (!this.isAwake) {
            // High-speed wake word detection ("Atlas", "Call Atlas", "Hey Atlas", etc.)
            const wakeMatch = activeTranscript.match(/\b(?:(?:call|hey|ok|okay)\s+)?atlas\b/i);
            if (wakeMatch) {
              console.log("Wake word 'Atlas' triggered! Instant switch to listening...");
              this.isAwake = true;
              this.playWakeSound();
              this.updateState("listening", "Atlas Active · Say Command");
              this.cmdInput.placeholder = "Listening... Speak your command";

              // Check if user spoke command in the same breath
              const matchEnd = wakeMatch.index + wakeMatch[0].length;
              const remainder = activeTranscript.slice(matchEnd).replace(/^[,.\s]+/, "").trim();

              if (remainder) {
                this.currentUtterance = remainder;
                this.cmdInput.value = remainder;
                this.updateState("listening", remainder.slice(0, 30));
                this.resetPauseTimer();
              } else {
                this.currentUtterance = "";
                this.cmdInput.value = "";
                this.startWakeTimeout(); // Stay awake waiting for command
              }
            }
            return;
          }

          // User is ALREADY awake: capture command words accurately
          const cleanCommand = activeTranscript.replace(/^\b(?:(?:call|hey|ok|okay)\s+)?atlas\b[,.\s]*/i, "").trim() || activeTranscript;
          if (cleanCommand) {
            clearTimeout(this.wakeTimeout); // Command words arriving: keep session awake
            this.currentUtterance = cleanCommand;
            this.cmdInput.value = cleanCommand;
            this.updateState("listening", cleanCommand.slice(0, 30));
            this.resetPauseTimer(); // Reset the 2.0-second silence timer
          }
          return;
        }

        // --- MODE B: Always-Listening Mode (Listening Toggle is ON) ---
        // Clean any leading call "atlas" prefix and capture command directly without self-disturbance
        const cleanSpoken = activeTranscript.replace(/^\b(?:(?:call|hey|ok|okay)\s+)?atlas\b[,.\s]*/i, "").trim() || activeTranscript;
        if (cleanSpoken) {
          this.currentUtterance = cleanSpoken;
          this.cmdInput.value = cleanSpoken;
          this.updateState("listening", cleanSpoken.slice(0, 30));
          this.resetPauseTimer(); // Reset the 2.0-second silence timer
        }
      };

      this.speechRecognition.onerror = (event) => {
        if (event.error !== "no-speech" && event.error !== "aborted") {
          console.warn("Speech Recognition Error:", event.error);
        }
      };

      this.speechRecognition.onend = () => {
        // Continuous background listening without lag
        if (this.isListeningActive || this.isAlwaysListening || this.isVoiceTypingOnly || this.isAwake) {
          setTimeout(() => {
            try { this.speechRecognition.start(); } catch (e) {}
          }, 60);
        }
      };
    }

    try {
      this.speechRecognition.start();
    } catch (e) {}
  }

  startWakeTimeout() {
    clearTimeout(this.wakeTimeout);
    clearTimeout(this.pauseTimer);
    // Stay awake for 6.0 seconds waiting for command; if no command received, return to standby
    this.wakeTimeout = setTimeout(() => {
      if (this.isAwake && !this.currentUtterance.trim()) {
        console.log("Wake window timed out (no command within 6.0s). Returning to standby...");
        this.isAwake = false;
        this.currentUtterance = "";
        this.cmdInput.value = "";
        this.cmdInput.placeholder = "Command ATLAS or explore...";
        this.updateState("idle", "Standby · Call 'Atlas'");
        if (this.isVoiceTypingOnly) {
          this.stopVoiceTyping();
        }
      }
    }, 6000);
  }

  resetPauseTimer() {
    clearTimeout(this.wakeTimeout);
    clearTimeout(this.pauseTimer);

    // Execute automatically when user has paused speaking for 2.0 seconds
    this.pauseTimer = setTimeout(async () => {
      const commandToExecute = this.currentUtterance.trim();
      if (!commandToExecute) return;

      console.log("2.0-second silence detected. Executing command:", commandToExecute);
      this.isAwake = false;

      // Extract real-time speech PCM audio buffer for Resemblyzer cosine similarity check
      const audioB64 = await this.getPcmWavBase64();

      const focusToggle = document.getElementById("toggle-commander-focus");
      const isCommanderFocus = focusToggle && focusToggle.checked;
      if (isCommanderFocus) {
        this.updateState("processing", "Checking voice biometrics (Cosine)...");
      } else {
        this.updateState("processing", commandToExecute.slice(0, 30));
      }

      this.addChatMessage("user", commandToExecute, "voice");
      this.dispatchCommand(commandToExecute, "voice", audioB64);

      this.cmdInput.value = "";
      this.currentUtterance = "";

      // Recycle speech recognition session to keep Chrome's buffer fresh and lag-free
      try {
        this.speechRecognition.abort();
      } catch (e) {}

      if (this.isVoiceTypingOnly) {
        this.stopVoiceTyping();
      } else if (!this.isAlwaysListening) {
        this.cmdInput.placeholder = "Command ATLAS or explore...";
      }
    }, 2000);
  }

  stopSpeechRecognition() {
    if (this.speechRecognition) {
      try {
        this.speechRecognition.stop();
      } catch (e) {}
    }
  }

  dispatchCommand(commandText, source = "text", audioB64 = null, imageB64 = null, imageName = null) {
    const detailLabel = commandText || (imageName ? `Attached Image: ${imageName}` : "Processing");
    this.updateState("processing", detailLabel);
    this.sendWsAction("execute_command", {
      text: commandText,
      source: source,
      audio_b64: audioB64,
      image_b64: imageB64,
      image_name: imageName
    });
  }
}

// Bootstrap Application on DOM Ready
window.addEventListener("DOMContentLoaded", () => {
  window.atlasApp = new AtlasApp();
});

/**
 * Converts arbitrary browser Audio Blob to genuine 16kHz Mono 16-bit PCM WAV Blob.
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

  const byteLength = channelData.length * 2;
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
  view.setUint16(20, 1, true);
  view.setUint32(24, targetSampleRate, true);
  view.setUint32(28, targetSampleRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(36, 'data');
  view.setUint32(40, byteLength, true);

  let offset = 44;
  for (let i = 0; i < channelData.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, channelData[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
  }

  audioCtx.close();
  return new Blob([wavBuffer], { type: 'audio/wav' });
}
