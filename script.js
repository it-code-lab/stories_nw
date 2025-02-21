let overlayData = [];
let currentOverlayText = "";

// Load structured_output.json
fetch('temp/structured_output.json')
    .then(response => response.json())
    .then(data => {
        overlayData = data;
    })
    .catch(error => console.error("Error loading overlay data:", error));

const video = document.getElementById("video");
const overlay = document.getElementById("overlayText");

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
});
