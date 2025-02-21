let overlayData = [];
let currentOverlayText = "";

let captionsData = [];
let currentCaption = "";

let captionWordLimit = 5;  // Default number of words to display
let currentCaptionWords = [];
// Load structured_output.json
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

// Update the caption word limit dynamically from user input
captionInput.addEventListener("input", () => {
    captionWordLimit = parseInt(captionInput.value, 10) || 5;
});

// Listen for video time updates
video.addEventListener("timeupdate", () => {
    const currentTime = video.currentTime;

    // Find active overlay text for this timestamp
    const activeOverlay = overlayData.find(item => 
        currentTime >= item.start_word_start_timing && currentTime <= item.end_word_end_timing
    );

    if (activeOverlay) {
        if (activeOverlay.text !== currentOverlayText) { // Only update if text has changed
            overlay.innerText = activeOverlay.text;

            // Apply dynamic class based on type
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

    /** 🔹 2. Display Captions with Fixed Positioning **/
    let currentIndex = captionsData.findIndex(word => currentTime >= word.start && currentTime <= word.end);
    
    if (currentIndex !== -1) {
        let startIdx = Math.max(0, currentIndex - Math.floor(captionWordLimit / 2));
        let endIdx = Math.min(startIdx + captionWordLimit, captionsData.length);

        // Keep previous words fixed in place to prevent shifting
        if (currentCaptionWords.length === 0) {
            currentCaptionWords = captionsData.slice(startIdx, endIdx).map(word => word.word);
        }

        let displayedWords = currentCaptionWords.map((word, index) => {
            let wordData = captionsData.find(w => w.word === word);
            let isCurrent = wordData && (currentTime >= wordData.start && currentTime <= wordData.end);
            return isCurrent ? `<span class="current-word">${word}</span>` : word;
        });

        const newCaption = displayedWords.join(" ");

        if (newCaption !== captions.innerHTML) {
            captions.innerHTML = newCaption;
            captions.classList.add("show-caption");
            captions.classList.remove("hide-caption");
        }
    } else {
        if (captions.innerHTML !== "") { 
            captions.classList.add("hide-caption");
            setTimeout(() => captions.classList.remove("show-caption"), 300);
        }
    }

});
