let overlayData = [];
let currentOverlayText = "";
let captionsData = [];
let currentCaption = "";

let captionWordLimit = 5;  // Default number of words per block
let currentBlockStart = 0; // Track where the current caption block starts
let lastSpokenWordIndex = -1; // Last word index processed
let lastCaptionUpdateTime = 0; // Time when captions were last updated

// Load structured_output.json (for headings & list items)
fetch('temp/structured_output.json')
    .then(response => response.json())
    .then(data => {
        overlayData = data;
    })
    .catch(error => console.error("Error loading overlay data:", error));

// Load full_text and word_timestamps (for captions)
fetch('temp/word_timestamps.json')
    .then(response => response.json())
    .then(data => {
        captionsData = data;
    })
    .catch(error => console.error("Error loading captions data:", error));

const video = document.getElementById("video");
const overlay = document.getElementById("overlayText");
const captions = document.getElementById("captions");

const captionInput = document.getElementById("captionLength");

// Update caption word limit dynamically from user input
captionInput.addEventListener("input", () => {
    captionWordLimit = parseInt(captionInput.value, 10) || 5;
});

// Listen for video time updates
video.addEventListener("timeupdate", () => {
    const currentTime = video.currentTime;

    /** 🔹 1. Show Headings & List Items **/
    const activeOverlay = overlayData.find(item => 
        currentTime >= item.start_word_start_timing && currentTime <= item.end_word_end_timing
    );

    if (activeOverlay) {
        if (activeOverlay.text !== currentOverlayText) {
            overlay.innerText = activeOverlay.text;
            overlay.classList.remove("heading", "list-item");
            overlay.classList.add(activeOverlay.type === "heading" ? "heading" : "list-item");

            overlay.classList.add("show");
            overlay.classList.remove("hide");
            currentOverlayText = activeOverlay.text; 
        }
    } else {
        if (currentOverlayText !== "") { 
            overlay.classList.add("hide");
            setTimeout(() => overlay.classList.remove("show"), 500);
            currentOverlayText = "";
        }
    }

    /** 🔹 2. Display Captions in Blocks & Maintain Them During Pauses **/
    let currentIndex = captionsData.findIndex(word => currentTime >= word.start && currentTime <= word.end);
    
    if (currentIndex !== -1) {
        // Only update if we reach the last word of the current block
        if (currentIndex >= currentBlockStart + captionWordLimit) {
            currentBlockStart = currentIndex; // Move to the next block
            lastCaptionUpdateTime = currentTime; // Update last update time
        }

        let endIdx = Math.min(currentBlockStart + captionWordLimit, captionsData.length);
        let currentBlockWords = captionsData.slice(currentBlockStart, endIdx);

        let displayedWords = currentBlockWords.map((wordObj) => {
            return (currentTime >= wordObj.start && currentTime <= wordObj.end)
                ? `<span class="current-word">${wordObj.word}</span>` // Highlight spoken word
                : wordObj.word;
        });

        const newCaption = displayedWords.join(" ");

        if (newCaption !== captions.innerHTML) {
            captions.innerHTML = newCaption;
            captions.classList.add("show-caption");
            captions.classList.remove("hide-caption");
        }
    } else if (currentTime - lastCaptionUpdateTime < 2) {
        // 🔹 If there’s a pause, keep the last caption visible for 2 seconds
        captions.classList.add("show-caption");
        captions.classList.remove("hide-caption");
    } else if (captions.innerHTML !== "") {
        // 🔹 After the pause, fade out the caption
        captions.classList.add("hide-caption");
        setTimeout(() => captions.classList.remove("show-caption"), 300);
    }
});
