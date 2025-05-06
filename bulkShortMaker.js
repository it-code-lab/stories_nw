//let content_style = "style2_upper_center_up";

//DND - Tobe used for facts/history stories
//let content_style = "style1_camel_center_up"; 

//DND - Tobe used for scary stories
let content_style = "style4_camel_center_up"; 

let textStyleDropdown = document.getElementById("textStyle");
let loadDataDropdown = document.getElementById("loadData");
const fontFamily = document.getElementById('fontFamily');

let dummyInputData = [
    {
        templateType: "Fact",
        title: "Mind Blown 🤯",
        text1: "Octopuses have three hearts^Two hearts pump blood to the gills^One heart pumps blood to the body",
        text2: "",
        text3: "",
        text4: "",
        text5: "",
        text6: "",
        text7: "",
        text8: "",
        text9: "",
        text10: "",
        subText: "When they swim, one heart stops!",
        ctaText: "👉 Follow for more wild facts!",
        musicFile: "background_music/sample_music.mp3",
        musicVolume: 0.2,
        backgroundVideo: "sample_bg",
        ttsEnabled: true
    },
    {
        templateType: "Quote",
        title: "",
        text1: "Success is not final, failure is not fatal.^It is the courage to continue that counts.",
        text2: "",
        text3: "",
        text4: "",
        text5: "",
        text6: "",
        text7: "",
        text8: "",
        text9: "",
        text10: "",
        subText: "— Winston Churchill",
        ctaText: "",
        musicFile: "background_music/sample_music.mp3",
        musicVolume: 0.2,
        backgroundVideo: "sample_bg",
        ttsEnabled: true
    },
    {
        templateType: "List",
        title: "Top 5 Energy Boosters ⚡",
        text1: "1. Morning sunlight^2. 2L water^3. 30 min walk^4. Cold shower^5. Deep breathing",
        text2: "",
        text3: "",
        text4: "",
        text5: "",
        text6: "",
        text7: "",
        text8: "",
        text9: "",
        text10: "",
        subText: "Try them for a week and feel the difference!",
        ctaText: "💪 Stay energized!",
        musicFile: "background_music/sample_music.mp3",
        musicVolume: 0.2,
        backgroundVideo: "sample_bg",
        ttsEnabled: true
    },
    {
        templateType: "Challenge",
        title: "Brain Teaser 🧠",
        text1: "I speak without a mouth^I echo but have no ears^What am I?",
        text2: "",
        text3: "",
        text4: "",
        text5: "",
        text6: "",
        text7: "",
        text8: "",
        text9: "",
        text10: "",
        subText: "Answer: An echo.",
        ctaText: "🧩 Follow for daily riddles!",
        musicFile: "background_music/sample_music.mp3",
        musicVolume: 0.2,
        backgroundVideo: "sample_bg",
        ttsEnabled: true
    },
    {
        templateType: "Life Advice",
        title: "Simple Truth 🌱",
        text1: "You can't pour from an empty cup.^Take care of yourself first.^Even 10 minutes a day is enough.",
        text2: "",
        text3: "",
        text4: "",
        text5: "",
        text6: "",
        text7: "",
        text8: "",
        text9: "",
        text10: "",
        subText: "Self-care is not selfish.",
        ctaText: "✨ Share this with someone who needs it!",
        musicFile: "background_music/sample_music.mp3",
        musicVolume: 0.2,
        backgroundVideo: "sample_bg",
        ttsEnabled: true
    },
    {
        templateType: "Fact",
        title: "Weird But True 😲",
        text1: "Sharks existed before trees!^Trees: 350 million years ago^Sharks: 400 million years ago",
        text2: "",
        text3: "",
        text4: "",
        text5: "",
        text6: "",
        text7: "",
        text8: "",
        text9: "",
        text10: "",
        subText: "They’ve been around longer than dinosaurs too!",
        ctaText: "",
        musicFile: "background_music/sample_music.mp3",
        musicVolume: 0.2,
        backgroundVideo: "sample_bg",
        ttsEnabled: true
    },
    {
        templateType: "Quote",
        title: "",
        text1: "“Be yourself; everyone else is already taken.”",
        text2: "",
        text3: "",
        text4: "",
        text5: "",
        text6: "",
        text7: "",
        text8: "",
        text9: "",
        text10: "",
        subText: "— Oscar Wilde",
        ctaText: "",
        musicFile: "background_music/sample_music.mp3",
        musicVolume: 0.2,
        backgroundVideo: "sample_bg",
        ttsEnabled: true
    },
    {
        templateType: "List",
        title: "3 Quick Wins Today 🎯",
        text1: "✅ Make your bed^✅ Drink water^✅ Plan your top 3 tasks",
        text2: "",
        text3: "",
        text4: "",
        text5: "",
        text6: "",
        text7: "",
        text8: "",
        text9: "",
        text10: "",
        subText: "Small wins lead to big momentum!",
        ctaText: "",
        musicFile: "background_music/sample_music.mp3",
        musicVolume: 0.2,
        backgroundVideo: "sample_bg",
        ttsEnabled: true
    },
    {
        templateType: "Challenge",
        title: "Can You Guess? 🤔",
        text1: "The more you take, the more you leave behind.^What are they?",
        text2: "",
        text3: "",
        text4: "",
        text5: "",
        text6: "",
        text7: "",
        text8: "",
        text9: "",
        text10: "",
        subText: "Answer: Footsteps 👣",
        ctaText: "",
        musicFile: "background_music/sample_music.mp3",
        musicVolume: 0.2,
        backgroundVideo: "sample_bg",
        ttsEnabled: true
    },
    {
        templateType: "Life Advice",
        title: "Gentle Reminder 💛",
        text1: "Slow progress is still progress.^Resting is part of the journey.^You’re doing better than you think.",
        text2: "",
        text3: "",
        text4: "",
        text5: "",
        text6: "",
        text7: "",
        text8: "",
        text9: "",
        text10: "",
        subText: "",
        ctaText: "✨ Be kind to yourself.",
        musicFile: "background_music/sample_music.mp3",
        musicVolume: 0.2,
        backgroundVideo: "sample_bg",
        ttsEnabled: true
    }
];

