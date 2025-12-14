document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.webcam-capture-container').forEach(container => {
        const video = container.querySelector('video');
        const captureButton = container.querySelector('button.capture');
        const canvas = container.querySelector('canvas');
        const imageInput = container.querySelector('input[type="file"]');
        const deviceSelect = container.querySelector('select');
        const retakeButton = container.querySelector('button.retake');

        let stream;
        const existingValue = imageInput.dataset.url;

        const startVideo = (deviceId) => {
            const constraints = {
                video: deviceId ? { deviceId: { exact: deviceId } } : true
            };

            navigator.mediaDevices.getUserMedia(constraints)
                .then(newStream => {
                    stream = newStream;
                    video.srcObject = stream;
                    video.style.display = 'block';
                    canvas.style.display = 'none';
                    captureButton.style.display = 'inline-block';
                    retakeButton.style.display = 'none';
                })
                .catch(err => {
                    console.error('Error accessing webcam:', err);
                    alert('Unable to access webcam. Please ensure it is connected and permissions are granted.');
                });
        };

        const stopVideo = () => {
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
            }
        };

        // Populate device selection dropdown
        navigator.mediaDevices.enumerateDevices().then(devices => {
            const videoDevices = devices.filter(device => device.kind === 'videoinput');
            videoDevices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.deviceId;
                option.text = device.label || `Camera ${deviceSelect.options.length + 1}`;
                deviceSelect.appendChild(option);
            });
            if (videoDevices.length > 0 && !existingValue) {
                startVideo(videoDevices[0].deviceId);
            }
            if (videoDevices.length === 0) {
                alert('No webcam detected. Please connect a webcam or upload an image manually.');
                captureButton.disabled = true;
            }
        }).catch(err => {
            console.error('Error enumerating devices:', err);
            alert('Error detecting cameras. Please check your device settings.');
        });

        // Device selection change
        deviceSelect.addEventListener('change', (event) => {
            stopVideo();
            startVideo(event.target.value);
        });

        // Capture photo
        captureButton.addEventListener('click', () => {
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            stopVideo();
            video.style.display = 'none';
            canvas.style.display = 'block';
            captureButton.style.display = 'none';
            retakeButton.style.display = 'inline-block';

            canvas.toBlob(blob => {
                if (blob.size > 5 * 1024 * 1024) { // 5MB limit
                    alert('Captured image is too large. Please try again.');
                    startVideo(deviceSelect.value);
                    return;
                }
                const file = new File([blob], `webcam-photo-${Date.now()}.jpg`, { type: 'image/jpeg' });
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(file);
                imageInput.files = dataTransfer.files;
                imageInput.dispatchEvent(new Event('change', { bubbles: true }));
            }, 'image/jpeg', 0.9);
        });

        // Retake photo
        retakeButton.addEventListener('click', () => {
            startVideo(deviceSelect.value);
        });

        // Display existing image
        if (existingValue) {
            const img = new Image();
            img.onload = () => {
                canvas.width = img.width;
                canvas.height = img.height;
                canvas.getContext('2d').drawImage(img, 0, 0);
                video.style.display = 'none';
                canvas.style.display = 'block';
                captureButton.style.display = 'none';
                retakeButton.style.display = 'inline-block';
            };
            img.onerror = () => {
                console.error('Error loading existing image:', existingValue);
                alert('Failed to load existing image.');
            };
            img.src = existingValue;
        }
    });
});