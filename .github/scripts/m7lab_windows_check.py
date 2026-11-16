"""Test the M7Lab .exe on a real Windows machine (GitHub Actions) and make screenshots.

Run by .github/workflows/m7lab-windows-build.yml after build_exe.bat. It:
  1. turns the real build_exe.bat output into Command Prompt-style images,
  2. runs dist/M7Lab_Launcher.exe by itself in an empty folder and drives it
     like a user (all three programs), checking each web page,
  3. screenshots the pages with Chromium on Windows,
  4. runs make_submission_zip.py,
  5. writes everything to docs/screenshots (05_*.png) and docs/windows_build/.

Usage: python m7lab_windows_check.py <project_dir> <build_log>
"""

import html
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT = Path(sys.argv[1]).resolve()
BUILD_LOG = Path(sys.argv[2])
EXE_NAME = "M7Lab_Launcher.exe" if os.name == "nt" else "M7Lab_Launcher"
SHOTS = PROJECT / "docs" / "screenshots"
LOGS = PROJECT / "docs" / "windows_build"
PROMPT = f"{PROJECT}>"
CAPTION = "Captured on GitHub Actions (windows-latest)"
results = []


# ------------------------------------------------------------------ rendering
def console_image(page, lines, out_name, title="Command Prompt"):
    """Render text as a Windows Command Prompt-style window and screenshot it."""
    body = []
    for line in lines:
        text = html.escape(line)
        if line.startswith(PROMPT) or re.match(r"^[A-Z]:\\.*>", line):
            text = f'<span class="cmd">{text}</span>'
        elif re.search(r"\b(FAILED|Traceback|ERROR)\b", line):
            text = f'<span class="bad">{text}</span>'
        elif re.search(r"(SUCCEEDED|Successfully|completed successfully|Build complete|^OK$|Goodbye)", line):
            text = f'<span class="good">{text}</span>'
        body.append(text)
    page.set_content(f"""<html><body style="margin:0;padding:14px;background:#fff;display:inline-block">
<div id="w" style="width:1000px;border:1px solid #2b2b2b;box-shadow:0 4px 16px rgba(0,0,0,.3);font-family:Consolas,'Cascadia Mono','DejaVu Sans Mono',monospace">
<div style="background:#ffffff;color:#000;font:13px 'Segoe UI',sans-serif;padding:7px 12px;display:flex;justify-content:space-between;border-bottom:1px solid #ddd">
<span>&#9645; {html.escape(title)}</span><span style="letter-spacing:14px">&#8212; &#9744; &#10005;</span></div>
<pre style="margin:0;background:#0c0c0c;color:#cccccc;padding:12px 14px;font-size:14px;line-height:1.35;white-space:pre-wrap;word-break:break-all">{chr(10).join(body)}</pre>
<div style="background:#1b1b1b;color:#8a8a8a;font:11px 'Segoe UI',sans-serif;padding:4px 12px">{CAPTION}</div></div>
<style>.cmd{{color:#ffffff}}.bad{{color:#ff6b6b}}.good{{color:#6ee36e}}</style></body></html>""")
    page.locator("#w").screenshot(path=str(SHOTS / out_name))
    print("saved", out_name)


def build_sections(log_text):
    """Split build_exe.bat output into its header and [1/5]..[5/5] sections."""
    sections, current = {0: []}, 0
    for line in log_text.splitlines():
        m = re.match(r"^\[(\d)/5\]", line)
        if m:
            current = int(m.group(1))
            sections[current] = []
        sections[current].append(line.rstrip())
    return sections


def trim(lines, head, tail):
    lines = [line for line in lines if line.strip()]
    if len(lines) <= head + tail:
        return lines
    return lines[:head] + [f"   ... ({len(lines) - head - tail} lines omitted) ..."] + lines[-tail:]


