/**
 * Acoustic Vault Frontend Application Logic
 * Implements:
 * - Interactive YouTube IFrame Player API (YT.Player) with privacy-isolated youtube-nocookie.com
 * - Seamless YouTube-like Continuous Autoplay with 5s "Up Next" countdown transition
 * - Fast-path catalog checking to bypass audio extraction for known YouTube URLs
 * - Infinite discovery radio stream via dynamic background re-seeding
 * - Full player navigation (Prev, Play/Pause, Next, Reseed) and YouTube keyboard shortcuts
 * - Zero-replay local & server session cooldown ledger
 */

const API_BASE = "/api/v1";

class AcousticVaultApp {
    constructor() {
        this.sessionToken = this.getOrCreateSessionToken();
        this.obscurityFactor = 0.75;
        this.bpmFilter = "all";
        this.activeSeedId = null;
        this.currentTrack = null;
        this.queue = [];
        this.historyStack = [];
        this.localCooldownIds = new Set(JSON.parse(localStorage.getItem("acoustic_cooldown_ids") || "[]"));

        // Autoplay & Countdown State
        this.autoplayEnabled = localStorage.getItem("acoustic_autoplay") !== "false"; // Default true
        this.countdownInterval = null;
        this.countdownTimer = null;
        this.countdownRemaining = 5;

        // YouTube Player Instance
        this.ytPlayer = null;
        this.isPlayerReady = false;
        this.pendingVideoId = null;
        this.isPlaying = false;
        this.isMuted = false;

        this.initDOMElements();
        this.bindEvents();
        this.initYouTubePlayer();
        this.loadCatalogStatus();
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
        // Controls
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

        // BPM Pills
        document.querySelectorAll(".tempo-pills .pill").forEach(pill => {
            pill.addEventListener("click", () => {
                document.querySelectorAll(".tempo-pills .pill").forEach(p => p.classList.remove("active"));
                pill.classList.add("active");
                this.bpmFilter = pill.dataset.bpm;
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
            // Ignore keystrokes when typing inside inputs
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
        // YT.PlayerState: -1 (UNSTARTED), 0 (ENDED), 1 (PLAYING), 2 (PAUSED), 3 (BUFFERING), 5 (CUED)
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

        // If no items in queue, attempt immediate replenishment
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
            // Trigger reflow to restart transition
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

    getBpmFilterBounds() {
        if (this.bpmFilter === "slow") return { min_bpm: 50, max_bpm: 100 };
        if (this.bpmFilter === "mid") return { min_bpm: 100, max_bpm: 128 };
        if (this.bpmFilter === "fast") return { min_bpm: 128, max_bpm: 220 };
        return { min_bpm: null, max_bpm: null };
    }

    async fetchInitialQueue() {
        await this.fetchQueue(true);
    }

    async fetchQueue(autoPlayFirst = false, isBackgroundRefill = false) {
        if (!isBackgroundRefill) {
            this.queueContainer.innerHTML = `<div class="loading-queue">Computing acoustic similarities in latent space...</div>`;
        }

        const bpmBounds = this.getBpmFilterBounds();
        const payload = {
            seed_track_id: this.activeSeedId,
            session_token: this.sessionToken,
            obscurity_factor: this.obscurityFactor,
            min_bpm: bpmBounds.min_bpm,
            max_bpm: bpmBounds.max_bpm,
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
                // Filter out duplicates and append to existing queue
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
            this.queueContainer.innerHTML = `<div class="loading-queue">No unplayed tracks match current filters. Try adjusting the obscurity dial or resetting history.</div>`;
            return;
        }

        this.queueContainer.innerHTML = "";
        this.queue.forEach((item) => {
            const el = document.createElement("div");
            el.className = "queue-item";
            const matchPct = Math.round(item.acoustic_similarity_score * 100);
            const obscurePct = Math.round(item.obscurity_score * 100);

            el.innerHTML = `
                <div class="queue-item-info">
                    <div class="queue-item-title">${item.title}</div>
                    <div class="queue-item-meta">
                        <span>${item.channel_name}</span>
                        <span>•</span>
                        <span>${Math.round(item.bpm)} BPM</span>
                        <span>•</span>
                        <span>${this.formatDuration(item.duration_seconds)}</span>
                    </div>
                </div>
                <div class="queue-item-scores">
                    <span class="score-badge score-match">${matchPct}% Sound Match</span>
                    <span class="score-obscurity">🔮 ${obscurePct}% Obscurity</span>
                </div>
            `;
            el.addEventListener("click", () => {
                this.cancelUpNextCountdown();
                this.playTrack(item);
            });
            this.queueContainer.appendChild(el);
        });
    }

    /* ----------------- Playback Actions & Navigation ----------------- */

    playTrack(track) {
        this.cancelUpNextCountdown();

        if (this.currentTrack) {
            // Push old track to history stack for previous playback
            this.historyStack.push(this.currentTrack);
            if (this.historyStack.length > 25) this.historyStack.shift();
            // Record completion feedback
            this.recordFeedback(this.currentTrack.track_id, "COMPLETED");
        }

        this.currentTrack = track;
        this.addToLocalCooldown(track.track_id);

        // Update UI meters and metadata
        this.currentTitle.textContent = track.title;
        this.currentChannel.textContent = track.channel_name;
        this.currentViews.innerHTML = `<span>👁️ ${this.formatViews(track.view_count)} views</span>`;
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

        // Continuous Infinite Radio: Dynamic background replenishment when queue runs low
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
            // Place current back at top of queue
            if (this.currentTrack) {
                this.queue.unshift(this.currentTrack);
            }
            this.currentTrack = null; // Reset so current won't get pushed onto historyStack in playTrack
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
            // 1. Fast-Path Check in Vector Store
            const checkRes = await fetch(`${API_BASE}/catalog/check-url`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ youtube_url: url })
            });
            const checkData = await checkRes.json();

            if (checkData.exists && checkData.track) {
                // Fast-Path Hit: Immediately play and reseed recommendations!
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
                    harmonic_key: track.acoustic_features.harmonic_key
                });
                this.fetchQueue();
                return;
            }

            // 2. Full Ingestion & Feature Extraction Flow via SSE
            this.progressStage.textContent = "Extracting audio features & timbre...";
            this.progressFill.style.width = "25%";
            this.progressPct.textContent = "25%";

            const res = await fetch(`${API_BASE}/ingest/url`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ youtube_url: url })
            });
            const data = await res.json();
            const taskId = data.task_id;

            // Subscribe to SSE progress
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
                        // Instantly play the newly ingested track and generate recommendations
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
                            harmonic_key: info.track.acoustic_features.harmonic_key
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
