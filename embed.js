(function () {
    // 1. CONFIGURATION
    const API_URL = "http://localhost:8000/chat";
    const WIDGET_ID = "elastique-chat-widget";

    // 2. INJECT CSS
    const styles = `
        /* --- WIDGET CONTAINER --- */
        #${WIDGET_ID} {
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 9999;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            display: flex;
            align-items: flex-end;
            gap: 15px;
        }

        /* --- CHAT BUBBLE (LAUNCHER) --- */
        #${WIDGET_ID} .chat-bubble {
            width: 60px;
            height: 60px;
            background-color: #6C5CE7; /* GHL Purpleish */
            border-radius: 50%;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            transition: transform 0.2s;
            z-index: 10002; /* Top */
        }
        #${WIDGET_ID} .chat-bubble:hover {
            transform: scale(1.1);
        }
        #${WIDGET_ID} .chat-bubble svg {
            width: 30px;
            height: 30px;
            fill: white;
        }

        /* --- CHAT WINDOW --- */
        #${WIDGET_ID} .chat-window {
            width: 350px;
            height: 500px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
            display: none; /* Hidden by default */
            flex-direction: column;
            overflow: visible; /* FIXED: Allow Chevron to hang out */
            border: 1px solid #eee;
            position: relative; /* For chevron positioning */
            z-index: 10001;
        }

        /* --- AVATAR DRAWER (Bottom Center Pop-up) --- */
        #${WIDGET_ID} .avatar-drawer {
            position: fixed;
            bottom: -600px; /* Hidden below fold */
            left: 50%;
            transform: translateX(-50%);
            width: 350px; /* Larger Portrait */
            height: 450px;
            background: transparent; /* Seamless */
            border-radius: 20px 20px 0 0;
            overflow: hidden;
            transition: bottom 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275); /* Bouncy pop */
            box-shadow: 0 -10px 40px rgba(0,0,0,0.2);
            display: flex;
            flex-direction: column;
            justify-content: flex-end; /* Align bottom */
            align-items: center;
            z-index: 10000;
            pointer-events: none; /* Let clicks pass through transparent areas */
        }
        #${WIDGET_ID} .avatar-drawer.open {
            bottom: 0; /* Slide up */
            pointer-events: auto;
        }
        #${WIDGET_ID} .avatar-video-container {
            width: 100%;
            height: 100%;
            position: relative;
            background: #1a1a1a; /* Dark background for video */
            border-radius: 20px 20px 0 0;
            overflow: hidden;
        }
        #${WIDGET_ID} video {
            width: 100%;
            height: 100%;
            object-fit: cover;
        }
        #${WIDGET_ID} .voice-status {
            position: absolute;
            bottom: 80px; /* Above bottom edge */
            left: 50%;
            transform: translateX(-50%);
            background: rgba(108, 92, 231, 0.9); /* Purple Branding */
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 14px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
            backdrop-filter: blur(4px);
            z-index: 10005;
            box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        }
        #${WIDGET_ID} .mic-icon {
            width: 10px;
            height: 10px;
            background: white;
            border-radius: 50%;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(1); opacity: 1; }
            50% { transform: scale(1.5); opacity: 0.5; }
            100% { transform: scale(1); opacity: 1; }
        }

        /* --- CHEVRON TOGGLE --- */
        #${WIDGET_ID} .chevron-toggle {
            position: absolute;
            top: 60px; /* Moved down slightly */
            left: -40px; /* More distinct protrusion */
            width: 40px; /* Wider hit area */
            height: 60px;
            background: #6C5CE7;
            border-top-left-radius: 30px; 
            border-bottom-left-radius: 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            box-shadow: -2px 0 5px rgba(0,0,0,0.1);
            color: white;
            font-weight: bold;
            font-size: 20px;
            z-index: 2147483647; /* MAX Z-INDEX */
        }
        #${WIDGET_ID} .chevron-toggle:hover {
            background: #5A4EBC;
        }

        /* Header */
        #${WIDGET_ID} .chat-header {
            background: #6C5CE7;
            color: white;
            padding: 15px;
            font-weight: 600;
            display: flex;
            align-items: center;
        }
        #${WIDGET_ID} .chat-header img {
            width: 40px;
            height: 40px;
            border-radius: 50%;
            background: white;
            margin-right: 12px;
            object-fit: cover;
            object-position: top;
            border: 2px solid white;
            box-shadow: 0 1px 3px rgba(0,0,0,0.2);
        }

        /* Messages Area */
        #${WIDGET_ID} .chat-messages {
            flex: 1;
            padding: 15px;
            overflow-y: auto;
            background: #f9f9f9;
        }

        /* Message Bubbles */
        #${WIDGET_ID} .message {
            margin-bottom: 12px;
            max-width: 80%;
            padding: 10px 14px;
            border-radius: 12px;
            font-size: 14px;
            line-height: 1.4;
        }
        #${WIDGET_ID} .message strong {
            font-weight: 700;
        }
        #${WIDGET_ID} .message em {
            font-style: italic;
        }
        #${WIDGET_ID} .message ul {
            margin: 0;
            padding-left: 20px;
        }
        #${WIDGET_ID} .message li {
            margin-bottom: 4px;
        }
        #${WIDGET_ID} .message a {
            color: inherit;
            text-decoration: underline;
        }
        #${WIDGET_ID} .message.bot {
            background: white;
            color: #6C5CE7; /* Sarah's text is Purple */
            border-bottom-left-radius: 2px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            margin-right: auto;
            border: 1px solid #eee;
        }
        #${WIDGET_ID} .message.user {
            background: #f5f5f5; /* Light Grey */
            color: black; /* User text is Black */
            border-bottom-right-radius: 2px;
            margin-left: auto;
        }

        /* Input Area */
        #${WIDGET_ID} .chat-input {
            padding: 15px;
            background: white;
            border-top: 1px solid #eee;
            display: flex;
            align-items: center;
        }
        #${WIDGET_ID} .chat-input input {
            flex: 1;
            border: 1px solid #ddd;
            border-radius: 20px;
            padding: 10px 16px;
            outline: none;
            font-size: 14px;
        }
        #${WIDGET_ID} .chat-input button {
            background: none;
            border: none;
            color: #6C5CE7;
            margin-left: 10px;
            cursor: pointer;
            font-weight: 700;
        }

        /* Typing Indicator */
        #${WIDGET_ID} .typing-indicator {
            display: none;
            padding: 10px 14px;
            background: white;
            border-radius: 12px;
            border-bottom-left-radius: 2px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
            width: fit-content;
            margin-bottom: 12px;
        }
        #${WIDGET_ID} .typing-indicator span {
            display: inline-block;
            width: 6px;
            height: 6px;
            background-color: #aaa;
            border-radius: 50%;
            animation: typing 1.4s infinite ease-in-out both;
            margin: 0 2px;
        }
        #${WIDGET_ID} .typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
        #${WIDGET_ID} .typing-indicator span:nth-child(2) { animation-delay: -0.16s; }
        
        @keyframes typing {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }

        /* --- MIC PROMPT (Overlay) --- */
        #${WIDGET_ID} .mic-prompt {
            display: none;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 10002;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            width: 80%;
        }
        #${WIDGET_ID} .mic-btn {
            margin-top: 10px;
            background: #6C5CE7;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
        }

        /* --- STOP BUTTON PULSE ANIMATION --- */
        @keyframes eq-pulse {
            0% { box-shadow: 0 0 0 0 rgba(108, 92, 231, 0.7); transform: translateX(-50%) scale(1); }
            50% { box-shadow: 0 0 0 10px rgba(108, 92, 231, 0); transform: translateX(-50%) scale(1.1); }
            100% { box-shadow: 0 0 0 0 rgba(108, 92, 231, 0); transform: translateX(-50%) scale(1); }
        }

        /* --- PRODUCT TILE STYLES (Reused from GHL) --- */
        .ghl-product-tile {
            font-family: inherit;
        }
    `;

    const styleSheet = document.createElement("style");
    styleSheet.innerText = styles;
    document.head.appendChild(styleSheet);

    // 3. INJECT HTML
    const widgetHTML = `
        <div id="${WIDGET_ID}">
            
            <!-- AVATAR DRAWER (LEFT OF CHAT) -->
            <div id="elastique-drawer" class="avatar-drawer">
                <div class="avatar-video-container" id="video-mount-point">
                    <!-- Video injected here -->
                    <div style="color: #666; font-size: 14px;">(Offline)</div>
                </div>
                <div class="voice-status" id="voice-indicator" style="display: none;">
                    <div class="mic-icon"></div>
                    <span>Listening...</span>
                </div>
                
                <!-- PURPLE EQ STOP BUTTON (Overlay) -->
                <div id="elastique-stop-btn" style="
                    position: absolute; 
                    bottom: 30px; 
                    left: 50%; 
                    transform: translateX(-50%);
                    width: 50px;
                    height: 50px;
                    background: #6C5CE7;
                    border-radius: 50%;
                    display: none;
                    justify-content: center;
                    align-items: center;
                    cursor: pointer;
                    z-index: 9999;
                    box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                    border: 2px solid rgba(255,255,255,0.2);
                    animation: eq-pulse 1.5s infinite;">
                    
                <!-- STOP ICON (Removed White Square as per user request) -->
                <!-- <div style="width: 14px; height: 14px; background: white; border-radius: 2px;"></div> -->
            </div>
        </div>


            <!-- LEAD FORM (OVERLAY) -->
            <div id="elastique-lead-form" style="
                display: none; 
                position: absolute; 
                bottom: 80px; 
                right: 0; 
                width: 300px; 
                background: white; 
                border-radius: 12px; 
                padding: 20px; 
                box-shadow: 0 5px 20px rgba(0,0,0,0.2); 
                z-index: 10001;
                font-family: inherit;">
                
                <h3 style="margin: 0 0 10px 0; color: #6C5CE7;">Welcome</h3>
                <p style="font-size: 13px; color: #666; margin-bottom: 15px;">To start your medical-grade consultation with Sarah, please verify your details.</p>
                
                <input type="text" id="lead-name" placeholder="Name" style="box-sizing: border-box; width: 100%; padding: 8px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 4px;">
                <input type="email" id="lead-email" placeholder="Email" style="box-sizing: border-box; width: 100%; padding: 8px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 4px;">
                
                <button id="start-chat-btn" style="
                    width: 100%; 
                    padding: 10px; 
                    background: #6C5CE7; 
                    color: white; 
                    border: none; 
                    border-radius: 4px; 
                    cursor: pointer; 
                    font-weight: 600;">Start Consultation</button>
            </div>

            <!-- CHAT WINDOW -->
            <div class="chat-window" id="elastique-window">
                
                <!-- CHEVRON TOGGLE (Side Attached) -->
                <div id="elastique-chevron" class="chevron-toggle" title="Talk to Sarah">
                    &lt; <!-- Chevron Left Icon -->
                </div>

                <div class="chat-header">
                    <img src="http://localhost:8000/static/img/sarah_v2.png" alt="Sarah">
                    <span>Sarah (Senior Consultant)</span>
                </div>
                
                <div class="chat-messages" id="elastique-messages">
                    <!-- Initial Message injected dynamically -->
                </div>
                
                <!-- TYPING INDICATOR (Hidden by default) -->
                <div id="elastique-typing" class="typing-indicator" style="margin-left: 15px;">
                    <span></span><span></span><span></span>
                </div>

                <div class="chat-input" style="align-items: center;">
                    <!-- FILE UPLOAD INPUT (Hidden) -->
                    <input type="file" id="elastique-file-upload" accept="image/*,video/*,audio/*" style="display: none;">
                    
                    <!-- CLIP ICON -->
                    <div id="elastique-clip-icon" style="cursor: pointer; margin-right: 10px; color: #999;" title="Attach Photo/Video">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
                    </div>

                    <input type="text" id="elastique-input" placeholder="Type message..." style="margin: 0;">
                    <button id="elastique-send-btn">Send</button>
                </div>
                
                <!-- FILE PREVIEW -->
                <div id="upload-preview" style="display: none; padding: 5px 15px; font-size: 11px; color: #6C5CE7; background: #f0f0f0;">
                    <!-- Preview filled via JS -->
                </div>
            </div>

            <!-- LAUNCHER BUBBLE -->
            <div class="chat-bubble" id="elastique-bubble">
                <!-- SVG Icon -->
                <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"/></svg>
            </div>
        </div>
    `;

    const div = document.createElement("div");
    div.innerHTML = widgetHTML;
    document.body.appendChild(div);

    // 4. LOGIC
    const windowEl = document.getElementById('elastique-window');
    const bubbleEl = document.getElementById('elastique-bubble');
    const inputEl = document.getElementById('elastique-input');
    const sendBtn = document.getElementById('elastique-send-btn');
    const messagesEl = document.getElementById('elastique-messages');

    // New UI Elements
    const chevronEl = document.getElementById('elastique-chevron');
    const drawerEl = document.getElementById('elastique-drawer');
    const videoMount = document.getElementById('video-mount-point');
    const voiceIndicator = document.getElementById('voice-indicator');
    const stopBtn = document.getElementById('elastique-stop-btn');


    // Lead Form
    const leadForm = document.getElementById('elastique-lead-form');
    const leadNameInput = document.getElementById('lead-name');
    const leadEmailInput = document.getElementById('lead-email');
    const startChatBtn = document.getElementById('start-chat-btn');

    // File Upload
    const fileInput = document.getElementById('elastique-file-upload');
    const clipIcon = document.getElementById('elastique-clip-icon');
    const previewEl = document.getElementById('upload-preview');

    let userData = {
        name: null,
        email: null,
        authenticated: false
    };

    let isAvatarOpen = false;
    let silenceTimer = null;

    // --- GLOBAL VIDEO STATE (DOUBLE BUFFERED) ---
    let videoQueue = [];
    let isPlaying = false;
    let currentFetchController = null;
    let activePlayer = 0; // 0 or 1
    const players = [null, null]; // DOM Elements

    // --- SMART FILLERS ---
    const FILLER_IDLE = "http://localhost:8000/static/fillers/filler_idle.mp4";
    const FILLER_QUESTION = "http://localhost:8000/static/fillers/filler_question.mp4";
    const FILLER_THINKING = "http://localhost:8000/static/fillers/filler_thinking.mp4";

    function getSmartFiller(userMsg) {
        if (!userMsg) return null;
        if (userMsg.includes("?")) return FILLER_QUESTION;
        // if (userMsg.length > 20) return FILLER_THINKING; // Optional
        return null;
    }

    function initPlayers() {
        videoMount.innerHTML = "";
        // Create Two Players
        for (let i = 0; i < 2; i++) {
            const vid = document.createElement('video');
            vid.style.width = "100%";
            vid.style.height = "100%";
            vid.style.objectFit = "cover";
            vid.style.position = "absolute";
            vid.style.top = "0";
            vid.style.left = "0";
            vid.style.opacity = (i === 0) ? "1" : "0"; // Start with 0 visible
            vid.autoplay = true;
            vid.muted = false; // We unmute on interaction
            vid.playsInline = true;

            // Critical: Preload
            vid.preload = "auto";

            videoMount.appendChild(vid);
            players[i] = vid;

            // Events
            vid.onended = () => onVideoEnded(i);
            vid.onerror = (e) => {
                console.error(`Player ${i} Error`, e);
                onVideoEnded(i); // Skip
            };
        }
    }

    function playQueue() {
        if (isPlaying || videoQueue.length === 0) return;

        // Peek next
        const nextItem = videoQueue[0];
        const nextUrl = (typeof nextItem === 'object') ? nextItem.url : nextItem;

        if (!nextUrl) { videoQueue.shift(); playQueue(); return; }

        console.log(`[Player] Starting: ${nextUrl}`);
        isPlaying = true;

        if (stopBtn) stopBtn.style.display = "block";
        if (!isAvatarOpen) toggleAvatarMode();

        // Pause Mic
        if (recognition) try { recognition.stop(); } catch (e) { }

        // Use Active Player logic (Swap)
        // Current Visible is activePlayer. We want to play on activePlayer if it's idle, 
        // OR if this is a transition, we act on the *next* player?
        // Actually, Double Buffer usually implies we load B while A plays.
        // Simplified Logic: Just use the active player for now, ensuring seamlessness is hard without complex pre-loading.
        // IMPROVED: We queue 2nd video into *hidden* player immediately?

        // Let's stick to "Play on Current" but make sure we don't clear DOM.
        // We cross-fade? No, hard cut.

        const vid = players[activePlayer];
        vid.src = nextUrl;
        vid.play().catch(e => console.warn("Autoplay blocked", e));

        // If we want true gapless, we should have loaded this earlier.
        // For "Instant" feel, the black screen is removing the element. We are NOT removing it now.
        // It stays visible until src changes. 
        // Wait, changing src causes black flicker usually.
        // BETTER: Use 'nextPlayer'

        const nextPlayerIdx = (activePlayer + 1) % 2;
        const nextPlayer = players[nextPlayerIdx];

        nextPlayer.src = nextUrl;
        nextPlayer.loop = false; // CRITICAL: Ensure speech chunks don't loop
        nextPlayer.play().then(() => {
            // Once playing, bring to front
            nextPlayer.style.opacity = "1";
            nextPlayer.style.zIndex = "10";

            players[activePlayer].style.opacity = "0";
            players[activePlayer].style.zIndex = "1";
            players[activePlayer].pause(); // Stop old

            activePlayer = nextPlayerIdx; // Swap
            videoQueue.shift(); // Remove from queue

        }).catch(e => {
            console.error("Play failed", e);
            videoQueue.shift();
            isPlaying = false;
            playQueue();
        });
    }

    function onVideoEnded(playerIdx) {
        if (playerIdx !== activePlayer) return; // Ignore old player events

        console.log("Video chunk ended");
        // Is there more?
        if (videoQueue.length > 0) {
            // Trigger next (Logic handled in playQueue recursion?)
            // We need to set isPlaying false to allow playQueue to pick it up?
            isPlaying = false;
            playQueue();
        } else {
            // Queue Empty -> Go IDLE
            console.log("Queue Empty -> Loop Idle");
            isPlaying = false;

            // Loop Idle on *Current* player? Or Swap?
            // Swap to Idle
            const nextPlayerIdx = (activePlayer + 1) % 2;
            const nextPlayer = players[nextPlayerIdx];
            nextPlayer.src = FILLER_IDLE;
            nextPlayer.loop = true;
            nextPlayer.play();

            nextPlayer.style.opacity = "1";
            nextPlayer.style.zIndex = "10";
            players[activePlayer].style.opacity = "0";
            players[activePlayer].style.zIndex = "1";
            activePlayer = nextPlayerIdx;

            // Resume Mic
            if (stopBtn) stopBtn.style.display = "none";
            if (recognition && isAvatarOpen) try { recognition.start(); } catch (e) { }
        }
    }

    // --- VOICE RECOGNITION SETUP ---
    if ('webkitSpeechRecognition' in window) {
        recognition = new webkitSpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onstart = function () {
            voiceIndicator.style.display = "flex";
            inputEl.placeholder = "Listening...";
        };

        recognition.onend = function () {
            if (videoQueue.length === 0 && isAvatarOpen) {
                // Should restart?
            }
            voiceIndicator.style.display = "none";
            inputEl.placeholder = "Type message...";
        };

        recognition.onresult = function (event) {
            let transcript = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                transcript += event.results[i][0].transcript;
            }
            inputEl.value = transcript;
            if (silenceTimer) clearTimeout(silenceTimer);
            silenceTimer = setTimeout(() => {
                console.log("Silence detected. Sending...");
                if (recognition) recognition.stop();
                sendMessage();
                silenceTimer = null;
            }, 2000); // 2s silence
        };
    } else {
        console.warn("Web Speech API not supported.");
    }

    // --- MIC PERMISSION UX ---
    const micPrompt = document.getElementById('elastique-mic-prompt');
    const enableMicBtn = document.getElementById('enable-mic-btn');

    if (enableMicBtn) {
        enableMicBtn.addEventListener('click', () => {
            // Explicit user gesture to start mic
            micPrompt.style.display = 'none';
            if (recognition) {
                try { recognition.start(); } catch (e) { }
            }
        });
    }

    // Handle Errors
    if (recognition) {
        recognition.onerror = function (event) {
            console.warn("Speech Recognition Error:", event.error);
            if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
                // Show Button
                if (isAvatarOpen) micPrompt.style.display = 'block';
                voiceIndicator.style.display = 'none';
            }
        };
    }

    function loadIntroVideo() {
        console.log("Loading Intro Video...");
        const introUrl = "http://localhost:8000/static/generated/intro_sarah.mp4";
        videoQueue.push(introUrl);
        playQueue();
    }

    function toggleAvatarMode() {
        isAvatarOpen = !isAvatarOpen;
        if (isAvatarOpen) {
            // Open Drawer
            if (!players[0]) initPlayers();

            drawerEl.classList.add('open');
            if (chevronEl) chevronEl.innerHTML = "&gt;";

            // Play Intro (Only if queue empty and not playing)
            if (!isPlaying && videoQueue.length === 0) {
                loadIntroVideo();
            }



        } else {
            // Close Drawer
            drawerEl.classList.remove('open');
            if (chevronEl) chevronEl.innerHTML = "&lt;"; // Point Left
            if (recognition) recognition.stop();
        }
    }

    // LISTENER
    if (chevronEl) {
        chevronEl.addEventListener('click', toggleAvatarMode);
    }

    // STOP BUTTON LOGIC (Global Abort)
    if (stopBtn) {
        stopBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            console.log("TERMINATING AVATAR STREAM [User Interrupt]");

            // 1. ABORT FETCH
            if (currentFetchController) {
                currentFetchController.abort();
                currentFetchController = null;
            }

            // 2. Clear Queue
            videoQueue = [];

            // 3. Stop Video
            const currentVid = videoMount.querySelector('video');
            if (currentVid) {
                currentVid.pause();
                currentVid.src = "";
                currentVid.remove();
            }
            isPlayingVideo = false;

            // 4. Reset UI
            loadIntroVideo();
            stopBtn.style.display = "none";

            // 5. Force Resume Mic
            if (recognition) {
                try { recognition.start(); } catch (e) { }
            }
            inputEl.placeholder = "Listening (Interrupted)...";
        });
    }

    function loadIntroVideo() {
        // Prevent duplicate load if already present
        if (videoMount.querySelector('video')) return;

        // Force load intro
        const vid = document.createElement('video');
        vid.src = "http://localhost:8000/static/videos/intro_sarah.mp4?t=" + new Date().getTime();
        vid.autoplay = true;
        vid.controls = false;
        vid.loop = false; // STOP LOOPING VOICE
        vid.muted = false; // Ensure audio plays

        // CRITICAL FIX: PREVENT SELF-HEARING
        // Do NOT start mic until intro finishes.
        if (recognition) recognition.stop();

        vid.onended = () => {
            console.log("Intro ended. Starting mic...");
            if (recognition && isAvatarOpen) {
                try { recognition.start(); } catch (e) { }
            }
        };

        videoMount.innerHTML = "";
        videoMount.appendChild(vid);
    }

    // Toggle Chat / Lead Gate
    bubbleEl.addEventListener('click', () => {
        if (!userData.authenticated) {
            // Show Form if not auth (toggle)
            leadForm.style.display = leadForm.style.display === 'block' ? 'none' : 'block';
            windowEl.style.display = 'none';
        } else {
            // Show Chat
            windowEl.style.display = windowEl.style.display === 'flex' ? 'none' : 'flex';
        }
    });

    // Handle Lead Submit
    startChatBtn.addEventListener('click', () => {
        const name = leadNameInput.value.trim();
        const email = leadEmailInput.value.trim();
        if (name && email) {
            userData.name = name;
            userData.email = email;
            userData.authenticated = true;

            // Switch UI
            leadForm.style.display = 'none';
            windowEl.style.display = 'flex';

            // Initial Greeting
            // Initial Greeting
            appendMessage(`Hello ${name}, I am Sarah, your Senior Consultant. <br>I am listening...`, 'bot');

            // Load intro video into drawer (ready to play)
            // REMOVED: loadIntroVideo(); -> Now triggered by Chevron only.

        } else {
            alert("Please enter both Name and Email to proceed.");
        }
    });

    // Handle File Selection
    clipIcon.addEventListener('click', () => {
        // Reset and open
        fileInput.click();
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length > 0) {
            previewEl.style.display = 'block';
            previewEl.innerText = `📎 ${fileInput.files[0].name} attached`;
        } else {
            previewEl.style.display = 'none';
        }
    });

    // Handle Input
    inputEl.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
    sendBtn.addEventListener('click', sendMessage);

    // Markdown Parser
    function parseMarkdown(text) {
        if (!text) return "";
        text = text.replace(/<!--[\s\S]*?-->/g, '');
        text = text.replace(/\[INTERNAL THOUGHT\][\s\S]*?\[END THOUGHT\]/g, '');
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        text = text.replace(/\*(.*?)\*/g, '<em>$1</em>');
        text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
        text = text.replace(/\r\n/g, '<br>').replace(/\n/g, '<br>');
        text = text.replace(/<br>\s*[\*\-]\s+(.*?)(?=<br>|$)/g, '<ul><li>$1</li></ul>');
        return text.trim();
    }

    function appendMessage(text, sender, isHtml = false, audioBase64 = null, videoUrl = null) {
        const div = document.createElement('div');
        div.className = `message ${sender}`;
        div.style.position = "relative";

        if (isHtml) {
            div.innerHTML = text;
            div.style.background = "transparent";
            div.style.padding = "0";
            div.style.maxWidth = "100%";
        } else {
            div.innerHTML = parseMarkdown(text);
        }

        // --- VIDEO AVATAR LOGIC ---
        // If video is returned, we play it in the DRAWER, not the chat bubble
        if (videoUrl) {
            // Open Drawer if closed
            if (!isAvatarOpen) {
                toggleAvatarMode(); // Open and start mic
            }

            const vid = document.createElement('video');
            vid.src = videoUrl;
            vid.loop = false; // CRITICAL: Reset loop (idle player handles loop=true)
            vid.load();
            vid.autoplay = true;
            vid.controls = false;

            // Swap video in drawer
            videoMount.innerHTML = "";
            videoMount.appendChild(vid);

            // When video ends, maybe restart mic?
            vid.onended = () => {
                if (recognition && isAvatarOpen) {
                    try { recognition.start(); } catch (e) { }
                }
            };
        }

        // --- AUDIO PLAYBACK (Fallback) ---
        else if (audioBase64) {
            const audioId = "audio-" + Date.now();
            const audio = new Audio("data:audio/mp3;base64," + audioBase64);
            audio.id = audioId;

            const iconDiv = document.createElement('div');
            iconDiv.innerHTML = '🔊';
            iconDiv.style.cursor = "pointer";
            iconDiv.style.fontSize = "16px";
            iconDiv.style.marginTop = "5px";
            iconDiv.style.color = "#6C5CE7";
            iconDiv.title = "Replay Voice";

            iconDiv.onclick = () => {
                // If audio plays, stop recognition momentarily?
                if (recognition) try { recognition.stop(); } catch (e) { }
                audio.play().catch(e => alert("Please interact with the page first."));
                audio.onended = () => {
                    if (recognition && isAvatarOpen) try { recognition.start(); } catch (e) { }
                };
            };

            div.appendChild(iconDiv);
            setTimeout(() => {
                audio.play().catch(e => console.log("Auto-play blocked."));
            }, 500);
        }

        messagesEl.appendChild(div);
        messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    async function sendMessage() {
        const message = inputEl.value.trim();
        const file = fileInput.files[0];

        if (!message && !file) return;

        // 1. ABORT PREVIOUS STREAM
        if (currentFetchController) {
            console.log("Aborting previous stream...");
            currentFetchController.abort();
        }
        currentFetchController = new AbortController();
        const signal = currentFetchController.signal;

        // UI: Show User Message
        let displayMsg = message;
        if (file) displayMsg += ` <br><small>📎 [Sending ${file.name}...]</small>`;
        appendMessage(displayMsg, 'user', true);

        inputEl.value = '';
        previewEl.style.display = 'none';

        const formData = new FormData();
        const finalMessage = message || "Please analyze this file attached.";
        formData.append("message", finalMessage);
        // SMART FILLER LOGIC
        const fillerUrl = getSmartFiller(message);
        if (fillerUrl) {
            console.log("Queueing Smart Filler:", fillerUrl);
            videoQueue.push(fillerUrl);
            playQueue();
        }

        if (userData.name) formData.append("user_name", userData.name);
        if (userData.email) formData.append("user_email", userData.email);
        if (file) formData.append("file", file);

        const typingEl = document.getElementById('elastique-typing');

        try {
            // SHOW TYPING
            typingEl.style.display = 'block';
            messagesEl.scrollTop = messagesEl.scrollHeight;

            // CLEAR OLD QUEUE (Implicit new start)
            // CLEAR OLD QUEUE (Implicit new start)
            videoQueue = [];
            isPlaying = false;

            // FETCH STREAM

            // FETCH STREAM
            const response = await fetch(API_URL, {
                method: 'POST',
                body: formData,
                signal: signal // BIND SIGNAL
            });

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            const botBubbleId = 'msg-' + new Date().getTime();
            // We do NOT start a text bubble yet if we want synced text.
            // BUT currently server sends immediate text chunks.
            // Let's create a "Streaming Bubble" for direct LLM output.
            appendMessage('<div id="' + botBubbleId + '"></div>', 'bot');
            const botBubbleContent = document.getElementById(botBubbleId);

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                buffer += chunk;
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep partial line

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const msg = JSON.parse(line);

                        if (msg.type === "text") {
                            // HIDE TYPING ON FIRST CONTENT
                            typingEl.style.display = 'none';

                            // Immediate Text Feedback (Streaming)
                            if (botBubbleContent) {
                                botBubbleContent.innerHTML += msg.content;
                                messagesEl.scrollTop = messagesEl.scrollHeight;
                            }
                        } else if (msg.type === "video") {
                            // Queue Video
                            videoQueue.push(msg);
                            playQueue();
                        } else if (msg.type === "product_card") {
                            appendMessage(msg.content, 'bot');
                        }
                    } catch (e) {
                        console.error("JSON Parse Error", e);
                    }
                }
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                console.log("Fetch aborted by user.");
            } else {
                console.error("Fetch Error:", error);
                appendMessage("Error connecting to server.", 'bot');
            }
        } finally {
            typingEl.style.display = 'none';
            currentFetchController = null; // Reset
        }
    }


})();
