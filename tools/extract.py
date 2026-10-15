"""Extract the game's SWFs from originals/NReality6g2.zip to .local/original (input for decompile.sh)."""
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    target = ROOT / '.local/original'
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ROOT / 'originals/NReality6g2.zip') as archive:
        for entry in archive.infolist():
            # Top-level game files only; the bundled Flash players are never unpacked.
            if '/' not in entry.filename and entry.filename.endswith(('.swf', '.txt')):
                (target / entry.filename).write_bytes(archive.read(entry))
                print(entry.filename)


if __name__ == '__main__':
    main()
