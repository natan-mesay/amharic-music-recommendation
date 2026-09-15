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
        this.galaxyFilterMode = "all"; // 'all' | 'liked'

        this.initDOMElements();
        this.bindEvents();
        this.initYouTubePlayer();
        this.initGalaxyCanvas();
        this.initVaultDrawer();
        this.initHistoryDrawer();
        this.loadCatalogStatus();
        this.loadGalaxyData();
        this.loadVaultFromBackend();
        this.loadSessionHistoryFromBackend();
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

        // History Drawer Elements
        this.historyBadgeCount = document.getElementById("history-badge-count");
        this.historyTrackCount = document.getElementById("history-track-count");
        this.historyCooldownCount = document.getElementById("history-cooldown-count");
        this.historyDrawer = document.getElementById("history-drawer");
        this.historyBackdrop = document.getElementById("history-backdrop");
        this.btnOpenHistory = document.getElementById("btn-open-history");
        this.btnCloseHistory = document.getElementById("btn-close-history");
        this.btnClearHistory = document.getElementById("btn-clear-history");
        this.historyTableBody = document.getElementById("history-table-body");

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
        console.warn("YouTube Player embed restriction / network error (Code: " + event.data + "). Auto-skipping to next candidate.");
        this.cancelUpNextCountdown();
        if (this.currentTrack) {
            this.recordFeedback(this.currentTrack.track_id, "UNAVAILABLE");
        }
        setTimeout(() => {
            if (this.queue.length > 0) {
                const next = this.queue[0];
                this.playTrack(next);
            } else {
                this.fetchQueue(true);
            }
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

    restoreLastPlayedTrackIfPresent() {
        try {
            const saved = localStorage.getItem("acoustic_last_played_track");
            if (saved) {
                const track = JSON.parse(saved);
                if (track && (track.track_id || track.youtube_video_id)) {
                    this.currentTrack = track;
                    this.activeSeedId = track.track_id || `track_${track.youtube_video_id}`;

                    // Update UI meters and metadata
                    if (this.currentTitle) this.currentTitle.textContent = track.title || "Selected Track";
                    if (this.currentChannel) this.currentChannel.textContent = track.channel_name || "Acoustic Vault";
                    if (this.currentViews) this.currentViews.innerHTML = `<span>👁️ ${this.formatViews(track.view_count || 1000)} views</span>`;

                    const qenet = track.qenet_mode || "Tizita";
                    if (this.currentQenetBadge) {
                        this.currentQenetBadge.textContent = `ቅኝት: ${qenet}`;
                        this.currentQenetBadge.className = `qenet-badge ${qenet.toLowerCase()}`;
                    }

                    if (this.btnStarCurrent) {
                        this.btnStarCurrent.classList.toggle("starred", this.isFavorite(track.track_id, track.youtube_video_id));
                    }

                    if (this.meterBpm) this.meterBpm.textContent = `${Math.round(track.bpm || 100)} BPM`;
                    if (this.meterEnergy) this.meterEnergy.style.width = `${Math.round((track.energy || 0.5) * 100)}%`;
                    if (this.meterBright) this.meterBright.style.width = `${Math.round((track.brightness || 0.5) * 100)}%`;
                    if (this.meterKey) this.meterKey.textContent = track.harmonic_key || "C";

                    // Cue/Load into YouTube player
                    if (this.isPlayerReady && this.ytPlayer && track.youtube_video_id) {
                        this.ytPlayer.loadVideoById(track.youtube_video_id);
                    } else if (track.youtube_video_id) {
                        this.pendingVideoId = track.youtube_video_id;
                    }
                    return true;
                }
            }
        } catch (e) {
            console.warn("Could not restore last played track from storage", e);
        }
        return false;
    }

    async fetchInitialQueue() {
        const hasRestored = this.restoreLastPlayedTrackIfPresent();
        // If we restored the last playing song, populate queue based on it without overwriting currentTrack
        await this.fetchQueue(!hasRestored);
    }

    async fetchQueue(autoPlayFirst = false, isBackgroundRefill = false) {
        if (!isBackgroundRefill) {
            this.queueContainer.innerHTML = `<div class="loading-queue">Computing pentatonic & acoustic similarities in latent space...</div>`;
        }

        const excludedIds = new Set(this.localCooldownIds);
        if (this.vaultFavorites && this.vaultFavorites.length > 0) {
            for (const fav of this.vaultFavorites) {
                if (fav.track_id) excludedIds.add(fav.track_id);
            }
        }

        const payload = {
            seed_track_id: this.activeSeedId,
            session_token: this.sessionToken,
            obscurity_factor: this.obscurityFactor,
            qenet_filter: this.qenetFilter !== "all" ? this.qenetFilter : null,
            vibe_preset: this.vibePreset,
            era_filter: this.eraFilter !== "all" ? this.eraFilter : null,
            batch_size: 10,
            excluded_track_ids: Array.from(excludedIds)
        };

        try {
            const res = await fetch(`${API_BASE}/recommendations/next`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            const newItems = data.items || [];
            const currentVid = this.currentTrack ? this.currentTrack.youtube_video_id : null;
            const currentTid = this.currentTrack ? this.currentTrack.track_id : null;

            if (isBackgroundRefill) {
                const existingTids = new Set(this.queue.map(t => t.track_id));
                const existingVids = new Set(this.queue.map(t => t.youtube_video_id));
                if (currentTid) existingTids.add(currentTid);
                if (currentVid) existingVids.add(currentVid);

                const filtered = newItems.filter(t => !existingTids.has(t.track_id) && !existingVids.has(t.youtube_video_id));
                this.queue = this.queue.concat(filtered);
            } else {
                // Deduplicate new items against themselves and against currently playing track
                const seenTids = new Set();
                const seenVids = new Set();
                if (currentTid) seenTids.add(currentTid);
                if (currentVid) seenVids.add(currentVid);

                const cleanItems = [];
                for (const t of newItems) {
                    if (!seenTids.has(t.track_id) && !seenVids.has(t.youtube_video_id)) {
                        seenTids.add(t.track_id);
                        seenVids.add(t.youtube_video_id);
                        cleanItems.push(t);
                    }
                }
                this.queue = cleanItems;
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
            if (this.historyStack.length > 50) this.historyStack.shift();
            this.recordFeedback(this.currentTrack.track_id, "COMPLETED", this.currentTrack.youtube_video_id);
        }

        this.currentTrack = track;
        this.addToLocalCooldown(track.track_id, track.youtube_video_id);

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
            this.btnStarCurrent.classList.toggle("starred", this.isFavorite(track.track_id, track.youtube_video_id));
        }

        // Persist last played track so refreshing the page resumes this exact track
        try {
            localStorage.setItem("acoustic_last_played_track", JSON.stringify(track));
        } catch (e) {
            console.warn("Could not persist last played track", e);
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

        // Remove from current queue display by both track_id and youtube_video_id
        this.queue = this.queue.filter(t => t.track_id !== track.track_id && t.youtube_video_id !== track.youtube_video_id);
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
            this.recordFeedback(this.currentTrack.track_id, "SKIPPED", this.currentTrack.youtube_video_id);
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

    addToLocalCooldown(trackId, videoId = null) {
        if (trackId) this.localCooldownIds.add(trackId);
        if (videoId) this.localCooldownIds.add(videoId);
        // Generous 150-track sliding window (prevents repeat loops across entire catalog)
        const arr = Array.from(this.localCooldownIds);
        if (arr.length > 150) {
            this.localCooldownIds = new Set(arr.slice(-150));
        }
        localStorage.setItem("acoustic_cooldown_ids", JSON.stringify(Array.from(this.localCooldownIds)));
        this.updateCooldownDisplay(this.localCooldownIds.size);
    }

    updateCooldownDisplay(count) {
        const c = count !== undefined ? count : this.localCooldownIds.size;
        if (this.cooldownCount) {
            this.cooldownCount.textContent = c;
        }
        if (this.historyCooldownCount) {
            this.historyCooldownCount.textContent = c;
        }
    }

    async recordFeedback(trackId, eventType, videoId = null) {
        try {
            await fetch(`${API_BASE}/sessions/feedback`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_token: this.sessionToken,
                    track_id: trackId,
                    youtube_video_id: videoId,
                    event_type: eventType,
                    listen_duration_seconds: 60
                })
            });
            this.loadSessionHistoryFromBackend();
        } catch (e) {
            console.warn("Feedback sync failed", e);
        }
    }

    resetSessionHistory() {
        if (confirm("Reset zero-replay session history and cooldown blocks?")) {
            this.localCooldownIds.clear();
            this.historyStack = [];
            this.currentTrack = null;
            localStorage.removeItem("acoustic_cooldown_ids");
            localStorage.removeItem("acoustic_last_played_track");
            this.sessionToken = "session_" + Math.random().toString(36).substring(2, 15) + "_" + Date.now();
            localStorage.setItem("acoustic_session_token", this.sessionToken);
            this.updateCooldownDisplay(0);
            this.fetchQueue(true);
        }
    }

    /* ----------------- 2D Acoustic Latent Galaxy Canvas Engine ----------------- */

    initGalaxyCanvas() {
        this.galaxyCanvas = document.getElementById("galaxy-canvas");
        if (!this.galaxyCanvas) return;
        this.galaxyCtx = this.galaxyCanvas.getContext("2d");
        this.galaxyTooltip = document.getElementById("galaxy-tooltip");

        // Viewport state for Interactive Zoom & Pan
        this.galaxyViewport = {
            zoom: 1.0,
            panX: 0.0,
            panY: 0.0,
            isDragging: false,
            dragStartX: 0,
            dragStartY: 0,
            dragStartPanX: 0,
            dragStartPanY: 0,
            hasMoved: false,
            touchDist: 0,
            touchCenter: { x: 0, y: 0 }
        };

        const resizeCanvas = () => {
            if (!this.galaxyCanvas || !this.galaxyCanvas.parentElement) return;
            const rect = this.galaxyCanvas.parentElement.getBoundingClientRect();
            const cssW = Math.floor(rect.width);
            const cssH = Math.floor(rect.height) || 380;
            const dpr = window.devicePixelRatio || 1;
            this.dpr = dpr;
            this.logicalWidth = cssW;
            this.logicalHeight = cssH;

            if (cssW > 0 && cssH > 0) {
                const physicalW = Math.floor(cssW * dpr);
                const physicalH = Math.floor(cssH * dpr);
                if (this.galaxyCanvas.width !== physicalW || this.galaxyCanvas.height !== physicalH) {
                    this.galaxyCanvas.width = physicalW;
                    this.galaxyCanvas.height = physicalH;
                    this.galaxyCanvas.style.width = `${cssW}px`;
                    this.galaxyCanvas.style.height = `${cssH}px`;
                }
            }
            this.drawGalaxy();
        };

        window.addEventListener("resize", resizeCanvas);
        setTimeout(resizeCanvas, 50);
        setTimeout(resizeCanvas, 300);

        // --- Mouse & Gesture Event Listeners ---

        // 1. Mouse Wheel Zoom (Cursor-Anchored)
        this.galaxyCanvas.addEventListener("wheel", (e) => {
            e.preventDefault();
            const rect = this.galaxyCanvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            const zoomFactor = Math.exp(-e.deltaY * 0.002);
            const newZoom = this.galaxyViewport.zoom * zoomFactor;
            this.zoomGalaxyAtPoint(newZoom, mouseX, mouseY);
        }, { passive: false });

        // 2. Mouse Down (Initiate Drag / Pan)
        this.galaxyCanvas.addEventListener("mousedown", (e) => {
            if (e.button !== 0) return; // Left click only
            this.galaxyViewport.isDragging = true;
            this.galaxyViewport.hasMoved = false;
            this.galaxyViewport.dragStartX = e.clientX;
            this.galaxyViewport.dragStartY = e.clientY;
            this.galaxyViewport.dragStartPanX = this.galaxyViewport.panX;
            this.galaxyViewport.dragStartPanY = this.galaxyViewport.panY;
            this.galaxyCanvas.classList.add("is-dragging");
        });

        // 3. Global Mouse Move (Drag Panning & Node Hover Hit Testing)
        window.addEventListener("mousemove", (e) => {
            if (this.galaxyViewport.isDragging) {
                const dx = e.clientX - this.galaxyViewport.dragStartX;
                const dy = e.clientY - this.galaxyViewport.dragStartY;
                if (Math.hypot(dx, dy) > 4) {
                    this.galaxyViewport.hasMoved = true;
                    if (this.galaxyTooltip) this.galaxyTooltip.classList.add("hidden");
                }
                this.galaxyViewport.panX = this.galaxyViewport.dragStartPanX + dx;
                this.galaxyViewport.panY = this.galaxyViewport.dragStartPanY + dy;
                return;
            }

            if (!this.galaxyCanvas) return;
            const rect = this.galaxyCanvas.getBoundingClientRect();
            if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) {
                if (this.hoveredPoint) {
                    this.hoveredPoint = null;
                    this.galaxyCanvas.classList.remove("is-hovering-node");
                    if (this.galaxyTooltip) this.galaxyTooltip.classList.add("hidden");
                }
                return;
            }

            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            const pt = this.findNearestGalaxyPoint(mouseX, mouseY);

            if (pt) {
                this.hoveredPoint = pt;
                this.galaxyCanvas.classList.add("is-hovering-node");
                if (this.galaxyTooltip) {
                    this.galaxyTooltip.classList.remove("hidden");
                    this.galaxyTooltip.style.left = `${mouseX}px`;
                    this.galaxyTooltip.style.top = `${mouseY - 10}px`;
                    
                    const isPlaying = this.currentTrack && (
                        (this.currentTrack.track_id && this.currentTrack.track_id === pt.track_id) ||
                        (this.currentTrack.youtube_video_id && this.currentTrack.youtube_video_id === pt.youtube_video_id)
                    );
                    const isFav = this.isFavorite(pt.track_id, pt.youtube_video_id);
                    const isHeard = this.isHeard(pt.track_id, pt.youtube_video_id);
                    const queueIdx = this.queue.findIndex(q =>
                        (q.track_id && q.track_id === pt.track_id) ||
                        (q.youtube_video_id && q.youtube_video_id === pt.youtube_video_id)
                    );

                    let statusBadges = "";
                    if (isPlaying) statusBadges += `<span style="background: rgba(56, 189, 248, 0.2); color: #38bdf8; padding: 2px 6px; border-radius: 4px; font-weight: bold; margin-right: 4px;">⚡ NOW PLAYING</span>`;
                    if (isFav) statusBadges += `<span style="background: rgba(251, 191, 36, 0.2); color: #fbbf24; padding: 2px 6px; border-radius: 4px; font-weight: bold; margin-right: 4px;">⭐ IN VAULT</span>`;
                    if (isHeard && !isPlaying) statusBadges += `<span style="background: rgba(148, 163, 184, 0.2); color: #94a3b8; padding: 2px 6px; border-radius: 4px; margin-right: 4px;">🎧 HEARD</span>`;
                    if (queueIdx >= 0 && !isPlaying) statusBadges += `<span style="background: rgba(6, 182, 212, 0.2); color: #06b6d4; padding: 2px 6px; border-radius: 4px; font-weight: bold;">🎵 QUEUE #${queueIdx + 1}</span>`;

                    this.galaxyTooltip.innerHTML = `
                        <div style="font-weight: 700; margin-bottom: 2px;">${pt.title}</div>
                        <div style="color: #94a3b8; margin-bottom: 6px;">${pt.channel_name}</div>
                        <div style="margin-bottom: 4px;">
                            <span style="color: #06b6d4;">ቅኝት: ${pt.qenet_mode || "Tizita"}</span> • 
                            <span style="color: #f59e0b;">${Math.round(pt.bpm)} BPM</span> • 
                            <span style="color: #a855f7;">${pt.era || "Amharic"}</span>
                        </div>
                        ${statusBadges ? `<div style="margin-top: 6px;">${statusBadges}</div>` : ''}
                    `;
                }
            } else {
                this.hoveredPoint = null;
                this.galaxyCanvas.classList.remove("is-hovering-node");
                if (this.galaxyTooltip) {
                    this.galaxyTooltip.classList.add("hidden");
                }
            }
        });

        // 4. Mouse Up (End Dragging)
        window.addEventListener("mouseup", () => {
            if (this.galaxyViewport.isDragging) {
                this.galaxyViewport.isDragging = false;
                this.galaxyCanvas.classList.remove("is-dragging");
            }
        });

        // 5. Canvas Click (Play Song if not Dragging)
        this.galaxyCanvas.addEventListener("click", (e) => {
            if (this.galaxyViewport.hasMoved) {
                this.galaxyViewport.hasMoved = false;
                return;
            }
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

        // 6. Double Click (Smart Zoom In / Reset)
        this.galaxyCanvas.addEventListener("dblclick", (e) => {
            const rect = this.galaxyCanvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            if (this.galaxyViewport.zoom > 6.0) {
                this.resetGalaxyView();
            } else {
                this.zoomGalaxyAtPoint(this.galaxyViewport.zoom * 2.2, mouseX, mouseY);
            }
        });

        // 7. Touch Gestures (Pinch-to-Zoom & Touch Pan)
        this.galaxyCanvas.addEventListener("touchstart", (e) => {
            if (e.touches.length === 1) {
                const touch = e.touches[0];
                this.galaxyViewport.isDragging = true;
                this.galaxyViewport.hasMoved = false;
                this.galaxyViewport.dragStartX = touch.clientX;
                this.galaxyViewport.dragStartY = touch.clientY;
                this.galaxyViewport.dragStartPanX = this.galaxyViewport.panX;
                this.galaxyViewport.dragStartPanY = this.galaxyViewport.panY;
            } else if (e.touches.length === 2) {
                this.galaxyViewport.isDragging = false;
                const t1 = e.touches[0];
                const t2 = e.touches[1];
                this.galaxyViewport.touchDist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
                const rect = this.galaxyCanvas.getBoundingClientRect();
                this.galaxyViewport.touchCenter = {
                    x: (t1.clientX + t2.clientX) / 2 - rect.left,
                    y: (t1.clientY + t2.clientY) / 2 - rect.top
                };
            }
        }, { passive: true });

        this.galaxyCanvas.addEventListener("touchmove", (e) => {
            if (e.touches.length === 1 && this.galaxyViewport.isDragging) {
                const touch = e.touches[0];
                const dx = touch.clientX - this.galaxyViewport.dragStartX;
                const dy = touch.clientY - this.galaxyViewport.dragStartY;
                if (Math.hypot(dx, dy) > 4) {
                    this.galaxyViewport.hasMoved = true;
                }
                this.galaxyViewport.panX = this.galaxyViewport.dragStartPanX + dx;
                this.galaxyViewport.panY = this.galaxyViewport.dragStartPanY + dy;
            } else if (e.touches.length === 2 && this.galaxyViewport.touchDist > 0) {
                const t1 = e.touches[0];
                const t2 = e.touches[1];
                const newDist = Math.hypot(t2.clientX - t1.clientX, t2.clientY - t1.clientY);
                const scale = newDist / this.galaxyViewport.touchDist;
                const newZoom = this.galaxyViewport.zoom * scale;
                this.zoomGalaxyAtPoint(newZoom, this.galaxyViewport.touchCenter.x, this.galaxyViewport.touchCenter.y);
                this.galaxyViewport.touchDist = newDist;
            }
        }, { passive: true });

        this.galaxyCanvas.addEventListener("touchend", (e) => {
            if (e.touches.length === 0) {
                this.galaxyViewport.isDragging = false;
                this.galaxyViewport.touchDist = 0;
            }
        });

        // 8. Bind Floating HUD Toolbar Controls & View Filter
        const btnFilterAll = document.getElementById("btn-galaxy-filter-all");
        const btnFilterLiked = document.getElementById("btn-galaxy-filter-liked");
        const btnZoomIn = document.getElementById("btn-galaxy-zoom-in");
        const btnZoomOut = document.getElementById("btn-galaxy-zoom-out");
        const btnReset = document.getElementById("btn-galaxy-reset");
        const zoomBadge = document.getElementById("galaxy-zoom-badge");

        if (btnFilterAll && btnFilterLiked) {
            btnFilterAll.addEventListener("click", () => {
                this.galaxyFilterMode = "all";
                btnFilterAll.classList.add("active");
                btnFilterLiked.classList.remove("active");
                this.drawGalaxy();
            });
            btnFilterLiked.addEventListener("click", () => {
                this.galaxyFilterMode = "liked";
                btnFilterLiked.classList.add("active");
                btnFilterAll.classList.remove("active");
                this.drawGalaxy();
            });
        }

        if (btnZoomIn) {
            btnZoomIn.addEventListener("click", () => {
                this.zoomGalaxyAtPoint(this.galaxyViewport.zoom * 1.35);
            });
        }
        if (btnZoomOut) {
            btnZoomOut.addEventListener("click", () => {
                this.zoomGalaxyAtPoint(this.galaxyViewport.zoom / 1.35);
            });
        }
        if (btnReset) {
            btnReset.addEventListener("click", () => this.resetGalaxyView());
        }
        if (zoomBadge) {
            zoomBadge.addEventListener("click", () => this.resetGalaxyView());
        }

        // 9. Keyboard Hotkeys (+ / - / 0 / Esc)
        window.addEventListener("keydown", (e) => {
            if (e.target && (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA")) return;
            if (e.key === "+" || e.key === "=") {
                this.zoomGalaxyAtPoint(this.galaxyViewport.zoom * 1.3);
            } else if (e.key === "-" || e.key === "_") {
                this.zoomGalaxyAtPoint(this.galaxyViewport.zoom / 1.3);
            } else if (e.key === "0" || e.key === "Escape") {
                this.resetGalaxyView();
            }
        });

        this.startGalaxyAnimation();
    }

    projectGalaxyCoord(rawX, rawY) {
        const width = this.logicalWidth || (this.galaxyCanvas ? this.galaxyCanvas.clientWidth : 1300);
        const height = this.logicalHeight || (this.galaxyCanvas ? this.galaxyCanvas.clientHeight : 380);
        const cx = width / 2;
        const cy = height / 2;
        const baseX = ((rawX + 1.0) / 2.0) * (width - 100) + 50;
        const baseY = ((rawY + 1.0) / 2.0) * (height - 100) + 50;
        const screenX = (baseX - cx) * this.galaxyViewport.zoom + cx + this.galaxyViewport.panX;
        const screenY = (baseY - cy) * this.galaxyViewport.zoom + cy + this.galaxyViewport.panY;
        return { screenX, screenY, baseX, baseY };
    }

    zoomGalaxyAtPoint(newZoom, pivotScreenX, pivotScreenY) {
        const width = this.logicalWidth || (this.galaxyCanvas ? this.galaxyCanvas.clientWidth : 1300);
        const height = this.logicalHeight || (this.galaxyCanvas ? this.galaxyCanvas.clientHeight : 380);
        const cx = width / 2;
        const cy = height / 2;
        // Expanded maximum zoom limit up to 35.0 (3500% magnification)
        const clampedZoom = Math.min(Math.max(newZoom, 0.4), 35.0);
        const oldZoom = this.galaxyViewport.zoom;
        if (Math.abs(clampedZoom - oldZoom) < 0.0001) return;

        const px = pivotScreenX !== undefined ? pivotScreenX : cx;
        const py = pivotScreenY !== undefined ? pivotScreenY : cy;
        const ratio = clampedZoom / oldZoom;

        this.galaxyViewport.panX = px - cx - ratio * (px - cx - this.galaxyViewport.panX);
        this.galaxyViewport.panY = py - cy - ratio * (py - cy - this.galaxyViewport.panY);
        this.galaxyViewport.zoom = clampedZoom;

        this.updateGalaxyZoomBadge();
    }

    resetGalaxyView() {
        this.galaxyViewport.zoom = 1.0;
        this.galaxyViewport.panX = 0.0;
        this.galaxyViewport.panY = 0.0;
        this.updateGalaxyZoomBadge();
    }

    updateGalaxyZoomBadge() {
        const zoomBadge = document.getElementById("galaxy-zoom-badge");
        if (zoomBadge) {
            zoomBadge.textContent = `${Math.round(this.galaxyViewport.zoom * 100)}%`;
        }
    }

    updateGalaxyFilterCounts() {
        const countAllEl = document.getElementById("galaxy-count-all");
        const countLikedEl = document.getElementById("galaxy-count-liked");
        if (countAllEl) {
            countAllEl.textContent = (this.galaxyPoints || []).length;
        }
        if (countLikedEl) {
            let likedCount = 0;
            if (this.galaxyPoints && this.galaxyPoints.length > 0) {
                likedCount = this.galaxyPoints.filter(pt => this.isFavorite(pt.track_id, pt.youtube_video_id)).length;
            } else if (this.vaultFavorites) {
                likedCount = this.vaultFavorites.length;
            }
            countLikedEl.textContent = likedCount;
        }
    }

    async loadGalaxyData() {
        try {
            const res = await fetch(`${API_BASE}/catalog/galaxy`);
            const data = await res.json();
            this.galaxyPoints = data.points || [];
            this.updateGalaxyFilterCounts();
            this.drawGalaxy();
        } catch (e) {
            console.warn("Could not load galaxy coordinates", e);
        }
    }

    findNearestGalaxyPoint(canvasX, canvasY) {
        if (!this.galaxyCanvas || !this.galaxyPoints.length) return null;
        let nearest = null;
        let minDist = 22; // Hit detection radius (px) in screen space

        const activePoints = (this.galaxyFilterMode === "liked")
            ? this.galaxyPoints.filter(pt => this.isFavorite(pt.track_id, pt.youtube_video_id) || (this.currentTrack && (
                (this.currentTrack.track_id && this.currentTrack.track_id === pt.track_id) ||
                (this.currentTrack.youtube_video_id && this.currentTrack.youtube_video_id === pt.youtube_video_id)
            )))
            : this.galaxyPoints;

        for (const pt of activePoints) {
            const rawX = pt.galaxy_x !== undefined ? pt.galaxy_x : (pt.x !== undefined ? pt.x : 0.0);
            const rawY = pt.galaxy_y !== undefined ? pt.galaxy_y : (pt.y !== undefined ? pt.y : 0.0);
            const { screenX, screenY } = this.projectGalaxyCoord(rawX, rawY);
            const dist = Math.hypot(canvasX - screenX, canvasY - screenY);

            if (dist < minDist) {
                minDist = dist;
                nearest = pt;
            }
        }
        return nearest;
    }

    startGalaxyAnimation() {
        if (this.animFrameId) cancelAnimationFrame(this.animFrameId);
        const render = () => {
            this.drawGalaxy();
            this.animFrameId = requestAnimationFrame(render);
        };
        this.animFrameId = requestAnimationFrame(render);
    }

    drawGalaxy() {
        if (!this.galaxyCtx || !this.galaxyCanvas) return;
        const width = this.logicalWidth || this.galaxyCanvas.clientWidth || 1300;
        const height = this.logicalHeight || this.galaxyCanvas.clientHeight || 380;
        if (width === 0 || height === 0) return;

        const ctx = this.galaxyCtx;
        const dpr = this.dpr || window.devicePixelRatio || 1;
        const zoom = this.galaxyViewport.zoom;
        const panX = this.galaxyViewport.panX;
        const panY = this.galaxyViewport.panY;
        const cx = width / 2;
        const cy = height / 2;

        ctx.save();
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, width, height);

        // 1. Constellation Grid (Adaptive multi-scale subdivision)
        let effZoom = zoom;
        while (effZoom > 2.5) effZoom /= 2;
        while (effZoom < 0.7) effZoom *= 2;
        const gridSpacing = 65 * effZoom;
        const offsetX = (cx + panX) % gridSpacing;
        const offsetY = (cy + panY) % gridSpacing;

        ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
        ctx.lineWidth = 1;
        for (let x = offsetX; x < width; x += gridSpacing) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, height);
            ctx.stroke();
        }
        for (let y = offsetY; y < height; y += gridSpacing) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(width, y);
            ctx.stroke();
        }

        // Center Axis Crosslines (Transformed with Pan & Zoom)
        const axisX = cx + panX;
        const axisY = cy + panY;

        ctx.strokeStyle = "rgba(255, 255, 255, 0.09)";
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        if (axisX >= 0 && axisX <= width) {
            ctx.moveTo(axisX, 0); ctx.lineTo(axisX, height);
        }
        if (axisY >= 0 && axisY <= height) {
            ctx.moveTo(0, axisY); ctx.lineTo(width, axisY);
        }
        ctx.stroke();
        ctx.setLineDash([]);

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

        const pointCoordsMap = new Map();
        let currentCoord = null;
        const queueCoords = [];
        const historyCoords = [];

        // Dynamic scale bonus for node radii and typography (smoothly damped at extreme zoom)
        const nodeScale = Math.min(Math.sqrt(zoom), 2.4);

        // Filter active points based on All vs Liked mode
        const activePoints = (this.galaxyFilterMode === "liked")
            ? this.galaxyPoints.filter(pt => this.isFavorite(pt.track_id, pt.youtube_video_id) || (this.currentTrack && (
                (this.currentTrack.track_id && this.currentTrack.track_id === pt.track_id) ||
                (this.currentTrack.youtube_video_id && this.currentTrack.youtube_video_id === pt.youtube_video_id)
            )))
            : this.galaxyPoints;

        // Liked Mode Empty State
        if (this.galaxyFilterMode === "liked" && activePoints.length === 0) {
            ctx.save();
            ctx.fillStyle = "rgba(251, 191, 36, 0.9)";
            ctx.font = "bold 15px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
            ctx.textAlign = "center";
            ctx.fillText("⭐ No Liked Songs in Your Vault Yet", cx, cy - 12);
            ctx.fillStyle = "rgba(148, 163, 184, 0.85)";
            ctx.font = "12px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
            ctx.fillText("Click the star icon ⭐ on any song to map it in your personalized Liked Galaxy.", cx, cy + 14);
            ctx.restore();
            ctx.restore();
            return;
        }

        // Build projected screen coordinate map for visible catalog points
        for (const pt of activePoints) {
            const rawX = pt.galaxy_x !== undefined ? pt.galaxy_x : (pt.x !== undefined ? pt.x : 0.0);
            const rawY = pt.galaxy_y !== undefined ? pt.galaxy_y : (pt.y !== undefined ? pt.y : 0.0);
            const { screenX: px, screenY: py } = this.projectGalaxyCoord(rawX, rawY);
            const color = getQenetColor(pt.qenet_mode);

            const isCurrent = this.currentTrack && (
                (this.currentTrack.track_id && this.currentTrack.track_id === pt.track_id) ||
                (this.currentTrack.youtube_video_id && this.currentTrack.youtube_video_id === pt.youtube_video_id)
            );
            const isFav = this.isFavorite(pt.track_id, pt.youtube_video_id);
            const isHeard = this.isHeard(pt.track_id, pt.youtube_video_id);
            const queueIdx = this.queue.findIndex(q =>
                (q.track_id && q.track_id === pt.track_id) ||
                (q.youtube_video_id && q.youtube_video_id === pt.youtube_video_id)
            );

            const coordObj = { pt, px, py, color, isCurrent, isFav, isHeard, queueIdx };
            pointCoordsMap.set(pt.track_id, coordObj);
            pointCoordsMap.set(pt.youtube_video_id, coordObj);

            if (isCurrent) currentCoord = coordObj;
            if (queueIdx >= 0 && queueIdx < 5) queueCoords.push({ ...coordObj, rank: queueIdx + 1 });
            if (isHeard && !isCurrent) historyCoords.push(coordObj);
        }

        // Sort queue coords in order
        queueCoords.sort((a, b) => a.rank - b.rank);

        // 2. Draw Heard History Trail (Faint Connected Flight Path)
        if (historyCoords.length > 1) {
            ctx.save();
            ctx.strokeStyle = "rgba(148, 163, 184, 0.18)";
            ctx.lineWidth = 1.5;
            ctx.setLineDash([3, 4]);
            ctx.beginPath();
            for (let i = 0; i < historyCoords.length; i++) {
                const hc = historyCoords[i];
                if (i === 0) ctx.moveTo(hc.px, hc.py);
                else ctx.lineTo(hc.px, hc.py);
            }
            if (currentCoord) ctx.lineTo(currentCoord.px, currentCoord.py);
            ctx.stroke();
            ctx.restore();
        }

        // 3. Draw Discovery Queue Pathway (Animated Glowing Cyan Trajectory)
        if (currentCoord && queueCoords.length > 0) {
            ctx.save();
            ctx.strokeStyle = "rgba(6, 182, 212, 0.75)";
            ctx.lineWidth = 2 * Math.min(nodeScale, 1.4);
            ctx.setLineDash([6, 6]);
            ctx.lineDashOffset = -now * 30;

            ctx.beginPath();
            ctx.moveTo(currentCoord.px, currentCoord.py);
            for (let i = 0; i < queueCoords.length; i++) {
                const qc = queueCoords[i];
                const prevX = (i === 0) ? currentCoord.px : queueCoords[i - 1].px;
                const prevY = (i === 0) ? currentCoord.py : queueCoords[i - 1].py;
                const midX = (prevX + qc.px) / 2;
                const midY = (prevY + qc.py) / 2 - (20 * nodeScale);
                ctx.quadraticCurveTo(midX, midY, qc.px, qc.py);
            }
            ctx.stroke();
            ctx.restore();
        }

        // 4. Render All Visible Star Nodes
        const uniqueCoords = Array.from(new Set(pointCoordsMap.values()));
        for (const coord of uniqueCoords) {
            const { pt, px, py, color, isCurrent, isFav, isHeard, queueIdx } = coord;
            
            // Culling: Skip rendering if far outside viewport bounds
            if (px < -120 || px > width + 120 || py < -120 || py > height + 120) continue;

            const isHovered = (pt === this.hoveredPoint);

            ctx.save();

            // ⭐ Liked / Vault Starred Tracks (Golden Amber Halo)
            if (isFav) {
                const goldAura = (Math.sin(now * 2.5) + 1) / 2;
                ctx.strokeStyle = "rgba(251, 191, 36, 0.85)";
                ctx.lineWidth = 1.8 * Math.min(nodeScale, 1.3);
                ctx.beginPath();
                ctx.arc(px, py, (11 + goldAura * 4) * nodeScale, 0, Math.PI * 2);
                ctx.stroke();

                // Faint golden filled ring
                ctx.fillStyle = "rgba(251, 191, 36, 0.15)";
                ctx.beginPath();
                ctx.arc(px, py, 11 * nodeScale, 0, Math.PI * 2);
                ctx.fill();
            }

            // 🎧 Heard History Ring
            if (isHeard && !isCurrent) {
                ctx.strokeStyle = "rgba(148, 163, 184, 0.4)";
                ctx.lineWidth = 1;
                ctx.setLineDash([2, 3]);
                ctx.beginPath();
                ctx.arc(px, py, 8 * nodeScale, 0, Math.PI * 2);
                ctx.stroke();
                ctx.setLineDash([]);
            }

            // 🎵 Up Next Queue Marker Ring & Step Number
            if (queueIdx >= 0 && queueIdx < 5 && !isCurrent) {
                ctx.strokeStyle = "#06b6d4";
                ctx.lineWidth = 1.5;
                ctx.beginPath();
                ctx.arc(px, py, 10 * nodeScale, 0, Math.PI * 2);
                ctx.stroke();

                // Number badge
                ctx.fillStyle = "#06b6d4";
                ctx.font = `bold ${Math.round(9 * nodeScale)}px 'JetBrains Mono', monospace`;
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(`${queueIdx + 1}`, px + 12 * nodeScale, py - 10 * nodeScale);
            }

            // Base Star Node
            ctx.fillStyle = isCurrent ? "#38bdf8" : (isFav ? "#fbbf24" : color);
            ctx.shadowColor = isCurrent ? "#38bdf8" : (isFav ? "#fbbf24" : color);
            ctx.shadowBlur = isCurrent ? 25 : (isFav ? 16 : (isHovered ? 12 : 6));

            ctx.beginPath();
            const radius = (isCurrent ? 8 : (isFav ? 6 : (isHovered ? 6 : 4))) * nodeScale;
            ctx.arc(px, py, radius, 0, Math.PI * 2);
            ctx.fill();

            // ⭐ Golden Star Icon in center of Liked tracks
            if (isFav && !isCurrent) {
                ctx.fillStyle = "#ffffff";
                ctx.font = `${Math.round(10 * nodeScale)}px sans-serif`;
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText("★", px, py - 0.5);
            }

            // ⚡ Double Radar Pulse Beacon on Current Playing Song
            if (isCurrent) {
                const pulse1 = (Math.sin(now * 3) + 1) / 2;
                ctx.strokeStyle = "rgba(56, 189, 248, 0.9)";
                ctx.lineWidth = 2 * Math.min(nodeScale, 1.3);
                ctx.beginPath();
                ctx.arc(px, py, (12 + pulse1 * 14) * nodeScale, 0, Math.PI * 2);
                ctx.stroke();

                const pulse2 = (Math.sin(now * 3 + Math.PI / 2) + 1) / 2;
                ctx.strokeStyle = "rgba(56, 189, 248, 0.5)";
                ctx.lineWidth = 1.2;
                ctx.beginPath();
                ctx.arc(px, py, (10 + pulse2 * 20) * nodeScale, 0, Math.PI * 2);
                ctx.stroke();

                ctx.fillStyle = "#ffffff";
                ctx.font = `bold ${Math.round(10 * nodeScale)}px sans-serif`;
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText("⚡", px, py - 0.5);
            }

            // 🏷️ Dynamic Multi-tier Level-of-Detail (LOD) for Deep Zooming (up to 3500%)
            if (zoom >= 1.6) {
                ctx.save();
                ctx.shadowBlur = 4;
                ctx.shadowColor = "#000000";
                
                const fontSize = Math.min(10 * Math.sqrt(zoom / 1.6), 14);
                ctx.font = `600 ${fontSize}px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`;
                ctx.fillStyle = isCurrent ? "#38bdf8" : (isFav ? "#fbbf24" : "rgba(226, 232, 240, 0.95)");
                ctx.textAlign = "center";
                
                const maxLen = zoom > 6.0 ? 55 : (zoom > 3.0 ? 32 : 20);
                const labelText = pt.title.length > maxLen ? pt.title.substring(0, maxLen - 2) + "…" : pt.title;
                ctx.fillText(labelText, px, py + radius + 11);

                if (zoom >= 2.6) {
                    ctx.font = `${Math.min(9 * Math.sqrt(zoom / 2.6), 11)}px 'JetBrains Mono', monospace`;
                    ctx.fillStyle = "rgba(148, 163, 184, 0.9)";
                    const channelText = (pt.channel_name || "Unknown").length > 28 ? (pt.channel_name || "").substring(0, 26) + "…" : pt.channel_name;
                    ctx.fillText(`${channelText} • ${Math.round(pt.bpm)} BPM`, px, py + radius + 23);
                }

                if (zoom >= 5.0) {
                    const mode = pt.qenet_mode || "General";
                    const era = pt.era || "";
                    const views = pt.view_count ? `${(pt.view_count / 1000).toFixed(0)}k views` : "";
                    ctx.font = "bold 9px 'JetBrains Mono', monospace";
                    ctx.fillStyle = color;
                    const tagText = `[${mode}] ${era ? '• ' + era : ''} ${views ? '• ' + views : ''}`.trim();
                    ctx.fillText(tagText, px, py + radius + 35);
                }

                if (zoom >= 9.0) {
                    // Super Close-up Planetary Metadata Card
                    const cardW = 150;
                    const cardH = 20;
                    ctx.fillStyle = "rgba(15, 23, 42, 0.85)";
                    ctx.strokeStyle = "rgba(6, 182, 212, 0.4)";
                    ctx.lineWidth = 1;
                    ctx.fillRect(px - cardW / 2, py + radius + 41, cardW, cardH);
                    ctx.strokeRect(px - cardW / 2, py + radius + 41, cardW, cardH);
                    ctx.fillStyle = "#38bdf8";
                    ctx.font = "9px 'JetBrains Mono', monospace";
                    ctx.fillText(`ID: ${pt.youtube_video_id || (pt.track_id || '').substring(0, 8)}`, px, py + radius + 54);
                }
                ctx.restore();
            }

            ctx.restore();
        }
        ctx.restore();
    }


    /* ----------------- My Vault Drawer & Playlist Export ----------------- */

    initVaultDrawer() {
        this.updateVaultDisplay();
        this.loadVaultFromBackend();

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

    async loadVaultFromBackend() {
        try {
            const res = await fetch(`${API_BASE}/vault/starred`);
            const data = await res.json();
            if (data.starred_tracks) {
                this.vaultFavorites = data.starred_tracks;
                localStorage.setItem("acoustic_vault_favorites", JSON.stringify(this.vaultFavorites));
                this.updateVaultDisplay();
                this.updateGalaxyFilterCounts();
                this.drawGalaxy();
            }
        } catch (e) {
            console.warn("Could not sync vault from SQLite backend", e);
        }
    }

    initHistoryDrawer() {
        if (this.btnOpenHistory) {
            this.btnOpenHistory.addEventListener("click", () => this.openHistoryDrawer());
        }
        if (this.btnCloseHistory) {
            this.btnCloseHistory.addEventListener("click", () => this.closeHistoryDrawer());
        }
        if (this.historyBackdrop) {
            this.historyBackdrop.addEventListener("click", () => this.closeHistoryDrawer());
        }
        if (this.btnClearHistory) {
            this.btnClearHistory.addEventListener("click", () => this.clearSessionHistory());
        }
    }

    openHistoryDrawer() {
        if (this.historyDrawer) this.historyDrawer.classList.remove("hidden");
        if (this.historyBackdrop) this.historyBackdrop.classList.remove("hidden");
        this.loadSessionHistoryFromBackend();
    }

    closeHistoryDrawer() {
        if (this.historyDrawer) this.historyDrawer.classList.add("hidden");
        if (this.historyBackdrop) this.historyBackdrop.classList.add("hidden");
    }

    async loadSessionHistoryFromBackend() {
        try {
            const res = await fetch(`${API_BASE}/sessions/${this.sessionToken}/history?limit=100`);
            const data = await res.json();
            const items = data.history || [];

            if (items.length > 0) {
                items.forEach(h => {
                    if (h.track_id) this.localCooldownIds.add(h.track_id);
                    if (h.youtube_video_id) this.localCooldownIds.add(h.youtube_video_id);
                });
                localStorage.setItem("acoustic_cooldown_ids", JSON.stringify(Array.from(this.localCooldownIds)));
            }

            if (this.historyBadgeCount) this.historyBadgeCount.textContent = items.length;
            if (this.historyTrackCount) this.historyTrackCount.textContent = items.length;
            if (this.historyCooldownCount) this.historyCooldownCount.textContent = this.localCooldownIds.size;
            this.updateCooldownDisplay(this.localCooldownIds.size);

            this.renderListeningHistoryTable(items);
            this.drawGalaxy();
        } catch (e) {
            console.warn("Could not sync session history from SQLite", e);
        }
    }

    renderListeningHistoryTable(items) {
        if (!this.historyTableBody) return;
        if (!items || items.length === 0) {
            this.historyTableBody.innerHTML = `
                <tr>
                    <td colspan="6" class="empty-history">No tracks played yet in this session. Start listening to build your history!</td>
                </tr>
            `;
            return;
        }

        this.historyTableBody.innerHTML = "";
        items.forEach(h => {
            const tr = document.createElement("tr");
            const rawEvent = (h.event_type || "COMPLETED").toUpperCase();
            let eventClass = "completed";
            let eventLabel = "▶️ Completed";

            if (rawEvent.includes("SKIP")) {
                eventClass = "skipped";
                eventLabel = "⏭️ Skipped";
            } else if (rawEvent.includes("DISLIKE")) {
                eventClass = "disliked";
                eventLabel = "👎 Disliked";
            }

            const qenet = h.qenet_mode || "Tizita";
            const bpm = Math.round(h.bpm || 100);
            const title = h.title || "Amharic Track";
            const artist = h.channel_name || "Acoustic Vault";

            // Format played time
            let timeStr = "Recently";
            if (h.created_at) {
                try {
                    const d = new Date(h.created_at.replace(" ", "T") + "Z");
                    timeStr = isNaN(d.getTime()) ? h.created_at.substring(11, 16) : d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
                } catch (_) {
                    timeStr = "Played";
                }
            }

            tr.innerHTML = `
                <td><span class="event-badge ${eventClass}">${eventLabel}</span></td>
                <td>
                    <div class="history-track-title" title="${title}">${title}</div>
                    <div class="history-track-artist">${artist}</div>
                </td>
                <td><span class="qenet-badge ${qenet.toLowerCase()}">ቅኝት: ${qenet}</span></td>
                <td><span style="font-family: var(--font-mono, monospace); font-size: 11px;">${bpm} BPM</span></td>
                <td><span style="font-size: 11px; color: var(--text-muted);">${timeStr}</span></td>
                <td>
                    <button class="btn-replay-history" title="Replay ${title}">▶️ Play</button>
                </td>
            `;

            tr.querySelector(".btn-replay-history").addEventListener("click", () => {
                this.closeHistoryDrawer();
                this.playTrack({
                    track_id: h.track_id,
                    youtube_video_id: h.youtube_video_id,
                    title: title,
                    channel_name: artist,
                    qenet_mode: qenet,
                    bpm: bpm,
                    duration_seconds: h.listen_duration_seconds || 240
                });
            });

            this.historyTableBody.appendChild(tr);
        });
    }

    async clearSessionHistory() {
        if (!confirm("Clear your session playback history and reset discovery cooldowns?")) return;
        try {
            await fetch(`${API_BASE}/sessions/${this.sessionToken}/history`, { method: "DELETE" });
        } catch (e) {
            console.warn("History clear failed", e);
        }
        this.localCooldownIds.clear();
        this.historyStack = [];
        localStorage.removeItem("acoustic_cooldown_ids");
        if (this.historyBadgeCount) this.historyBadgeCount.textContent = "0";
        if (this.historyTrackCount) this.historyTrackCount.textContent = "0";
        if (this.historyCooldownCount) this.historyCooldownCount.textContent = "0";
        this.updateCooldownDisplay(0);
        this.renderListeningHistoryTable([]);
        this.drawGalaxy();
        this.fetchQueue();
    }

    async syncVaultToBackend() {
        try {
            await fetch(`${API_BASE}/vault/starred`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ starred_tracks: this.vaultFavorites })
            });
            await fetch(`${API_BASE}/sessions/vault/sync`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_token: this.sessionToken,
                    liked_track_ids: this.vaultFavorites.map(t => t.track_id)
                })
            });
        } catch (e) {
            console.warn("Could not persist starred tracks to SQLite backend", e);
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

    isFavorite(trackId, videoId = null) {
        if (!trackId && !videoId) return false;
        return this.vaultFavorites.some(t =>
            (trackId && (t.track_id === trackId || t.youtube_video_id === trackId)) ||
            (videoId && (t.youtube_video_id === videoId || t.track_id === videoId))
        );
    }

    isHeard(trackId, videoId = null) {
        if (!trackId && !videoId) return false;
        return (
            (trackId && (this.localCooldownIds.has(trackId) || this.historyStack.some(h => h.track_id === trackId || h.youtube_video_id === trackId))) ||
            (videoId && (this.localCooldownIds.has(videoId) || this.historyStack.some(h => h.youtube_video_id === videoId || h.track_id === videoId)))
        );
    }

    toggleFavorite(track) {
        const tid = track.track_id;
        const vid = track.youtube_video_id;
        const idx = this.vaultFavorites.findIndex(t =>
            (tid && (t.track_id === tid || t.youtube_video_id === tid)) ||
            (vid && (t.youtube_video_id === vid || t.track_id === vid))
        );

        if (idx >= 0) {
            const removed = this.vaultFavorites.splice(idx, 1)[0];
            fetch(`${API_BASE}/vault/starred/${removed.track_id || removed.youtube_video_id}`, { method: "DELETE" }).catch(() => {});
        } else {
            const newFav = {
                track_id: track.track_id || `track_${track.youtube_video_id}`,
                youtube_video_id: track.youtube_video_id,
                title: track.title,
                channel_name: track.channel_name,
                duration_seconds: track.duration_seconds,
                bpm: track.bpm,
                qenet_mode: track.qenet_mode || "Tizita",
                era: track.era || "Amharic"
            };
            this.vaultFavorites.push(newFav);
            fetch(`${API_BASE}/vault/starred`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ starred_tracks: [newFav] })
            }).catch(() => {});
        }

        localStorage.setItem("acoustic_vault_favorites", JSON.stringify(this.vaultFavorites));
        this.updateVaultDisplay();
        this.renderVaultList();
        this.syncVaultToBackend();
        this.drawGalaxy();

        if (this.currentTrack && (this.currentTrack.track_id === tid || this.currentTrack.youtube_video_id === vid) && this.btnStarCurrent) {
            this.btnStarCurrent.classList.toggle("starred", this.isFavorite(tid, vid));
        }
    }


    updateVaultDisplay() {
        const count = this.vaultFavorites.length;
        if (this.vaultBadgeCount) this.vaultBadgeCount.textContent = count;
        if (this.vaultTrackCount) this.vaultTrackCount.textContent = count;
        this.updateGalaxyFilterCounts();
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
            this.syncVaultToBackend();
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
