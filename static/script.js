function scrollChat() {
    const chat = document.getElementById("chat");
    if (chat) chat.scrollTop = chat.scrollHeight;
}

function addBubble(role, text) {
    const bubble = document.createElement("div");
    bubble.className = "msg " + (role === "user" ? "user" : "bot");
    bubble.textContent = text;
    document.querySelector("#chat .empty")?.remove();
    document.getElementById("chat").appendChild(bubble);
    scrollChat();
    return bubble;
}

// Sends the question and shows the answer word by word as the AI writes it
async function sendQuestion(form, question) {
    const input = form.querySelector("input[name='question']");
    const button = form.querySelector("button");
    if (!question || button.disabled) return;

    addBubble("user", question);
    input.value = "";
    button.disabled = true;
    const reply = addBubble("bot", "Thinking...");

    try {
        const response = await fetch(`/chats/${form.dataset.chat}/ask`, {
            method: "POST",
            body: new URLSearchParams({ question }),
        });
        if (!response.ok) throw new Error(response.status);

        // the first question names the chat in the list on the left
        const link = document.getElementById(`chat-link-${form.dataset.chat}`);
        const title = response.headers.get("X-Chat-Title");
        if (link && title) link.textContent = decodeURIComponent(title);

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let text = "";
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            text += decoder.decode(value, { stream: true });
            reply.textContent = text;
            scrollChat();
        }

        const sources = JSON.parse(decodeURIComponent(response.headers.get("X-Sources") || "%5B%5D"));
        if (sources.length && !text.includes("couldn't reach the AI model")) {
            const small = document.createElement("small");
            small.textContent = "From your notes: " + sources.join(", ");
            reply.appendChild(small);
        }
    } catch {
        reply.textContent = "Something went wrong sending your question. Try again.";
    } finally {
        button.disabled = false;
        input.focus();
        scrollChat();
    }
}

document.addEventListener("DOMContentLoaded", () => {
    scrollChat();

    const form = document.getElementById("ask-form");
    if (!form) return;

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        sendQuestion(form, form.question.value.trim());
    });

    // the suggestion buttons in a chat about a note
    document.querySelectorAll("[data-ask]").forEach((button) => {
        button.addEventListener("click", () => sendQuestion(form, button.dataset.ask));
    });
});
