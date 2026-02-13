import sys

import PyInstaller.__main__

if __name__ == "__main__":
    try:
        PyInstaller.__main__.run(
            [
                "sd-cpp-gui.spec",
                "--noconfirm",
                "--clean",
            ]
        )
    except Exception as e:
        print(f"An error occurred during the build process: {e}", file=sys.stderr)
        sys.exit(1)
