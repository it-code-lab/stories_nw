const puppeteer = require('puppeteer');
const fs = require('fs');
const { exec } = require('child_process');

(async () => {
    const browser = await puppeteer.launch({
        headless: false,  // Keep it visible for debugging
        defaultViewport: { width: 1280, height: 720 }
    });

    const page = await browser.newPage();
    await page.goto('file://' + __dirname + '/index.html');

    await page.waitForSelector("#video-container");

    // Get the video container position & size
    const videoBox = await page.evaluate(() => {
        const videoElement = document.querySelector("#video-container");
        const rect = videoElement.getBoundingClientRect();
        return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
    });

    console.log("📏 Video Capture Area:", videoBox);

    // Ensure the "frames" folder exists
    if (!fs.existsSync("frames")) fs.mkdirSync("frames");

    // Start playing the video
    await page.evaluate(() => {
        const video = document.getElementById("video");
        video.currentTime = 0;  // Restart video
        video.play();  // Start playback
    });

    let frameIndex = 0;
    const FPS = 30;  // Target frame rate
    const duration = await page.evaluate(() => document.getElementById("video").duration);
    const totalFrames = Math.ceil(duration * FPS);

    console.log(`🎬 Capturing ${totalFrames} frames at ${FPS} FPS...`);

    for (let i = 0; i < totalFrames; i++) {
        // Capture screenshot of only the video container
        await page.screenshot({
            path: `frames/frame-${String(frameIndex).padStart(4, '0')}.png`,
            clip: videoBox
        });

        frameIndex++;

        // Wait for the next frame (1/FPS seconds)
        await new Promise(resolve => setTimeout(resolve, 1000 / FPS));
    }

    await browser.close();

    console.log("🖼️ Screenshots Captured! Now Rendering Video...");

    // Convert frames to video using FFmpeg
    exec(`ffmpeg -r ${FPS} -i frames/frame-%04d.png -c:v libx264 -pix_fmt yuv420p -vf "scale=1280:720" temp_video.mp4`, (error) => {
        if (error) console.error("FFmpeg Error:", error);
        else console.log("✅ Video Rendered Successfully!");
    });

})();
