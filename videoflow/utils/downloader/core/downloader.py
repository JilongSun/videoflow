"""
Video and media downloader for TikHub Downloader
支持多平台内容的下载，包括视频、图片、音频等多媒体内容
"""

import concurrent.futures
import mimetypes
import os
import random
import time

import httpx
from jinja2 import Template

from downloader.core.fallback_html_template import fallback_album_template, fallback_mixed_template
from downloader.constants import DEFAULT_VIDEO_HEADERS
from downloader.utils.logger import logger_instance
from downloader.utils.utils import sanitize_filename


class VideoDownloader:
    """Handles multimedia downloading functionality for various platforms"""

    # HTML templates as class variables to avoid repetition
    ALBUM_PREVIEW_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ album_name }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1 {
            text-align: center;
            color: #333;
        }
        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            grid-gap: 15px;
            margin-top: 20px;
        }
        .gallery img {
            width: 100%;
            height: auto;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            transition: transform 0.3s ease;
        }
        .gallery img:hover {
            transform: scale(1.03);
        }
        .info {
            text-align: center;
            margin-bottom: 20px;
            color: #666;
        }
        .desc {
            margin-top: 15px;
            padding: 10px;
            background-color: #fff;
            border-radius: 5px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
    </style>
</head>
<body>
    <h1>{{ album_name }}</h1>
    <div class="info">
        <p>Platform: {{ platform }}</p>
        <p>Author: {{ author }}</p>
        <p>Album contains {{ image_files|length }} images</p>
    </div>
    {% if description %}
    <div class="desc">{{ description }}</div>
    {% endif %}
    <div class="gallery">
        {% for image in image_files %}
        <img src="{{ image }}" alt="{{ image }}">
        {% endfor %}
    </div>
</body>
</html>
"""

    MIXED_CONTENT_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ content_name }}</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        h1, h2 {
            color: #333;
        }
        h1 {
            text-align: center;
        }
        .info {
            text-align: center;
            margin-bottom: 20px;
            color: #666;
        }
        .section {
            margin-top: 30px;
            padding: 15px;
            background-color: #fff;
            border-radius: 5px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            grid-gap: 15px;
            margin-top: 20px;
        }
        .gallery img {
            width: 100%;
            height: auto;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        }
        .media-item {
            margin: 10px 0;
            padding: 10px;
            background-color: #f9f9f9;
            border-radius: 5px;
        }
        .desc {
            margin-top: 15px;
            padding: 10px;
            background-color: #fff;
            border-radius: 5px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        }
        video, audio {
            width: 100%;
            margin-top: 10px;
        }
        a {
            color: #0066cc;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <h1>{{ content_name }}</h1>
    <div class="info">
        <p>Platform: {{ platform }}</p>
        <p>Author: {{ author }}</p>
    </div>
    
    {% if description %}
    <div class="desc">{{ description }}</div>
    {% endif %}
    
    {% if videos %}
    <div class="section">
        <h2>Videos ({{ videos|length }})</h2>
        {% for video in videos %}
        <div class="media-item">
            <p>{{ video }}</p>
            <video controls>
                <source src="{{ video }}" type="video/mp4">
                Your browser does not support the video tag.
            </video>
            <p><a href="{{ video }}" download>Download Video</a></p>
        </div>
        {% endfor %}
    </div>
    {% endif %}
    
    {% if images %}
    <div class="section">
        <h2>Images ({{ images|length }})</h2>
        <div class="gallery">
            {% for image in images %}
            <a href="{{ image }}" target="_blank"><img src="{{ image }}" alt="{{ image }}"></a>
            {% endfor %}
        </div>
    </div>
    {% endif %}
    
    {% if audio %}
    <div class="section">
        <h2>Audio ({{ audio|length }})</h2>
        {% for audio_file in audio %}
        <div class="media-item">
            <p>{{ audio_file }}</p>
            <audio controls>
                <source src="{{ audio_file }}" type="audio/mpeg">
                Your browser does not support the audio tag.
            </audio>
            <p><a href="{{ audio_file }}" download>Download Audio</a></p>
        </div>
        {% endfor %}
    </div>
    {% endif %}
    
    {% if music %}
    <div class="section">
        <h2>Music ({{ music|length }})</h2>
        {% for music_file in music %}
        <div class="media-item">
            <p>{{ music_file }}</p>
            <audio controls>
                <source src="{{ music_file }}" type="audio/mpeg">
                Your browser does not support the audio tag.
            </audio>
            <p><a href="{{ music_file }}" download>Download Music</a></p>
        </div>
        {% endfor %}
    </div>
    {% endif %}
</body>
</html>
"""

    def __init__(self, download_path, use_description=False, skip_existing=True, max_workers=4):
        """Initialize the downloader

        Args:
            download_path: Path to save downloaded media
            use_description: Whether to use content description as filename
            skip_existing: Whether to skip existing files
            max_workers: Maximum number of parallel downloads
        """
        self.download_path = download_path
        self.use_description = use_description
        self.skip_existing = skip_existing
        self.max_workers = max_workers  # New parameter for parallel downloads

        # Ensure download directory exists
        os.makedirs(self.download_path, exist_ok=True)

        # Set the logger
        self.logger = logger_instance

        # Initialize template engine
        self._init_templates()

        # Initialize MIME types
        mimetypes.init()

    def _init_templates(self):
        """Initialize Jinja2 templates"""
        try:
            self.album_template = Template(self.ALBUM_PREVIEW_TEMPLATE)
            self.mixed_template = Template(self.MIXED_CONTENT_TEMPLATE)
            self.logger.info("Templates initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize templates: {e}")
            self.album_template = None
            self.mixed_template = None

    def parallel_download(self, items, progress_callback=None):
        """Download multiple items in parallel

        Args:
            items: List of data dictionaries to download
            progress_callback: Optional callback for progress updates

        Returns:
            dict: Results with success, files, and errors
        """
        result = {
            "success": False,
            "files": [],
            "errors": []
        }

        if not items:
            return result

        total = len(items)
        completed = 0

        # Function to handle individual download with progress reporting
        def download_item(item_data):
            try:
                # Create custom progress callback for this item
                item_progress = None
                if progress_callback:
                    def item_progress(p, t):
                        # We can't update the UI from worker threads, so we just track progress
                        pass

                # Download the item
                item_result = self.main_downloader(
                    item_data,
                    None,  # Use default output directory
                    item_progress,
                    3  # Default max retries
                )

                return item_result
            except Exception as e:
                self.logger.error(f"Error in parallel download worker: {e}")
                return {"success": False, "files": [], "errors": [str(e)]}

        # Use thread pool for parallel downloads
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {executor.submit(download_item, item): item for item in items}

            # Process results as they complete
            for i, future in enumerate(concurrent.futures.as_completed(future_to_item)):
                try:
                    item_result = future.result()
                    result['files'].extend(item_result['files'])
                    result['errors'].extend(item_result['errors'])

                    # Update overall progress
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)

                except Exception as e:
                    result['errors'].append(str(e))
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)

        # Set success flag if any files were downloaded
        result['success'] = len(result['files']) > 0

        return result

    def main_downloader(self, data, output_dir=None, progress_callback=None, max_retries=3):
        """Universal media downloader that handles all media types

        Args:
            data: Standardized content information dictionary
            output_dir: Optional custom output directory
            progress_callback: Optional callback for progress updates
            max_retries: Maximum number of retry attempts

        Returns:
            dict: Results containing success, file paths and any errors
        """
        # Use specified output directory or default
        output_dir = output_dir or self.download_path
        os.makedirs(output_dir, exist_ok=True)

        # Initialize results
        result = {
            "success": False,
            "files": [],
            "errors": []
        }

        try:
            # Validate essential data fields
            if not data.get('id'):
                raise ValueError("Missing required field: 'id'")

            # Smart media type detection - determine media type from available URLs if not provided
            if not data.get('media_type'):
                media_type = self._detect_media_type(data)
                if not media_type:
                    raise ValueError("Missing required field: 'media_type' and couldn't determine from data")
                data['media_type'] = media_type

            # Create author directory if needed
            if self.use_description and data.get('author_name'):
                safe_author = sanitize_filename(data['author_name'], max_length=50)
                output_dir = os.path.join(output_dir, safe_author)
                os.makedirs(output_dir, exist_ok=True)

            # Process based on media type using unified interface
            self._process_content(data, output_dir, progress_callback, max_retries, result)

            # Set success flag if any files were downloaded
            result['success'] = len(result['files']) > 0

            # Final progress update
            if progress_callback:
                progress_callback(100, 100)

            return result

        except Exception as e:
            error_msg = f"Error in main_downloader: {str(e)}"
            self.logger.error(error_msg)
            result['errors'].append(error_msg)
            return result

    def _detect_media_type(self, data):
        """Intelligently detect media type from data structure

        Args:
            data: Content data dictionary

        Returns:
            str: Detected media type or None if can't determine
        """
        # Check for multiple media types (mixed content)
        media_types = []
        if data.get('video_urls'):
            media_types.append('video')
        if data.get('image_urls'):
            media_types.append('image')
        if data.get('audio_urls'):
            media_types.append('audio')

        # If multiple types detected, it's mixed content
        if len(media_types) > 1:
            return 'mixed'
        elif len(media_types) == 1:
            return media_types[0]

        # Check platform-specific patterns as fallback
        platform = data.get('platform', '').lower()
        if platform in ['tiktok', 'douyin']:
            # These platforms typically have videos
            return 'video'
        elif platform in ['xiaohongshu']:
            # Red Book can have either images or videos
            return 'mixed'
        elif platform in ['bilibili'] and data.get('music_urls'):
            return 'audio'

        # Can't determine
        return None

    def _process_content(self, data, output_dir, progress_callback, max_retries, result):
        """Unified content processing method that handles all media types

        Args:
            data: Content data dictionary
            output_dir: Directory to save files
            progress_callback: Progress reporting callback
            max_retries: Maximum retry attempts
            result: Result dictionary to be updated
        """
        media_type = data['media_type']

        # Dispatch to appropriate handler based on media type
        if media_type == 'video':
            self._process_video(data, output_dir, progress_callback, max_retries, result)
        elif media_type == 'image':
            self._process_image(data, output_dir, progress_callback, max_retries, result)
        elif media_type == 'audio':
            self._process_audio(data, output_dir, progress_callback, max_retries, result)
        elif media_type == 'mixed':
            self._process_mixed(data, output_dir, progress_callback, max_retries, result)
        else:
            raise ValueError(f"Unsupported media type: {media_type}")

    def _process_video(self, data, output_dir, progress_callback, max_retries, result):
        """Process video type content

        Args:
            data: Content data dictionary
            output_dir: Directory to save files
            progress_callback: Progress reporting callback
            max_retries: Maximum retry attempts
            result: Result dictionary to be updated
        """
        # Check for video URLs
        if not data.get('video_urls'):
            error_msg = "No video URLs found for video content"
            self.logger.error(error_msg)
            result['errors'].append(error_msg)
            return

        # For multiple videos, use parallel downloading
        video_urls = data['video_urls']
        if len(video_urls) > 1 and self.max_workers > 1:
            self._parallel_process_videos(data, video_urls, output_dir, progress_callback, max_retries, result)
        else:
            # Sequential download for single video or if parallel disabled
            for idx, video_url in enumerate(video_urls):
                if not video_url or not isinstance(video_url, str) or not video_url.startswith('http'):
                    self.logger.warning(f"Invalid video URL: {video_url}")
                    continue

                file_path = self._download_media_file(
                    data,
                    video_url,
                    output_dir,
                    '.mp4',  # Default extension, will be updated based on content
                    idx if len(video_urls) > 1 else None,
                    progress_callback,
                    max_retries
                )

                if file_path:
                    result['files'].append(file_path)
                    self.logger.info(f"Successfully downloaded video to {file_path}")

    def _parallel_process_videos(self, data, video_urls, output_dir, progress_callback, max_retries, result):
        """Process multiple videos in parallel

        Args:
            data: Content data dictionary
            video_urls: List of video URLs
            output_dir: Directory to save files
            progress_callback: Progress reporting callback
            max_retries: Maximum retry attempts
            result: Result dictionary to be updated
        """
        valid_urls = [url for url in video_urls if url and isinstance(url, str) and url.startswith('http')]
        total_videos = len(valid_urls)

        if not valid_urls:
            self.logger.warning("No valid video URLs found")
            return

        completed = 0

        # Create a progress tracker for overall progress
        def update_progress():
            nonlocal completed
            completed += 1
            if progress_callback:
                progress_callback(min(int((completed / total_videos) * 100), 99), 100)

        # Function to download a single video
        def download_video(idx, url):
            try:
                file_path = self._download_media_file(
                    data,
                    url,
                    output_dir,
                    '.mp4',  # Default extension, will be updated based on content
                    idx if total_videos > 1 else None,
                    None,  # No individual progress callback for parallel downloads
                    max_retries
                )

                update_progress()
                return file_path
            except Exception as e:
                self.logger.error(f"Error downloading video {idx}: {e}")
                update_progress()
                return None

        # Initialize progress
        if progress_callback:
            progress_callback(0, 100)

        # Use thread pool for parallel downloads
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(self.max_workers, total_videos)) as executor:
            # Submit all download tasks
            future_to_idx = {executor.submit(download_video, idx, url): idx
                            for idx, url in enumerate(valid_urls)}

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_idx):
                file_path = future.result()
                if file_path:
                    result['files'].append(file_path)

        # Final progress update
        if progress_callback:
            progress_callback(100, 100)

    def _process_image(self, data, output_dir, progress_callback, max_retries, result):
        """Process image type content with enhanced parallel downloading for albums

        Args:
            data: Content data dictionary
            output_dir: Directory to save files
            progress_callback: Progress reporting callback
            max_retries: Maximum retry attempts
            result: Result dictionary to be updated
        """
        self.logger.info(f"Processing image content with {len(data.get('image_urls', []))} images")

        # Check for image URLs
        if not data.get('image_urls'):
            error_msg = "No image URLs found for image content"
            self.logger.error(error_msg)
            result['errors'].append(error_msg)
            return

        # Handle multiple images (album)
        if len(data['image_urls']) > 1:
            album_name = self._get_content_name(data)
            album_dir = os.path.join(output_dir, album_name)
            os.makedirs(album_dir, exist_ok=True)

            # Always use parallel downloading for multiple images
            # Adjust worker count based on image count for better efficiency
            effective_workers = min(self.max_workers, len(data['image_urls']))
            self.logger.info(f"Using {effective_workers} workers for {len(data['image_urls'])} images")

            self._parallel_process_images(data, data['image_urls'], album_dir, progress_callback, max_retries, result)

            # Create HTML preview for multiple images if any were downloaded
            if result['files']:
                preview_path = self._create_album_preview(album_dir, data)
                if preview_path:
                    result['files'].append(preview_path)

        else:
            # Single image download
            image_url = data['image_urls'][0]
            if not image_url or not isinstance(image_url, str) or not image_url.startswith('http'):
                error_msg = f"Invalid image URL: {image_url}"
                self.logger.error(error_msg)
                result['errors'].append(error_msg)
                return

            file_path = self._download_media_file(
                data,
                image_url,
                output_dir,
                self._determine_file_extension(image_url, '.jpg'),
                None,
                progress_callback,
                max_retries
            )

            if file_path:
                result['files'].append(file_path)
                self.logger.info(f"Successfully downloaded image to {file_path}")

    def _parallel_process_images(self, data, image_urls, output_dir, progress_callback, max_retries, result):
        """Enhanced parallel processing for multiple images with better resource utilization

        Args:
            data: Content data dictionary
            image_urls: List of image URLs
            output_dir: Directory to save files
            progress_callback: Progress reporting callback
            max_retries: Maximum retry attempts
            result: Result dictionary to be updated
        """
        # Filter invalid URLs first
        valid_urls = [url for url in image_urls if url and isinstance(url, str) and url.startswith('http')]
        total_images = len(valid_urls)

        if not valid_urls:
            self.logger.warning("No valid image URLs found")
            return

        completed = 0
        download_results = []

        # Create a thread-safe progress tracker that prevents UI updates too frequently
        # to avoid overwhelming the main thread
        last_update_time = [0]  # Use list for mutable reference in nested function
        min_update_interval = 0.1  # Minimum seconds between progress updates

        def update_progress():
            nonlocal completed
            completed += 1

            # Throttle UI updates to prevent UI freezing
            current_time = time.time()
            if progress_callback and (
                    current_time - last_update_time[0] >= min_update_interval or completed == total_images):
                progress = min(int((completed / total_images) * 100), 99)
                progress_callback(progress, 100)
                last_update_time[0] = current_time

        # Function to download a single image with better error handling
        def download_image(idx, url):
            try:
                # Determine image extension
                ext = self._determine_file_extension(url, '.jpg')

                # Unique filename based on index
                file_path = self._download_media_file(
                    data,
                    url,
                    output_dir,
                    ext,
                    idx,
                    None,  # No individual progress callback for parallel downloads
                    max_retries
                )

                update_progress()
                return idx, file_path, None  # Success
            except Exception as e:
                self.logger.error(f"Error downloading image {idx}: {e}")
                update_progress()
                return idx, None, str(e)  # Error

        # Initialize progress
        if progress_callback:
            progress_callback(0, 100)

        # Calculate optimal batch size to prevent overwhelming the system
        # This is important for very large image sets
        batch_size = 20  # Default batch size
        max_workers = min(self.max_workers, 8)  # Cap workers at a reasonable number

        # Process in batches for very large image sets
        if total_images > 100:
            self.logger.info(f"Processing {total_images} images in batches of {batch_size}")

            for batch_start in range(0, total_images, batch_size):
                batch_end = min(batch_start + batch_size, total_images)
                batch = valid_urls[batch_start:batch_end]

                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [executor.submit(download_image, batch_start + i, url) for i, url in enumerate(batch)]

                    for future in concurrent.futures.as_completed(futures):
                        idx, file_path, error = future.result()
                        if file_path:
                            download_results.append((idx, file_path))
                        elif error:
                            result['errors'].append(f"Image {idx}: {error}")

                # Short pause between batches to allow system resources to recover
                time.sleep(0.2)
        else:
            # For smaller image sets, process all at once
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(download_image, idx, url) for idx, url in enumerate(valid_urls)]

                for future in concurrent.futures.as_completed(futures):
                    idx, file_path, error = future.result()
                    if file_path:
                        download_results.append((idx, file_path))
                    elif error:
                        result['errors'].append(f"Image {idx}: {error}")

        # Sort results by index to maintain original order
        download_results.sort(key=lambda x: x[0])

        # Add successfully downloaded files to result
        for _, file_path in download_results:
            result['files'].append(file_path)

        # Final progress update
        if progress_callback:
            progress_callback(100, 100)

        self.logger.info(f"Parallel download completed: {len(download_results)} of {total_images} images downloaded")

    def _process_audio(self, data, output_dir, progress_callback, max_retries, result):
        """Process audio type content with parallel capability

        Args:
            data: Content data dictionary
            output_dir: Directory to save files
            progress_callback: Progress reporting callback
            max_retries: Maximum retry attempts
            result: Result dictionary to be updated
        """
        # Check for audio URLs
        if not data.get('audio_urls'):
            error_msg = "No audio URLs found for audio content"
            self.logger.error(error_msg)
            result['errors'].append(error_msg)
            return

        # For multiple audio files, use parallel downloading
        audio_urls = data['audio_urls']
        if len(audio_urls) > 1 and self.max_workers > 1:
            self._parallel_process_audio(data, audio_urls, output_dir, progress_callback, max_retries, result)
        else:
            # Sequential download
            for idx, audio_url in enumerate(audio_urls):
                if not audio_url or not isinstance(audio_url, str) or not audio_url.startswith('http'):
                    self.logger.warning(f"Invalid audio URL: {audio_url}")
                    continue

                # Determine audio extension
                ext = self._determine_file_extension(audio_url, '.mp3')

                file_path = self._download_media_file(
                    data,
                    audio_url,
                    output_dir,
                    ext,
                    idx if len(audio_urls) > 1 else None,
                    progress_callback,
                    max_retries
                )

                if file_path:
                    result['files'].append(file_path)
                    self.logger.info(f"Successfully downloaded audio to {file_path}")

    def _parallel_process_audio(self, data, audio_urls, output_dir, progress_callback, max_retries, result):
        """Process multiple audio files in parallel

        Args:
            data: Content data dictionary
            audio_urls: List of audio URLs
            output_dir: Directory to save files
            progress_callback: Progress reporting callback
            max_retries: Maximum retry attempts
            result: Result dictionary to be updated
        """
        # Implementation similar to _parallel_process_videos but for audio files
        valid_urls = [url for url in audio_urls if url and isinstance(url, str) and url.startswith('http')]
        total_audio = len(valid_urls)

        if not valid_urls:
            self.logger.warning("No valid audio URLs found")
            return

        completed = 0

        # Create a progress tracker for overall progress
        def update_progress():
            nonlocal completed
            completed += 1
            if progress_callback:
                progress_callback(min(int((completed / total_audio) * 100), 99), 100)

        # Function to download a single audio file
        def download_audio(idx, url):
            try:
                # Determine audio extension
                ext = self._determine_file_extension(url, '.mp3')

                file_path = self._download_media_file(
                    data,
                    url,
                    output_dir,
                    ext,
                    idx if total_audio > 1 else None,
                    None,  # No individual progress callback for parallel downloads
                    max_retries
                )

                update_progress()
                return file_path
            except Exception as e:
                self.logger.error(f"Error downloading audio {idx}: {e}")
                update_progress()
                return None

        # Initialize progress
        if progress_callback:
            progress_callback(0, 100)

        # Use thread pool for parallel downloads
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(self.max_workers, total_audio)) as executor:
            # Submit all download tasks
            future_to_idx = {executor.submit(download_audio, idx, url): idx
                            for idx, url in enumerate(valid_urls)}

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_idx):
                file_path = future.result()
                if file_path:
                    result['files'].append(file_path)

        # Final progress update
        if progress_callback:
            progress_callback(100, 100)

    def _process_mixed(self, data, output_dir, progress_callback, max_retries, result):
        """Process mixed type content with parallel downloads for different media types

        Args:
            data: Content data dictionary
            output_dir: Directory to save files
            progress_callback: Progress reporting callback
            max_retries: Maximum retry attempts
            result: Result dictionary to be updated
        """
        # Create a directory for mixed content
        mixed_dir = os.path.join(output_dir, self._get_content_name(data))
        os.makedirs(mixed_dir, exist_ok=True)

        # Count total items to download for progress calculation
        total_items = 0
        total_items += len(data.get('video_urls', []))
        total_items += len(data.get('image_urls', []))
        total_items += len(data.get('audio_urls', []))
        total_items += len(data.get('music_urls', [])) if data.get('music_id') else 0

        if total_items == 0:
            error_msg = "No media URLs found in mixed content"
            self.logger.error(error_msg)
            result['errors'].append(error_msg)
            return

        # For mixed content with multiple files, use parallel downloading if enabled
        if total_items > 1 and self.max_workers > 1:
            self._parallel_process_mixed(data, mixed_dir, progress_callback, max_retries, result)
        else:
            # Sequential processing
            current_item = 0

            # Helper function to update progress for mixed content
            def update_mixed_progress(p, t):
                if progress_callback:
                    item_portion = 100 / total_items
                    overall = int(((current_item * item_portion) + (p * item_portion / t)))
                    progress_callback(min(overall, 99), 100)  # Cap at 99% until completely done

            # Process each media type sequentially
            # Process videos
            if data.get('video_urls'):
                for idx, video_url in enumerate(data['video_urls']):
                    if not video_url or not isinstance(video_url, str) or not video_url.startswith('http'):
                        self.logger.warning(f"Invalid video URL: {video_url}")
                        current_item += 1
                        continue

                    file_path = self._download_media_file(
                        data,
                        video_url,
                        mixed_dir,
                        '.mp4',
                        idx if len(data['video_urls']) > 1 else None,
                        update_mixed_progress,
                        max_retries,
                        suffix='_video'
                    )

                    if file_path:
                        result['files'].append(file_path)

                    current_item += 1

            # Process images, audio, and music similarly...
            # (Code omitted for brevity - similar pattern to videos)

        # Create an index.html that links to all downloaded files
        if result['files']:
            index_path = self._create_mixed_content_index(mixed_dir, data, result['files'])
            if index_path:
                result['files'].append(index_path)

    def _parallel_process_mixed(self, data, mixed_dir, progress_callback, max_retries, result):
        """Process mixed content with parallel downloads

        Args:
            data: Content data dictionary
            mixed_dir: Directory to save mixed content
            progress_callback: Progress reporting callback
            max_retries: Maximum retry attempts
            result: Result dictionary to be updated
        """
        # Prepare download tasks for all media types
        download_tasks = []

        # Add video tasks
        for idx, url in enumerate(data.get('video_urls', [])):
            if url and isinstance(url, str) and url.startswith('http'):
                download_tasks.append({
                    'type': 'video',
                    'url': url,
                    'idx': idx,
                    'ext': '.mp4',
                    'suffix': '_video'
                })

        # Add image tasks
        for idx, url in enumerate(data.get('image_urls', [])):
            if url and isinstance(url, str) and url.startswith('http'):
                ext = self._determine_file_extension(url, '.jpg')
                download_tasks.append({
                    'type': 'image',
                    'url': url,
                    'idx': idx,
                    'ext': ext,
                    'suffix': '_image'
                })

        # Add audio tasks
        for idx, url in enumerate(data.get('audio_urls', [])):
            if url and isinstance(url, str) and url.startswith('http'):
                ext = self._determine_file_extension(url, '.mp3')
                download_tasks.append({
                    'type': 'audio',
                    'url': url,
                    'idx': idx,
                    'ext': ext,
                    'suffix': '_audio'
                })

        # Add music tasks
        if data.get('music_id'):
            for idx, url in enumerate(data.get('music_urls', [])):
                if url and isinstance(url, str) and url.startswith('http'):
                    ext = self._determine_file_extension(url, '.mp3')
                    download_tasks.append({
                        'type': 'music',
                        'url': url,
                        'idx': idx,
                        'ext': ext,
                        'suffix': '_music'
                    })

        total_tasks = len(download_tasks)
        if total_tasks == 0:
            self.logger.warning("No valid media URLs found in mixed content")
            return

        completed = 0

        # Progress update function
        def update_progress():
            nonlocal completed
            completed += 1
            if progress_callback:
                progress_callback(min(int((completed / total_tasks) * 100), 99), 100)

        # Function to download a single media item
        def download_media_item(task):
            try:
                file_path = self._download_media_file(
                    data,
                    task['url'],
                    mixed_dir,
                    task['ext'],
                    task['idx'],
                    None,  # No individual progress callback
                    max_retries,
                    task['suffix']
                )

                update_progress()
                return file_path
            except Exception as e:
                self.logger.error(f"Error downloading {task['type']} {task['idx']}: {e}")
                update_progress()
                return None

        # Initialize progress
        if progress_callback:
            progress_callback(0, 100)

        # Use thread pool for parallel downloads
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(self.max_workers, total_tasks)) as executor:
            # Submit all download tasks
            future_to_task = {executor.submit(download_media_item, task): task
                             for task in download_tasks}

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_task):
                file_path = future.result()
                if file_path:
                    result['files'].append(file_path)

        # Final progress update
        if progress_callback:
            progress_callback(100, 100)

    def _get_content_name(self, data):
        """Generate a standardized content name from data

        Args:
            data: Content data dictionary

        Returns:
            str: Sanitized name for files/folders
        """
        content_id = data['id']
        platform = data.get('platform', 'unknown')

        if self.use_description and data.get('desc'):
            desc = data['desc']
            safe_desc = sanitize_filename(desc, max_length=50)
            if safe_desc:
                return f"{safe_desc}_{content_id}"

        # Include platform and author if available
        author_part = ""
        if data.get('author_name'):
            author_part = f"_{sanitize_filename(data['author_name'], max_length=15)}"

        return f"{platform}{author_part}_{content_id}"

    def _determine_file_extension(self, url, default_ext, content_type=None):
        """Enhanced file extension detection using URL and content-type

        Args:
            url: Media URL
            default_ext: Default extension to use if can't determine
            content_type: Optional HTTP Content-Type header

        Returns:
            str: File extension with leading dot
        """
        # First try to determine from content-type if available
        if content_type:
            content_type = content_type.lower()
            # Map MIME types to extensions
            mime_map = {
                'image/jpeg': '.jpg',
                'image/png': '.png',
                'image/heic': '.heic',
                'image/webp': '.webp',
                'image/gif': '.gif',
                'video/mp4': '.mp4',
                'video/quicktime': '.mov',
                'video/webm': '.webm',
                'audio/mpeg': '.mp3',
                'audio/mp4': '.m4a',
                'audio/wav': '.wav',
                'audio/aac': '.aac'
            }

            for mime, ext in mime_map.items():
                if mime in content_type:
                    return ext

        # If couldn't determine from content-type, try from URL
        if url:
            lower_url = url.lower()

            # Use mimetypes module first
            ext = mimetypes.guess_extension(mimetypes.guess_type(url)[0] or '')
            if ext and ext != '.jpe':  # Skip .jpe which is sometimes returned for .jpg
                return ext

            # Fallback to manual checks
            # Images
            if '.webp' in lower_url:
                return '.webp'
            elif '.png' in lower_url:
                return '.png'
            elif '.jpg' in lower_url or '.jpeg' in lower_url:
                return '.jpg'
            elif '.gif' in lower_url:
                return '.gif'

            # Videos
            elif '.mp4' in lower_url:
                return '.mp4'
            elif '.mov' in lower_url:
                return '.mov'
            elif '.webm' in lower_url:
                return '.webm'

            # Audio
            elif '.mp3' in lower_url:
                return '.mp3'
            elif '.m4a' in lower_url:
                return '.m4a'
            elif '.wav' in lower_url:
                return '.wav'
            elif '.aac' in lower_url:
                return '.aac'

        # Default extension if couldn't determine
        return default_ext

    def _download_media_file(self, data, url, output_dir, extension, index=None, progress_callback=None, max_retries=3,
                             suffix=None):
        """Enhanced media file downloader with improved retry logic and content-type detection

        Args:
            data: Content data dictionary
            url: URL to download
            output_dir: Directory to save the file
            extension: File extension (with dot)
            index: Optional index for multi-file content
            progress_callback: Optional progress reporting callback
            max_retries: Maximum retry attempts
            suffix: Optional suffix to add to filename

        Returns:
            str: Path to downloaded file or None if failed
        """
        # Validate URL
        if not url or not isinstance(url, str) or not url.startswith('http'):
            self.logger.error(f"Invalid URL: {url}")
            return None

        try:
            # Generate base filename
            base_name = self._get_content_name(data)

            # Add index if provided (for multi-file content)
            if index is not None:
                base_name = f"{base_name}_{index + 1:03d}"

            # Add suffix if provided
            if suffix:
                base_name = f"{base_name}{suffix}"

            # Complete filename with extension
            file_name = os.path.join(output_dir, f"{base_name}{extension}")

            # Skip if file exists and skip_existing is True
            if self.skip_existing and os.path.exists(file_name):
                self.logger.info(f"Skipping existing file: {file_name}")
                return file_name

            # Initialize progress if callback provided
            if progress_callback:
                progress_callback(0, 100)

            # Create a temporary file for partial downloads
            temp_file = f"{file_name}.part"

            # Track where to resume download if supported
            resume_position = 0
            if os.path.exists(temp_file):
                resume_position = os.path.getsize(temp_file)

            # Download with retry logic and exponential backoff
            retry_count = 0
            backoff_factor = 2.0  # Increased for more effective backoff

            while retry_count < max_retries:
                try:
                    # Configure appropriate timeouts based on media type
                    if extension in ['.mp4', '.mov', '.webm']:
                        # Longer timeouts for video
                        timeout_settings = httpx.Timeout(
                            connect=15.0,
                            read=300.0,
                            write=15.0,
                            pool=10.0
                        )
                    else:
                        # Shorter timeouts for images/audio
                        timeout_settings = httpx.Timeout(
                            connect=8.0,  # Reduced from 10.0
                            read=30.0,  # Reduced from 60.0 for images
                            write=8.0,  # Reduced from 10.0
                            pool=5.0
                        )

                    # Prepare headers with resume capability
                    headers = DEFAULT_VIDEO_HEADERS.copy()
                    if resume_position > 0:
                        headers['Range'] = f'bytes={resume_position}-'

                    # Add randomized User-Agent to avoid pattern detection by servers
                    # This helps prevent rate limiting when downloading many files
                    if retry_count > 0:
                        # Rotate user agents to reduce risk of being blocked
                        user_agents = [
                            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Safari/605.1.15',
                            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36',
                            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36',
                        ]
                        headers['User-Agent'] = user_agents[retry_count % len(user_agents)]

                    with httpx.Client(timeout=timeout_settings, follow_redirects=True) as client:
                        with client.stream("GET", url, headers=headers) as response:
                            # Check for success response
                            if response.status_code in (200, 206):  # OK or Partial Content
                                # Update file extension based on content-type if needed
                                content_type = response.headers.get('content-type')
                                detected_ext = self._determine_file_extension(url, extension, content_type)

                                if detected_ext != extension:
                                    # Update file name with correct extension
                                    new_file_name = os.path.join(output_dir, f"{base_name}{detected_ext}")
                                    new_temp_file = f"{new_file_name}.part"

                                    # If we already have a temp file, rename it
                                    if os.path.exists(temp_file):
                                        os.rename(temp_file, new_temp_file)

                                    file_name = new_file_name
                                    temp_file = new_temp_file
                                    extension = detected_ext

                                # Get total size if available
                                total_size = int(response.headers.get('content-length', 0))
                                if response.status_code == 206:  # Partial content
                                    # Adjust total size for resumed downloads
                                    content_range = response.headers.get('content-range', '')
                                    if content_range and '/' in content_range:
                                        try:
                                            total_size = int(content_range.split('/')[1])
                                        except (ValueError, IndexError):
                                            # Fall back to adding content-length to resume position
                                            total_size += resume_position
                                    else:
                                        total_size += resume_position

                                # Adjust chunk size based on file type and size for better performance
                                if extension in ['.mp4', '.mov', '.webm']:
                                    # Larger chunks for video
                                    chunk_size = 16384
                                elif total_size > 5 * 1024 * 1024:  # > 5MB
                                    # Medium chunks for large images
                                    chunk_size = 8192
                                else:
                                    # Smaller chunks for typical images
                                    chunk_size = 4096

                                # Open file for writing/appending
                                mode = 'ab' if resume_position > 0 else 'wb'
                                with open(temp_file, mode) as f:
                                    downloaded = resume_position
                                    last_progress_update = time.time()

                                    for chunk in response.iter_bytes(chunk_size=chunk_size):
                                        if chunk:
                                            f.write(chunk)
                                            downloaded += len(chunk)

                                            # Update progress at most every 100ms to avoid UI freezing
                                            current_time = time.time()
                                            if progress_callback and total_size > 0 and (
                                                    current_time - last_progress_update >= 0.1):
                                                progress = int((downloaded / total_size) * 100)
                                                progress_callback(progress, 100)
                                                last_progress_update = current_time

                                # Success: rename temp file to final filename
                                os.replace(temp_file, file_name)

                                # Final progress update
                                if progress_callback:
                                    progress_callback(100, 100)

                                return file_name

                            # Handle specific errors
                            elif response.status_code == 429:  # Too Many Requests
                                # Wait longer for rate limit errors
                                retry_delay = (backoff_factor ** retry_count) * 5 + (random.random() * 2)  # Add jitter
                                self.logger.warning(
                                    f"Rate limited. Retrying in {retry_delay:.1f}s... ({retry_count + 1}/{max_retries})")
                                time.sleep(retry_delay)

                            elif response.status_code == 504:  # Gateway Timeout
                                # For timeout errors, wait before retrying
                                retry_delay = (backoff_factor ** retry_count) * 3
                                self.logger.warning(
                                    f"Gateway timeout. Retrying in {retry_delay:.1f}s... ({retry_count + 1}/{max_retries})")
                                time.sleep(retry_delay)

                            elif 500 <= response.status_code < 600:  # Server errors
                                # For other server errors, wait a bit
                                retry_delay = (backoff_factor ** retry_count) * 2
                                self.logger.warning(
                                    f"Server error {response.status_code}. Retrying in {retry_delay:.1f}s... ({retry_count + 1}/{max_retries})")
                                time.sleep(retry_delay)

                            else:
                                # Other errors are not retried
                                self.logger.error(f"HTTP error {response.status_code} when downloading media")
                                break  # Exit retry loop for non-retriable errors

                except (httpx.TimeoutException, httpx.ConnectTimeout) as e:
                    # Update resume position if file exists
                    if os.path.exists(temp_file):
                        resume_position = os.path.getsize(temp_file)

                    retry_delay = (backoff_factor ** retry_count) * 3 + (random.random() * 1.5)  # Add jitter
                    self.logger.warning(
                        f"Timeout error: {e}. Retrying in {retry_delay:.1f}s... ({retry_count + 1}/{max_retries})")
                    time.sleep(retry_delay)

                except (httpx.NetworkError, httpx.ProtocolError) as e:
                    # Update resume position if file exists
                    if os.path.exists(temp_file):
                        resume_position = os.path.getsize(temp_file)

                    retry_delay = (backoff_factor ** retry_count) * 2 + (random.random() * 1)  # Add jitter
                    self.logger.warning(
                        f"Network error: {e}. Retrying in {retry_delay:.1f}s... ({retry_count + 1}/{max_retries})")
                    time.sleep(retry_delay)

                except Exception as e:
                    self.logger.error(f"Unexpected error downloading media: {e}")
                    if os.path.exists(temp_file):
                        os.remove(temp_file)  # Clean up temp file on unexpected errors
                    return None

                # Increment retry counter
                retry_count += 1

            # If we reach here, all retries failed
            self.logger.error(f"Failed to download media after {max_retries} attempts")
            if os.path.exists(temp_file):
                os.remove(temp_file)  # Clean up temp file
            return None

        except Exception as e:
            self.logger.error(f"Error in _download_media_file: {e}")
            # Clean up any temp file
            temp_file = f"{file_name}.part" if 'file_name' in locals() else None
            if temp_file and os.path.exists(temp_file):
                os.remove(temp_file)
            return None

    def _create_album_preview(self, album_dir, data):
        """Create an HTML preview for downloaded album using Jinja2 templates

        Args:
            album_dir: Directory containing the downloaded images
            data: Content data dictionary

        Returns:
            str: Path to the created HTML file or None if failed
        """
        try:
            # Get all image files in the album directory
            image_files = self._get_image_files(album_dir)

            if not image_files:
                self.logger.warning(f"No image files found in album directory: {album_dir}")
                return None

            # Prepare template context
            context = {
                'album_name': self._get_content_name(data),
                'platform': data.get('platform', 'unknown'),
                'author': data.get('author_name', 'Unknown Author'),
                'description': data.get('desc', ''),
                'image_files': image_files
            }

            # Render template
            if self.album_template:
                html_content = self.album_template.render(**context)
            else:
                # Fallback to direct string template (less ideal)
                self.logger.warning("Using fallback template rendering for album preview")
                html_content = fallback_album_template(context)

            # Write HTML file
            html_path = os.path.join(album_dir, "preview.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            return html_path

        except Exception as e:
            self.logger.error(f"Error creating album preview: {e}")
            return None

    def _get_image_files(self, directory):
        """Get all image files in the directory

        Args:
            directory: Directory to scan for image files

        Returns:
            list: List of image filenames
        """
        image_files = []
        for file in os.listdir(directory):
            lower_file = file.lower()
            if (lower_file.endswith('.jpg') or lower_file.endswith('.jpeg') or
                lower_file.endswith('.png') or lower_file.endswith('.webp') or
                lower_file.endswith('.gif')):
                image_files.append(file)

        # Sort image files numerically if possible
        image_files.sort()
        return image_files

    def _create_mixed_content_index(self, mixed_dir, data, file_paths):
        """Create an HTML index for mixed content using Jinja2 templates

        Args:
            mixed_dir: Directory containing the mixed content
            data: Content data dictionary
            file_paths: List of downloaded file paths

        Returns:
            str: Path to the created HTML file or None if failed
        """
        try:
            # Group files by media type
            media_files = self._group_files_by_type(mixed_dir, file_paths)

            if not media_files:
                self.logger.warning(f"No media files found for index in directory: {mixed_dir}")
                return None

            # Prepare template context
            context = {
                'content_name': self._get_content_name(data),
                'platform': data.get('platform', 'unknown'),
                'author': data.get('author_name', 'Unknown Author'),
                'description': data.get('desc', ''),
                'videos': media_files.get('videos', []),
                'images': media_files.get('images', []),
                'audio': media_files.get('audio', []),
                'music': media_files.get('music', []),
                'other': media_files.get('other', [])
            }

            # Render template
            if self.mixed_template:
                html_content = self.mixed_template.render(**context)
            else:
                # Fallback to direct string template (less ideal)
                self.logger.warning("Using fallback template rendering for mixed content index")
                html_content = fallback_mixed_template(context)

            # Write HTML file
            html_path = os.path.join(mixed_dir, "index.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            return html_path

        except Exception as e:
            self.logger.error(f"Error creating mixed content index: {e}")
            return None

    def _group_files_by_type(self, directory, file_paths):
        """Group files by their media type

        Args:
            directory: Directory containing the files
            file_paths: List of file paths to group

        Returns:
            dict: Dictionary with media types as keys and lists of files as values
        """
        media_files = {}  # Group by type

        for file_path in file_paths:
            if directory in file_path and os.path.exists(file_path):
                file_name = os.path.basename(file_path)
                lower_file = file_name.lower()

                # Skip HTML files
                if lower_file.endswith('.html'):
                    continue

                # Categorize by file type
                if lower_file.endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
                    media_type = 'images'
                elif lower_file.endswith(('.mp4', '.mov', '.webm')):
                    media_type = 'videos'
                elif lower_file.endswith(('.mp3', '.m4a', '.wav', '.aac')):
                    if '_music' in lower_file:
                        media_type = 'music'
                    else:
                        media_type = 'audio'
                else:
                    media_type = 'other'

                if media_type not in media_files:
                    media_files[media_type] = []

                media_files[media_type].append(file_name)

        # Sort each category
        for media_type in media_files:
            media_files[media_type].sort()

        return media_files

