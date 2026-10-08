from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets"
PORT = 8501
BASE_URL = f"http://127.0.0.1:{PORT}"


def wait_for_server(timeout: int = 40) -> None:
    started = time.time()
    while time.time() - started < timeout:
        with socket.socket() as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", PORT)) == 0:
                return
        time.sleep(0.5)
    raise TimeoutError("Streamlit server가 시작되지 않았습니다.")


def chromium_path() -> str | None:
    configured = os.getenv("PLAYWRIGHT_CHROMIUM", "").strip()
    if configured and Path(configured).exists():
        return configured

    for path in ["/usr/bin/chromium", "/usr/bin/google-chrome", "/usr/bin/chromium-browser"]:
        if Path(path).exists():
            return path
    return None


def make_gif(paths: list[Path], output: Path) -> None:
    frames = []
    for path in paths:
        image = Image.open(path).convert("RGB")
        image.thumbnail((1440, 900))
        canvas = Image.new("RGB", (1440, 900), "white")
        x = (canvas.width - image.width) // 2
        y = (canvas.height - image.height) // 2
        canvas.paste(image, (x, y))
        frames.append(canvas)

    frames[0].save(
        output,
        save_all=True,
        append_images=frames[1:],
        duration=1700,
        loop=0,
        optimize=True,
    )


def main() -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.headless=true",
            f"--server.port={PORT}",
            "--browser.gatherUsageStats=false",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )

    try:
        wait_for_server()
        with sync_playwright() as playwright:
            launch_args = {"headless": True, "args": ["--no-sandbox"]}
            executable = chromium_path()
            if executable:
                launch_args["executable_path"] = executable

            browser = playwright.chromium.launch(**launch_args)
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                record_video_dir=str(ASSET_DIR / "_video"),
                record_video_size={"width": 1440, "height": 900},
            )
            page = context.new_page()
            page.goto(BASE_URL, wait_until="networkidle")
            page.screenshot(path=str(ASSET_DIR / "dashboard.png"))

            page.get_by_text("Analysis", exact=True).click()
            page.locator('input[aria-label="질문"]').fill("샘플전자 최근 3년 재무상태 분석해줘")
            page.get_by_role("button", name="분석").click()
            page.get_by_text("분석 결과", exact=True).wait_for(timeout=10000)
            page.screenshot(path=str(ASSET_DIR / "analysis.png"))

            page.get_by_text("Evaluation", exact=True).click()
            page.wait_for_timeout(700)
            page.screenshot(path=str(ASSET_DIR / "evaluation.png"))

            page.get_by_text("DART Cohort", exact=True).click()
            page.wait_for_timeout(700)
            page.screenshot(path=str(ASSET_DIR / "cohort.png"))

            video = page.video
            context.close()
            video.save_as(str(ASSET_DIR / "demo.webm"))
            browser.close()

        make_gif(
            [
                ASSET_DIR / "dashboard.png",
                ASSET_DIR / "analysis.png",
                ASSET_DIR / "evaluation.png",
                ASSET_DIR / "cohort.png",
            ],
            ASSET_DIR / "demo.gif",
        )
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

        video_dir = ASSET_DIR / "_video"
        if video_dir.exists():
            for item in video_dir.iterdir():
                item.unlink()
            video_dir.rmdir()


if __name__ == "__main__":
    main()
