/**
 * MAXIMUS COMMAND CENTER — Dashboard Client
 * Real-time WebSocket connection, canvas-based YOLO rendering, live data updates
 */

(() => {
    'use strict';

    // ═══ CONFIG ═══
    const WS_STATE_URL = `ws://${location.host}/ws/state`;
    const WS_CAMERA_URL = `ws://${location.host}/ws/camera`;
    const RECONNECT_DELAY = 2000;

    // ═══ DOM REFS ═══
    const $ = id => document.getElementById(id);
    const clock = $('clock');
    const connStatus = $('connStatus');
    const connLabel = connStatus.querySelector('.label');

    // Camera
    const canvas = $('cameraCanvas');
    const ctx = canvas.getContext('2d');
    const cameraOverlay = $('cameraOverlay');
    const camFps = $('camFps');
    const camObjects = $('camObjects');
    const camDot = $('camDot');

    // Panels
    const yoloBody = $('yoloBody');
    const yoloDot = $('yoloDot');
    const sentinelBody = $('sentinelBody');
    const telemetryBody = $('telemetryBody');
    const thoughtsBody = $('thoughtsBody');
    const thoughtCount = $('thoughtCount');
    const visionBody = $('visionBody');
    const visionDot = $('visionDot');
    const chatBody = $('chatBody');
    const msgCount = $('msgCount');

    // Gauges
    const cpuArc = $('cpuArc');
    const ramArc = $('ramArc');
    const cpuVal = $('cpuVal');
    const ramVal = $('ramVal');
    const diskVal = $('diskVal');
    const tempVal = $('tempVal');
    const battVal = $('battVal');
    const usbVal = $('usbVal');

    // ═══ STATE ═══
    let stateWs = null;
    let cameraWs = null;
    let camImage = new Image();
    let lastDetections = [];
    let camFrameCount = 0;
    let camFpsValue = 0;
    let lastChatCount = 0;

    // ═══ CLOCK ═══
    function updateClock() {
        const now = new Date();
        clock.textContent = now.toLocaleTimeString('en-US', { hour12: false });
    }
    setInterval(updateClock, 1000);
    updateClock();

    // ═══ CONNECTION STATUS ═══
    function setConnected(connected) {
        if (connected) {
            connStatus.classList.add('connected');
            connLabel.textContent = 'LIVE';
        } else {
            connStatus.classList.remove('connected');
            connLabel.textContent = 'OFFLINE';
        }
    }

    // ═══ CAMERA FPS COUNTER ═══
    setInterval(() => {
        camFpsValue = camFrameCount;
        camFrameCount = 0;
        camFps.textContent = `${camFpsValue} FPS`;
    }, 1000);

    // ═══ STATE WEBSOCKET ═══
    function connectStateWs() {
        stateWs = new WebSocket(WS_STATE_URL);

        stateWs.onopen = () => {
            console.log('[State WS] Connected');
            setConnected(true);
        };

        stateWs.onmessage = (event) => {
            try {
                const state = JSON.parse(event.data);
                updateAllPanels(state);
            } catch (e) {
                console.error('[State WS] Parse error:', e);
            }
        };

        stateWs.onclose = () => {
            console.log('[State WS] Disconnected, reconnecting...');
            setConnected(false);
            setTimeout(connectStateWs, RECONNECT_DELAY);
        };

        stateWs.onerror = () => {
            stateWs.close();
        };
    }

    // ═══ CAMERA WEBSOCKET ═══
    function connectCameraWs() {
        cameraWs = new WebSocket(WS_CAMERA_URL);

        cameraWs.onopen = () => {
            console.log('[Camera WS] Connected');
            cameraOverlay.classList.add('hidden');
        };

        cameraWs.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.frame) {
                    camImage = new Image();
                    camImage.onload = () => {
                        drawCameraFrame();
                        camFrameCount++;
                    };
                    camImage.src = `data:image/jpeg;base64,${data.frame}`;
                }
            } catch (e) {
                console.error('[Camera WS] Parse error:', e);
            }
        };

        cameraWs.onclose = () => {
            console.log('[Camera WS] Disconnected, reconnecting...');
            cameraOverlay.classList.remove('hidden');
            setTimeout(connectCameraWs, RECONNECT_DELAY);
        };

        cameraWs.onerror = () => {
            cameraWs.close();
        };
    }

    // ═══ CAMERA CANVAS RENDERING ═══
    function drawCameraFrame() {
        if (!camImage.complete || !camImage.naturalWidth) return;

        // Resize canvas to container
        const container = canvas.parentElement;
        canvas.width = container.clientWidth;
        canvas.height = container.clientHeight;

        // Draw image scaled to fit
        const imgAspect = camImage.naturalWidth / camImage.naturalHeight;
        const canAspect = canvas.width / canvas.height;

        let drawW, drawH, drawX, drawY;
        if (imgAspect > canAspect) {
            drawW = canvas.width;
            drawH = canvas.width / imgAspect;
            drawX = 0;
            drawY = (canvas.height - drawH) / 2;
        } else {
            drawH = canvas.height;
            drawW = canvas.height * imgAspect;
            drawX = (canvas.width - drawW) / 2;
            drawY = 0;
        }

        ctx.fillStyle = '#000';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(camImage, drawX, drawY, drawW, drawH);

        // Draw YOLO bounding boxes
        if (lastDetections.length > 0) {
            const scaleX = drawW / camImage.naturalWidth;
            const scaleY = drawH / camImage.naturalHeight;

            lastDetections.forEach(det => {
                if (!det.bbox || det.bbox.length !== 4) return;

                const [x1, y1, x2, y2] = det.bbox;
                const sx1 = drawX + x1 * scaleX;
                const sy1 = drawY + y1 * scaleY;
                const sx2 = drawX + x2 * scaleX;
                const sy2 = drawY + y2 * scaleY;
                const w = sx2 - sx1;
                const h = sy2 - sy1;

                // Color by confidence
                const conf = det.confidence || 0;
                const hue = conf > 0.7 ? 160 : conf > 0.5 ? 40 : 0;
                const color = `hsl(${hue}, 100%, 60%)`;

                // Bounding box
                ctx.strokeStyle = color;
                ctx.lineWidth = 2;
                ctx.strokeRect(sx1, sy1, w, h);

                // Corner brackets for style
                const corner = Math.min(w, h) * 0.2;
                ctx.lineWidth = 3;
                // Top-left
                ctx.beginPath(); ctx.moveTo(sx1, sy1 + corner); ctx.lineTo(sx1, sy1); ctx.lineTo(sx1 + corner, sy1); ctx.stroke();
                // Top-right
                ctx.beginPath(); ctx.moveTo(sx2 - corner, sy1); ctx.lineTo(sx2, sy1); ctx.lineTo(sx2, sy1 + corner); ctx.stroke();
                // Bottom-left
                ctx.beginPath(); ctx.moveTo(sx1, sy2 - corner); ctx.lineTo(sx1, sy2); ctx.lineTo(sx1 + corner, sy2); ctx.stroke();
                // Bottom-right
                ctx.beginPath(); ctx.moveTo(sx2 - corner, sy2); ctx.lineTo(sx2, sy2); ctx.lineTo(sx2, sy2 - corner); ctx.stroke();

                // Label background
                const label = `${det.object} ${Math.round(conf * 100)}%`;
                ctx.font = '600 11px Inter, sans-serif';
                const metrics = ctx.measureText(label);
                const labelH = 18;
                const labelW = metrics.width + 10;

                ctx.fillStyle = color;
                ctx.globalAlpha = 0.85;
                ctx.fillRect(sx1, sy1 - labelH, labelW, labelH);
                ctx.globalAlpha = 1;

                // Label text
                ctx.fillStyle = '#000';
                ctx.fillText(label, sx1 + 5, sy1 - 5);
            });
        }

        // Scan line effect
        const scanY = (Date.now() / 20) % canvas.height;
        ctx.strokeStyle = 'rgba(0, 255, 204, 0.15)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, scanY);
        ctx.lineTo(canvas.width, scanY);
        ctx.stroke();

        // Status bar at top
        ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
        ctx.fillRect(0, 0, canvas.width, 22);
        ctx.font = '600 10px JetBrains Mono, monospace';
        ctx.fillStyle = '#00FFCC';
        ctx.fillText(`MAX VISION — LIVE  |  ${lastDetections.length} objects`, 8, 14);

        const timeStr = new Date().toLocaleTimeString('en-US', { hour12: false });
        const tw = ctx.measureText(timeStr).width;
        ctx.fillText(timeStr, canvas.width - tw - 8, 14);
    }

    // ═══ UPDATE ALL PANELS ═══
    function updateAllPanels(state) {
        updateSentinel(state);
        updateTelemetry(state);
        updateYolo(state);
        updateThoughts(state);
        updateVision(state);
        updateChat(state);
    }

    // ─── Sentinel Panel ───
    function updateSentinel(state) {
        const modules = [
            { id: 'sentCam', key: 'camera' },
            { id: 'sentYolo', key: 'yolo' },
            { id: 'sentSys', key: 'system' },
            { id: 'sentUsb', key: 'usb' },
            { id: 'sentUpdate', key: 'self_update' },
        ];

        modules.forEach(({ id, key }) => {
            const row = $(id);
            const mod = state[key] || {};
            const dot = row.querySelector('.s-dot');
            const status = row.querySelector('.s-status');
            const isActive = mod.status === 'active';
            const hasError = !!mod.error;

            dot.className = `s-dot ${isActive ? 'active' : hasError ? 'error' : ''}`;
            status.textContent = hasError ? mod.error?.substring(0, 30) : (isActive ? 'ACTIVE' : 'OFF');
        });

        // Camera status dot
        const cam = state.camera || {};
        camDot.className = `status-dot ${cam.status === 'active' ? 'active' : ''}`;
    }

    // ─── Telemetry Panel ───
    function updateTelemetry(state) {
        const sysData = state.system?.data || {};

        const cpu = parseFloat(sysData.cpu) || 0;
        const ram = parseFloat(sysData.ram) || 0;

        // Update arc gauges (stroke-dashoffset: 126 = 0%, 0 = 100%)
        const cpuOffset = 126 - (cpu / 100) * 126;
        const ramOffset = 126 - (ram / 100) * 126;

        cpuArc.style.strokeDashoffset = cpuOffset;
        ramArc.style.strokeDashoffset = ramOffset;

        // Color by usage
        cpuArc.style.stroke = cpu > 80 ? '#FF5555' : cpu > 50 ? '#FFAA00' : '#00FFCC';
        ramArc.style.stroke = ram > 80 ? '#FF5555' : ram > 50 ? '#FFAA00' : '#00FFCC';

        cpuVal.textContent = Math.round(cpu);
        ramVal.textContent = Math.round(ram);

        diskVal.textContent = sysData.disk_free || '--';
        tempVal.textContent = sysData.temp || '--';
        battVal.textContent = sysData.battery || '--';

        const usbDevices = state.usb?.devices || [];
        usbVal.textContent = `${usbDevices.length} devices`;
    }

    // ─── YOLO Panel ───
    function updateYolo(state) {
        const yolo = state.yolo || {};
        const dets = yolo.detections || [];
        lastDetections = dets;

        yoloDot.className = `status-dot ${yolo.status === 'active' ? 'active' : ''}`;
        camObjects.textContent = `${dets.length} objects`;

        if (dets.length === 0) {
            yoloBody.innerHTML = '<div class="empty-state">No objects detected</div>';
            return;
        }

        let html = '';
        dets.slice(0, 15).forEach(det => {
            const conf = Math.round((det.confidence || 0) * 100);
            const confColor = conf > 70 ? 'var(--accent-green)' : conf > 50 ? 'var(--accent-orange)' : 'var(--accent-red)';
            html += `
                <div class="detection-item">
                    <span class="det-icon">▸</span>
                    <span class="det-name">${det.object || '?'}</span>
                    <span class="det-conf" style="color:${confColor}">${conf}%</span>
                    <div class="det-bar-bg"><div class="det-bar-fill" style="width:${conf}%"></div></div>
                </div>`;
        });
        yoloBody.innerHTML = html;
    }

    // ─── Thoughts Panel ───
    function updateThoughts(state) {
        const thoughts = state.thoughts || {};
        const recent = thoughts.recent || [];

        thoughtCount.textContent = thoughts.count || 0;

        if (recent.length === 0) {
            thoughtsBody.innerHTML = '<div class="empty-state">Thinking...</div>';
            return;
        }

        let html = '';
        recent.forEach(t => {
            const ts = t.timestamp ? formatTime(t.timestamp) : '';
            const highSpeak = (t.speak_score || 0) > 0.6;
            html += `
                <div class="thought-item">
                    <div class="thought-meta">
                        <span class="thought-time">${ts}</span>
                        <span class="thought-cat">${t.category || '?'}</span>
                    </div>
                    <div class="thought-text ${highSpeak ? 'high-speak' : ''}">${escapeHtml(t.content || '')}</div>
                </div>`;
        });
        thoughtsBody.innerHTML = html;
        thoughtsBody.scrollTop = thoughtsBody.scrollHeight;
    }

    // ─── Vision Panel ───
    function updateVision(state) {
        const vision = state.vision_model || {};
        const desc = vision.last_description || '';
        const ts = vision.last_update ? formatTime(vision.last_update) : '';

        visionDot.className = `status-dot ${vision.status === 'active' ? 'active' : ''}`;

        if (!desc) {
            visionBody.innerHTML = '<div class="empty-state">Analyzing scene...</div>';
            return;
        }

        visionBody.innerHTML = `
            <div class="vision-desc">${escapeHtml(desc)}</div>
            <div class="vision-time">Updated: ${ts}</div>`;
    }

    // ─── Chat Panel ───
    function updateChat(state) {
        const messages = state.chat || [];

        if (messages.length === 0) {
            chatBody.innerHTML = '<div class="empty-state">Waiting for dialogue...</div>';
            msgCount.textContent = '0 msgs';
            return;
        }

        // Only update if new messages arrived
        if (messages.length === lastChatCount) return;
        lastChatCount = messages.length;

        msgCount.textContent = `${messages.length} msgs`;

        let html = '';
        messages.slice(-30).forEach(msg => {
            const src = (msg.source || '').toUpperCase();
            const ts = msg.timestamp ? formatTime(msg.timestamp) : '';
            let cssClass = 'system';
            let icon = '📡';
            let label = src;

            if (src === 'USER') { cssClass = 'user'; icon = '🎤'; label = 'You'; }
            else if (src === 'MAX') { cssClass = 'max'; icon = '🤖'; label = 'Max'; }
            else if (src === 'TOOL') { cssClass = 'tool'; icon = '⚡'; label = 'Tool'; }
            else if (src === 'MAX_THOUGHT') { cssClass = 'system'; icon = '💭'; label = 'Thought'; }
            else if (src === 'SYS' || src === 'ERROR') { cssClass = 'system'; icon = '⚙'; label = src; }

            html += `
                <div class="chat-msg ${cssClass}">
                    <span class="chat-icon">${icon}</span>
                    <span class="chat-source">${label}</span>
                    <span class="chat-text">${escapeHtml(msg.message || '')}</span>
                    <span class="chat-time">${ts}</span>
                </div>`;
        });

        chatBody.innerHTML = html;
        chatBody.scrollTop = chatBody.scrollHeight;
    }

    // ═══ HELPERS ═══
    function formatTime(isoStr) {
        try {
            const d = new Date(isoStr);
            return d.toLocaleTimeString('en-US', { hour12: false });
        } catch {
            return '';
        }
    }

    function escapeHtml(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }

    // ═══ INIT ═══
    connectStateWs();
    connectCameraWs();

    console.log('[MAXIMUS] Dashboard initialized');

})();
