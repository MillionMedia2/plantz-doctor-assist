document.addEventListener('DOMContentLoaded', function() {
  console.log('JS loaded');

  const messagesDiv = document.getElementById('messages');
  const input = document.getElementById('user-input');
  const sendBtn = document.getElementById('send-btn');
  const chatForm = document.getElementById('chat-form');
  const thinkingDiv = document.getElementById('thinking-indicator');

  function addMessage(role, content) {
    console.log('addMessage', role, content);
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role === 'user' ? 'userMessage' : 'assistantMessage'}`;
    const bubble = document.createElement('div');
    bubble.className = role === 'user' ? 'messageBubble userBubble' : 'messageBubble assistantBubble';
    if (role === 'assistant') {
      bubble.innerHTML = markdownToSafeHtml(content);
    } else {
      bubble.textContent = content;
    }
    msgDiv.appendChild(bubble);
    messagesDiv.appendChild(msgDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
  }

  let thinkingTimeout1 = null;
  let thinkingTimeout2 = null;

  function showThinking() {
    clearTimeout(thinkingTimeout1);
    clearTimeout(thinkingTimeout2);
    thinkingDiv.innerHTML = '<span id="thinking-text">Thinking</span><span class="thinking-dots"><span class="thinking-dot"></span><span class="thinking-dot"></span><span class="thinking-dot"></span></span>';
    // After 10 seconds, update to 'Still Thinking'
    thinkingTimeout1 = setTimeout(() => {
      const text = document.getElementById('thinking-text');
      if (text) text.textContent = 'Still Thinking';
    }, 10000);
    // After 20 seconds, update to 'Nearly there'
    thinkingTimeout2 = setTimeout(() => {
      const text = document.getElementById('thinking-text');
      if (text) text.textContent = 'Nearly there';
    }, 20000);
  }
  function hideThinking() {
    clearTimeout(thinkingTimeout1);
    clearTimeout(thinkingTimeout2);
    thinkingDiv.innerHTML = '';
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
  }

  function spinnerSVG() {
    return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-loader animate-spin"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`;
  }
  function clockSVG() {
    return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-clock"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`;
  }
  function pulsingClockSVG() {
    return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="feather feather-clock animate-pulse"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`;
  }

  function markdownToSafeHtml(md) {
    let html = window.marked ? marked.parse(md) : md;
    // Create a temporary DOM element
    const temp = document.createElement('div');
    temp.innerHTML = html;
    // Replace all tables with divs/lists
    temp.querySelectorAll('table').forEach(table => {
      const ul = document.createElement('ul');
      table.querySelectorAll('tr').forEach(tr => {
        const li = document.createElement('li');
        li.innerHTML = Array.from(tr.children).map(td => td.innerHTML).join(' | ');
        ul.appendChild(li);
      });
      table.replaceWith(ul);
    });
    // Remove any remaining table-related elements
    temp.querySelectorAll('thead, tbody, tr, th, td').forEach(el => {
      const div = document.createElement('div');
      div.innerHTML = el.innerHTML;
      el.replaceWith(div);
    });
    return temp.innerHTML;
  }

  // --- Conversation tracking ---
  let previous_response_id = null;
  let session = null;

  function generateUUID() {
    // Simple UUID v4 generator
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
  }

  async function sendMessage() {
    const text = input.value.trim();
    if (!text) return;
    addMessage('user', text);
    input.value = '';
    showThinking();

    let assistantMsg = '';
    let assistantDiv = null;
    let lastReceivedResponseId = previous_response_id;
    if (!session) {
      session = generateUUID();
      console.log('Generated new session:', session);
    }
    function startAssistantMsg() {
      assistantDiv = document.createElement('div');
      assistantDiv.className = 'message assistantMessage';
      const bubble = document.createElement('div');
      bubble.className = 'messageBubble assistantBubble';
      bubble.innerHTML = '';
      assistantDiv.appendChild(bubble);
      messagesDiv.appendChild(assistantDiv);
      messagesDiv.scrollTop = messagesDiv.scrollHeight;
      return bubble;
    }

    try {
      const body = { input: text, session };
      if (previous_response_id) body.previous_response_id = previous_response_id;
      console.log('Sending session:', session, 'previous_response_id:', previous_response_id);
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!response.body) throw new Error('No response body');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let bubble = null;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const chunk = JSON.parse(line.slice(6));
              if (
                chunk.event === 'thread.message.delta' &&
                chunk.data &&
                chunk.data.delta &&
                chunk.data.delta.content
              ) {
                for (const block of chunk.data.delta.content) {
                  if (block.type === 'text' && block.text && block.text.value) {
                    if (!bubble) bubble = startAssistantMsg();
                    // Remove thinking indicator right before showing first assistant text
                    if (thinkingDiv.innerHTML) hideThinking();
                    assistantMsg += block.text.value;
                    bubble.innerHTML = markdownToSafeHtml(assistantMsg);
                    messagesDiv.scrollTop = messagesDiv.scrollHeight;
                  }
                }
              } else if (chunk.event === 'previous_response_id' && chunk.data && chunk.data.previous_response_id) {
                lastReceivedResponseId = chunk.data.previous_response_id;
                console.log('Received new previous_response_id:', lastReceivedResponseId);
              }
            } catch (e) {
              // Ignore parse errors for non-data lines
            }
          }
        }
      }
      // After the stream, update previous_response_id to the last received value
      if (lastReceivedResponseId) {
        previous_response_id = lastReceivedResponseId;
        console.log('Final previous_response_id for next message:', previous_response_id);
      }
      if (!bubble && assistantMsg) {
        hideThinking();
        addMessage('assistant', assistantMsg);
      }
    } catch (err) {
      hideThinking();
      addMessage('assistant', 'Sorry, there was an error.');
    }
  }

  chatForm.addEventListener('submit', function(e) {
    e.preventDefault();
    sendMessage();
  });

  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') sendMessage();
  });

  // Remove showThinking() debug call on page load
  // Remove test message loop for production
}); 