/**
 * Acoustic Vault Frontend Application Logic
 * Implements:
 * - 🇪🇹 Ethiopian "Qenet" (ቅኝት) Pentatonic Mode Intelligence (Tizita, Bati, Ambassel, Anchihoye)
 * - 🌌 2D Interactive Acoustic Latent Space Map (t-SNE/SVD Canvas with pulsing seed beacons and trajectories)
 * - 📻 "Vibe & Era Dial" Presets (Buna & Tizita, Eskista Beat, Mulatu's Lounge, Azmari Underground, 70s/90s/2020s)
 * - 📥 "My Vault" Favorites Drawer & 1-Click YouTube Multi-Video Playlist Generation
 * - Interactive YouTube IFrame Player API (YT.Player) with privacy-isolated youtube-nocookie.com
 * - Seamless YouTube-like Continuous Autoplay with 5s "Up Next" countdown transition
 * - Fast-path catalog checking to bypass audio extraction for known YouTube URLs
 * - Zero-replay local & server session cooldown ledger
 */

const API_BASE = "/api/v1";

class AcousticVaultApp {
    constructor() {
        this.sessionToken = this.getOrCreateSessionToken();
        this.obscurityFactor = 0.75;
        this.bpmFilter = "all";
        this.qenetFilter = "all";
        this.vibePreset = null;
        this.eraFilter = "all";

        this.activeSeedId = null;
        this.currentTrack = null;
        this.queue = [];
        this.historyStack = [];
        this.localCooldownIds = new Set(JSON.parse(localStorage.getItem("acoustic_cooldown_ids") || "[]"));

        // Autoplay & Countdown State
        this.autoplayEnabled = localStorage.getItem("acoustic_autoplay") !== "false"; // Default true
        this.countdownInterval = null;
        this.countdownRemaining = 5;

        // YouTube Player Instance
        this.ytPlayer = null;
        this.isPlayerReady = false;
        this.pendingVideoId = null;
        this.isPlaying = false;
        this.isMuted = false;

        // My Vault Favorites
        this.vaultFavorites = JSON.parse(localStorage.getItem("acoustic_vault_favorites") || "[]");

        // Galaxy Canvas State
        this.galaxyPoints = [];
        this.galaxyCanvas = null;
        this.galaxyCtx = null;
        this.hoveredPoint = null;
        this.animFrameId = null;

        this.initDOMElements();
        this.bindEvents();
        this.initYouTubePlayer();
        this.initGalaxyCanvas();
        this.initVaultDrawer();
        this.loadCatalogStatus();
        this.loadGalaxyData();
        this.fetchInitialQueue();
    }

    getOrCreateSessionToken() {
        let token = localStorage.getItem("acoustic_session_token");
        if (!token) {
            token = "session_" + Math.random().toString(36).substring(2, 15) + "_" + Date.now();
            localStorage.setItem("acoustic_session_token", token);
        }
        return token;
    }

    initDOMElements() {
        // Sliders & Controls
        this.slider = document.getElementById("obscurity-slider");
        this.obscurityVal = document.getElementById("obscurity-val");
        this.urlInput = document.getElementById("youtube-url-input");
        this.btnIngest = document.getElementById("btn-ingest");
        this.progressContainer = document.getElementById("ingest-progress-container");
        this.progressFill = document.getElementById("ingest-progress-fill");
        this.progressStage = document.getElementById("ingest-stage-text");
        this.progressPct = document.getElementById("ingest-pct-text");

        // Player UI
        this.currentTitle = document.getElementById("current-track-title");
        this.currentChannel = document.getElementById("current-track-channel");
        this.currentViews = document.getElementById("current-track-views");
        this.currentQenetBadge = document.getElementById("current-qenet-badge");
        this.btnStarCurrent = document.getElementById("btn-star-current");
        this.meterBpm = document.getElementById("meter-bpm");
        this.meterEnergy = document.getElementById("meter-energy-fill");
        this.meterBright = document.getElementById("meter-bright-fill");
        this.meterKey = document.getElementById("meter-key");

        // Up Next Overlay UI
        this.upNextOverlay = document.getElementById("up-next-overlay");
        this.countdownNum = document.getElementById("countdown-num");
        this.upNextTitle = document.getElementById("up-next-title");
        this.upNextArtist = document.getElementById("up-next-artist");
        this.upNextMatch = document.getElementById("up-next-match");
        this.upNextProgressFill = document.getElementById("up-next-progress-fill");
        this.btnCancelCountdown = document.getElementById("btn-cancel-countdown");
        this.btnPlayNow = document.getElementById("btn-play-now");

        // Navigation & Actions
        this.btnPrev = document.getElementById("btn-prev");
        this.btnPlayPause = document.getElementById("btn-play-pause");
        this.playPauseIcon = document.getElementById("play-pause-icon");
        this.btnNext = document.getElementById("btn-next");
        this.btnReseed = document.getElementById("btn-reseed");
        this.toggleAutoplay = document.getElementById("toggle-autoplay");
        this.btnRefreshQueue = document.getElementById("btn-refresh-queue");
        this.btnResetSession = document.getElementById("btn-reset-session");

        // Seed & Header
        this.seedTitle = document.getElementById("seed-title");
        this.seedChannel = document.getElementById("seed-channel");
        this.seedBpmBadge = document.getElementById("seed-bpm-badge");
        this.catalogCountBadge = document.getElementById("catalog-count-badge");
        this.queueContainer = document.getElementById("queue-list-container");
        this.cooldownCount = document.getElementById("cooldown-count");

        // Badges & Drawer
        this.btnToggleGalaxy = document.getElementById("btn-toggle-galaxy");
        this.galaxySection = document.getElementById("galaxy-section");
        this.btnOpenVault = document.getElementById("btn-open-vault");
        this.vaultBadgeCount = document.getElementById("vault-badge-count");
        this.vaultTrackCount = document.getElementById("vault-track-count");
        this.vaultDrawer = document.getElementById("vault-drawer");
        this.vaultBackdrop = document.getElementById("vault-backdrop");
        this.btnCloseVault = document.getElementById("btn-close-vault");
        this.vaultListContainer = document.getElementById("vault-list-container");

        // Vault Actions
        this.btnPlayAllYoutube = document.getElementById("btn-play-all-youtube");
        this.btnExportM3u = document.getElementById("btn-export-m3u");
        this.btnExportJson = document.getElementById("btn-export-json");
        this.btnCopyTracklist = document.getElementById("btn-copy-tracklist");
        this.btnClearVault = document.getElementById("btn-clear-vault");

        // Hints
        this.activeQenetDesc = document.getElementById("active-qenet-desc");
        this.activeEraHint = document.getElementById("active-era-hint");

        // Set initial toggle state
        if (this.toggleAutoplay) {
            this.toggleAutoplay.checked = this.autoplayEnabled;
        }
    }

