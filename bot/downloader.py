import asyncio
import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import yt_dlp


class VideoInfo:
    def __init__(self, title: str, webpage_url: str, thumbnail_url: Optional[str], format_rows: List[Tuple[str, str]]):
        self.title = title
        self.webpage_url = webpage_url
        self.thumbnail_url = thumbnail_url
        # List of (selector, label) pairs for display as buttons
        self.format_rows = format_rows


def _best_thumbnail(info: Dict[str, Any]) -> Optional[str]:
    if not info:
        return None
    # Try single 'thumbnail' field first
    url = info.get("thumbnail")
    if url:
        return url
    # Else pick the largest by height or preference
    thumbs = info.get("thumbnails") or []
    best = None
    best_score = -1
    for t in thumbs:
        height = t.get("height") or 0
        pref = t.get("preference") or 0
        score = (height * 10) + pref
        if score > best_score and t.get("url"):
            best = t["url"]
            best_score = score
    return best


def _collect_heights(info: Dict[str, Any]) -> List[int]:
    heights: set[int] = set()
    for f in info.get("formats", []):
        if f.get("vcodec") and f.get("vcodec") != "none":
            height = f.get("height")
            if isinstance(height, int):
                heights.add(height)
    return sorted(heights, reverse=True)


def _build_format_rows(info: Dict[str, Any], limit: int = 10) -> List[Tuple[str, str]]:
    heights = _collect_heights(info)
    rows: List[Tuple[str, str]] = []

    # Build selectors that prefer separate streams with merge, fallback to single best at that height
    for h in heights[:limit]:
        selector = f"bv*[height={h}]+ba/b[height={h}]"
        label = f"{h}p"
        rows.append((selector, label))

    # Always include a generic best as a fallback
    if "best" not in [s for s, _ in rows]:
        rows.append(("bv*+ba/best", "Лучшее доступное"))

    return rows


def _base_ydl_opts(temp_dir: str) -> Dict[str, Any]:
    return {
        "noprogress": True,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
        "merge_output_format": "mp4",
        # Let yt-dlp use ffmpeg if needed
        "postprocessors": [],
    }


def extract_video_info_sync(url: str) -> VideoInfo:
    opts = _base_ydl_opts(tempfile.gettempdir())
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if info.get("_type") == "playlist":
            # Take first entry if a playlist URL is provided
            entries = info.get("entries") or []
            if not entries:
                raise RuntimeError("Плейлист пустой или не поддерживается")
            info = entries[0]
        title = info.get("title") or "Видео"
        thumb = _best_thumbnail(info)
        format_rows = _build_format_rows(info)
        return VideoInfo(title=title, webpage_url=info.get("webpage_url") or url, thumbnail_url=thumb, format_rows=format_rows)


async def extract_video_info(url: str) -> VideoInfo:
    return await asyncio.to_thread(extract_video_info_sync, url)


def download_video_sync(url: str, format_selector: str) -> Tuple[str, str, str]:
    """
    Download the video with the given selector. Returns (filepath, filename, ext).
    """
    temp_dir = tempfile.mkdtemp(prefix="vd_")
    opts = _base_ydl_opts(temp_dir)
    opts.update({
        "format": format_selector,
    })
    with yt_dlp.YoutubeDL(opts) as ydl:
        result = ydl.extract_info(url, download=True)
        if result.get("_type") == "playlist":
            entries = result.get("entries") or []
            if not entries:
                raise RuntimeError("Не удалось скачать видео")
            result = entries[0]
        filepath = ydl.prepare_filename(result)
        # Sometimes yt-dlp returns ext after merge
        ext = result.get("ext") or os.path.splitext(filepath)[1].lstrip(".")
        filename = os.path.basename(filepath)
        return filepath, filename, ext


async def download_video(url: str, format_selector: str) -> Tuple[str, str, str]:
    return await asyncio.to_thread(download_video_sync, url, format_selector)