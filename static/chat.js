const USER_ID = 1; // demo — replace with real session/login
const chatWindow = document.getElementById("chat-window");
const input = document.getElementById("msg-input");
const sendBtn = document.getElementById("send-btn");
const notifBar = document.getElementById("notif-bar");

function addMessage(text, sender) {
  const div = document.createElement("div");
  div.className = `msg ${sender === "user" ? "user-msg" : "axa-msg"}`;
  div.textContent = text;
  chatWindow.appendChild(div);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function sendMessage() {
  const message = input.value.trim();
  if (!message) return;
  addMessage(message, "user");
  input.value = "";

  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: USER_ID, message }),
  });
  const data = await res.json();
  addMessage(data.reply, "axa");
}

sendBtn.addEventListener("click", sendMessage);
input.addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendMessage();
});

// Poll for proactive notifications every 20s
setInterval(async () => {
  const res = await fetch(`/api/notifications/${USER_ID}`);
  const data = await res.json();
  if (data.notifications && data.notifications.length > 0) {
    notifBar.style.display = "block";
    notifBar.textContent = data.notifications[data.notifications.length - 1];
    data.notifications.forEach(n => addMessage(n, "axa"));
  }
}, 20000);