    bindEvents() {
        // Obscurity Slider
        this.slider.addEventListener("input", (e) => {
            this.obscurityFactor = parseFloat(e.target.value) / 100.0;
            this.obscurityVal.textContent = `${e.target.value}%`;
        });

        this.slider.addEventListener("change", () => {
            this.fetchQueue();
        });

        // Vibe Preset Buttons
        document.querySelectorAll(".vibe-pill").forEach(pill => {
            pill.addEventListener("click", () => {
                const vibe = pill.dataset.vibe;
                if (pill.classList.contains("active")) {
                    pill.classList.remove("active");
                    this.vibePreset = null;
                } else {
                    document.querySelectorAll(".vibe-pill").forEach(p => p.classList.remove("active"));
                    pill.classList.add("active");
                    this.vibePreset = vibe;
                }
                this.fetchQueue();
            });
        });

        // Ethiopian Qenet Modal Filter Buttons
        document.querySelectorAll(".qenet-pill").forEach(pill => {
            pill.addEventListener("click", () => {
                document.querySelectorAll(".qenet-pill").forEach(p => p.classList.remove("active"));
                pill.classList.add("active");
                this.qenetFilter = pill.dataset.qenet;
                if (this.activeQenetDesc) {
                    this.activeQenetDesc.textContent = this.qenetFilter === "all" ? "All Scales" : `Mode: ${this.qenetFilter}`;
                }
                this.fetchQueue();
            });
        });

        // Musical Era Buttons
        document.querySelectorAll(".era-pill").forEach(pill => {
            pill.addEventListener("click", () => {
                document.querySelectorAll(".era-pill").forEach(p => p.classList.remove("active"));
                pill.classList.add("active");
                this.eraFilter = pill.dataset.era;
                if (this.activeEraHint) {
                    this.activeEraHint.textContent = this.eraFilter === "all" ? "All Eras" : this.eraFilter;
                }
                this.fetchQueue();
            });
        });

        // Ingestion Trigger
        this.btnIngest.addEventListener("click", () => this.handleIngest());
        this.urlInput.addEventListener("keypress", (e) => {
            if (e.key === "Enter") this.handleIngest();
        });

        // Playback Controls
        if (this.btnPrev) this.btnPrev.addEventListener("click", () => this.playPreviousTrack());
        if (this.btnPlayPause) this.btnPlayPause.addEventListener("click", () => this.togglePlayPause());
        this.btnNext.addEventListener("click", () => this.playNextTrack(true));
        this.btnReseed.addEventListener("click", () => this.reseedFromCurrent());
        this.btnRefreshQueue.addEventListener("click", () => this.fetchQueue());
        this.btnResetSession.addEventListener("click", () => this.resetSessionHistory());

        // Star Current Track
        if (this.btnStarCurrent) {
            this.btnStarCurrent.addEventListener("click", () => {
                if (this.currentTrack) {
                    this.toggleFavorite(this.currentTrack);
                }
            });
        }

        // Toggle Galaxy Section
        if (this.btnToggleGalaxy && this.galaxySection) {
            this.btnToggleGalaxy.addEventListener("click", () => {
                this.galaxySection.classList.toggle("collapsed");
                if (!this.galaxySection.classList.contains("collapsed")) {
                    this.drawGalaxy();
                }
            });
        }

        // Autoplay Toggle
        if (this.toggleAutoplay) {
            this.toggleAutoplay.addEventListener("change", (e) => {
                this.autoplayEnabled = e.target.checked;
                localStorage.setItem("acoustic_autoplay", this.autoplayEnabled);
                if (!this.autoplayEnabled) {
                    this.cancelUpNextCountdown();
                }
            });
        }

        // Up Next Overlay Controls
        if (this.btnCancelCountdown) {
            this.btnCancelCountdown.addEventListener("click", () => this.cancelUpNextCountdown());
        }
        if (this.btnPlayNow) {
            this.btnPlayNow.addEventListener("click", () => {
                this.cancelUpNextCountdown();
                this.playNextTrack(false);
            });
        }

        // Global YouTube Keyboard Shortcuts
        document.addEventListener("keydown", (e) => {
            if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;

            if (e.shiftKey && (e.key === "N" || e.key === "n")) {
                e.preventDefault();
                this.cancelUpNextCountdown();
                this.playNextTrack(true);
            } else if (e.shiftKey && (e.key === "P" || e.key === "p")) {
                e.preventDefault();
                this.cancelUpNextCountdown();
                this.playPreviousTrack();
            } else if (e.key === " " || e.key === "k" || e.key === "K") {
                e.preventDefault();
                this.togglePlayPause();
            } else if (e.key === "m" || e.key === "M") {
                e.preventDefault();
                this.toggleMute();
            } else if (e.key === "Escape") {
                this.cancelUpNextCountdown();
                this.closeVaultDrawer();
            }
        });
    }

