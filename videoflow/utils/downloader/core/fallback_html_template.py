# Fallback methods for HTML generation (used if Jinja2 templates fail to initialize)
def fallback_album_template(context):
    """Simple string-based template for album preview"""
    album_name = context['album_name']
    platform = context['platform']
    author = context['author']
    description = context.get('description', '')
    image_files = context['image_files']

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{album_name}</title>
<style>
    body {{
        font-family: Arial, sans-serif;
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
        background-color: #f5f5f5;
    }}
    h1 {{
        text-align: center;
        color: #333;
    }}
    .gallery {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        grid-gap: 15px;
        margin-top: 20px;
    }}
    .gallery img {{
        width: 100%;
        height: auto;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease;
    }}
    .gallery img:hover {{
        transform: scale(1.03);
    }}
    .info {{
        text-align: center;
        margin-bottom: 20px;
        color: #666;
    }}
    .desc {{
        margin-top: 15px;
        padding: 10px;
        background-color: #fff;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }}
</style>
</head>
<body>
<h1>{album_name}</h1>
<div class="info">
    <p>Platform: {platform}</p>
    <p>Author: {author}</p>
    <p>Album contains {len(image_files)} images</p>
</div>"""

    # Add description if available
    if description:
        html_content += f'\n    <div class="desc">{description}</div>'

    # Add gallery
    html_content += '\n    <div class="gallery">'

    # Add images to the gallery
    for image_file in image_files:
        html_content += f'\n        <img src="{image_file}" alt="{image_file}">'

    html_content += '\n    </div>\n</body>\n</html>'

    return html_content

def fallback_mixed_template(context):
    """Simple string-based template for mixed content index"""
    content_name = context['content_name']
    platform = context['platform']
    author = context['author']
    description = context.get('description', '')
    videos = context.get('videos', [])
    images = context.get('images', [])
    audio = context.get('audio', [])
    music = context.get('music', [])

    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{content_name}</title>
<style>
    body {{
        font-family: Arial, sans-serif;
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
        background-color: #f5f5f5;
    }}
    h1, h2 {{
        color: #333;
    }}
    h1 {{
        text-align: center;
    }}
    .info {{
        text-align: center;
        margin-bottom: 20px;
        color: #666;
    }}
    .section {{
        margin-top: 30px;
        padding: 15px;
        background-color: #fff;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }}
    .gallery {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
        grid-gap: 15px;
        margin-top: 20px;
    }}
    .gallery img {{
        width: 100%;
        height: auto;
        border-radius: 5px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
    }}
    .media-item {{
        margin: 10px 0;
        padding: 10px;
        background-color: #f9f9f9;
        border-radius: 5px;
    }}
    .desc {{
        margin-top: 15px;
        padding: 10px;
        background-color: #fff;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    }}
    video, audio {{
        width: 100%;
        margin-top: 10px;
    }}
    a {{
        color: #0066cc;
        text-decoration: none;
    }}
    a:hover {{
        text-decoration: underline;
    }}
</style>
</head>
<body>
<h1>{content_name}</h1>
<div class="info">
    <p>Platform: {platform}</p>
    <p>Author: {author}</p>
</div>"""

    # Add description if available
    if description:
        html_content += f'\n    <div class="desc">{description}</div>'

    # Add videos section
    if videos:
        html_content += f'\n    <div class="section">\n        <h2>Videos ({len(videos)})</h2>'
        for video_file in videos:
            html_content += f'''
    <div class="media-item">
        <p>{video_file}</p>
        <video controls>
            <source src="{video_file}" type="video/mp4">
            Your browser does not support the video tag.
        </video>
        <p><a href="{video_file}" download>Download Video</a></p>
    </div>'''
        html_content += '\n    </div>'

    # Add images section
    if images:
        html_content += f'\n    <div class="section">\n        <h2>Images ({len(images)})</h2>\n        <div class="gallery">'
        for image_file in images:
            html_content += f'\n            <a href="{image_file}" target="_blank"><img src="{image_file}" alt="{image_file}"></a>'
        html_content += '\n        </div>\n    </div>'

    # Add audio section
    if audio:
        html_content += f'\n    <div class="section">\n        <h2>Audio ({len(audio)})</h2>'
        for audio_file in audio:
            html_content += f'''
    <div class="media-item">
        <p>{audio_file}</p>
        <audio controls>
            <source src="{audio_file}" type="audio/mpeg">
            Your browser does not support the audio tag.
        </audio>
        <p><a href="{audio_file}" download>Download Audio</a></p>
    </div>'''
        html_content += '\n    </div>'

    # Add music section
    if music:
        html_content += f'\n    <div class="section">\n        <h2>Music ({len(music)})</h2>'
        for music_file in music:
            html_content += f'''
    <div class="media-item">
        <p>{music_file}</p>
        <audio controls>
            <source src="{music_file}" type="audio/mpeg">
            Your browser does not support the audio tag.
        </audio>
        <p><a href="{music_file}" download>Download Music</a></p>
    </div>'''
        html_content += '\n    </div>'

    html_content += '\n</body>\n</html>'

    return html_content