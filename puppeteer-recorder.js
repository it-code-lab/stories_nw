const puppeteer = require("puppeteer");
const { spawn } = require("child_process");
const path = require("path");

(async () => {
    const videoUrl = "file:///C:/0.data/4.SM-WSpace/6B.Python/1.Create_Video_From_Readernook_Story/application/index.html"; // ✅ Change if needed
    const recordingDuration = 10; // seconds

    const browser = await puppeteer.launch({
        headless: false,
        defaultViewport: { width: 1280, height: 720 },
        args: [
            '--start-maximized',
            '--autoplay-policy=no-user-gesture-required'
        ]
    });

    const [page] = await browser.pages();
    await page.goto(videoUrl);

    console.log("✅ Browser opened. Waiting for video to load...");

    await page.waitForSelector("video");

    // Force autoplay
    await page.evaluate(() => {
        const video = document.querySelector("video");
        video.currentTime = 0;
        video.muted = false;
        video.volume = 1.0;
        video.play();
    });

    const delayMs = 1000;
    console.log(`⏳ Waiting ${delayMs}ms before starting recording...`);
    await new Promise(res => setTimeout(res, delayMs));

    // ⚠️ FFmpeg for Windows uses gdigrab (desktop capture)
    const outputFile = path.resolve(__dirname, "captured_video.mp4");

    const ffmpeg = spawn("ffmpeg", [
        "-y",
        "-f", "gdigrab",
        "-framerate", "30",
        "-offset_x", 12 ,
        "-offset_y", 130 ,
        "-video_size", "1664x936", // Adjust to your screen resolution
        "-i", "desktop",           // 🪟 Captures entire screen
    
        // 🎧 Add this block to capture system audio
        "-f", "dshow",
        "-i", "audio=Stereo Mix (Realtek(R) Audio)",

        // Sync audio + video
        "-c:v", "libx264",
        "-c:a", "aac",
        "-b:a", "192k",
        "-preset", "ultrafast",
        "-t", `${recordingDuration}`,
        "-pix_fmt", "yuv420p",
        outputFile
    ]);

    ffmpeg.stderr.on("data", (data) => {
        console.log("FFmpeg:", data.toString());
    });

    ffmpeg.on("close", async () => {
        console.log("✅ Recording complete: captured_video.mp4");
        await browser.close();
    });

})();
