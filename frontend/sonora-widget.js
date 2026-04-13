/**
 * Sonora Chat Widget — Embeddable
 * Add <script src="sonora-widget.js"></script> to any HVAC website
 */
(function() {
  'use strict';

  // ==========================================
  // CONFIG
  // ==========================================
  const VOICE_ENDPOINT = 'http://localhost:5000/api/voice';
  const SONORA_AVATAR = `<svg width="24" height="24" viewBox="0 0 32 32" fill="none"><path d="M16 4C10 4 6 8 6 12c0 3 2 5.5 5 6.5C9 19.5 8 21 8 23c0 3 3 5 8 5s8-2 8-5c0-2-1-3.5-3-4.5 3-1 5-3.5 5-6.5 0-4-4-8-10-8z" fill="url(#swg)"/><defs><linearGradient id="swg" x1="6" y1="4" x2="26" y2="28"><stop stop-color="#00E5FF"/><stop offset=".5" stop-color="#00838F"/><stop offset="1" stop-color="#7C4DFF"/></linearGradient></defs></svg>`;

  // ==========================================
  // DEMO CONVERSATION
  // ==========================================
  const demoConversation = [
    { role: 'user', text: "Hi, my AC isn't cooling. It's blowing warm air." },
    { role: 'sonora', text: "I'm sorry to hear that! I can definitely help. Let me get a few details to get you taken care of fast. What's your zip code?" },
    { role: 'user', text: "85281 — Tempe, Arizona." },
    { role: 'sonora', text: "Got it — Tempe. It's 112°F there today, so I'm flagging this as urgent. How old is your AC system?" },
    { role: 'user', text: "About 8 years, I think. It was making a weird clicking noise before it stopped cooling." },
    { role: 'sonora', text: "Clicking plus warm air on an 8-year system — that could be a compressor or contactor issue. Given the extreme heat, I want to get a tech to you today. I have a 2:30 PM slot available with Mike, one of our senior techs. Does that work?" },
    { role: 'user', text: "Yes, 2:30 works great." },
    { role: 'sonora', text: "✅ Booked! Mike will be at your home at 2:30 PM today. You'll get a text confirmation shortly with his photo and ETA. Is there anything else I can help with?" },
    { role: 'user', text: "No, that's perfect. Thank you!" },
    { role: 'sonora', text: "You're welcome! Stay cool — Mike's on his way. 😊" },
  ];

  // ==========================================
  // INJECT STYLES
  // ==========================================
  const styleEl = document.createElement('style');
  styleEl.textContent = `
    .sonora-widget-btn {
      position: fixed;
      bottom: 24px;
      right: 24px;
      z-index: 9999;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, #00838F 0%, #006064 50%, #5C35CC 100%);
      border: none;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 0 30px rgba(0,131,143,0.4), 0 4px 20px rgba(0,0,0,0.4);
      transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s;
      animation: sonoraFloat 3s ease-in-out infinite;
    }
    @keyframes sonoraFloat {
      0%, 100% { transform: translateY(0); }
      50% { transform: translateY(-4px); }
    }
    .sonora-widget-btn:hover {
      transform: scale(1.08) translateY(-2px);
      box-shadow: 0 0 50px rgba(0,131,143,0.6), 0 8px 30px rgba(0,0,0,0.5);
    }
    .sonora-widget-btn svg { width: 28px; height: 28px; }
    .sonora-widget-btn .sonora-close {
      display: none;
      width: 24px;
      height: 24px;
    }
    .sonora-widget-btn.active .sonora-avatar-icon { display: none; }
    .sonora-widget-btn.active .sonora-close { display: block; }
    .sonora-widget-btn.active { animation: none; }

    .sonora-chat {
      position: fixed;
      bottom: 100px;
      right: 24px;
      z-index: 9998;
      width: 380px;
      max-width: calc(100vw - 48px);
      height: 520px;
      max-height: calc(100vh - 140px);
      background: #0D1117;
      border: 1px solid rgba(0,131,143,0.3);
      border-radius: 20px;
      box-shadow: 0 0 60px rgba(0,131,143,0.2), 0 20px 60px rgba(0,0,0,0.5);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      opacity: 0;
      transform: translateY(20px) scale(0.95);
      pointer-events: none;
      transition: opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1), transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .sonora-chat.active {
      opacity: 1;
      transform: translateY(0) scale(1);
      pointer-events: auto;
    }
    .sonora-chat__header {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 16px 20px;
      background: linear-gradient(180deg, rgba(0,131,143,0.08) 0%, transparent 100%);
      border-bottom: 1px solid rgba(0,131,143,0.15);
    }
    .sonora-chat__avatar {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: linear-gradient(135deg, #00838F, #7C4DFF);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 0 20px rgba(0,131,143,0.4);
    }
    .sonora-chat__info h3 {
      color: #fff;
      font-size: 15px;
      font-weight: 700;
      font-family: 'Inter', sans-serif;
    }
    .sonora-chat__info p {
      color: #10B981;
      font-size: 12px;
      font-weight: 500;
      font-family: 'Inter', sans-serif;
    }
    .sonora-chat__messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .sonora-chat__messages::-webkit-scrollbar { width: 4px; }
    .sonora-chat__messages::-webkit-scrollbar-thumb { background: #1E293B; border-radius: 4px; }
    .sonora-msg {
      max-width: 85%;
      padding: 10px 14px;
      border-radius: 16px;
      font-size: 14px;
      line-height: 1.5;
      font-family: 'Inter', sans-serif;
      animation: msgIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    @keyframes msgIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }
    .sonora-msg--user {
      align-self: flex-end;
      background: rgba(0,131,143,0.2);
      color: #E2E8F0;
      border-bottom-right-radius: 4px;
    }
    .sonora-msg--sonora {
      align-self: flex-start;
      background: #111827;
      color: #E2E8F0;
      border: 1px solid #1E293B;
      border-bottom-left-radius: 4px;
    }
    .sonora-typing {
      display: flex;
      gap: 4px;
      padding: 12px 16px;
      align-self: flex-start;
    }
    .sonora-typing span {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #00838F;
      animation: typingBounce 1.4s infinite;
    }
    .sonora-typing span:nth-child(2) { animation-delay: 0.2s; }
    .sonora-typing span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes typingBounce {
      0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
      30% { transform: translateY(-6px); opacity: 1; }
    }
    .sonora-chat__input {
      display: flex;
      gap: 8px;
      padding: 12px 16px;
      border-top: 1px solid #1E293B;
      background: #0A0E1A;
    }
    .sonora-chat__input input {
      flex: 1;
      background: #111827;
      border: 1px solid #1E293B;
      border-radius: 12px;
      padding: 10px 14px;
      color: #E2E8F0;
      font-size: 14px;
      font-family: 'Inter', sans-serif;
      outline: none;
      transition: border-color 0.2s;
    }
    .sonora-chat__input input::placeholder { color: #64748B; }
    .sonora-chat__input input:focus { border-color: #00838F; }
    .sonora-chat__voice-btn {
      width: 40px;
      height: 40px;
      border-radius: 50%;
      background: linear-gradient(135deg, #00838F, #006064);
      border: none;
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      flex-shrink: 0;
      transition: box-shadow 0.2s, transform 0.2s;
    }
    .sonora-chat__voice-btn:hover {
      box-shadow: 0 0 20px rgba(0,131,143,0.4);
      transform: scale(1.05);
    }
    .sonora-chat__voice-btn.recording {
      background: linear-gradient(135deg, #FF1744, #D50000);
      animation: pulseMic 1s ease-in-out infinite;
    }
    @keyframes pulseMic {
      0%, 100% { box-shadow: 0 0 0 0 rgba(255,23,68,0.4); }
      50% { box-shadow: 0 0 0 10px rgba(255,23,68,0); }
    }
  `;
  document.head.appendChild(styleEl);

  // ==========================================
  // CREATE DOM
  // ==========================================
  // Floating button
  const btn = document.createElement('button');
  btn.className = 'sonora-widget-btn';
  btn.setAttribute('aria-label', 'Talk to Sonora');
  btn.innerHTML = `
    <span class="sonora-avatar-icon">${SONORA_AVATAR}</span>
    <svg class="sonora-close" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
  `;
  document.body.appendChild(btn);

  // Chat panel
  const chat = document.createElement('div');
  chat.className = 'sonora-chat';
  chat.innerHTML = `
    <div class="sonora-chat__header">
      <div class="sonora-chat__avatar">${SONORA_AVATAR}</div>
      <div class="sonora-chat__info">
        <h3>Sonora</h3>
        <p>● Online — AI Voice Agent</p>
      </div>
    </div>
    <div class="sonora-chat__messages" id="sonoraMessages"></div>
    <div class="sonora-chat__input">
      <input type="text" placeholder="Type a message..." id="sonoraInput" autocomplete="off">
      <button class="sonora-chat__voice-btn" id="sonoraVoice" aria-label="Voice mode">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/></svg>
      </button>
    </div>
  `;
  document.body.appendChild(chat);

  // ==========================================
  // STATE & LOGIC
  // ==========================================
  let isOpen = false;
  let demoIndex = 0;
  let demoPlaying = false;
  let isRecording = false;

  const messagesEl = chat.querySelector('#sonoraMessages');
  const inputEl = chat.querySelector('#sonoraInput');
  const voiceBtn = chat.querySelector('#sonoraVoice');

  function toggleChat() {
    isOpen = !isOpen;
    chat.classList.toggle('active', isOpen);
    btn.classList.toggle('active', isOpen);
    if (isOpen && messagesEl.children.length === 0) {
      startDemo();
    }
  }

  function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = `sonora-msg sonora-msg--${role === 'user' ? 'user' : 'sonora'}`;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function showTyping() {
    const div = document.createElement('div');
    div.className = 'sonora-typing';
    div.id = 'sonoraTyping';
    div.innerHTML = '<span></span><span></span><span></span>';
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function hideTyping() {
    const el = document.getElementById('sonoraTyping');
    if (el) el.remove();
  }

  function startDemo() {
    if (demoPlaying) return;
    demoPlaying = true;
    demoIndex = 0;
    playNextMessage();
  }

  function playNextMessage() {
    if (demoIndex >= demoConversation.length) {
      demoPlaying = false;
      return;
    }
    const msg = demoConversation[demoIndex];
    const delay = msg.role === 'sonora' ? 1200 : 600;

    if (msg.role === 'sonora') {
      showTyping();
      setTimeout(() => {
        hideTyping();
        addMessage(msg.role, msg.text);
        demoIndex++;
        setTimeout(playNextMessage, 800);
      }, delay);
    } else {
      setTimeout(() => {
        addMessage(msg.role, msg.text);
        demoIndex++;
        setTimeout(playNextMessage, 500);
      }, delay);
    }
  }

  // Event listeners
  btn.addEventListener('click', toggleChat);

  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && inputEl.value.trim()) {
      const text = inputEl.value.trim();
      addMessage('user', text);
      inputEl.value = '';
      // Simulated response
      showTyping();
      setTimeout(() => {
        hideTyping();
        addMessage('sonora', "Thanks for your message! In a live deployment, Sonora would respond in real-time. Try the demo conversation to see her in action.");
      }, 1500);
    }
  });

  voiceBtn.addEventListener('click', () => {
    isRecording = !isRecording;
    voiceBtn.classList.toggle('recording', isRecording);
    if (isRecording) {
      addMessage('sonora', "🎤 Voice mode activated. Connecting to Sonora voice agent...");
      // Attempt real voice connection
      fetch(VOICE_ENDPOINT, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({action:'start'}) })
        .then(r => r.json())
        .then(data => {
          addMessage('sonora', "Voice connection established. Speak naturally — Sonora is listening.");
        })
        .catch(() => {
          setTimeout(() => {
            addMessage('sonora', "Voice backend not available right now. In production, you'd be speaking directly with Sonora's AI voice agent.");
            isRecording = false;
            voiceBtn.classList.remove('recording');
          }, 1500);
        });
    } else {
      addMessage('sonora', "Voice mode ended. How else can I help?");
    }
  });

  // Expose global function to open chat
  window.openChat = function() {
    if (!isOpen) toggleChat();
  };
})();
