function scrollChat() {
    const chat = document.getElementById("chat");
    if (chat) chat.scrollTop = chat.scrollHeight;
}

// Shows your message in the chat right away, before the AI answers
function addUserBubble(form) {
    const input = form.querySelector("input[name='question']");
    const text = input.value.trim();
    if (!text) return;

    const bubble = document.createElement("div");
    bubble.className = "msg user";
    bubble.textContent = text;
    document.getElementById("chat").appendChild(bubble);
    scrollChat();

    // clear the box after the request has been built
    setTimeout(() => form.reset(), 0);
}

document.addEventListener("htmx:afterSwap", scrollChat);
document.addEventListener("DOMContentLoaded", scrollChat);