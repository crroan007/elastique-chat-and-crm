(function () {
    // Elastique Widget Logic v2.5 (Multimodal)

    // Config Defaults
    const DEFAULT_AVATAR = "/static/sarah_avatar.png";

    const WIDGET_HTML = `
        <div id="elastique-launcher" onclick="window.elastiqueWidget.toggle()">
            <svg viewBox="0 0 24 24" fill="white" width="28" height="28">
                <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/>
            </svg>
        </div>
        
        <div id="elastique-modal">
            <div class="chat-header">
                <img src="${DEFAULT_AVATAR}" class="chat-header-avatar" alt="Sarah">
                <div class="title-block">
                    <span class="name">Sarah</span>
                    <span class="role">Lymphatic Wellness Guide</span>
                </div>
                <div class="header-controls" style="display: flex; gap: 10px; align-items: center;">
                    <button class="reset-btn" onclick="window.elastiqueWidget.resetSession()" title="Restart Chat" style="background: none; border: none; cursor: pointer; color: #666;">
                        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M23 4v6h-6"></path>
                            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                        </svg>
                    </button>
                    <button class="close-btn" onclick="window.elastiqueWidget.toggle()">×</button>
                </div>
            </div>
            
            <div class="chat-body" id="chat-messages">
                <!-- Messages will be injected here dynamically -->
            </div>
            
            <div class="chat-footer">
                <div class="input-actions">
                     <!-- File Upload -->
                    <label for="file-upload" class="action-btn" title="Upload Photo/Video">
                        <svg viewBox="0 0 24 24" width="20" height="20" stroke="currentColor" fill="none" stroke-width="2">
                            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                            <circle cx="12" cy="13" r="4"/>
                        </svg>
                    </label>
                    <input type="file" id="file-upload" accept="image/*,video/*,audio/*" hidden onchange="window.elastiqueWidget.handleFile(this)">

                    <!-- Mic Button -->
                    <button id="mic-btn" class="action-btn" title="Speak" onclick="window.elastiqueWidget.toggleMic()">
                        <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                            <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.66 9 5v6c0 1.66 1.34 3 3 3z"/>
                            <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z"/>
                        </svg>
                    </button>
                </div>

                <input type="text" id="chat-input" placeholder="Type a message..." onkeypress="window.elastiqueWidget.handleKeyPress(event)">
                
                <button class="send-btn" onclick="window.elastiqueWidget.send()">
                    <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor">
                        <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                    </svg>
                </button>
            </div>
        </div>
        
        <style>
            .input-actions { display: flex; align-items: center; gap: 5px; margin-right: 5px; }
            .action-btn { background: none; border: none; cursor: pointer; color: #666; padding: 5px; border-radius: 50%; display: flex; align-items: center; justify-content: center;}
            .action-btn:hover { background: #f0f0f0; color: #6C5CE7; }
            .action-btn.recording { color: red; animation: pulse 1s infinite; background: #ffe6e6; }
            @keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.1); } 100% { transform: scale(1); } }
        </style>
    `;

    class ElastiqueWidget {
        constructor() {
            this.config = {};
            this.isOpen = false;
            this.mediaRecorder = null;
            this.audioChunks = [];

            // [NEW] Timeout Logic (30 mins)
            const SESSION_TIMEOUT_MS = 30 * 60 * 1000;
            const lastActive = localStorage.getItem("elastique_last_active");
            const now = Date.now();

            if (lastActive && (now - parseInt(lastActive) > SESSION_TIMEOUT_MS)) {
                console.log("Session timed out. Resetting.");
                localStorage.removeItem("elastique_session_id");
            }
            localStorage.setItem("elastique_last_active", now.toString()); // Update active

            // Persistence Logic
            let storedSession = localStorage.getItem("elastique_session_id");
            if (!storedSession) {
                storedSession = "session_" + Date.now();
                localStorage.setItem("elastique_session_id", storedSession);
            }
            this.sessionId = storedSession;
        }

        init(config) {
            this.config = config;
            const container = document.getElementById(config.containerId);
            if (!container) return;

            container.innerHTML = WIDGET_HTML;

            // Customize Info
            if (config.botName) container.querySelector('.name').innerText = config.botName;
            if (config.title) container.querySelector('.role').innerText = config.title;
        }

        toggle() {
            this.isOpen = !this.isOpen;
            const modal = document.getElementById('elastique-modal');
            modal.style.display = this.isOpen ? 'flex' : 'none';
            if (this.isOpen) {
                document.getElementById('chat-input').focus();
                // [FIX] Ensure Start Event is sent if chat is empty (e.g. after refresh)
                const container = document.getElementById('chat-messages');
                if (container.children.length === 0) {
                    this.send("Event: Start", true);
                }
            }
        }

        resetSession() {
            if (confirm("Start a new conversation?")) {
                localStorage.removeItem("elastique_session_id");
                // Generate new one immediately
                this.sessionId = "session_" + Date.now();
                localStorage.setItem("elastique_session_id", this.sessionId);
                localStorage.setItem("elastique_last_active", Date.now().toString());

                // Clear UI
                const container = document.getElementById('chat-messages');
                container.innerHTML = '';

                // Trigger Greeting
                this.send("Event: Start", true);
            }
        }

        open() {
            this.isOpen = true;
            document.getElementById('elastique-modal').style.display = 'flex';
            const container = document.getElementById('chat-messages');
            if (container.children.length === 0) {
                this.send("Event: Start", true);
            }
        }

        handleKeyPress(e) {
            if (e.key === 'Enter') this.send();
        }

        appendMessage(text, sender, type = 'text') {
            const container = document.getElementById('chat-messages');
            const row = document.createElement('div');
            row.className = `message-row ${sender === 'user' ? 'user-row' : ''}`;

            let html = '';
            if (sender === 'bot') {
                html += `<img src="/static/sarah_avatar.png" class="bot-avatar-small">`;
            }

            html += `<div class="message-bubble ${sender}">`;

            if (type === 'html') {
                html += text;
            } else {
                html += this.formatMessage(text);
            }
            html += `</div>`;
            row.innerHTML = html;
            container.appendChild(row);
            container.scrollTop = container.scrollHeight;
        }

        formatMessage(text) {
            if (!text) return "";

            // 1. Sanitize to prevent HTML injection (basic)
            let safeText = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");

            // 2. Bold (**text**)
            safeText = safeText.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');

            // 3. Italic (*text* or _text_)
            safeText = safeText.replace(/\*(.*?)\*/g, '<i>$1</i>');
            safeText = safeText.replace(/_(.*?)_/g, '<i>$1</i>');

            // 4. Links [Text](URL)
            safeText = safeText.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');

            // 5. Lists (Lines starting with * or -)
            // We split by newline, check for list items, and wrap.
            let lines = safeText.split('\n');
            let inList = false;
            let formattedLines = [];

            for (let line of lines) {
                let trimmed = line.trim();
                if (trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
                    if (!inList) {
                        formattedLines.push('<ul>');
                        inList = true;
                    }
                    formattedLines.push(`<li>${trimmed.substring(2)}</li>`);
                } else {
                    if (inList) {
                        formattedLines.push('</ul>');
                        inList = false;
                    }
                    formattedLines.push(line + '<br>');
                }
            }
            if (inList) formattedLines.push('</ul>');

            return formattedLines.join('');
        }

        // --- MULTIMODAL LOGIC ---

        async handleFile(input) {
            if (input.files && input.files[0]) {
                this.pendingFile = input.files[0];
                this.updateFileUI(this.pendingFile.name);
            }
        }

        updateFileUI(filename) {
            const inputField = document.getElementById('chat-input');
            const container = document.querySelector('.input-actions');

            // Remove existing indicator if any
            const existing = document.getElementById('file-indicator');
            if (existing) existing.remove();

            if (filename) {
                // Show visual indicator
                const indicator = document.createElement('div');
                indicator.id = 'file-indicator';
                indicator.innerHTML = `
                    <span style="font-size: 12px; color: #6C5CE7; background: #EEE; padding: 2px 6px; border-radius: 4px; display: flex; align-items: center; gap: 4px;">
                        📎 ${filename.substring(0, 15)}... 
                        <span style="cursor: pointer; color: #999;" onclick="window.elastiqueWidget.clearFile()">×</span>
                    </span>`;
                // Insert before the input field in the footer
                const footer = document.querySelector('.chat-footer');
                footer.insertBefore(indicator, footer.firstChild);
            }
        }

        clearFile() {
            this.pendingFile = null;
            this.updateFileUI(null);
            document.getElementById('file-upload').value = ""; // Reset input
        }

        async toggleMic() {
            const btn = document.getElementById('mic-btn');

            if (this.mediaRecorder && this.mediaRecorder.state === "recording") {
                // STOP Recording
                this.mediaRecorder.stop();
                btn.classList.remove("recording");
                this.appendMessage("🎤 Processing Audio...", 'user');
            } else {
                // START Recording
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                    this.mediaRecorder = new MediaRecorder(stream);
                    this.audioChunks = [];

                    this.mediaRecorder.ondataavailable = (event) => {
                        this.audioChunks.push(event.data);
                    };

                    this.mediaRecorder.onstop = async () => {
                        const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                        // Create a File object from blob
                        const file = new File([audioBlob], "voice_message.webm", { type: "audio/webm" });
                        // Voice is Auto-Sent (Standard UX)
                        await this.uploadMedia(file, null);
                    };

                    this.mediaRecorder.start();
                    btn.classList.add("recording");
                } catch (err) {
                    console.error("Mic Error:", err);
                    alert("Could not access microphone.");
                }
            }
        }

        async send(textOverride = null, hidden = false) {
            const input = document.getElementById('chat-input');
            const text = textOverride || input.value.trim();

            // Validation: Must have text OR a pending file
            if (!text && !this.pendingFile) return;

            if (!hidden) {
                // UX: Show text immediately. If file exists, show that too.
                let displayMsg = text;
                if (this.pendingFile) displayMsg += ` <br><small>📎 [Attached: ${this.pendingFile.name}]</small>`;
                this.appendMessage(displayMsg, 'user', 'html');

                input.value = '';
                this.updateFileUI(null); // Clear UI indicator
            }

            try {
                if (this.pendingFile) {
                    // Scenario A: File (+ optional Text)
                    await this.uploadMedia(this.pendingFile, text);
                    this.pendingFile = null; // Clear queue
                } else {
                    // Scenario B: Text Only
                    // [NEW] Smart Context: Include persisted email
                    const storedEmail = localStorage.getItem("elastique_user_email");
                    const payload = {
                        message: text,
                        session_id: this.sessionId,
                        email: storedEmail || null // Pass known email if we have it
                    };

                    const response = await fetch(this.config.apiUrl, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    const data = await response.json();

                    // [NEW] Persist Identity if Backend identified user
                    if (data.user_email) {
                        localStorage.setItem("elastique_user_email", data.user_email);
                    }

                    this.appendMessage(data.response, 'bot');
                }
            } catch (e) {
                console.error(e);
                this.appendMessage("Connection failed.", 'bot');
            }
        }

        async uploadMedia(file, textMessage) {
            const formData = new FormData();
            formData.append('file', file);
            formData.append('session_id', this.sessionId);
            if (textMessage) {
                formData.append('message', textMessage);
            }

            try {
                const response = await fetch('/upload', { // Calls the new /upload endpoint
                    method: 'POST',
                    body: formData // No Content-Type header (browser sets it for multipart)
                });
                const data = await response.json();
                this.appendMessage(data.response, 'bot');
                if (data.audio) {
                    this.playAudio(data.audio);
                }
            } catch (e) {
                console.error(e);
                this.appendMessage("Upload failed.", 'bot');
            }
        }

        playAudio(base64String) {
            try {
                const audioBlob = this.base64ToBlob(base64String, 'audio/mp3');
                const audioUrl = URL.createObjectURL(audioBlob);
                const audio = new Audio(audioUrl);
                audio.play().catch(e => {
                    console.warn("Autoplay blocked:", e);
                });
            } catch (e) {
                console.error("Audio Playback Failed", e);
            }
        }

        base64ToBlob(base64, type) {
            const binaryString = window.atob(base64);
            const len = binaryString.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            return new Blob([bytes], { type: type });
        }
    }

    window.elastiqueWidget = new ElastiqueWidget();

})();