let currentShortIndex = 0;
let currentShortMainTextIndex = 0;
let mainTexts = [];
let subText = "";
let ctaText = "";
let ttsEnabled = false;

let totalShortsData = [];  // will hold all shorts read from Excel or dummy

let usePreGeneratedAudio = true; // Set to true to use DIA audio
let preGeneratedAudioFolder = "generated_audio";


const titleEl = document.getElementById('title');
const mainTextEl = document.getElementById('mainText');
const subTextEl = document.getElementById('subText');
const ctaTextEl = document.getElementById('ctaText');
const bgMusic = document.getElementById('bgMusic');
const bgVideo = document.getElementById('bgVideo').querySelector('source');
let parts = [];
let currentPartIndex = 0;
let overAllPartNumber = 0;
let partElements = [];
let part = "";

function cleanCorruptedCharacters(inputText) {
    if (!inputText) return "";

    // Remove all isolated ? characters
    return inputText.replace(/\?/g, '').trim();
}


function playPreGeneratedAudio(shortIndex, partIndex, onComplete) {
    const audioPath = `${preGeneratedAudioFolder}/short_${shortIndex}_${partIndex}.mp3`;
    const audio = new Audio(audioPath);
    audio.volume = 1.0;
    audio.onended = onComplete;
    audio.onerror = () => {
        console.warn("Audio not found, skipping...");
        onComplete();
    };
    audio.play().catch((e) => {
        console.warn("Play error:", e);
        onComplete();
    });
}