# ------------------------------------------------------------------ the exe
class ExeSession:
    """Run the .exe with piped input/output and wait for text like a user would."""

    def __init__(self, exe, cwd):
        self.proc = subprocess.Popen([str(exe)], cwd=cwd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, env={**os.environ, "BROWSER": "none"},
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.buf = bytearray()
        threading.Thread(target=self._read, daemon=True).start()
        self.typed = []

    def _read(self):
        while True:
            chunk = self.proc.stdout.read1(4096) if hasattr(self.proc.stdout, "read1") else self.proc.stdout.read(1)
            if not chunk:
                return
            self.buf.extend(chunk)

    def text(self):
        return self.buf.decode("utf-8", "replace").replace("\r\n", "\n")

    def wait_for(self, pattern, start=0, timeout=120):
        end = time.time() + timeout
        while time.time() < end:
            m = re.search(pattern, self.text()[start:])
            if m:
                return m
            time.sleep(0.1)
        raise RuntimeError(f"timed out waiting for {pattern!r}\n---\n{self.text()}")

    def send(self, text, shown=None):
        time.sleep(0.3)
        self.typed.append((len(self.text()), shown if shown is not None else text))
        self.proc.stdin.write((text + "\r\n").encode())
        self.proc.stdin.flush()

    def transcript(self):
        """Output with what was typed shown after each prompt, like a real console."""
        out, parts, last = self.text(), [], 0
        for pos, shown in self.typed:
            parts.append(out[last:pos])
            parts.append(shown + "\n")
            last = pos
        parts.append(out[last:])
        return "".join(parts)


def check(name, body, must):
    ok = must in body
    results.append((ok, name))
    print(("PASS " if ok else "FAIL ") + name)


def get(url):
    return urllib.request.urlopen(url, timeout=60).read().decode()


def post(url, **form):
    data = urllib.parse.urlencode(form).encode()
    return urllib.request.urlopen(urllib.request.Request(url + "act", data=data), timeout=120).read().decode()


def main():
    SHOTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    log_text = BUILD_LOG.read_text(encoding="utf-8", errors="replace")
    (LOGS / "build_exe_log.txt").write_text(log_text, encoding="utf-8")
    sections = build_sections(log_text)
    exe_src = PROJECT / "dist" / EXE_NAME

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=os.environ.get("PW_CHROMIUM_PATH") or None)
        con = browser.new_page(device_scale_factor=2, viewport={"width": 1040, "height": 300})

        # ---- build steps (real build_exe.bat output)
        ver = subprocess.run("ver", shell=True, capture_output=True, text=True).stdout.strip() if os.name == "nt" \
            else platform.platform()
        console_image(con, [f"{PROMPT}ver", ver, "", f"{PROMPT}python --version", f"Python {sys.version.split()[0]}",
                            "", f"{PROMPT}dir /b"] + sorted(p.name for p in PROJECT.iterdir()
                                                            if p.name not in {"venv", "build", "dist", "logs", "saves", "output", "__pycache__"}
                                                            and not p.name.endswith(".spec")),
                      "05_01_win_project.png")
        console_image(con, [f"{PROMPT}build_exe.bat"] + trim(sections.get(0, []) + sections.get(1, []) + sections.get(2, []), 40, 10),
                      "05_02_win_venv.png", "Command Prompt - build_exe.bat")
        pip_lines = [line for line in sections.get(3, [])
                     if re.match(r"^(\[3/5\]|Collecting (flask|pandas|openpyxl|pyinstaller)\b|Successfully installed|Requirement already satisfied: pip)", line, re.I)]
        pip_lines += [line for line in sections.get(3, [])[-2:] if re.match(r"^\d+\.\d+", line.strip())]
        console_image(con, pip_lines, "05_04_win_pip_install.png", "Command Prompt - build_exe.bat")
        console_image(con, trim(sections.get(4, []), 6, 24), "05_05_win_tests.png", "Command Prompt - build_exe.bat")
        build_lines = sections.get(5, [])
        keep = [line for line in build_lines if re.search(r"(\[5/5\]|INFO: (PyInstaller|Python|Platform)|WARNING|"
                                                           r"completed successfully|Build complete|BUILD SUCCEEDED|M7Lab_Launcher\.exe|====)", line)]
        console_image(con, keep, "05_06_win_build.png", "Command Prompt - build_exe.bat")
        size_mb = exe_src.stat().st_size / (1024 * 1024)
        console_image(con, [f"{PROMPT}dir dist", f" Directory of {PROJECT / 'dist'}", "",
                            f"{time.strftime('%m/%d/%Y  %I:%M %p')}    {exe_src.stat().st_size:>14,} {EXE_NAME}",
                            f"               1 File(s)  ({size_mb:.1f} MB)"], "05_07_win_dist.png")

        # ---- run the exe by itself in an empty folder
        test_dir = Path(tempfile.mkdtemp(prefix="M7Lab_exe_test_"))
        exe = test_dir / EXE_NAME
        shutil.copy2(exe_src, exe)
        web = browser.new_page(device_scale_factor=2, viewport={"width": 1440, "height": 900})
        session = ExeSession(exe, test_dir)
        menu = r"Enter your choice \(1-4\): $"
        session.wait_for(menu)

        def start(choice, name):
            mark = len(session.text())
            session.send(choice)
            url = session.wait_for(rf"{re.escape(name)} is running at (http://\S+)", mark).group(1)
            session.wait_for(r"menu\.\.\. $", mark)
            return url

        def stop(name):
            mark = len(session.text())
            session.send("", "[Enter]")
            session.wait_for(rf"{re.escape(name)} stopped\.", mark)
            session.wait_for(menu, mark)

        url = start("1", "Vet Services (M5Pro)")
        check("vet home page", get(url), "Vet Services (M5Pro)")
        check("vet OWNER table + CSV save", get(url + "owners"), "Saved to")
        check("vet total charge 1011 = $80.00", get(url + "charges?owner_id=1011"), "Total charge for OwnerId 1011: $80.00")
        check("vet breed average $50.00", get(url + "breed?breed=beagle"), "Average charge for &#39;beagle&#39;: $50.00")
        check("vet bad OwnerId handled", get(url + "owner?owner_id=abc"), "must be a whole number")
        web.goto(url + "charges?owner_id=1011")
        web.screenshot(path=str(SHOTS / "05_09_win_exe_vet.png"), full_page=True)
        stop("Vet Services (M5Pro)")

        mark = len(session.text())
        session.send("9")
        session.wait_for(r"not a valid option", mark)
        session.wait_for(menu, mark)

        url = start("2", "Recipe Manager (M3Pro)")
        check("recipe all (missing level reported)", get(url + "all"), "Not specified in the recipe data")
        check("recipe search ignores punctuation", get(url + "search?name=veggie+stir+fry"), "Veggie Stir-fry")
        check("recipe adjust level", get(url + "adjust?name=Apple+Pie&amount=-2"), "Sweetness level is now 7/10")
        web.goto(url + "all")
        web.screenshot(path=str(SHOTS / "05_10_win_exe_recipe.png"), full_page=True)
        stop("Recipe Manager (M3Pro)")

        url = start("3", "Dungeon RPG (CSC-121 -> CTS-285)")
        check("rpg title screen", get(url), "Create Character")
        check("rpg bad age rejected", post(url, action="new_game", name="Hero", age="old", class_key="fighter"), "Age must be a number")
        check("rpg new game -> world map", post(url, action="new_game", name="Hero", age="25", class_key="fighter"), 'class="map world"')
        check("rpg move east", post(url, action="move", dir="east"), "World map (1, 0)")
        check("rpg inventory panel", post(url, action="panel", name="inventory"), "Potion of Healing")
        post(url, action="close")
        check("rpg save game", post(url, action="save"), "Game saved successfully")
        web.goto(url)
        web.screenshot(path=str(SHOTS / "05_11_win_exe_rpg.png"), full_page=True)
        stop("Dungeon RPG (CSC-121 -> CTS-285)")

        mark = len(session.text())
        session.send("4")
        session.wait_for(r"close this window\.\.\.$", mark)
        session.send("", "[Enter]")
        code = session.proc.wait(timeout=60)
        check("exe exits with code 0", str(code), "0")
        transcript = session.transcript().replace("[Enter]\n", " [Enter]\n").replace("...  [Enter]", "... [Enter]")
        (LOGS / "exe_run_transcript.txt").write_text(transcript, encoding="utf-8")
        run_lines = [f"{test_dir}>{EXE_NAME}"] + transcript.splitlines()
        console_image(con, run_lines[:22], "05_08_win_exe_menu.png", str(exe))
        console_image(con, run_lines, "05_08b_win_exe_full_run.png", str(exe))
        console_image(con, run_lines[-9:], "05_12_win_exe_goodbye.png", str(exe))

        listing = [f"{test_dir}>dir /s /b"]
        for path in sorted(test_dir.rglob("*")):
            size = f"  ({path.stat().st_size:,} bytes)" if path.is_file() else ""
            listing.append(f"{path}{size}")
        console_image(con, listing, "05_13_win_exe_files.png")

        # ---- submission zip (made with the venv's Python, like a student would)
        venv_python = PROJECT / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        zip_run = subprocess.run([str(venv_python), "make_submission_zip.py"], cwd=PROJECT, capture_output=True, text=True)
        zip_out = (zip_run.stdout + zip_run.stderr).strip().splitlines()
        check("submission zip created", "\n".join(zip_out), "Includes the .exe: True")
        check("submission zip has no venv", "\n".join(zip_out), "Includes a venv:   False")
        console_image(con, [f"{PROMPT}venv\\Scripts\\activate", f"(venv) {PROMPT}python make_submission_zip.py"] + zip_out,
                      "05_14_win_zip.png")
        zip_path = PROJECT.parent / "M7Lab_beckhamwilliam.zip"
        if zip_path.exists():
            zip_path.unlink()  # the zip itself is rebuilt from the repo; don't leave a 50 MB file around
        browser.close()

    passed = sum(ok for ok, _ in results)
    summary = [f"Windows: {ver}", f"Python: {sys.version.split()[0]}", f"Checks passed: {passed}/{len(results)}", ""]
    summary += [("PASS  " if ok else "FAIL  ") + name for ok, name in results]
    (LOGS / "check_results.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))
    shutil.rmtree(test_dir, ignore_errors=True)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as error:  # record the failure so it can be read from the repo
        LOGS.mkdir(parents=True, exist_ok=True)
        (LOGS / "check_results.txt").write_text(f"CHECK SCRIPT CRASHED: {error!r}\n", encoding="utf-8")
        raise
