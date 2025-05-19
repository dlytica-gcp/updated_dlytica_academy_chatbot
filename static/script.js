document.addEventListener("DOMContentLoaded", function () {
    const chatPopup = document.getElementById("chat-popup");
    const chatButton = document.getElementById("chatbot-button");
    const sendBtn = document.getElementById("send-btn");
    const voiceBtn = document.getElementById("voice-btn");
    const userInput = document.getElementById("user-input");
    const chatBox = document.getElementById("messages");
    const closeBtn = document.getElementById("close-chat");
    let currentAudio = null;

    // Initialize chat session
    initializeChatSession();

    chatButton.addEventListener("click", () => {
        const isVisible = chatPopup.style.display === "flex";
        chatPopup.style.display = isVisible ? "none" : "flex";

        if (!isVisible && !hasActiveSession()) {
            fetch("/reset_session", {
                method: "POST",
                credentials: "include",
            })
                .then(() => {
                    appendMessage("bot", "Welcome to Dlytica! I'm your AI assistant. How can I help you today?", true);
                })
                .catch(console.error);
        }
        scrollToBottom();
    });

    closeBtn.addEventListener("click", () => {
        chatPopup.style.animation = "fadeOut 0.3s ease";
        setTimeout(() => {
            chatPopup.style.display = "none";
            chatPopup.style.animation = "slideUp 0.3s ease";
        }, 300);
    });

    sendBtn.addEventListener("click", sendMessage);

    userInput.addEventListener("keypress", function (e) {
        if (e.key === "Enter") sendMessage();
    });

    voiceBtn.addEventListener("click", startVoiceRecognition);

    document.addEventListener("keydown", function (e) {
        if (e.key === "Escape") {
            chatPopup.style.display = "none";
        }
    });

    window.addEventListener("beforeunload", function () {
        fetch("/reset_session", {
            method: "POST",
            credentials: "include",
            keepalive: true,
        });
    });

    function hasActiveSession() {
        return document.querySelector(".message.bot") !== null;
    }

    function initializeChatSession() {
        fetch("/reset_session", {
            method: "POST",
            credentials: "include",
        })
            .then(() => {
                if (chatPopup.style.display === "flex") {
                    appendMessage("bot", "Welcome to Dlytica! I'm your AI assistant. How can I help you today?", true);
                }
            })
            .catch(console.error);
    }

    function validatePhoneNumber(phone) {
        const cleaned = phone.replace(/(?!^\+)[\D]/g, "");
        if (!cleaned) return false;

        if (!phone.startsWith("+") && !phone.startsWith("977")) {
            return /^(97|98)\d{8}$/.test(cleaned) && cleaned.length === 10;
        }

        if (phone.startsWith("977") || phone.startsWith("+977")) {
            const num = phone.startsWith("+977") ? cleaned.substring(4) : cleaned.substring(3);
            return /^(97|98)\d{8}$/.test(num) && num.length === 10;
        }

        if (phone.startsWith("+")) {
            return cleaned.length >= 8 && cleaned.length <= 15;
        }

        return false;
    }

    function sendMessage() {
        let message = userInput.value.trim();
        if (!message) return;

        const isPhoneInput = document.querySelector(".message.bot:last-child")?.textContent.includes("phone number");
        if (isPhoneInput && !validatePhoneNumber(message)) {
            const trimmedMsg = message.toLowerCase();
            if (["skip", "na", "none", ""].includes(trimmedMsg)) {
                userInput.value = "";
                message = "";
            } else {
                appendMessage("bot", "Please enter a valid Nepali phone number (e.g., 98XXXXXXXX or 01-XXXXXXX)");
                userInput.value = "";
                return;
            }
        }

        // Handle cancellation logic here
        if (message.toLowerCase().includes("cancel")) {
            appendMessage("user", message);
            userInput.value = "";

            const typingDiv = appendTypingAnimation();
            scrollToBottom();

            fetch("/get_response", {
                method: "POST",
                body: JSON.stringify({ message: message }),
                headers: { "Content-Type": "application/json" },
                credentials: "include",
            })
                .then((response) => {
                    if (!response.ok) throw new Error("Network response was not ok");
                    return response.json();
                })
                .then((data) => {
                    typingDiv.remove();
                    appendMessage("bot", data.response, true);
                })
                .catch((error) => {
                    typingDiv.remove();
                    console.error("Error:", error);
                    appendMessage("bot", "Sorry, something went wrong while cancelling.", true);
                });

            return;
        }

        appendMessage("user", message);
        userInput.value = "";

        const typingDiv = appendTypingAnimation();
        scrollToBottom();

        fetch("/get_response", {
            method: "POST",
            body: JSON.stringify({ message: message }),
            headers: { "Content-Type": "application/json" },
            credentials: "include",
        })
            .then((response) => {
                if (!response.ok) throw new Error("Network response was not ok");
                return response.json();
            })
            .then((data) => {
                typingDiv.remove();
                appendMessage("bot", data.response, true);
            })
            .catch((error) => {
                typingDiv.remove();
                console.error("Error:", error);
                appendMessage("bot", "Sorry, I'm having trouble responding right now. Please try again later.", true);
            });
    }

    function appendMessage(sender, text, withAvatar = false, audioUrl = null) {
        const msgDiv = document.createElement("div");
        msgDiv.classList.add("message", sender);

        if (sender === "bot" && withAvatar) {
            const botIcon = document.createElement("img");
            botIcon.src = "/static/dlytica_logo.jpg";
            botIcon.alt = "Bot";
            msgDiv.appendChild(botIcon);
        }

        const msgText = document.createElement("span");
        msgText.innerText = text;
        msgDiv.appendChild(msgText);

        chatBox.appendChild(msgDiv);
        scrollToBottom();

        if (audioUrl) {
            currentAudio = new Audio(audioUrl);
            currentAudio.play();
        }
    }

    function appendTypingAnimation() {
        const typing = document.createElement("div");
        typing.classList.add("message", "bot", "typing");
        typing.innerHTML = `
            <img src="/static/dlytica_logo.jpg" alt="Bot">
            <span><i>Typing<span class="dot one">.</span><span class="dot two">.</span><span class="dot three">.</span></i></span>
        `;
        chatBox.appendChild(typing);
        scrollToBottom();
        return typing;
    }

    function scrollToBottom() {
        chatBox.scrollTop = chatBox.scrollHeight;
    }

    function startVoiceRecognition() {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRecognition) return alert("Speech recognition not supported in this browser");

        const recognition = new SpeechRecognition();
        recognition.lang = "en-US";
        recognition.start();

        recognition.onresult = function (event) {
            const transcript = event.results[0][0].transcript;
            userInput.value = transcript;
            sendMessage();
        };

        recognition.onerror = function (event) {
            console.error("Speech recognition error:", event.error);
            alert("Error recognizing speech. Please try again.");
        };
    }
});