    /* ----------------- YouTube IFrame API Integration ----------------- */

    initYouTubePlayer() {
        const createPlayer = () => {
            this.ytPlayer = new YT.Player("yt-player-target", {
                height: "100%",
                width: "100%",
                host: "https://www.youtube-nocookie.com",
                playerVars: {
                    autoplay: 1,
                    enablejsapi: 1,
                    origin: window.location.origin,
                    rel: 0,
                    modestbranding: 1,
                    playsinline: 1
                },
                events: {
                    onReady: (event) => this.onPlayerReady(event),
                    onStateChange: (event) => this.onPlayerStateChange(event),
                    onError: (event) => this.onPlayerError(event)
                }
            });
        };

        if (window.YT && window.YT.Player) {
            createPlayer();
        } else {
            window.onYouTubeIframeAPIReady = () => {
                createPlayer();
            };
        }
    }

    onPlayerReady(event) {
        this.isPlayerReady = true;
        if (this.pendingVideoId) {
            this.ytPlayer.loadVideoById(this.pendingVideoId);
            this.pendingVideoId = null;
        }
    }

    onPlayerStateChange(event) {
        if (event.data === YT.PlayerState.PLAYING) {
            this.isPlaying = true;
            this.updatePlayPauseIcon("⏸️");
            this.cancelUpNextCountdown();
        } else if (event.data === YT.PlayerState.PAUSED) {
            this.isPlaying = false;
            this.updatePlayPauseIcon("▶️");
        } else if (event.data === YT.PlayerState.ENDED) {
            this.isPlaying = false;
            this.updatePlayPauseIcon("▶️");
            this.handleTrackEnded();
        }
    }

    onPlayerError(event) {
        console.warn("YouTube Player error encountered (Code: " + event.data + "). Auto-skipping to next candidate.");
        this.cancelUpNextCountdown();
        setTimeout(() => {
            this.playNextTrack(true);
        }, 1200);
    }

    togglePlayPause() {
        if (!this.ytPlayer || !this.isPlayerReady) return;
        try {
            const state = this.ytPlayer.getPlayerState();
            if (state === YT.PlayerState.PLAYING) {
                this.ytPlayer.pauseVideo();
            } else {
                this.ytPlayer.playVideo();
            }
        } catch (e) {
            console.warn("Could not toggle play/pause", e);
        }
    }

    toggleMute() {
        if (!this.ytPlayer || !this.isPlayerReady) return;
        try {
            if (this.ytPlayer.isMuted()) {
                this.ytPlayer.unMute();
                this.isMuted = false;
            } else {
                this.ytPlayer.mute();
                this.isMuted = true;
            }
        } catch (e) {
            console.warn("Could not toggle mute", e);
        }
    }

    updatePlayPauseIcon(icon) {
        if (this.playPauseIcon) {
            this.playPauseIcon.textContent = icon;
        }
    }

    /* ----------------- Continuous Autoplay & "Up Next" Transition ----------------- */

    handleTrackEnded() {
        if (!this.autoplayEnabled) return;

        if (this.queue.length === 0) {
            this.fetchQueue(true);
            return;
        }

        const nextTrack = this.queue[0];
        this.showUpNextCountdown(nextTrack);
    }

    showUpNextCountdown(nextTrack) {
        this.cancelUpNextCountdown();

        if (this.upNextTitle) this.upNextTitle.textContent = nextTrack.title;
        if (this.upNextArtist) this.upNextArtist.textContent = nextTrack.channel_name;
        if (this.upNextMatch) {
            const matchPct = Math.round(nextTrack.acoustic_similarity_score * 100);
            this.upNextMatch.textContent = `${matchPct}% Sound Match`;
        }

        this.countdownRemaining = 5;
        if (this.countdownNum) this.countdownNum.textContent = this.countdownRemaining;
        if (this.upNextProgressFill) {
            this.upNextProgressFill.style.transition = "none";
            this.upNextProgressFill.style.width = "100%";
            void this.upNextProgressFill.offsetWidth;
            this.upNextProgressFill.style.transition = "width 5s linear";
            this.upNextProgressFill.style.width = "0%";
        }

        if (this.upNextOverlay) {
            this.upNextOverlay.classList.remove("hidden");
        }

        this.countdownInterval = setInterval(() => {
            this.countdownRemaining--;
            if (this.countdownNum) this.countdownNum.textContent = Math.max(0, this.countdownRemaining);
            if (this.countdownRemaining <= 0) {
                this.cancelUpNextCountdown();
                this.playNextTrack(false);
            }
        }, 1000);
    }

    cancelUpNextCountdown() {
        if (this.countdownInterval) {
            clearInterval(this.countdownInterval);
            this.countdownInterval = null;
        }
        if (this.upNextOverlay) {
            this.upNextOverlay.classList.add("hidden");
        }
    }

    /* ----------------- Catalog & Recommendation Queue ----------------- */

    async loadCatalogStatus() {
        try {
            const res = await fetch(`${API_BASE}/health`);
            const data = await res.json();
            if (this.catalogCountBadge) {
                this.catalogCountBadge.textContent = `Indexed Tracks: ${data.indexed_tracks}`;
            }
        } catch (e) {
            console.warn("Could not fetch catalog status", e);
        }
    }

