const puppeteer = require('puppeteer');

// Set FFmpeg paths
ffmpeg.setFfmpegPath('C:\\ffmpeg\\bin\\ffmpeg.exe');
ffmpeg.setFfprobePath('C:\\ffmpeg\\bin\\ffprobe.exe');

(async () => {
  // Launch the browser in non-headless mode.
  const browser = await puppeteer.launch({ 
    headless: false,
    args: [
      '--auto-select-desktop-capture-source=Entire screen', 
      '--allow-http-screen-capture'
    ]
  });
  const page = await browser.newPage();

  // Forward page console messages to Node.
  page.on('console', msg => {
    console.log('PAGE LOG:', msg.text());
  });

  // Navigate to your local page.
  await page.goto('file://' + __dirname + '/index.html');

  // Wait for the video container (and optionally video element) to load.
  await page.waitForSelector('#video-container');
  await page.waitForSelector('#video'); // ensure the video element exists

  // Inject recording code into the page.
  await page.evaluate(() => {
    // Debug: log that the recording script is running.
    console.log('Injected recording script running.');

    // Get references to the video and caption elements.
    const video = document.getElementById('video');
    const captions = document.getElementById('captions'); // Optional overlay element

    if (!video) {
      console.error('No video element found!');
      return;
    }

    // Ensure the video is playing.
    if (video.paused) {
      video.play().catch(err => console.error('Error playing video:', err));
    }

    // Create a canvas the same size as the video.
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || video.clientWidth;
    canvas.height = video.videoHeight || video.clientHeight;
    // Optionally add the canvas to the DOM so you can see it.
    canvas.style.position = 'fixed';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.zIndex = '1000';
    document.body.appendChild(canvas);

    const ctx = canvas.getContext('2d');

    // Capture the canvas stream at 30 fps.
    const stream = canvas.captureStream(30);
    let recordedChunks = [];
    const options = { mimeType: 'video/webm; codecs=vp9' };
    const mediaRecorder = new MediaRecorder(stream, options);

    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        recordedChunks.push(event.data);
        console.log('Data available:', event.data.size, 'bytes');
      }
    };

    mediaRecorder.onstop = () => {
      console.log('Recording stopped, preparing download...');
      const blob = new Blob(recordedChunks, { type: 'video/webm' });
      const url = URL.createObjectURL(blob);
      // Create a temporary download link and trigger the download.
      const a = document.createElement('a');
      a.style.display = 'none';
      a.href = url;
      a.download = 'recording.webm';
      document.body.appendChild(a);
      a.click();
      // Clean up.
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        console.log('Recording complete and downloaded.');
      }, 100);
    };

    // Start recording.
    mediaRecorder.start();
    console.log('Recording started.');

    // Function to composite the video and overlay onto the canvas.
    function draw() {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      if (captions) {
        ctx.font = '30px Arial';
        ctx.fillStyle = 'red';
        ctx.fillText(captions.innerText, 50, 50);
      }
      requestAnimationFrame(draw);
    }
    draw();

    // Stop recording after 10 seconds.
    setTimeout(() => {
      mediaRecorder.stop();
      console.log('MediaRecorder stop called after 10 seconds.');
    }, 10000);
  });

  // Optionally keep the browser open for a while after recording.
  // For example, wait 15 seconds before closing.
  await new Promise(resolve => setTimeout(resolve, 15000));
  await browser.close();
})();