// -------------------------------------------------------------------------------------------------------------
// document.addEventListener("DOMContentLoaded", function () {
//     const chatPopup = document.getElementById("chat-popup");
//     const chatButton = document.getElementById("chatbot-button");
//     const sendBtn = document.getElementById("send-btn");
//     const voiceBtn = document.getElementById("voice-btn");
//     const userInput = document.getElementById("user-input");
//     const chatBox = document.getElementById("messages");
//     const closeBtn = document.getElementById("close-chat");
//     let currentAudio = null;

//     // Initialize chat session
//     initializeChatSession();

//     chatButton.addEventListener("click", () => {
//         const isVisible = chatPopup.style.display === "flex";
//         chatPopup.style.display = isVisible ? "none" : "flex";

//         if (!isVisible && !hasActiveSession()) {
//             fetch("/reset_session", { 
//                 method: "POST",
//                 credentials: 'include'
//             })
//             .then(() => {
//                 appendMessage("bot", "Welcome to Dlytica! I'm your AI assistant. How can I help you today?", true);
//             })
//             .catch(console.error);
//         }
//         scrollToBottom();
//     });

//     closeBtn.addEventListener("click", () => {
//         chatPopup.style.animation = "fadeOut 0.3s ease";
//         setTimeout(() => {
//             chatPopup.style.display = "none";
//             chatPopup.style.animation = "slideUp 0.3s ease";
//         }, 300);
//     });
    
//     sendBtn.addEventListener("click", sendMessage);

//     userInput.addEventListener("keypress", function (e) {
//         if (e.key === "Enter") sendMessage();
//     });

//     voiceBtn.addEventListener("click", startVoiceRecognition);

//     document.addEventListener("keydown", function (e) {
//         if (e.key === "Escape") {
//             chatPopup.style.display = "none";
//         }
//     });

//     // Handle page reloads and tab closes
//     window.addEventListener('beforeunload', function() {
//         fetch("/reset_session", { 
//             method: "POST",
//             credentials: 'include',
//             keepalive: true
//         });
//     });

//     // Check if we have an active session
//     function hasActiveSession() {
//         return document.querySelector('.message.bot') !== null;
//     }

//     // Initialize chat session
//     function initializeChatSession() {
//         fetch("/reset_session", { 
//             method: "POST",
//             credentials: 'include'
//         })
//         .then(() => {
//             if (chatPopup.style.display === "flex") {
//                 appendMessage("bot", "Welcome to Dlytica! I'm your AI assistant. How can I help you today?", true);
//             }
//         })
//         .catch(console.error);
//     }