    async fetchInitialQueue() {
        await this.fetchQueue(true);
    }

    async fetchQueue(autoPlayFirst = false, isBackgroundRefill = false) {
        if (!isBackgroundRefill) {
            this.queueContainer.innerHTML = `<div class="loading-queue">Computing pentatonic & acoustic similarities in latent space...</div>`;
        }

        const payload = {
            seed_track_id: this.activeSeedId,
            session_token: this.sessionToken,
            obscurity_factor: this.obscurityFactor,
            qenet_filter: this.qenetFilter !== "all" ? this.qenetFilter : null,
            vibe_preset: this.vibePreset,
            era_filter: this.eraFilter !== "all" ? this.eraFilter : null,
            batch_size: 10,
            excluded_track_ids: Array.from(this.localCooldownIds)
        };

        try {
            const res = await fetch(`${API_BASE}/recommendations/next`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            const newItems = data.items || [];

            if (isBackgroundRefill) {
                const existingIds = new Set(this.queue.map(t => t.track_id));
                const filtered = newItems.filter(t => !existingIds.has(t.track_id));
                this.queue = this.queue.concat(filtered);
            } else {
                this.queue = newItems;
            }

            this.updateCooldownDisplay(data.cooldown_count);

            if (data.active_seed) {
                this.updateSeedDisplay(data.active_seed);
            }

            this.renderQueue();
            this.drawGalaxy();

            if (autoPlayFirst && this.queue.length > 0 && !this.currentTrack) {
                this.playTrack(this.queue[0]);
            }
        } catch (e) {
            if (!isBackgroundRefill) {
                this.queueContainer.innerHTML = `<div class="loading-queue">Error loading recommendations. Please ensure backend is running.</div>`;
            }
            console.error(e);
        }
    }

    renderQueue() {
        if (!this.queue || this.queue.length === 0) {
            this.queueContainer.innerHTML = `<div class="loading-queue">No unplayed tracks match current filters. Try adjusting the obscurity dial or switching Qenet mode.</div>`;
            return;
        }

        this.queueContainer.innerHTML = "";
        this.queue.forEach((item) => {
            const el = document.createElement("div");
            el.className = "queue-item";
            const matchPct = Math.round(item.acoustic_similarity_score * 100);
            const obscurePct = Math.round(item.obscurity_score * 100);
            const qenetMode = item.qenet_mode || "Tizita";
            const qenetClass = qenetMode.toLowerCase();
            const isFav = this.isFavorite(item.track_id);

            el.innerHTML = `
                <div class="queue-item-info">
                    <div class="queue-item-title">${item.title}</div>
                    <div class="queue-item-meta">
                        <span>${item.channel_name}</span>
                        <span>•</span>
                        <span class="qenet-badge ${qenetClass}">ቅኝት: ${qenetMode}</span>
                        <span>•</span>
                        <span>${Math.round(item.bpm)} BPM</span>
                    </div>
                </div>
                <div class="queue-item-scores">
                    <button class="btn-star queue-star ${isFav ? 'starred' : ''}" data-id="${item.track_id}" title="${isFav ? 'Remove from Vault' : 'Save to Vault'}">⭐</button>
                    <span class="score-badge score-match">${matchPct}% Sound Match</span>
                    <span class="score-obscurity">🔮 ${obscurePct}%</span>
                </div>
            `;

            // Click on info area to play
            el.querySelector(".queue-item-info").addEventListener("click", () => {
                this.cancelUpNextCountdown();
                this.playTrack(item);
            });

            // Click star to toggle favorite
            const starBtn = el.querySelector(".queue-star");
            starBtn.addEventListener("click", (e) => {
                e.stopPropagation();
                this.toggleFavorite(item);
                starBtn.classList.toggle("starred", this.isFavorite(item.track_id));
            });

            this.queueContainer.appendChild(el);
        });
    }

    /* ----------------- Playback Actions & Navigation ----------------- */

    playTrack(track) {
        this.cancelUpNextCountdown();

        if (this.currentTrack) {
            this.historyStack.push(this.currentTrack);
            if (this.historyStack.length > 25) this.historyStack.shift();
            this.recordFeedback(this.currentTrack.track_id, "COMPLETED");
        }

        this.currentTrack = track;
        this.addToLocalCooldown(track.track_id);

        // Update UI meters and metadata
        this.currentTitle.textContent = track.title;
        this.currentChannel.textContent = track.channel_name;
        this.currentViews.innerHTML = `<span>👁️ ${this.formatViews(track.view_count)} views</span>`;

        // Update Qenet badge
        const qenet = track.qenet_mode || "Tizita";
        if (this.currentQenetBadge) {
            this.currentQenetBadge.textContent = `ቅኝት: ${qenet}`;
            this.currentQenetBadge.className = `qenet-badge ${qenet.toLowerCase()}`;
        }

        // Update Star status
        if (this.btnStarCurrent) {
            this.btnStarCurrent.classList.toggle("starred", this.isFavorite(track.track_id));
        }

        this.meterBpm.textContent = `${Math.round(track.bpm)} BPM`;
        this.meterEnergy.style.width = `${Math.round((track.energy || 0.5) * 100)}%`;
        this.meterBright.style.width = `${Math.round((track.brightness || 0.5) * 100)}%`;
        this.meterKey.textContent = track.harmonic_key || "C";

        // Load into YouTube Player
        if (this.isPlayerReady && this.ytPlayer) {
            this.ytPlayer.loadVideoById(track.youtube_video_id);
        } else {
            this.pendingVideoId = track.youtube_video_id;
        }

        // Remove from current queue display
        this.queue = this.queue.filter(t => t.track_id !== track.track_id);
        this.renderQueue();
        this.drawGalaxy();

        // Infinite discovery chain
        if (this.queue.length < 3) {
            this.activeSeedId = track.track_id;
            this.fetchQueue(false, true);
        }
    }

    playNextTrack(isSkip = false) {
        this.cancelUpNextCountdown();

        if (this.currentTrack && isSkip) {
            this.recordFeedback(this.currentTrack.track_id, "SKIPPED");
        }

        if (this.queue.length > 0) {
            const next = this.queue[0];
            this.playTrack(next);
        } else {
            this.fetchQueue(true);
        }
    }

    playPreviousTrack() {
        this.cancelUpNextCountdown();

        if (this.historyStack.length > 0) {
            const prev = this.historyStack.pop();
            if (this.currentTrack) {
                this.queue.unshift(this.currentTrack);
            }
            this.currentTrack = null;
            this.playTrack(prev);
        }
    }

    reseedFromCurrent() {
        if (!this.currentTrack) return;
        this.activeSeedId = this.currentTrack.track_id;
        this.updateSeedDisplay(this.currentTrack);
        this.fetchQueue();
    }

    updateSeedDisplay(track) {
        this.seedTitle.textContent = track.title;
        this.seedChannel.textContent = track.channel_name;
        const bpm = track.bpm || (track.acoustic_features && track.acoustic_features.bpm) || "--";
        this.seedBpmBadge.textContent = `${Math.round(bpm)} BPM`;
    }

    addToLocalCooldown(trackId) {
        this.localCooldownIds.add(trackId);
        localStorage.setItem("acoustic_cooldown_ids", JSON.stringify(Array.from(this.localCooldownIds)));
        this.updateCooldownDisplay(this.localCooldownIds.size);
    }

    updateCooldownDisplay(count) {
        if (this.cooldownCount) {
            this.cooldownCount.textContent = count || this.localCooldownIds.size;
        }
    }

    async recordFeedback(trackId, eventType) {
        try {
            await fetch(`${API_BASE}/sessions/feedback`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_token: this.sessionToken,
                    track_id: trackId,
                    event_type: eventType,
                    listen_duration_seconds: 60
                })
            });
        } catch (e) {
            console.warn("Feedback sync failed", e);
        }
    }

    resetSessionHistory() {
        if (confirm("Reset zero-replay session history and cooldown blocks?")) {
            this.localCooldownIds.clear();
            this.historyStack = [];
            localStorage.removeItem("acoustic_cooldown_ids");
            this.sessionToken = "session_" + Math.random().toString(36).substring(2, 15) + "_" + Date.now();
            localStorage.setItem("acoustic_session_token", this.sessionToken);
            this.updateCooldownDisplay(0);
            this.fetchQueue();
        }
    }

    /* ----------------- 2D Acoustic Latent Galaxy Canvas Engine ----------------- */

    initGalaxyCanvas() {
        this.galaxyCanvas = document.getElementById("galaxy-canvas");
        if (!this.galaxyCanvas) return;
        this.galaxyCtx = this.galaxyCanvas.getContext("2d");
        this.galaxyTooltip = document.getElementById("galaxy-tooltip");

        const resizeCanvas = () => {
            if (!this.galaxyCanvas || !this.galaxyCanvas.parentElement) return;
            const rect = this.galaxyCanvas.parentElement.getBoundingClientRect();
            const w = Math.floor(rect.width);
            const h = Math.floor(rect.height) || 360;
            if (w > 0 && h > 0 && (this.galaxyCanvas.width !== w || this.galaxyCanvas.height !== h)) {
                this.galaxyCanvas.width = w;
                this.galaxyCanvas.height = h;
            }
            this.drawGalaxy();
        };

        window.addEventListener("resize", resizeCanvas);
        setTimeout(resizeCanvas, 50);
        setTimeout(resizeCanvas, 300);

        // Mouse Hover & Interaction
        this.galaxyCanvas.addEventListener("mousemove", (e) => {
            const rect = this.galaxyCanvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            const pt = this.findNearestGalaxyPoint(mouseX, mouseY);

            if (pt) {
                this.hoveredPoint = pt;
                this.galaxyCanvas.style.cursor = "pointer";
                if (this.galaxyTooltip) {
                    this.galaxyTooltip.classList.remove("hidden");
                    this.galaxyTooltip.style.left = `${mouseX}px`;
                    this.galaxyTooltip.style.top = `${mouseY - 10}px`;
                    this.galaxyTooltip.innerHTML = `
                        <strong>${pt.title}</strong><br>
                        <span style="color: #94a3b8;">${pt.channel_name}</span><br>
                        <span style="color: #06b6d4;">ቅኝት: ${pt.qenet_mode || "Tizita"}</span> • 
                        <span style="color: #f59e0b;">${Math.round(pt.bpm)} BPM</span> • 
                        <span style="color: #a855f7;">${pt.era || "Amharic"}</span>
                    `;
                }
            } else {
                this.hoveredPoint = null;
                this.galaxyCanvas.style.cursor = "crosshair";
                if (this.galaxyTooltip) {
                    this.galaxyTooltip.classList.add("hidden");
                }
            }
        });

        this.galaxyCanvas.addEventListener("mouseleave", () => {
            this.hoveredPoint = null;
            if (this.galaxyTooltip) this.galaxyTooltip.classList.add("hidden");
        });

        this.galaxyCanvas.addEventListener("click", (e) => {
            const rect = this.galaxyCanvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            const pt = this.findNearestGalaxyPoint(mouseX, mouseY);

            if (pt) {
                this.cancelUpNextCountdown();
                this.playTrack({
                    track_id: pt.track_id,
                    youtube_video_id: pt.youtube_video_id,
                    title: pt.title,
                    channel_name: pt.channel_name,
                    duration_seconds: pt.duration_seconds,
                    view_count: pt.view_count,
                    bpm: pt.bpm,
                    energy: pt.energy,
                    brightness: pt.brightness,
                    qenet_mode: pt.qenet_mode,
                    era: pt.era
                });
            }
        });

        this.startGalaxyAnimation();
    }

    async loadGalaxyData() {
        try {
            const res = await fetch(`${API_BASE}/catalog/galaxy`);
            const data = await res.json();
            this.galaxyPoints = data.points || [];
            this.drawGalaxy();
        } catch (e) {
            console.warn("Could not load galaxy coordinates", e);
        }
    }

    findNearestGalaxyPoint(canvasX, canvasY) {
        if (!this.galaxyCanvas || !this.galaxyPoints.length) return null;
        const rect = this.galaxyCanvas.getBoundingClientRect();
        const width = rect.width;
        const height = rect.height;

        let nearest = null;
        let minDist = 18; // Hit detection radius (px)

        for (const pt of this.galaxyPoints) {
            const rawX = pt.galaxy_x !== undefined ? pt.galaxy_x : (pt.x !== undefined ? pt.x : 0.0);
            const rawY = pt.galaxy_y !== undefined ? pt.galaxy_y : (pt.y !== undefined ? pt.y : 0.0);
            const px = ((rawX + 1.0) / 2.0) * (width - 80) + 40;
            const py = ((rawY + 1.0) / 2.0) * (height - 80) + 40;
            const dist = Math.hypot(canvasX - px, canvasY - py);

            if (dist < minDist) {
                minDist = dist;
                nearest = pt;
            }
        }
        return nearest;
    }

    startGalaxyAnimation() {
        const render = () => {
            this.drawGalaxy();
            this.animFrameId = requestAnimationFrame(render);
        };
        this.animFrameId = requestAnimationFrame(render);
    }

    drawGalaxy() {
        if (!this.galaxyCtx || !this.galaxyCanvas) return;
        const width = this.galaxyCanvas.width || 1200;
        const height = this.galaxyCanvas.height || 360;
        if (width === 0 || height === 0) return;

        const ctx = this.galaxyCtx;
        ctx.clearRect(0, 0, width, height);

        // Draw faint constellation grid
        ctx.strokeStyle = "rgba(255, 255, 255, 0.03)";
        ctx.lineWidth = 1;
        for (let x = 0; x < width; x += 60) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.stroke();
        }
        for (let y = 0; y < height; y += 60) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        }

        const now = Date.now() / 1000;

        // Color mapper for Ethiopian Qenet modes
        const getQenetColor = (mode) => {
            switch ((mode || "").toLowerCase()) {
                case "tizita": return "#f59e0b";
                case "bati": return "#06b6d4";
                case "ambassel": return "#10b981";
                case "anchihoye": return "#a855f7";
                default: return "#38bdf8";
            }
        };

        let seedCoord = null;
        let nextCoord = null;

        // Draw all catalog star nodes
        for (const pt of this.galaxyPoints) {
            const rawX = pt.galaxy_x !== undefined ? pt.galaxy_x : (pt.x !== undefined ? pt.x : 0.0);
            const rawY = pt.galaxy_y !== undefined ? pt.galaxy_y : (pt.y !== undefined ? pt.y : 0.0);
            const px = ((rawX + 1.0) / 2.0) * (width - 80) + 40;
            const py = ((rawY + 1.0) / 2.0) * (height - 80) + 40;
            const color = getQenetColor(pt.qenet_mode);

            const isCurrent = this.currentTrack && this.currentTrack.track_id === pt.track_id;
            const isNext = this.queue.length > 0 && this.queue[0].track_id === pt.track_id;

            if (isCurrent) seedCoord = { x: px, y: py, color };
            if (isNext) nextCoord = { x: px, y: py, color };

            ctx.save();
            ctx.fillStyle = color;
            ctx.shadowColor = color;
            ctx.shadowBlur = isCurrent ? 20 : 6;

            ctx.beginPath();
            const radius = isCurrent ? 7 : (pt === this.hoveredPoint ? 6 : 4);
            ctx.arc(px, py, radius, 0, Math.PI * 2);
            ctx.fill();

            // Pulse ring around current playing track
            if (isCurrent) {
                const pulse = (Math.sin(now * 3) + 1) / 2;
                ctx.strokeStyle = color;
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.arc(px, py, 12 + pulse * 10, 0, Math.PI * 2);
                ctx.stroke();
            }

            ctx.restore();
        }

        // Draw animated curved trajectory line between Current -> Up Next
        if (seedCoord && nextCoord) {
            ctx.save();
            ctx.strokeStyle = "rgba(6, 182, 212, 0.6)";
            ctx.lineWidth = 2;
            ctx.setLineDash([6, 6]);
            ctx.lineDashOffset = -now * 25;

            ctx.beginPath();
            ctx.moveTo(seedCoord.x, seedCoord.y);
            const midX = (seedCoord.x + nextCoord.x) / 2;
            const midY = (seedCoord.y + nextCoord.y) / 2 - 30;
            ctx.quadraticCurveTo(midX, midY, nextCoord.x, nextCoord.y);
            ctx.stroke();
            ctx.restore();
        }
    }

    /* ----------------- My Vault Drawer & Playlist Export ----------------- */

    initVaultDrawer() {
        this.updateVaultDisplay();

        if (this.btnOpenVault) {
            this.btnOpenVault.addEventListener("click", () => this.openVaultDrawer());
        }
        if (this.btnCloseVault) {
            this.btnCloseVault.addEventListener("click", () => this.closeVaultDrawer());
        }
        if (this.vaultBackdrop) {
            this.vaultBackdrop.addEventListener("click", () => this.closeVaultDrawer());
        }

        if (this.btnPlayAllYoutube) {
            this.btnPlayAllYoutube.addEventListener("click", () => this.playAllInYouTube());
        }
        if (this.btnExportM3u) {
            this.btnExportM3u.addEventListener("click", () => this.exportVaultM3U());
        }
        if (this.btnExportJson) {
            this.btnExportJson.addEventListener("click", () => this.exportVaultJSON());
        }
        if (this.btnCopyTracklist) {
            this.btnCopyTracklist.addEventListener("click", () => this.copyVaultLinks());
        }
        if (this.btnClearVault) {
            this.btnClearVault.addEventListener("click", () => this.clearVault());
        }
    }

    openVaultDrawer() {
        if (this.vaultDrawer) this.vaultDrawer.classList.remove("hidden");
        if (this.vaultBackdrop) this.vaultBackdrop.classList.remove("hidden");
        this.renderVaultList();
    }

    closeVaultDrawer() {
        if (this.vaultDrawer) this.vaultDrawer.classList.add("hidden");
        if (this.vaultBackdrop) this.vaultBackdrop.classList.add("hidden");
    }

    isFavorite(trackId) {
        return this.vaultFavorites.some(t => t.track_id === trackId);
    }

    toggleFavorite(track) {
        const idx = this.vaultFavorites.findIndex(t => t.track_id === track.track_id);
        if (idx >= 0) {
            this.vaultFavorites.splice(idx, 1);
        } else {
            this.vaultFavorites.push({
                track_id: track.track_id,
                youtube_video_id: track.youtube_video_id,
                title: track.title,
                channel_name: track.channel_name,
                duration_seconds: track.duration_seconds,
                bpm: track.bpm,
                qenet_mode: track.qenet_mode || "Tizita",
                era: track.era || "Amharic"
            });
        }
        localStorage.setItem("acoustic_vault_favorites", JSON.stringify(this.vaultFavorites));
        this.updateVaultDisplay();
        this.renderVaultList();

        if (this.currentTrack && this.currentTrack.track_id === track.track_id && this.btnStarCurrent) {
            this.btnStarCurrent.classList.toggle("starred", this.isFavorite(track.track_id));
        }
    }

    updateVaultDisplay() {
        const count = this.vaultFavorites.length;
        if (this.vaultBadgeCount) this.vaultBadgeCount.textContent = count;
        if (this.vaultTrackCount) this.vaultTrackCount.textContent = count;
    }

    renderVaultList() {
        if (!this.vaultListContainer) return;

        if (this.vaultFavorites.length === 0) {
            this.vaultListContainer.innerHTML = `<div class="empty-vault">Your Vault is empty.<br>Click the ⭐ icon on any track to save it here!</div>`;
            return;
        }

        this.vaultListContainer.innerHTML = "";
        this.vaultFavorites.forEach((track) => {
            const el = document.createElement("div");
            el.className = "vault-item";
            const qenetMode = track.qenet_mode || "Tizita";

            el.innerHTML = `
                <div class="vault-item-left">
                    <button class="btn btn-sm btn-primary btn-play-vault" title="Play Track">▶️</button>
                    <div class="vault-item-info">
                        <div class="vault-item-title">${track.title}</div>
                        <div class="vault-item-meta">
                            <span>${track.channel_name}</span>
                            <span>•</span>
                            <span class="qenet-badge ${qenetMode.toLowerCase()}">ቅኝት: ${qenetMode}</span>
                        </div>
                    </div>
                </div>
                <div class="vault-item-actions">
                    <a href="https://www.youtube.com/watch?v=${track.youtube_video_id}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline" title="Open in YouTube">↗</a>
                    <button class="btn-text btn-remove-vault" title="Remove from Vault">✕</button>
                </div>
            `;

            el.querySelector(".btn-play-vault").addEventListener("click", () => {
                this.closeVaultDrawer();
                this.playTrack(track);
            });

            el.querySelector(".btn-remove-vault").addEventListener("click", () => {
                this.toggleFavorite(track);
            });

            this.vaultListContainer.appendChild(el);
        });
    }

    playAllInYouTube() {
        if (this.vaultFavorites.length === 0) {
            alert("Your Vault is empty! Save some tracks first.");
            return;
        }
        const videoIds = this.vaultFavorites.map(t => t.youtube_video_id).filter(Boolean);
        const playlistUrl = `https://www.youtube.com/watch_videos?video_ids=${videoIds.join(",")}`;
        window.open(playlistUrl, "_blank", "noopener,noreferrer");
    }

    exportVaultM3U() {
        if (this.vaultFavorites.length === 0) return alert("Your Vault is empty.");
        let m3u = "#EXTM3U\n";
        this.vaultFavorites.forEach(t => {
            m3u += `#EXTINF:${Math.round(t.duration_seconds || 0)},${t.channel_name} - ${t.title}\n`;
            m3u += `https://www.youtube.com/watch?v=${t.youtube_video_id}\n`;
        });

        const blob = new Blob([m3u], { type: "audio/x-mpegurl;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "acoustic_vault_playlist.m3u";
        a.click();
        URL.revokeObjectURL(url);
    }

    exportVaultJSON() {
        if (this.vaultFavorites.length === 0) return alert("Your Vault is empty.");
        const blob = new Blob([JSON.stringify(this.vaultFavorites, null, 2)], { type: "application/json" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "acoustic_vault_favorites.json";
        a.click();
        URL.revokeObjectURL(url);
    }

    copyVaultLinks() {
        if (this.vaultFavorites.length === 0) return alert("Your Vault is empty.");
        const text = this.vaultFavorites.map(t => `${t.title} - https://www.youtube.com/watch?v=${t.youtube_video_id}`).join("\n");
        navigator.clipboard.writeText(text).then(() => {
            if (this.btnCopyTracklist) {
                const orig = this.btnCopyTracklist.textContent;
                this.btnCopyTracklist.textContent = "✓ Copied!";
                setTimeout(() => { this.btnCopyTracklist.textContent = orig; }, 1800);
            }
        });
    }

    clearVault() {
        if (confirm("Are you sure you want to remove all tracks from My Vault?")) {
            this.vaultFavorites = [];
            localStorage.removeItem("acoustic_vault_favorites");
            this.updateVaultDisplay();
            this.renderVaultList();
            if (this.btnStarCurrent) this.btnStarCurrent.classList.remove("starred");
        }
    }

    /* ----------------- Fast-Path URL Check & On-Demand Ingest ----------------- */

    async handleIngest() {
        const url = this.urlInput.value.trim();
        if (!url) return;

        this.btnIngest.disabled = true;
        this.progressContainer.classList.remove("hidden");
        this.progressFill.style.background = "linear-gradient(90deg, var(--accent-cyan), var(--accent-purple))";
        this.progressFill.style.width = "10%";
        this.progressStage.textContent = "Checking Vault catalog fast-path...";
        this.progressPct.textContent = "10%";

        try {
            const checkRes = await fetch(`${API_BASE}/catalog/check-url`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ youtube_url: url })
            });
            const checkData = await checkRes.json();

            if (checkData.exists && checkData.track) {
                this.progressFill.style.width = "100%";
                this.progressStage.textContent = "⚡ Track found in Vault! Starting instant playback...";
                this.progressPct.textContent = "100%";

                setTimeout(() => {
                    this.progressContainer.classList.add("hidden");
                    this.btnIngest.disabled = false;
                    this.urlInput.value = "";
                }, 1200);

                const track = checkData.track;
                this.activeSeedId = track.track_id;
                this.playTrack({
                    track_id: track.track_id,
                    youtube_video_id: track.youtube_video_id,
                    title: track.title,
                    channel_name: track.channel_name,
                    duration_seconds: track.duration_seconds,
                    view_count: track.view_count,
                    bpm: track.acoustic_features.bpm,
                    energy: track.acoustic_features.energy,
                    brightness: track.acoustic_features.brightness,
                    danceability: track.acoustic_features.danceability,
                    harmonic_key: track.acoustic_features.harmonic_key,
                    qenet_mode: track.qenet_mode,
                    era: track.era
                });
                this.fetchQueue();
                return;
            }

            this.progressStage.textContent = "Extracting audio features & Qenet modal scale...";
            this.progressFill.style.width = "25%";
            this.progressPct.textContent = "25%";

            const res = await fetch(`${API_BASE}/ingest/url`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ youtube_url: url })
            });
            const data = await res.json();
            const taskId = data.task_id;

            const eventSource = new EventSource(`${API_BASE}/ingest/stream/${taskId}`);

            eventSource.addEventListener("progress", (e) => {
                const info = JSON.parse(e.data);
                this.progressFill.style.width = `${info.pct}%`;
                this.progressStage.textContent = info.stage;
                this.progressPct.textContent = `${info.pct}%`;

                if (info.status === "COMPLETED") {
                    eventSource.close();
                    this.btnIngest.disabled = false;
                    this.urlInput.value = "";
                    setTimeout(() => {
                        this.progressContainer.classList.add("hidden");
                    }, 2000);

                    if (info.track) {
                        this.loadCatalogStatus();
                        this.loadGalaxyData();
                        this.activeSeedId = info.track.track_id;
                        this.playTrack({
                            track_id: info.track.track_id,
                            youtube_video_id: info.track.youtube_video_id,
                            title: info.track.title,
                            channel_name: info.track.channel_name,
                            duration_seconds: info.track.duration_seconds,
                            view_count: info.track.view_count,
                            bpm: info.track.acoustic_features.bpm,
                            energy: info.track.acoustic_features.energy,
                            brightness: info.track.acoustic_features.brightness,
                            danceability: info.track.acoustic_features.danceability,
                            harmonic_key: info.track.acoustic_features.harmonic_key,
                            qenet_mode: info.track.qenet_mode,
                            era: info.track.era
                        });
                        this.fetchQueue();
                    }
                } else if (info.status === "FAILED") {
                    eventSource.close();
                    this.btnIngest.disabled = false;
                    this.progressStage.textContent = `Failed: ${info.error || "Extraction error"}`;
                    this.progressFill.style.background = "#ef4444";
                }
            });

            eventSource.onerror = () => {
                eventSource.close();
                this.btnIngest.disabled = false;
            };

        } catch (e) {
            alert("Error initiating ingestion: " + e.message);
            this.btnIngest.disabled = false;
            this.progressContainer.classList.add("hidden");
        }
    }

    formatDuration(sec) {
        if (!sec) return "0:00";
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        return `${m}:${s < 10 ? '0' : ''}${s}`;
    }

    formatViews(count) {
        if (!count) return "0";
        if (count >= 1000000) return (count / 1000000).toFixed(1) + "M";
        if (count >= 1000) return (count / 1000).toFixed(1) + "K";
        return count.toString();
    }
}

document.addEventListener("DOMContentLoaded", () => {
    window.app = new AcousticVaultApp();
});
