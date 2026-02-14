import os
import shutil
import argparse
import subprocess
import sys
import urllib.request

# --- CONFIGURATION ---
APP_NAME = "scg"
MAIN_SCRIPT = "sd_cpp_gui/main.py"
BUILD_DIR = "build"
DIST_DIR = "dist"
APP_DIR = os.path.join(BUILD_DIR, "AppDir")
ICON_PATH = "icon.png"  # Adjust path to your icon


def run_nuitka():
    print("🔨 [1/4] Compiling with Nuitka...")
    # Clean previous builds
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)
    os.makedirs(BUILD_DIR, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--show-progress",
        "--enable-plugin=tk-inter",
        "--include-package=sd_cpp_gui.plugins.core_embedding",
        "--include-package=sd_cpp_gui.plugins.core_img2img",
        "--include-package=sd_cpp_gui.plugins.core_lora",
        "--include-package=sd_cpp_gui.plugins.core_networks",
        "--include-package=sd_cpp_gui.plugins.core_preview",
        "--include-package=sd_cpp_gui.plugins.core_queue",
        "--include-package=sd_cpp_gui.plugins.core_remote",
        "--include-package=sd_cpp_gui.plugins.core_txt2img",
        "--include-package=sd_cpp_gui.plugins.shared_ui",
        "--include-package-data=ttkbootstrap",
        "--include-data-dir=./data=data",
        f"--output-dir={BUILD_DIR}",
        f"--output-filename={APP_NAME}",
        MAIN_SCRIPT,
    ]
    subprocess.check_call(cmd)

    # Move the final standalone distribution to the dist folder
    print("📦 Moving standalone distribution to dist folder...")
    main_script_name = os.path.splitext(os.path.basename(MAIN_SCRIPT))[0]
    nuitka_dist_path = os.path.join(BUILD_DIR, f"{main_script_name}.dist")
    final_dist_path = os.path.join(DIST_DIR, f"{APP_NAME}.dist")

    if os.path.exists(final_dist_path):
        shutil.rmtree(final_dist_path)
    os.makedirs(DIST_DIR, exist_ok=True)
    shutil.move(nuitka_dist_path, final_dist_path)
    print(f"✅ Standalone distribution available at {final_dist_path}")


def prepare_appdir():
    print("📂 [2/4] Creating AppDir structure...")
    if os.path.exists(APP_DIR):
        shutil.rmtree(APP_DIR)

    # 1. Create Directories
    bin_dir = os.path.join(APP_DIR, "usr", "bin")
    icon_dir = os.path.join(
        APP_DIR, "usr", "share", "icons", "hicolor", "256x256", "apps"
    )
    os.makedirs(bin_dir)
    os.makedirs(icon_dir)

    # 2. Copy Nuitka Output
    dist_folder = os.path.join(DIST_DIR, f"{APP_NAME}.dist")
    # Copy content of .dist to usr/bin
    for item in os.listdir(dist_folder):
        s = os.path.join(dist_folder, item)
        d = os.path.join(bin_dir, item)
        if os.path.isdir(s):
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)

    # 3. Copy Icon
    if os.path.exists(ICON_PATH):
        shutil.copy(ICON_PATH, os.path.join(icon_dir, f"{APP_NAME}.png"))
        shutil.copy(
            ICON_PATH, os.path.join(APP_DIR, f"{APP_NAME}.png")
        )  # Icon at root for AppImage
        shutil.copy(
            ICON_PATH, os.path.join(APP_DIR, ".DirIcon")
        )  # Icon for file manager

    # 4. Create AppRun Symlink
    # AppRun -> usr/bin/myapp
    os.symlink(
        os.path.join("usr", "bin", APP_NAME), os.path.join(APP_DIR, "AppRun")
    )

    # 5. Create .desktop file
    desktop_file = f"""[Desktop Entry]
Name={APP_NAME}
Exec={APP_NAME}
Icon={APP_NAME}
Type=Application
Categories=Utility;
Terminal=false
"""
    with open(os.path.join(APP_DIR, f"{APP_NAME}.desktop"), "w") as f:
        f.write(desktop_file)


def build_appimage():
    print("📦 [3/4] Downloading AppImageTool (if missing)...")
    tool_filename = "appimagetool-x86_64.AppImage"
    tool_path = os.path.join(BUILD_DIR, tool_filename)
    if not os.path.exists(tool_path):
        url = "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
        urllib.request.urlretrieve(url, tool_path)
        os.chmod(tool_path, 0o755)

    print("🚀 [4/4] Generating AppImage...")
    # ARCH=x86_64 is required for appimagetool to work in some environments
    env = os.environ.copy()
    env["ARCH"] = "x86_64"

    os.makedirs(DIST_DIR, exist_ok=True)
    output_appimage = os.path.join(DIST_DIR, f"{APP_NAME}-x86_64.AppImage")

    subprocess.check_call(
        [tool_path, APP_DIR, output_appimage], env=env
    )
    print(f"✅ Done! Created {output_appimage}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build script for scg, supporting Nuitka compilation and AppImage creation."
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["nuitka", "appimage", "all"],
        default="all",
        help=(
            "Specify the build step: "
            "'nuitka' for standalone compilation only, "
            "'appimage' to create the AppImage from existing compiled files, "
            "'all' to perform the full build process (default)."
        ),
    )
    args = parser.parse_args()

    if args.command == "nuitka":
        run_nuitka()
    elif args.command == "appimage":
        prepare_appdir()
        build_appimage()
    elif args.command == "all":
        run_nuitka()
        prepare_appdir()
        build_appimage()