//     function validatePhoneNumber(phone) {
//         // Remove all non-digit characters except leading +
//         const cleaned = phone.replace(/(?!^\+)[\D]/g, '');
        
//         // Check for empty string
//         if (!cleaned) return false;
        
//         // Nepali numbers without country code (must be exactly 10 digits starting with 97/98)
//         if (!phone.startsWith('+') && !phone.startsWith('977')) {
//             return /^(97|98)\d{8}$/.test(cleaned) && cleaned.length === 10;
//         }
        
//         // Nepali numbers with country code
//         if (phone.startsWith('977') || phone.startsWith('+977')) {
//             const num = phone.startsWith('+977') ? cleaned.substring(4) : cleaned.substring(3);
//             return /^(97|98)\d{8}$/.test(num) && num.length === 10;
//         }
        
//         // International numbers
//         if (phone.startsWith('+')) {
//             // Basic length check for international numbers
//             return cleaned.length >= 8 && cleaned.length <= 15;
//         }
        
//         return false;
//     }

//     function sendMessage() {
//         const message = userInput.value.trim();
//         if (!message) return;
    
//         // Check if we're in phone number collection state
//         const isPhoneInput = document.querySelector('.message.bot:last-child')?.textContent.includes('phone number');
        
//         if (isPhoneInput && !validatePhoneNumber(message)) {
//             const trimmedMsg = message.toLowerCase();
//             if (trimmedMsg === 'skip' || trimmedMsg === 'na' || trimmedMsg === 'none' || trimmedMsg === '') {
//                 // Allow skipping
//                 userInput.value = "";
//                 message = "";
//             } else {
//                 appendMessage("bot", "Please enter a valid Nepali phone number (e.g., 98XXXXXXXX or 01-XXXXXXX)");
//                 userInput.value = "";
//                 return;
//             }
//         }
    
//         // Handle cancellation
//         if (message.toLowerCase().includes('cancel')) {
//             fetch("/reset_session", { 
//                 method: "POST",
//                 credentials: 'include'
//             })
//             .catch(console.error);
//         }
    
//         appendMessage("user", message);
//         userInput.value = "";
    
//         // Add bot typing animation
//         const typingDiv = appendTypingAnimation();
//         scrollToBottom();
    
//         // Send message to backend
//         fetch("/get_response", {
//             method: "POST",
//             body: JSON.stringify({ message: message }),
//             headers: { "Content-Type": "application/json" },
//             credentials: 'include'
//         })
//         .then(response => {
//             if (!response.ok) throw new Error('Network response was not ok');
//             return response.json();
//         })
//         .then(data => {
//             typingDiv.remove();
//             appendMessage("bot", data.response, true);
//         })
//         .catch(error => {
//             typingDiv.remove();
//             console.error("Error:", error);
//             appendMessage("bot", "Sorry, I'm having trouble responding right now. Please try again later.", true);
//         });
//     }

//     function appendMessage(sender, text, withAvatar = false, audioUrl = null) {
//         const msgDiv = document.createElement("div");
//         msgDiv.classList.add("message", sender);

//         if (sender === "bot" && withAvatar) {
//             const botIcon = document.createElement("img");
//             botIcon.src = "/static/dlytica_logo.jpg";
//             botIcon.alt = "Bot";
//             msgDiv.appendChild(botIcon);
//         }

//         const msgText = document.createElement("span");
//         msgText.innerText = text;
//         msgDiv.appendChild(msgText);

//         chatBox.appendChild(msgDiv);
//         scrollToBottom();

//         if (audioUrl) {
//             currentAudio = new Audio(audioUrl);
//             currentAudio.play();
//         }
//     }

//     function appendTypingAnimation() {
//         const typing = document.createElement("div");
//         typing.classList.add("message", "bot", "typing");
//         typing.innerHTML = `
//             <img src="/static/dlytica_logo.jpg" alt="Bot">
//             <span><i>Typing<span class="dot one">.</span><span class="dot two">.</span><span class="dot three">.</span></i></span>
//         `;
//         chatBox.appendChild(typing);
//         scrollToBottom();
//         return typing;
//     }

//     function scrollToBottom() {
//         chatBox.scrollTop = chatBox.scrollHeight;
//     }

//     function startVoiceRecognition() {
//         const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
//         if (!SpeechRecognition) return alert("Speech recognition not supported in this browser");

//         const recognition = new SpeechRecognition();
//         recognition.lang = "en-US";
//         recognition.start();

//         recognition.onresult = function (event) {
//             const transcript = event.results[0][0].transcript;
//             userInput.value = transcript;
//             sendMessage();
//         };

//         recognition.onerror = function (event) {
//             console.error("Speech recognition error:", event.error);
//             alert("Error recognizing speech. Please try again.");
//         };
//     }
// });