function isMostlyCorrupted(text) {
    if (!text) return true;
    const cleaned = text.replace(/[^\w\s.,!?'"()-]/g, '');
    const corruptionRatio = 1 - (cleaned.length / text.length);
    return corruptionRatio > 0.5;  // If >50% characters are weird, consider it bad
}


function displayNextMainText() {
    console.log("=======Inside displayNextMainText======",currentShortMainTextIndex);

    if (currentShortMainTextIndex < mainTexts.length) {
        mainTextEl.innerHTML = '';

        let currentText = mainTexts[currentShortMainTextIndex];
        parts = currentText.includes("^") ? currentText.split("^") : [currentText];
        partElements = [];
        // ttsEnabled = data.ttsEnabled;

        // Step 1: Add all elements initially (but hidden)
        parts.forEach((part, index) => {
            let el = document.createElement('p');
            const cleanPart = cleanCorruptedCharacters(part);
            if (!isMostlyCorrupted(cleanPart)) {
                el.textContent = cleanPart;
                el.classList.add("mainTextPart");
                el.style.opacity = 0;
                el.style.transition = "opacity 0.5s ease";
                mainTextEl.appendChild(el);
                partElements.push(el);
            }

        });

        currentPartIndex = 0;

        // Step 2: Show each part (and optionally speak)


        displayNextPart();

    } else if (currentShortMainTextIndex == mainTexts.length) {
        overAllPartNumber = 0;
        displaySubTextAndCTA()
    }
}

function displayNextPart() {
    console.log("Inside displayNextPart. currentPartIndex:", currentPartIndex, " parts.length:", parts.length );
    if (currentPartIndex >= parts.length) {
        currentShortMainTextIndex++;
        displayNextMainText();
        return;
    }

    const el = partElements[currentPartIndex];
    el.style.opacity = 1;  // reveal smoothly
    part = parts[currentPartIndex];
    console.log("Part to display:", part, "ttsEnabled:", ttsEnabled, "usePreGeneratedAudio:", usePreGeneratedAudio);
    //currentPartIndex++;
    if (ttsEnabled) {
        if (usePreGeneratedAudio) {
            // playAudioForPart(currentShortIndex, currentPartIndex, displayNextPart);
            playPreGeneratedAudio(currentShortIndex, overAllPartNumber, () => {
                currentPartIndex++;
                overAllPartNumber++;
                setTimeout(displayNextPart, 300); // slight delay between parts
            });
        } else {
            currentPartIndex++;
            overAllPartNumber++;
            speakText(part, displayNextPart);
        }
    } else {
        currentPartIndex++;
        overAllPartNumber++;
        setTimeout(displayNextPart, part.length * 60);
    }

}
function displaySubTextAndCTA() {
    console.log("Inside displaySubTextAndCTA. currentShortMainTextIndex:", currentShortMainTextIndex, " mainTexts.length:", mainTexts.length);
    // Show subText
    if (subText) {
        //const subTextEl = document.createElement('p');
        subTextEl.textContent = subText;
        subTextEl.classList.add("fade-in-slide-Up");
        // addVisibility(subTextEl, 10);
        //mainTextEl.appendChild(subTextEl);
    }

    // Show CTA
    if (ctaText) {
        setTimeout(() => {
            // const ctaTextEl = document.createElement('p');
            ctaTextEl.textContent = ctaText;
            ctaTextEl.classList.add("fade-in-slide-Up");
            // addVisibility(ctaTextEl, 10);
            // mainTextEl.appendChild(ctaEl);
        }, 1000);
    }

    // Short fully loaded → Notify Puppeteer to start recording
    //triggerPuppeteerRecording(currentShortIndex);
}



function playAudioForPart(index, partIndex, onComplete) {
    const audio = new Audio(`${preGeneratedAudioFolder}/audio_${index}_${partIndex}.mp3`);
    audio.volume = 1.0;
    audio.onended = onComplete;
    audio.onerror = () => {
        console.error("Audio not found. Falling back to TTS.");
        speakText(mainTexts[index].split("^")[partIndex], onComplete); // fallback to speechSynthesis
    };
    audio.play().catch((e) => {
        console.error("Play error. Falling back to TTS.", e);
        speakText(mainTexts[index].split("^")[partIndex], onComplete);
    });
}


function speakText(text, onComplete) {
    console.log("speakText called with text:", text);
    if (!window.speechSynthesis) return onComplete();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'en-US';
    utterance.rate = 1.0;
    utterance.onend = onComplete;
    speechSynthesis.speak(utterance);
}

function readFromDummyInputData(selectedOption) {
    console.log("Inside readFromDummyInputData. selectedOption:", selectedOption);
    const selectedData = dummyInputData[selectedOption];
    if (!selectedData) {
        console.error("Invalid selection");
        return null;
    }

    mainTexts = [];
    for (let i = 0; i <= 10; i++) {
        const textValue = selectedData[`text${i}`];
        if (textValue !== undefined && textValue !== null && textValue !== "") {
            mainTexts.push(textValue);
        }
    }

    return {
        templateType: selectedData.templateType || "Fact",
        title: selectedData.title || "",
        mainTexts: mainTexts,
        subText: selectedData.subText || "",
        ctaText: selectedData.ctaText || "",
        musicFile: selectedData.musicFile || "background_music/sample_music.mp3",
        musicVolume: parseFloat(selectedData.musicVolume) || 0.2,
        backgroundVideo: "background_videos/" + selectedData.backgroundVideo + ".mp4" || "background_videos/sample_bg.mp4",
        ttsEnabled: selectedData.ttsEnabled || false
    };
}

// let data = getQueryParams();
//let data = readFromDummyInputData("1");
//showContent(data);
contentContainer = document.getElementById("contentContainer");
contentContainer.classList.add(content_style);



textStyleDropdown.addEventListener("change", () => {
    content_style = textStyleDropdown.value;
    // Remove old styles
    contentContainer.className = "content";
    // Apply new style
    contentContainer.classList.add(content_style);
    showContent(data);
});

backgroundStyle.addEventListener("change", () => {
    let video = "background_videos/" + backgroundStyle.value + ".mp4";
    bgVideo.src = video;
    document.getElementById('bgVideo').load();

});

backgroundSound.addEventListener("change", () => {
    let audioSrc = "sounds/" + backgroundSound.value + ".mp3";
    bgMusic.src = audioSrc;
    bgMusic.volume = 0.02;
    bgMusic.play().catch(e => console.log('Music autoplay blocked'));

});

loadDataDropdown.addEventListener("change", () => {
    const selectedOption = loadDataDropdown.value;
    data = readFromDummyInputData(selectedOption);
    showContent(data);
});

fontFamily.addEventListener('change', () => {
    const selectedFont = fontFamily.value;
    document.body.style.fontFamily = selectedFont;
});

function loadShort(shortData, shortIndex) {
    console.log("Inside loadShort. Loading shortData:", shortData);

    currentShortIndex = shortIndex;
    currentPartIndex = 0;
    overAllPartNumber = 0;
    mainTexts = [];

    titleEl.innerHTML = "";
    mainTextEl.innerHTML = "";

    if (shortData.title) {
        titleEl.textContent = shortData.title;
    }

    subText = shortData.subText || "";
    ctaText = shortData.ctaText || "";

    for (let i = 1; i <= 10; i++) {
        const textValue = shortData[`text${i}`];
        if (textValue !== undefined && textValue !== null && textValue !== "") {
            mainTexts.push(textValue);
        }
        // if (textPart) {
        //     const parts = textPart.includes("^") ? textPart.split("^") : [textPart];
        //     mainTexts.push(...parts);
        // }
    }

    // let bgVideoNme = shortData.backgroundVideo || "sample_bg";
    // let bgVideoSrc = "background_videos/" + bgVideoNme + ".mp4" 

    let bgVideoSrc = shortData.background_video_src || "background_videos/sample_bg.mp4";

    bgVideo.src = decodeURIComponent(bgVideoSrc);
    document.getElementById('bgVideo').load();

    let audioName = shortData.musicFile || "story-classical-3-710";
    let audioSrc = "sounds/" + audioName + ".mp3";
    bgMusic.src = audioSrc;
    bgMusic.volume = 0.05;
    bgMusic.play().catch(e => console.log('Music autoplay blocked'));
    
    
    // Animate Title
    if (shortData.title !== "") {
        titleEl.textContent = shortData.title;
        titleEl.style.padding = "10px";
    } else {
        titleEl.textContent = "";
        titleEl.style.padding = "0px";
    }

    ttsEnabled = shortData.ttsEnabled || true;
    currentShortMainTextIndex = 0;
    setTimeout(() => {
        displayNextMainText(); // Start displaying the first text
    }, 4000);
    

}

//DND - Not in use
function loadAllShorts() {
    // You would dynamically load from Excel later
    // For now assume dummyInputData is already populated
    totalShortsData = dummyInputData;
    console.log("All shorts loaded. Proceeding with first");
    if (totalShortsData.length > 0) {
        loadShort(totalShortsData[0], 0);
    }
}

async function loadShortsDataFromJsonFile(shortIndexToLoad = 0) {
    const response = await fetch('bulkShorts_input.json');
    const data = await response.json();
    totalShortsData = data;
    if (totalShortsData.length > 0) {
        loadShort(totalShortsData[shortIndexToLoad], shortIndexToLoad);
    }
}


function loadNextShort() {
    currentShortIndex++;
    if (currentShortIndex < totalShortsData.length) {
        loadShort(totalShortsData[currentShortIndex], currentShortIndex);
    } else {
        console.log("All shorts processed!");
    }
}

// Puppeteer can call this after each recording is done
window.recordingFinished = function (shortIndex) {
    console.log("Recording finished for short:", shortIndex);
    loadNextShort();
};

// Load everything
//document.addEventListener("DOMContentLoaded", loadAllShorts);
//document.addEventListener("DOMContentLoaded", loadShortsDataFromJsonFile);

// document.addEventListener("DOMContentLoaded", async () => {
//     const params = new URLSearchParams(window.location.search);
//     const shortIndex = parseInt(params.get('shortIndex')) || 0;
//     await loadShortsDataFromJsonFile(shortIndex);
// });

document.getElementById('startOverlay').addEventListener('click', () => {
    document.getElementById('startOverlay').style.display = 'none';
    document.getElementById('shortsContainer').style.visibility = 'visible';
    const params = new URLSearchParams(window.location.search);
    const shortIndex = parseInt(params.get('shortIndex')) || 0;
    loadShortsDataFromJsonFile(shortIndex);  
    
});

document.getElementById('stopMusic').addEventListener('click', () => {
    console.log("Stop music clicked");
    bgMusic.pause();
    bgMusic.currentTime = 0;
});
//DND - Not in use
//DND - Working 
function displayNextShort_old() {
    if (currentShortIndex < mainTexts.length) {

        // Clear previous text element if it exists
        mainTextEl.innerHTML = '';

        let text = mainTexts[currentShortIndex];
        let textElement = document.createElement('p');
        let subTexts = text.split("^");
        let prevText = "";
        if (subTexts.length > 1) {
            for (let i = 0; i < subTexts.length; i++) {
                let subTextElement = document.createElement('p');
                if (i > 0) {
                    //subTextElement.className = "noDisplay";
                    subTextElement.style.visibility = "hidden";
                    addVisibility(subTextElement, prevText.length / 10);
                }
                subTextElement.textContent = subTexts[i];
                subTextElement.classList.add("fade-in-slide-Up");
                mainTextEl.appendChild(subTextElement);
                prevText = prevText + subTexts[i];
            }

        } else {
            textElement.textContent = text;
        }
        // Calculate duration based on text length (you can adjust the multiplier)
        let durationMs = text.length * 100; // Example: 100ms per character

        mainTextEl.appendChild(textElement);

        if (currentShortIndex < mainTexts.length - 1) {
            setTimeout(() => {
                textElement.style.display = 'none';
                currentShortIndex++;
                displayNextMainText(); // Display the next text
            }, durationMs);
        }
        // currentShortIndex++;
    }
}



// function removeNoDisplayAfterSeconds(element, seconds) {
//     setTimeout(() => {
//         element.style.display = 'block';
//     }, seconds * 1000);
// }

//DND - Not in use
function splitTextIntoSpans(element, text, baseDelay = 1.5) {
    element.innerHTML = "";
    const words = text.split(" ");
    words.forEach((word, index) => {
        const span = document.createElement("span");
        span.textContent = word;
        element.appendChild(span);
    });
}

//DND - Not in use
function getQueryParams() {
    const params = new URLSearchParams(window.location.search);
    const mainTexts = [];
    for (let i = 1; i <= 10; i++) {
        const textParam = params.get(`text${i}`);
        if (textParam !== null) {
            mainTexts.push(textParam);
        } else {
            //mainTexts.push(""); // Or you could choose to not push anything, depending on desired behavior
        }
    }

    return {
        templateType: params.get('templateType') || "Fact",
        title: params.get('title') || "",
        mainTexts: mainTexts,
        subText: params.get('subText') || "",
        ctaText: params.get('ctaText') || "",
        musicFile: params.get('musicFile') || "background_music/sample_music.mp3",
        musicVolume: parseFloat(params.get('musicVolume')) || 0.2,
        backgroundVideo: params.get('backgroundVideo') || "background_videos/sample_bg.mp4"
    };
}

//NOT IN USE
// This function is not used in the current code but is kept for reference
function addVisibilityClass(el, delay = 0) {
    console.log("Adding visibility class with delay:", delay);
    el.style.animationDelay = `${delay}s`;
    el.classList.add("fade-in");
}

//Not in use
// This function is not used in the current code but is kept for reference  
function addVisibility(element, seconds = 0) {
    console.log("Inside addVisibility");

    setTimeout(() => {

        // 🔹 Reset animation (remove & re-add class)
        element.classList.remove("fade-in-slide-Up");
        void element.offsetWidth;  // Trigger reflow to restart animation
        element.classList.add("fade-in-slide-Up");
        element.style.visibility = 'visible';
    }, seconds * 1000);
}

//Not used in batch processing
function showContent(data) {
    console.log("showContent called with data:", data);


    // Set video and music********DND**********
    // bgMusic.src = decodeURIComponent(data.musicFile);
    // bgMusic.volume = data.musicVolume;
    // bgMusic.play().catch(e => console.log('Music autoplay blocked'));

    bgVideo.src = decodeURIComponent(data.backgroundVideo);
    document.getElementById('bgVideo').load();

    // Animate Title
    if (data.title !== "") {
        titleEl.textContent = decodeURIComponent(data.title);
        titleEl.style.padding = "10px";
    } else {
        titleEl.textContent = "";
        titleEl.style.padding = "0px";
    }

    // Animate MainText blocks sequentially
    mainTexts = data.mainTexts;
    ttsEnabled = data.ttsEnabled;
    let totalTextLength = 0;
    for (let i = 0; i < mainTexts.length; i++) {
        totalTextLength += mainTexts[i].length;
    }
    currentShortIndex = 0;
    currentShortMainTextIndex = 0;
    mainTextEl.innerHTML = ''; // Clear previous content
    displayNextMainText(); // Start displaying the first text

    subTextEl.textContent = decodeURIComponent(data.subText);
    subTextEl.style.visibility = "hidden";
    addVisibility(subTextEl, totalTextLength / 10);

    // CTA and Subscribe
    ctaTextEl.textContent = decodeURIComponent(data.ctaText);
    ctaTextEl.style.visibility = "hidden";
    addVisibility(ctaTextEl, (totalTextLength / 10) + 1);
}

//Not in use
// This function is not used in the current code but is kept for reference
function triggerPuppeteerRecording(shortIndex) {
    console.log("Trigger recording for short:", shortIndex);
    if (window.startRecording) {
        window.startRecording(shortIndex);  // Puppeteer script will listen and start recording
    }
}