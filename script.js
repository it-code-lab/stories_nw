// 🔹 Dummy Caption Data for Preview
let dummyCaptionsData = [
    { "word": "This", "start": 0.0, "end": 0.22 },
    { "word": "is", "start": 0.22, "end": 0.36 },
    { "word": "a", "start": 0.36, "end": 0.48 },
    { "word": "caption", "start": 0.48, "end": 0.72 },
    { "word": "preview", "start": 0.72, "end": 1.12 }
];

let overlayData = [];
let currentOverlayText = "";
//let currentCaptionIndex = 0;  // Track the index of the caption being displayed
let captionsData = [];
let currentCaption = "";

let captionWordLimit = 5;  // Default number of words per block
let currentBlockStart = 0; // Track where the current caption block starts
let lastSpokenWordIndex = -1; // Last word index processed
let lastCaptionUpdateTime = 0; // Time when captions were last updated

let previewTime = 0.0;
let previewInterval;

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
const playPauseBtn = document.getElementById("playPauseBtn");
const restartBtn = document.getElementById("restartBtn");
const videoTimeDisplay = document.getElementById("video-time");

const captionStyleDropdown = document.getElementById("captionStyle");
const captionPreview = document.getElementById("caption-preview");

const subscribeGif = document.getElementById("subscribe-gif");

// 🔹 Hide Default Video Controls
video.removeAttribute("controls");

// 🔹 Play/Pause Button Functionality
playPauseBtn.addEventListener("click", () => {
    if (video.paused) {
        video.play();
        playPauseBtn.innerHTML = "⏸ Pause";
    } else {
        video.pause();
        playPauseBtn.innerHTML = "▶ Play";
    }
});

// 🔹 Restart Button Functionality
restartBtn.addEventListener("click", () => {
    video.currentTime = 0;
    video.play();
    playPauseBtn.innerHTML = "⏸ Pause";  // Change button to "Pause" when restarted

    //currentCaptionIndex = 0;  // Reset caption tracking
    captions.innerHTML = "";  // Clear previous captions
    currentBlockStart = 0
});

// 🔹 Format Time Function (Convert Seconds to mm:ss)
function formatTime(time) {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

// // 🔹 Update Time Display
// video.addEventListener("timeupdate", () => {
//     videoTimeDisplay.innerHTML = `${formatTime(video.currentTime)} / ${formatTime(video.duration)}`;
// });

// 🔹 Update Total Duration When Metadata Loads
video.addEventListener("loadedmetadata", () => {
    videoTimeDisplay.innerHTML = `00:00 / ${formatTime(video.duration)}`;
});

const overlay = document.getElementById("overlayText");
const captions = document.getElementById("captions");

const captionInput = document.getElementById("captionLength");

// Update caption word limit dynamically from user input
captionInput.addEventListener("input", () => {
    captionWordLimit = parseInt(captionInput.value, 10) || 5;
});

// Change Caption Style Based on Selection
captionStyleDropdown.addEventListener("change", () => {
    let selectedStyle = captionStyleDropdown.value;

    // Remove old styles
    captions.className = "captions-text";
    captionPreview.className = "preview-captions-text";

    // Apply new style
    captions.classList.add(selectedStyle);
    captionPreview.classList.add(selectedStyle);
});

// Update caption word limit dynamically from user input
captionInput.addEventListener("input", () => {
    captionWordLimit = parseInt(captionInput.value, 10) || 5;
});

let videoDuration = video.duration;

// Listen for video time updates
video.addEventListener("timeupdate", () => {
    const currentTime = video.currentTime;
    

    if (currentTime >= 30 && currentTime <= 35) {
        // Show GIF 30 seconds after start (for 5 seconds)
        subscribeGif.classList.add("show-gif");
        subscribeGif.classList.remove("hidden");
    } else if (videoDuration - currentTime <= 30 && videoDuration - currentTime >= 25) {
        // Show GIF 30 seconds before end (for 5 seconds)
        subscribeGif.classList.add("show-gif");
        subscribeGif.classList.remove("hidden");
    } else {
        // Hide otherwise
        subscribeGif.classList.remove("show-gif");
        subscribeGif.classList.add("hidden");
    }
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
    videoTimeDisplay.innerHTML = `${formatTime(video.currentTime)} / ${formatTime(video.duration)}`;

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


// 🔹 Simulate Caption Animation in Preview Section
function startPreviewAnimation() {
    clearInterval(previewInterval); // Reset animation if already running
    previewTime = 0.0;

    previewInterval = setInterval(() => {
        previewTime += 0.1; // Move forward in time

        let currentIndex = dummyCaptionsData.findIndex(word => previewTime >= word.start && previewTime <= word.end);

        if (currentIndex !== -1) {
            let displayedWords = dummyCaptionsData.map((wordObj, index) => {
                return index === currentIndex
                    ? `<span class="current-word">${wordObj.word}</span>` // Highlight current word
                    : wordObj.word;
            });

            captionPreview.innerHTML = displayedWords.join(" ");
        }

        if (previewTime >= 2.0) {
            previewTime = 0.0; // Restart the animation loop
        }
    }, 100);
}

// Start the caption animation loop on page load
startPreviewAnimation();